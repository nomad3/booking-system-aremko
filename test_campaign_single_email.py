#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para probar envío de UN solo email de una campaña
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from ventas.models import EmailCampaign, EmailRecipient
from ventas.utils.email_footer import get_email_footer_html

print("\n" + "="*60)
print("PRUEBA DE ENVÍO DE 1 EMAIL DE CAMPAÑA")
print("="*60)

# Obtener campaña
campaign_id = 88
try:
    campaign = EmailCampaign.objects.get(id=campaign_id)
    print(f"\n📧 Campaña: {campaign.name}")
    print(f"   Estado: {campaign.status}")
except EmailCampaign.DoesNotExist:
    print(f"\n❌ Campaña {campaign_id} no encontrada")
    sys.exit(1)

# Obtener primer recipient pendiente
recipient = EmailRecipient.objects.filter(
    campaign=campaign,
    status='pending',
    send_enabled=True
).first()

if not recipient:
    print("\n❌ No hay destinatarios pendientes")
    sys.exit(1)

print(f"\n👤 Destinatario de prueba:")
print(f"   Nombre: {recipient.name}")
print(f"   Email: {recipient.email}")
print(f"   Estado: {recipient.status}")

# Preparar email
subject = recipient.personalized_subject.replace('{nombre_cliente}', recipient.name)
body = recipient.personalized_body.replace('{nombre_cliente}', recipient.name)

# Agregar footer con unsubscribe
body_with_footer = body + get_email_footer_html(recipient.email)

print(f"\n📝 Contenido:")
print(f"   Asunto: {subject[:60]}...")
print(f"   From: {settings.DEFAULT_FROM_EMAIL}")

# Confirmar
confirm = input("\n¿Enviar este email de prueba? (s/n): ").strip().lower()

if confirm != 's':
    print("\n❌ Envío cancelado")
    sys.exit(0)

print("\n📤 Enviando...")

try:
    msg = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient.email]
    )

    msg.attach_alternative(body_with_footer, "text/html")

    result = msg.send()

    if result:
        print("\n" + "="*60)
        print("✅ EMAIL ENVIADO EXITOSAMENTE")
        print("="*60)
        print(f"\n   📬 Destinatario: {recipient.email}")
        print(f"   📧 From: {settings.DEFAULT_FROM_EMAIL}")
        print("\n   ¿Marca este recipient como enviado? (s/n): ", end='')
        mark = input().strip().lower()

        if mark == 's':
            recipient.status = 'sent'
            recipient.save()
            print("   ✅ Marcado como enviado")

        print()
    else:
        print("\n❌ Error: send() retornó 0")

except Exception as e:
    print("\n" + "="*60)
    print("❌ ERROR AL ENVIAR")
    print("="*60)
    print(f"\n   {str(e)}")
    print()
    sys.exit(1)
