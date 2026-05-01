#!/usr/bin/env python
"""
Script de diagnóstico para campañas de email
Ejecutar desde Render: python diagnose_campaign.py
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.conf import settings
from ventas.models import EmailCampaign, EmailRecipient, EmailDeliveryLog
from datetime import date, datetime

print("=" * 80)
print("DIAGNÓSTICO DE SISTEMA DE EMAIL")
print("=" * 80)

# 1. Configuración de Email
print("\n1️⃣  CONFIGURACIÓN DE EMAIL")
print("-" * 80)
print(f"   EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"   EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
print(f"   EMAIL_HOST_USER: {'Configurado ✅' if settings.EMAIL_HOST_USER else 'NO configurado ❌'}")
print(f"   EMAIL_HOST_PASSWORD: {'Configurado ✅' if settings.EMAIL_HOST_PASSWORD else 'NO configurado ❌'}")
print(f"   DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")

if hasattr(settings, 'ANYMAIL'):
    print(f"   ANYMAIL: {settings.ANYMAIL}")
else:
    print(f"   ANYMAIL: No configurado")

# 2. Buscar campañas del 1 de mayo
print("\n2️⃣  CAMPAÑAS DEL 1 DE MAYO 2026")
print("-" * 80)

# Buscar por fecha de creación
campanas_mayo = EmailCampaign.objects.filter(created_at__date=date(2026, 5, 1))
print(f"   Campañas encontradas (por created_at): {campanas_mayo.count()}")

for c in campanas_mayo:
    print(f"\n   📋 Campaña: '{c.name}' (ID: {c.id})")
    print(f"      Estado: {c.status}")
    print(f"      Creada: {c.created_at}")
    print(f"      Subject template: {c.email_subject_template[:50]}...")

    # Estadísticas de destinatarios
    total_recipients = c.recipients.count()
    pending = c.recipients.filter(status='pending').count()
    pending_enabled = c.recipients.filter(status='pending', send_enabled=True).count()
    sent = c.recipients.filter(status='sent').count()
    failed = c.recipients.filter(status='failed').count()

    print(f"      Destinatarios totales: {total_recipients}")
    print(f"      - Pendientes: {pending} (con send_enabled=True: {pending_enabled})")
    print(f"      - Enviados: {sent}")
    print(f"      - Fallidos: {failed}")

    # Configuración de envío
    print(f"      Batch size: {c.batch_size}")
    print(f"      Batch interval: {c.batch_interval} min")
    print(f"      Campaign interval: {c.campaign_interval} min")

    # Horarios de envío
    if c.schedule_config:
        print(f"      Schedule config: {c.schedule_config}")

# Si no encontramos por fecha, buscar todas las campañas recientes
if campanas_mayo.count() == 0:
    print("\n   No se encontraron campañas del 1 de mayo.")
    print("   Buscando campañas recientes...")

    recientes = EmailCampaign.objects.all().order_by('-created_at')[:5]
    print(f"\n   Últimas 5 campañas:")
    for c in recientes:
        print(f"   - {c.name} (ID: {c.id}) - Estado: {c.status} - Creada: {c.created_at}")

# 3. Logs de envío recientes
print("\n3️⃣  LOGS DE ENVÍO RECIENTES (últimos 10)")
print("-" * 80)

recent_logs = EmailDeliveryLog.objects.all().order_by('-timestamp')[:10]
if recent_logs.exists():
    for log in recent_logs:
        status_icon = "✅" if log.status == 'sent' else "❌"
        print(f"   {status_icon} {log.timestamp} - {log.recipient_email}")
        print(f"      Campaña: {log.campaign.name if log.campaign else 'N/A'}")
        print(f"      Estado: {log.status}")
        if log.error_message:
            print(f"      Error: {log.error_message}")
        print()
else:
    print("   No hay logs de envío registrados")

# 4. Estado del sistema
print("\n4️⃣  ESTADO DEL SISTEMA")
print("-" * 80)

all_campaigns = EmailCampaign.objects.all()
print(f"   Total campañas: {all_campaigns.count()}")
print(f"   - Draft: {all_campaigns.filter(status='draft').count()}")
print(f"   - Ready: {all_campaigns.filter(status='ready').count()}")
print(f"   - Sending: {all_campaigns.filter(status='sending').count()}")
print(f"   - Paused: {all_campaigns.filter(status='paused').count()}")
print(f"   - Completed: {all_campaigns.filter(status='completed').count()}")
print(f"   - Cancelled: {all_campaigns.filter(status='cancelled').count()}")

print("\n" + "=" * 80)
print("FIN DEL DIAGNÓSTICO")
print("=" * 80)

# Recomendaciones
print("\n💡 RECOMENDACIONES:")
print("-" * 80)

if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
    print("⚠️  IMPORTANTE: Estás usando Console Backend (solo imprime en logs)")
    print("   Los emails NO se están enviando realmente.")
    print("   Configura SENDGRID_API_KEY o variables SMTP.")
elif settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
    print("✅ Usando SMTP Backend correctamente")

campanas_ready = EmailCampaign.objects.filter(status__in=['ready', 'sending'])
if campanas_ready.exists():
    print(f"\n📬 Tienes {campanas_ready.count()} campaña(s) lista(s) para enviar:")
    for c in campanas_ready:
        pending = c.recipients.filter(status='pending', send_enabled=True).count()
        if pending > 0:
            print(f"   - '{c.name}' (ID: {c.id}) tiene {pending} destinatarios pendientes")
            print(f"     Para enviar: python manage.py enviar_campana_email --campaign-id={c.id} --ignore-schedule")
else:
    print("\n📭 No hay campañas en estado 'ready' o 'sending'")
    campanas_draft = EmailCampaign.objects.filter(status='draft')
    if campanas_draft.exists():
        print(f"   Tienes {campanas_draft.count()} campaña(s) en 'draft'.")
        print("   Cambia el estado a 'ready' desde el admin para poder enviarlas.")

print("\n")
