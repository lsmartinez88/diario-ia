---
name: operacion
description: Operar el workflow diario - dispararlo a mano, diagnosticar una corrida fallida, cambiar horario o modelo, y qué secrets necesita. Usar cuando una edición no salió, salió mal o hay que tocar la automatización.
---

# Operación del diario

## Disparar a mano

```bash
gh workflow run diario.yml && gh run watch
```

## Diagnóstico de una corrida fallida

```bash
gh run list --workflow=diario.yml --limit 5
gh run view --log-failed
```

Orden de fallas típicas:
- **Ingesta**: un feed caído no rompe nada (se loguea y sigue); cero candidatos sí.
- **Generación**: HTTP 4xx = problema de key/cuota de Gemini; "no devolvió una
  edición válida" = el modelo falló el JSON dos veces → no se publica (correcto).
  Los 503 de pico de demanda se reintentan con backoff sobre el primario y después
  sobre `gemini-flash-lite-latest` (env `DIARIO_MODELO_FALLBACK`). Si aun así
  falla, hay un cron de reintento a las 12:30 UTC que solo publica si la edición
  del día no existe todavía (guardia en el workflow; el disparo manual siempre corre).
- **Publicar**: "la corrida no produjo cambios" = algo raro antes; mirar el log.
- **Email**: DESACTIVADO por decisión del usuario (2026-09-01). El paso se
  saltea solo mientras no existan los secrets de Gmail; para activarlo, cargar
  `GMAIL_USER`, `GMAIL_APP_PASSWORD` y `MAIL_TO`. Si algún día falla, la web ya
  quedó publicada — solo se pierde el mail del día.

## Secrets del repo (Settings → Secrets → Actions)

`DIARIO_API_KEY` (Gemini). Opcionales, solo para email: `GMAIL_USER`,
`GMAIL_APP_PASSWORD`, `MAIL_TO`.

## Cambios frecuentes

- **Horario**: `cron` en `.github/workflows/diario.yml` (en UTC; 10:30 UTC = 7:30 AR).
- **Modelo/proveedor**: env vars `DIARIO_MODELO` / `DIARIO_API_BASE` en el workflow.
  Cualquier API compatible con OpenAI sirve.
- **Criterios editoriales**: `prompt-editorial.md`.

## Si la edición salió con mal criterio

No borrar ediciones ya publicadas ni reescribir historia. Ajustar
`prompt-editorial.md` (o los pesos en `feeds.yaml`) para la próxima.
