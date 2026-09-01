---
name: convenciones
description: Reglas del repo diario-ia - qué no puede entrar al repo público, estilo de commits y límites del pipeline. Usar al escribir código, commitear o tocar plantillas.
---

# Convenciones del proyecto

## Repo público: qué NO entra

- Secretos de ningún tipo (tokens, passwords, direcciones de email).
- Nombres de clientes, juicios sobre proveedores, comentarios internos.
- `.out/` (contiene el email con la línea privada de reclutamiento de pacientes).

## Reglas del pipeline

- Los links de la edición salen de los feeds; el modelo nunca inventa URLs.
- La línea "Aplicación en reclutamiento de pacientes" va solo en el email.
- Si un paso falla, el job falla entero: nunca publicar a medias.
- No introducir dependencias pagas.

## Commits

- Mensajes en español, en imperativo: `agrega`, `corrige`, `elimina`.
- Un cambio lógico por commit.
- Las ediciones diarias las commitea el workflow como `diario-ia[bot]` con el
  mensaje `Edición AAAA-MM-DD`.
- Nunca `git push --force`.

## Estilo de código

- Python con nombres en español (el repo es personal y todo el contenido es en
  español); libs estándar + las de `requirements.txt`.
- Docstring al inicio de cada script: qué hace, entrada/salida, uso.

## Plantillas

- Web (`templates/edicion.html` + `estilo.css`): CSS moderno sin restricciones,
  estética blueprint (paleta en `estilo.css`; sin border-radius, degradados ni sombras).
- Email (`templates/email.html`): tablas, CSS inline, 640px, `bgcolor` en cada `td`
  con fondo, links con color explícito, fuente mínima 14px, sin JS/imágenes/fuentes remotas.
