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
- **Publicar**: "la corrida no produjo cambios" = algo raro antes; mirar el log.
- **Email**: solo corre si todo lo anterior pasó. Si falla, la web ya quedó
  publicada — solo se pierde el mail del día.

## Secrets del repo (Settings → Secrets → Actions)

`DIARIO_API_KEY` (Gemini), `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `MAIL_TO`.

## Cambios frecuentes

- **Horario**: `cron` en `.github/workflows/diario.yml` (en UTC; 10:30 UTC = 7:30 AR).
- **Modelo/proveedor**: env vars `DIARIO_MODELO` / `DIARIO_API_BASE` en el workflow.
  Cualquier API compatible con OpenAI sirve.
- **Criterios editoriales**: `prompt-editorial.md`.

## Si la edición salió con mal criterio

No borrar ediciones ya publicadas ni reescribir historia. Ajustar
`prompt-editorial.md` (o los pesos en `feeds.yaml`) para la próxima.
