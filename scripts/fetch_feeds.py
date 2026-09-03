#!/usr/bin/env python3
"""Pipeline de ingesta: lee los feeds, filtra, deduplica, puntúa y arma candidatos.

Salida: .out/candidatos.json con hasta 60 candidatos ordenados por puntaje.
Uso: python3 scripts/fetch_feeds.py
"""

import calendar
import concurrent.futures
import difflib
import html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests
import yaml

RAIZ = Path(__file__).resolve().parent.parent
TIMEOUT = 15
UA = "Mozilla/5.0 (compatible; diario-ia/1.0; +https://github.com/lsmartinez88/diario-ia)"
VENTANA_HORAS = 24
VENTANA_EXTENDIDA_HORAS = 48
MINIMO_PARA_NO_EXTENDER = 15
MAX_CANDIDATOS = 60
MAX_POR_FUENTE = 5
TOP_CON_TEXTO = 10

# Fierce (Biotech/Healthcare) publica fechas fuera de RFC 822, ej: "Aug 31, 2026 4:27pm"
FORMATO_FIERCE = "%b %d, %Y %I:%M%p"


def limpiar_html(texto):
    """Saca tags y entidades; los feeds de Fierce traen <a> dentro del título."""
    texto = re.sub(r"<[^>]+>", "", texto or "")
    return html.unescape(texto).strip()


def normalizar_url(url):
    """Baja el host a minúsculas, saca utm_* y fragmentos, y el slash final."""
    p = urlparse(url.strip())
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid", "ref"))]
    path = p.path.rstrip("/")
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(query), ""))


def titulo_clave(titulo):
    """Título normalizado para comparar similitud."""
    return re.sub(r"[^a-z0-9áéíóúñü ]", "", titulo.lower()).strip()


def fecha_de_entrada(entrada):
    t = entrada.get("published_parsed") or entrada.get("updated_parsed")
    if t:
        return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    # fechas no estándar (Fierce): "Aug 31, 2026 4:27pm", a veces con zona pegada
    crudo = limpiar_html(entrada.get("published") or entrada.get("updated") or "")
    if crudo:
        try:
            return datetime.strptime(crudo, FORMATO_FIERCE).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def crudo(feed, titulo, link, extracto, fecha, imagen=None):
    return {
        "titulo": titulo,
        "link": normalizar_url(link),
        "extracto": extracto[:500],
        "fecha": fecha.isoformat(),
        "fuente": feed["nombre"],
        "imagen": imagen,
        "peso": feed.get("peso", 1),
        "bloque_fuente": feed.get("bloque", "general"),
    }


def items_rss(feed):
    r = requests.get(feed["url"], timeout=TIMEOUT, headers={"User-Agent": UA})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    items = []
    for e in feedparser.parse(r.content).entries:
        fecha = fecha_de_entrada(e)
        link, titulo = e.get("link"), limpiar_html(e.get("title", ""))
        if fecha and link and titulo:
            items.append(crudo(feed, titulo, link, limpiar_html(e.get("summary", "")),
                               fecha, imagen_de_entrada(e)))
    return items


def items_hf_papers(feed):
    """Daily Papers de Hugging Face (sin RSS público; API JSON)."""
    r = requests.get("https://huggingface.co/api/daily_papers?limit=15",
                     timeout=TIMEOUT, headers={"User-Agent": UA})
    r.raise_for_status()
    items = []
    for p in r.json():
        paper = p.get("paper") or {}
        crudo_fecha = paper.get("submittedOnDailyAt") or paper.get("publishedAt")
        if not (paper.get("id") and paper.get("title") and crudo_fecha):
            continue
        fecha = datetime.fromisoformat(crudo_fecha.replace("Z", "+00:00"))
        extracto = limpiar_html(paper.get("summary", "")).replace("\n", " ")
        items.append(crudo(feed, limpiar_html(paper["title"]),
                           f"https://huggingface.co/papers/{paper['id']}",
                           extracto, fecha, p.get("thumbnail")))
    return items


def items_hf_trending(feed):
    """Modelos en tendencia del Hub; solo los creados en las últimas 2 semanas
    (la noticia es el lanzamiento, no la popularidad sostenida). La fecha del
    candidato es el snapshot de hoy; state.json evita que se repitan."""
    r = requests.get("https://huggingface.co/api/models?sort=trendingScore&limit=10",
                     timeout=TIMEOUT, headers={"User-Agent": UA})
    r.raise_for_status()
    ahora = datetime.now(timezone.utc)
    items = []
    for m in r.json():
        creado = m.get("createdAt")
        if not (m.get("id") and creado):
            continue
        creado = datetime.fromisoformat(creado.replace("Z", "+00:00"))
        if (ahora - creado).days > 14:
            continue
        extracto = (f"Modelo {m.get('pipeline_tag') or 'de propósito general'} publicado el "
                    f"{creado:%Y-%m-%d}; hoy en tendencia en Hugging Face con "
                    f"{m.get('likes', 0)} likes y {m.get('downloads', 0)} descargas.")
        items.append(crudo(feed, f"Nuevo modelo en tendencia: {m['id']}",
                           f"https://huggingface.co/{m['id']}", extracto, ahora))
    return items[:8]


LECTORES = {"rss": items_rss, "hf_papers": items_hf_papers, "hf_trending": items_hf_trending}


