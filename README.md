# Diario IA

Diario personal de noticias de IA que se publica solo, todos los días. Dos salidas
del mismo contenido: un blog en [GitHub Pages](https://lsmartinez88.github.io/diario-ia/)
y un email.

Todo el stack es gratuito: GitHub Actions como runner, la API de Gemini (free tier)
como editor, RSS como fuente y el SMTP de Gmail para el envío.

## Cómo funciona

Cada día a las 10:30 UTC (7:30 en Argentina) el workflow corre cuatro pasos:

1. **`scripts/fetch_feeds.py`** lee los feeds de `feeds.yaml`, filtra por recencia y
   ruido, deduplica, puntúa y arma 30–40 candidatos.
2. **`scripts/generar.py`** manda los candidatos y `prompt-editorial.md` al modelo,
   que selecciona y redacta la edición en JSON estricto. Los links siempre salen de
   los feeds, nunca del modelo.
3. **`scripts/render.py`** genera la edición HTML, la portada, el RSS y la versión
   email, y actualiza `state.json` para no repetir noticias.
4. **`scripts/send_mail.py`** envía el email. Si la edición no se generó, no se
   envía nada.

Si cualquier paso falla, el job falla visible y no se publica a medias.

## Cambiar las fuentes

Editá `feeds.yaml`. Cada feed tiene `nombre`, `url`, `peso` (1–3, cuánto suma al
puntaje) y `bloque` (a qué sección suele aportar). Ahí también viven la lista
`ruido` (palabras que descartan un título) y las `keywords` por bloque.

Para verificar que un feed funciona antes de sumarlo:

```bash
python3 check_feeds.py
```

## Cambiar el horario

Editá el `cron` en `.github/workflows/diario.yml`. Está en UTC. GitHub puede
demorar la ejecución en horarios de pico.

## Cambiar los criterios editoriales

Editá `prompt-editorial.md`: bloques, volumen, puntuación, qué se descarta, cuándo
hay destacado y el estilo de redacción.

## Cambiar el modelo

`generar.py` habla con cualquier API compatible con OpenAI. Por defecto usa el
endpoint de Gemini con `gemini-3.6-flash`. Se cambia por variables de entorno (en
Actions, como variables o secrets del repo):

- `DIARIO_API_KEY` — API key del proveedor (secret, obligatoria)
- `DIARIO_API_BASE` — base de la API (default: endpoint OpenAI-compatible de Gemini)
- `DIARIO_MODELO` — nombre del modelo

## Secrets que necesita el workflow

| Secret | Qué es |
| --- | --- |
| `DIARIO_API_KEY` | API key de Gemini (gratis en aistudio.google.com) |
| `GMAIL_USER` | Cuenta de Gmail que envía |
| `GMAIL_APP_PASSWORD` | App password de Gmail (no la contraseña de la cuenta) |
| `MAIL_TO` | Destinatario del email |

## Correr en local

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/fetch_feeds.py
DIARIO_API_KEY=... .venv/bin/python scripts/generar.py
.venv/bin/python scripts/render.py
```

La edición queda en `ediciones/`, el email en `.out/email.html` (no se versiona:
contiene una línea de uso interno que no va en la web pública).
