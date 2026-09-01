#!/usr/bin/env python3
"""Envía la edición del día por email vía SMTP de Gmail.

No envía nada si la edición de hoy no está generada: preferimos que no llegue
ningún mail antes que llegue uno vacío o viejo.

Entorno:
  GMAIL_USER          cuenta que envía
  GMAIL_APP_PASSWORD  app password de Gmail (no la contraseña de la cuenta)
  MAIL_TO             destinatario (default: GMAIL_USER)

Uso: python3 scripts/send_mail.py
"""

import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def main():
    usuario = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    destino = os.environ.get("MAIL_TO") or usuario
    if not (usuario and password):
        print("faltan GMAIL_USER o GMAIL_APP_PASSWORD en el entorno", file=sys.stderr)
        return 1

    edicion_path = RAIZ / ".out" / "edicion.json"
    email_path = RAIZ / ".out" / "email.html"
    if not (edicion_path.exists() and email_path.exists()):
        print("no hay edición generada (.out/edicion.json / .out/email.html); no se envía nada", file=sys.stderr)
        return 1

    edicion = json.loads(edicion_path.read_text())
    hoy = datetime.now(timezone.utc).date().isoformat()
    if edicion["fecha"] != hoy:
        print(f"la edición es del {edicion['fecha']} y hoy es {hoy}; no se envía nada", file=sys.stderr)
        return 1

    d = datetime.fromisoformat(edicion["fecha"])
    asunto = f"Diario IA — {d.day} de {MESES[d.month - 1]} de {d.year}"

    html = email_path.read_text()
    texto_plano = re.sub(r"<[^>]+>", "", html)
    texto_plano = re.sub(r"\n{3,}", "\n\n", texto_plano).strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = f"Diario IA <{usuario}>"
    msg["To"] = destino
    msg.attach(MIMEText(texto_plano, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(usuario, password)
        smtp.sendmail(usuario, [destino], msg.as_string())

    print(f"email enviado: “{asunto}”")
    return 0


if __name__ == "__main__":
    sys.exit(main())
