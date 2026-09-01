---
name: dev-setup
description: Instalar dependencias y correr el pipeline completo del diario en local. Usar cuando el usuario pida correr el proyecto, probar una edición o trabajar en una máquina nueva.
---

# Setup y corrida local

## Requisitos

Python 3.12+. Sin servicios externos salvo la API key del modelo.

## Instalación

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Corrida completa

```bash
.venv/bin/python scripts/fetch_feeds.py      # → .out/candidatos.json
DIARIO_API_KEY=$(cat .env.local 2>/dev/null || echo "$DIARIO_API_KEY") \
  .venv/bin/python scripts/generar.py        # → .out/edicion.json
.venv/bin/python scripts/render.py           # → ediciones/, index.html, feed.xml, .out/email.html
```

La key local vive fuera del repo (variable de entorno o archivo ignorado). Nunca
pedirla por chat ni escribirla en archivos versionados.

## Verificar fuentes

```bash
.venv/bin/python check_feeds.py
```

## Preview del sitio

Servidor estático en el puerto 8123 (config en `.claude/launch.json`):

```bash
python3 -m http.server 8123
```

## Ojo con state.json

`render.py` marca los links como publicados en `state.json`. Si corrés una prueba
que no vas a publicar, restaurá `state.json` después (o los links de la prueba no
volverán a aparecer en la edición real).
