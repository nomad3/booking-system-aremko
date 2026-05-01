#!/usr/bin/env python
"""
Script para probar envío de campaña ID 88
Ejecutar: python test_send_campaign.py
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import EmailCampaign, EmailRecipient
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import sys

print("=" * 80)
print("TEST DE ENVÍO - CAMPAÑA ID 88")
print("=" * 80)

try:
    # Obtener la campaña
    campaign = EmailCampaign.objects.get(id=88)
    print(f"\n✅ Campaña encontrada: {campaign.name}")
    print(f"   Estado: {campaign.status}")

    # Obtener el primer destinatario pendiente
    recipient = campaign.recipients.filter(send_enabled=True, status='pending').first()

    if not recipient:
        print("\n❌ No hay destinatarios pendientes")
        sys.exit(1)

    print(f"\n📧 Probando envío a: {recipient.email}")
    print(f"   Nombre: {recipient.name}")
    print(f"   Asunto: {recipient.personalized_subject[:60]}...")

    # Configuración de email
    print(f"\n⚙️  CONFIGURACIÓN EMAIL:")
    print(f"   EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"   EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"   DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")

    # Crear el email
    email = EmailMultiAlternatives(
        subject=recipient.personalized_subject,
        body=recipient.personalized_body[:200] + "...",  # Texto plano corto
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient.email]
    )

    # Adjuntar HTML
    email.attach_alternative(recipient.personalized_body, "text/html")

    # Enviar
    print(f"\n📤 Enviando email...")
    result = email.send()

    if result == 1:
        print(f"\n✅ EMAIL ENVIADO EXITOSAMENTE")
        print(f"   Destinatario: {recipient.email}")
        print(f"   Resultado: {result} email enviado")

        # Actualizar estado del recipient
        recipient.status = 'sent'
        recipient.sent_at = django.utils.timezone.now()
        recipient.save()
        print(f"   Estado actualizado a: {recipient.status}")

    else:
        print(f"\n❌ ERROR: El envío retornó {result}")

except EmailCampaign.DoesNotExist:
    print("\n❌ Campaña ID 88 no encontrada")
    sys.exit(1)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("FIN DEL TEST")
print("=" * 80)
