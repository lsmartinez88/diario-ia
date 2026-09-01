#!/usr/bin/env python3
"""Selección y redacción: manda los candidatos al modelo y valida la respuesta.

Entrada: .out/candidatos.json + prompt-editorial.md
Salida: .out/edicion.json

Usa cualquier API compatible con OpenAI. Por defecto, el endpoint OpenAI-compatible
de Gemini (free tier: ~1.500 requests/día para los modelos Flash; acá se usa 1).
GitHub Models, el plan original, fue retirado el 2026-07-30.

Entorno:
  DIARIO_API_KEY   (obligatoria) API key del proveedor
  DIARIO_API_BASE  (opcional) base de la API, default Gemini
  DIARIO_MODELO    (opcional) modelo, default gemini-3.6-flash

Uso: python3 scripts/generar.py
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
API_BASE = os.environ.get("DIARIO_API_BASE", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
MODELO = os.environ.get("DIARIO_MODELO", "gemini-3.6-flash")
BLOQUES = {"modelos", "agentes", "herramientas", "clinica", "futuro"}

INSTRUCCIONES = """Respondé SOLO con un objeto JSON válido, sin texto alrededor, con esta forma exacta:

{
  "en_pocas_palabras": [
    {"texto": "una línea sobre una noticia menor", "link": "...", "fuente": "..."}
  ],
  "items": [
    {
      "bloque": "modelos | agentes | herramientas | clinica | futuro",
      "titular": "titular en español, reescrito",
      "resumen": "2 a 4 líneas con palabras propias",
      "por_que_importa": "una línea",
      "link": "URL exacta de un candidato",
      "destacado": false,
      "aplicacion": "solo en bloque clinica: una línea de aplicación en reclutamiento de pacientes"
    }
  ],
  "prompt_del_dia": {"titulo": "...", "texto": "..."}
}

