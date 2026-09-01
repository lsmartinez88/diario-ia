# diario-ia

Diario automatizado de noticias de IA. Se publica solo cada día: blog en GitHub
Pages + email. El README explica la arquitectura; esto es lo que no está ahí.

## Reglas duras

- **Todo gratis.** Actions + Gemini free tier + RSS + SMTP de Gmail. Ninguna
  dependencia paga sin preguntar antes.
- **Ningún secreto en el repo.** Credenciales solo por secrets de Actions o
  variables de entorno locales.
- **El repo es público.** Nada de nombres de clientes, juicios sobre proveedores ni
  comentarios internos en archivos versionados.
- **Los links salen de los feeds, nunca del modelo.** `generar.py` descarta
  cualquier item cuyo link no esté entre los candidatos.
- La línea **"Aplicación en reclutamiento de pacientes"** va SOLO en el email
  (`.out/email.html`, gitignoreado). Nunca en la web, el index ni el RSS.
- No usar `git push --force` ni reescribir historia.

## Contexto

El usuario (Lucas) lidera IT en una empresa de reclutamiento de pacientes para
ensayos clínicos (LatAm, España, US). El bloque de IA clínica es el que más le
importa: pesa doble en la puntuación editorial.

## Detalles no obvios

- GitHub Models (el plan original) fue retirado el 2026-07-30; por eso se usa el
  endpoint OpenAI-compatible de Gemini. Proveedor intercambiable por env vars
  (`DIARIO_API_KEY` / `DIARIO_API_BASE` / `DIARIO_MODELO`).
- Los feeds de Fierce (Biotech/Healthcare) publican fechas no estándar
  ("Aug 31, 2026 4:27pm") y títulos con HTML adentro; `fetch_feeds.py` tiene
  parser y limpieza propios para eso.
- La plantilla email es tablas + CSS inline + `bgcolor` en cada `td` con fondo
  (sin eso Outlook pinta el panel blanco). No agregar imágenes, JS ni fuentes
  remotas ahí.
- `state.json` guarda links ya publicados (para no repetir) y el índice de
  ediciones (para portada y RSS).

## Comandos

Ver skills en `.claude/skills/` y la sección "Correr en local" del README.
Servidor de preview: `python3 -m http.server 8123` (config en `.claude/launch.json`).
