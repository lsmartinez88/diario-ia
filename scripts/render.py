#!/usr/bin/env python3
"""Render: convierte .out/edicion.json en la edición web, la portada, el RSS y el email.

Escribe:
  ediciones/AAAA-MM-DD.html   edición del día
  index.html                  portada con las últimas 30 ediciones
  feed.xml                    RSS 2.0 con las últimas 20 ediciones
  .out/email.html             versión email (no se versiona)
  state.json                  links publicados + índice de ediciones

Uso: python3 scripts/render.py
"""

import html
import json
import os
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

RAIZ = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("DIARIO_BASE_URL", "https://lsmartinez88.github.io/diario-ia").rstrip("/")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

NOMBRES_BLOQUE = {
    "modelos": "Modelos y avances",
    "agentes": "Agentes de IA",
    "herramientas": "Herramientas para probar",
    "clinica": "IA en ensayos clínicos y salud",
    "futuro": "Futuro de la IA",
}
ORDEN_BLOQUES = ["modelos", "agentes", "herramientas", "clinica", "futuro"]


def fecha_legible(iso):
    d = datetime.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def armar_contexto(edicion, para_email):
    """Estructura común para las plantillas web y email."""
    items = edicion["items"]
    destacado = next((i for i in items if i.get("destacado")), None)
    resto = [i for i in items if not i.get("destacado")]

    numero = 0
    bloques = []
    for clave in ORDEN_BLOQUES:
        del_bloque = [i for i in resto if i["bloque"] == clave]
        if not del_bloque:
            continue
        numerados = []
        for i in del_bloque:
            numero += 1
            it = dict(i)
            it["numero"] = f"{numero:02d}"
            if not para_email:
                it.pop("aplicacion", None)  # la aplicación privada nunca va a la web
            numerados.append(it)
        bloques.append({"clave": clave, "nombre": NOMBRES_BLOQUE[clave], "items": numerados})

    return {
        "fecha": edicion["fecha"],
        "fecha_legible": fecha_legible(edicion["fecha"]),
        "destacado": destacado,
        "breves": edicion.get("en_pocas_palabras", []),
        "bloques": bloques,
        "prompt_del_dia": edicion.get("prompt_del_dia"),
        "base_url": BASE_URL,
        "url_edicion": f"{BASE_URL}/ediciones/{edicion['fecha']}.html",
    }


def rss(ediciones):
    ahora = format_datetime(datetime.now(timezone.utc))
    items_xml = []
    for e in ediciones[:20]:
        url = f"{BASE_URL}/ediciones/{e['fecha']}.html"
        titulo = html.escape(f"Diario IA — {fecha_legible(e['fecha'])}")
        desc = html.escape(" · ".join(e.get("titulares", [])))
        pub = format_datetime(datetime.fromisoformat(e["fecha"]).replace(hour=11, tzinfo=timezone.utc))
        items_xml.append(
            f"    <item>\n      <title>{titulo}</title>\n      <link>{url}</link>\n"
            f"      <guid isPermaLink=\"true\">{url}</guid>\n      <pubDate>{pub}</pubDate>\n"
            f"      <description>{desc}</description>\n    </item>"
        )
    cuerpo = "\n".join(items_xml)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        "    <title>Diario IA</title>\n"
        f"    <link>{BASE_URL}/</link>\n"
        "    <description>Diario personal de noticias de IA, generado a diario.</description>\n"
        "    <language>es</language>\n"
        f"    <lastBuildDate>{ahora}</lastBuildDate>\n"
        f'    <atom:link href="{BASE_URL}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        f"{cuerpo}\n"
        "  </channel>\n"
        "</rss>\n"
    )


def main():
    edicion = json.loads((RAIZ / ".out" / "edicion.json").read_text())

    env = Environment(loader=FileSystemLoader(RAIZ / "templates"), autoescape=select_autoescape(["html"]))

    # 1. edición del día
    ctx_web = armar_contexto(edicion, para_email=False)
    (RAIZ / "ediciones").mkdir(exist_ok=True)
    pagina = RAIZ / "ediciones" / f"{edicion['fecha']}.html"
    pagina.write_text(env.get_template("edicion.html").render(**ctx_web))

    # 2. estado: links publicados + índice de ediciones
    estado_path = RAIZ / "state.json"
    estado = json.loads(estado_path.read_text()) if estado_path.exists() else {}
    links = set(estado.get("links", []))
    links.update(i["link"] for i in edicion["items"])
    links.update(b["link"] for b in edicion.get("en_pocas_palabras", []))

    ediciones = [e for e in estado.get("ediciones", []) if e["fecha"] != edicion["fecha"]]
    titulares = [i["titular"] for i in edicion["items"]][:3]
    ediciones.append({
        "fecha": edicion["fecha"],
        "titulares": titulares,
        "total": len(edicion["items"]) + len(edicion.get("en_pocas_palabras", [])),
    })
    ediciones.sort(key=lambda e: e["fecha"], reverse=True)

    estado = {"links": sorted(links)[-2000:], "ediciones": ediciones}
    estado_path.write_text(json.dumps(estado, ensure_ascii=False, indent=2))

    # 3. portada
    vista = [dict(e, fecha_legible=fecha_legible(e["fecha"])) for e in ediciones[:30]]
    (RAIZ / "index.html").write_text(
        env.get_template("index.html").render(ediciones=vista, base_url=BASE_URL)
    )

    # 4. RSS
    (RAIZ / "feed.xml").write_text(rss(ediciones))

    # 5. email (con las líneas de aplicación privadas)
    ctx_mail = armar_contexto(edicion, para_email=True)
    (RAIZ / ".out").mkdir(exist_ok=True)
    (RAIZ / ".out" / "email.html").write_text(env.get_template("email.html").render(**ctx_mail))

    print(f"render listo: {pagina.relative_to(RAIZ)}, index.html, feed.xml, .out/email.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