Reglas duras:
- Todo link tiene que ser la URL exacta de un candidato de la lista. No inventes ni modifiques URLs.
- "en_pocas_palabras": 3 a 5 entradas, noticias menores que no merecen item completo. Puede ir vacío.
- "items": el volumen total de la edición (items + en_pocas_palabras) es de 8 a 14.
- "destacado": true en máximo UN item, y solo si de verdad califica según los criterios. La mayoría de los días ninguno.
- "aplicacion" solo aparece en items de bloque "clinica".
- "prompt_del_dia" es opcional: incluilo solo si se te ocurre uno genuinamente útil ligado a las noticias de hoy; si no, null.
"""


def armar_candidatos_compactos(candidatos):
    lineas = []
    for c in candidatos:
        linea = {
            "titulo": c["titulo"],
            "extracto": c["extracto"][:220],
            "link": c["link"],
            "fuente": c["fuente"],
            "fecha": c["fecha"][:10],
            "bloque_sugerido": c["bloque_sugerido"],
        }
        if c.get("texto"):
            linea["texto"] = c["texto"][:400]
        lineas.append(linea)
    return lineas


def llamar_modelo(mensajes):
    token = os.environ.get("DIARIO_API_KEY")
    if not token:
        print("falta DIARIO_API_KEY en el entorno", file=sys.stderr)
        sys.exit(1)
    # 429/5xx suelen ser picos pasajeros del free tier: backoff antes de rendirse
    for espera in (0, 30, 90, 180):
        if espera:
            print(f"  modelo saturado, reintento en {espera}s", file=sys.stderr)
            time.sleep(espera)
        r = requests.post(
            f"{API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "model": MODELO,
                "messages": mensajes,
                "temperature": 0.4,
                "response_format": {"type": "json_object"},
            },
            timeout=120,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        if r.status_code not in (429, 500, 502, 503, 504):
            break
    print(f"el modelo respondió HTTP {r.status_code}: {r.text[:500]}", file=sys.stderr)
    sys.exit(1)


def parsear_json(texto):
    texto = re.sub(r"^```(json)?|```$", "", texto.strip(), flags=re.MULTILINE).strip()
    return json.loads(texto)


def validar(data, candidatos_por_link):
    """Valida estructura y descarta items con links que no salgan de los candidatos.

    Devuelve (edicion_limpia, errores_estructurales). Los errores estructurales
    ameritan reintento; los items con link inventado se descartan en silencio.
    """
    if not isinstance(data, dict):
        return None, "la raíz no es un objeto"
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return None, "falta la lista items"

    limpios = []
    hubo_destacado = False
    for it in items:
        if not isinstance(it, dict):
            continue
        link = (it.get("link") or "").strip()
        candidato = candidatos_por_link.get(link)
        if candidato is None:
            print(f"  descartado (link fuera de candidatos): {link[:80]}", file=sys.stderr)
            continue
        if it.get("bloque") not in BLOQUES:
            continue
        if not all(isinstance(it.get(k), str) and it[k].strip() for k in ("titular", "resumen", "por_que_importa")):
            continue
        destacado = bool(it.get("destacado")) and not hubo_destacado
        hubo_destacado = hubo_destacado or destacado
        limpio = {
            "bloque": it["bloque"],
            "titular": it["titular"].strip(),
            "resumen": it["resumen"].strip(),
            "por_que_importa": it["por_que_importa"].strip(),
            "link": link,
            # fuente y fecha salen del candidato, no del modelo
            "fuente": candidato["fuente"],
            "fecha": candidato["fecha"][:10],
            "destacado": destacado,
        }
        if it["bloque"] == "clinica" and isinstance(it.get("aplicacion"), str) and it["aplicacion"].strip():
            limpio["aplicacion"] = it["aplicacion"].strip()
        limpios.append(limpio)

    if not limpios:
        return None, "ningún item sobrevivió la validación"

    breves = []
    for b in data.get("en_pocas_palabras") or []:
        if not isinstance(b, dict):
            continue
        link = (b.get("link") or "").strip()
        candidato = candidatos_por_link.get(link)
        if candidato and isinstance(b.get("texto"), str) and b["texto"].strip():
            breves.append({"texto": b["texto"].strip(), "link": link, "fuente": candidato["fuente"]})

    prompt_dia = data.get("prompt_del_dia")
    if not (
        isinstance(prompt_dia, dict)
        and isinstance(prompt_dia.get("titulo"), str)
        and isinstance(prompt_dia.get("texto"), str)
    ):
        prompt_dia = None

    return {"items": limpios, "en_pocas_palabras": breves, "prompt_del_dia": prompt_dia}, None


def main():
    candidatos = json.loads((RAIZ / ".out" / "candidatos.json").read_text())["candidatos"]
    editorial = (RAIZ / "prompt-editorial.md").read_text()
    candidatos_por_link = {c["link"]: c for c in candidatos}

    mensajes = [
        {"role": "system", "content": editorial + "\n\n" + INSTRUCCIONES},
        {
            "role": "user",
            "content": "Candidatos de hoy:\n" + json.dumps(armar_candidatos_compactos(candidatos), ensure_ascii=False),
        },
    ]

    edicion = None
    for intento in (1, 2):
        respuesta = llamar_modelo(mensajes)
        try:
            data = parsear_json(respuesta)
            edicion, error = validar(data, candidatos_por_link)
        except json.JSONDecodeError as e:
            edicion, error = None, f"JSON inválido: {e}"
        if edicion:
            break
        if intento == 1:
            print(f"  respuesta inválida ({error}), reintento con corrección", file=sys.stderr)
            mensajes.append({"role": "assistant", "content": respuesta})
            mensajes.append(
                {
                    "role": "user",
                    "content": f"Tu respuesta no cumplió el formato ({error}). "
                    "Devolvé SOLO el objeto JSON corregido, con links tomados textualmente de los candidatos.",
                }
            )

    if not edicion:
        print("el modelo no devolvió una edición válida tras el reintento; no se publica", file=sys.stderr)
        return 1

    edicion["fecha"] = datetime.now(timezone.utc).date().isoformat()
    edicion["modelo"] = MODELO
    (RAIZ / ".out" / "edicion.json").write_text(json.dumps(edicion, ensure_ascii=False, indent=2))
    total = len(edicion["items"]) + len(edicion["en_pocas_palabras"])
    destacado = "con destacado" if any(i["destacado"] for i in edicion["items"]) else "sin destacado"
    print(f"edición del {edicion['fecha']}: {len(edicion['items'])} items + "
          f"{len(edicion['en_pocas_palabras'])} breves ({total} total, {destacado}) → .out/edicion.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
