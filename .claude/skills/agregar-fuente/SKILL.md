---
name: agregar-fuente
description: Agregar, reemplazar o dar de baja un feed RSS en feeds.yaml. Usar cuando el usuario quiera sumar una fuente nueva, cuando un feed se rompa o cuando falte cobertura en un bloque.
---

# Agregar o cambiar una fuente

## Alta

1. Conseguir la URL del feed (probar `/feed`, `/rss`, `/rss.xml`, `/atom.xml` o
   mirar el `<link rel="alternate">` del HTML).
2. Verificar que responde y parsea ANTES de sumarla:
   ```bash
   .venv/bin/python check_feeds.py
   ```
3. Agregar a `feeds.yaml` con `nombre`, `url`, `peso` (1–3) y `bloque`
   (modelos | agentes | herramientas | clinica | futuro | general).

## Fuentes sin RSS (tipo especial)

Para sitios con API JSON en vez de RSS, `feeds.yaml` acepta `tipo:` y el lector
vive en `LECTORES` de `fetch_feeds.py`. Existen `hf_papers` (Daily Papers de
Hugging Face, con thumbnail como imagen) y `hf_trending` (modelos del Hub creados
en los últimos 14 días que hoy están en tendencia; la fecha del candidato es el
snapshot del día y `state.json` evita repeticiones). Para una fuente nueva de este
estilo: escribir un lector que devuelva items con `crudo(...)` y registrarlo.

## Criterio de peso

- 3: fuente primaria (blog del lab, revista peer-reviewed, voz técnica de referencia).
- 2: medio con buena señal.
- 1: agregadores y fuentes ruidosas (ej: Hacker News).

## Baja

No borrar en silencio: dejar un comentario en `feeds.yaml` con el motivo (URL
muerta, 403 anti-bot, RSS descontinuado), como los que ya están ahí.

## Casos conocidos

- Sitios de HIMSS (MobiHealthNews, Healthcare IT News) y varios médicos bloquean
  clientes no-navegador con 403: no insistir, no funcionarán desde Actions.
- Fierce (Biotech/Healthcare) manda fechas no estándar y títulos con HTML:
  `fetch_feeds.py` ya lo maneja; no hace falta tocar nada.
- El slot de PubMed está comentado en `feeds.yaml` esperando que el usuario genere
  la URL desde la interfaz de PubMed (botón "Create RSS").
