#!/usr/bin/env python3
"""Pipeline de ingesta: lee los feeds, filtra, deduplica, puntúa y arma candidatos.

Salida: .out/candidatos.json con 30-40 candidatos ordenados por puntaje.
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
MAX_CANDIDATOS = 40
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


def leer_feed(feed):
    try:
        r = requests.get(feed["url"], timeout=TIMEOUT, headers={"User-Agent": UA})
        if r.status_code != 200:
            return feed, [], f"HTTP {r.status_code}"
        parsed = feedparser.parse(r.content)
        return feed, parsed.entries, None
    except Exception as e:
        return feed, [], type(e).__name__


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


def bajar_texto(url):
    """Texto del artículo con trafilatura; si falla, devuelve None sin romper."""
    try:
        import trafilatura

        bajado = trafilatura.fetch_url(url)
        if bajado:
            texto = trafilatura.extract(bajado, include_comments=False, include_tables=False)
            if texto:
                return texto[:3000]
    except Exception:
        pass
    return None


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
    for feed, entradas, error in resultados:
        if error:
            print(f"  aviso: {feed['nombre']} falló ({error}), sigo sin él", file=sys.stderr)
            continue
        for e in entradas:
            fecha = fecha_de_entrada(e)
            link = e.get("link")
            titulo = limpiar_html(e.get("title", ""))
            if not (fecha and link and titulo):
                continue
            crudos.append(
                {
                    "titulo": titulo,
                    "link": normalizar_url(link),
                    "extracto": limpiar_html(e.get("summary", ""))[:500],
                    "fecha": fecha.isoformat(),
                    "fuente": feed["nombre"],
                    "peso": feed.get("peso", 1),
                    "bloque_fuente": feed.get("bloque", "general"),
                }
            )

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
    candidatos = items[:MAX_CANDIDATOS]

    for i in candidatos[:TOP_CON_TEXTO]:
        texto = bajar_texto(i["link"])
        if texto:
            i["texto"] = texto

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