def leer_feed(feed):
    try:
        lector = LECTORES[feed.get("tipo", "rss")]
        return feed, lector(feed), None
    except Exception as e:
        return feed, [], f"{type(e).__name__}: {e}"[:120]


def puntuar(item, keywords):
    """peso de la fuente + coincidencia de keywords por bloque + recencia."""
    texto = f"{item['titulo']} {item['extracto']}".lower()
    hits_por_bloque = {}
    for bloque, palabras in keywords.items():
        hits = sum(1 for kw in palabras if kw.lower() in texto)
        if hits:
            hits_por_bloque[bloque] = hits
    mejor_bloque = max(hits_por_bloque, key=hits_por_bloque.get) if hits_por_bloque else item["bloque_fuente"]
    puntos_kw = min(sum(hits_por_bloque.values()), 6)

    horas = (datetime.now(timezone.utc) - datetime.fromisoformat(item["fecha"])).total_seconds() / 3600
    recencia = 3 if horas <= 6 else 2 if horas <= 12 else 1 if horas <= 24 else 0

    return item["peso"] * 2 + puntos_kw + recencia, mejor_bloque


def imagen_de_entrada(e):
    """Imagen declarada en el propio feed (media RSS o enclosure), si hay."""
    for m in e.get("media_content") or []:
        u = m.get("url", "")
        if u and ("image" in (m.get("type") or "") or m.get("medium") == "image"
                  or re.search(r"\.(jpe?g|png|webp|gif)(\?|$)", u, re.I)):
            return u
    for m in e.get("media_thumbnail") or []:
        if m.get("url"):
            return m["url"]
    for l in e.get("links") or []:
        if l.get("rel") == "enclosure" and "image" in (l.get("type") or ""):
            return l.get("href")
    return None


def bajar_articulo(url):
    """(texto, og_image) del artículo con trafilatura; si falla, (None, None)."""
    try:
        import trafilatura

        bajado = trafilatura.fetch_url(url)
        if not bajado:
            return None, None
        texto = trafilatura.extract(bajado, include_comments=False, include_tables=False)
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', bajado) \
            or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', bajado)
        og = html.unescape(m.group(1)) if m else None
        if og and not og.startswith("http"):
            og = None
        return (texto[:3000] if texto else None), og
    except Exception:
        return None, None


def main():
    cfg = yaml.safe_load((RAIZ / "feeds.yaml").read_text())
    ruido = [p.lower() for p in cfg.get("ruido", [])]
    keywords = cfg.get("keywords", {})

    estado_path = RAIZ / "state.json"
    publicados = set()
    if estado_path.exists():
        publicados = set(json.loads(estado_path.read_text()).get("links", []))

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        resultados = list(ex.map(leer_feed, cfg["feeds"]))

    ahora = datetime.now(timezone.utc)
    crudos = []
    for feed, items_feed, error in resultados:
        if error:
            print(f"  aviso: {feed['nombre']} falló ({error}), sigo sin él", file=sys.stderr)
            continue
        crudos.extend(items_feed)

    def dentro_de(horas):
        limite = ahora - timedelta(hours=horas)
        return [i for i in crudos if datetime.fromisoformat(i["fecha"]) >= limite]

    ventana = VENTANA_HORAS
    items = dentro_de(ventana)
    if len(items) < MINIMO_PARA_NO_EXTENDER:
        ventana = VENTANA_EXTENDIDA_HORAS
        items = dentro_de(ventana)
        print(f"  pocos items en 24h, extiendo la ventana a {ventana}h", file=sys.stderr)

    items = [i for i in items if not any(r in i["titulo"].lower() for r in ruido)]
    items = [i for i in items if i["link"] not in publicados]

    # dedup: primero por URL exacta normalizada, después por título similar
    por_url, vistos_titulos = {}, []
    for i in sorted(items, key=lambda x: -x["peso"]):
        if i["link"] in por_url:
            continue
        clave = titulo_clave(i["titulo"])
        if any(difflib.SequenceMatcher(None, clave, v).ratio() > 0.85 for v in vistos_titulos):
            continue
        por_url[i["link"]] = i
        vistos_titulos.append(clave)
    items = list(por_url.values())

    for i in items:
        i["puntaje"], i["bloque_sugerido"] = puntuar(i, keywords)
        del i["peso"], i["bloque_fuente"]

    items.sort(key=lambda x: -x["puntaje"])

    # tope por fuente: que ninguna (p. ej. Xataka, que publica tech general
    # todo el día) inunde la lista de candidatos
    conteo, acotados = {}, []
    for i in items:
        if conteo.get(i["fuente"], 0) >= MAX_POR_FUENTE:
            continue
        conteo[i["fuente"]] = conteo.get(i["fuente"], 0) + 1
        acotados.append(i)
    candidatos = acotados[:MAX_CANDIDATOS]

    for i in candidatos[:TOP_CON_TEXTO]:
        texto, og = bajar_articulo(i["link"])
        if texto:
            i["texto"] = texto
        if og and not i.get("imagen"):
            i["imagen"] = og

    salida = RAIZ / ".out"
    salida.mkdir(exist_ok=True)
    (salida / "candidatos.json").write_text(
        json.dumps(
            {"generado": ahora.isoformat(), "ventana_horas": ventana, "candidatos": candidatos},
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"{len(candidatos)} candidatos (ventana {ventana}h) → .out/candidatos.json")
    return 0 if candidatos else 1


if __name__ == "__main__":
    sys.exit(main())
