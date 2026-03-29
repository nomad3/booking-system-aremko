#!/usr/bin/env python
"""Enviar correo de prueba con SendGrid"""
import os, smtplib
from email.mime.text import MIMEText

k = os.getenv('SENDGRID_API_KEY')
if not k:
    print("❌ No hay SENDGRID_API_KEY")
    exit(1)

to = input("Email destino: ").strip()
if not to:
    print("Cancelado")
    exit()

try:
    s = smtplib.SMTP('smtp.sendgrid.net', 587)
    s.starttls()
    s.login('apikey', k)

    m = MIMEText("Test SendGrid OK")
    m['Subject'] = 'Test Aremko'
    m['From'] = 'ventas@aremko.cl'
    m['To'] = to

    s.send_message(m)
    print(f"✅ Enviado a {to}")
    s.quit()
except Exception as e:
    print(f"❌ {e}")