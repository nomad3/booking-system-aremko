#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar el estado actual de las campañas de email
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'booking_system.settings')
django.setup()

from ventas.models import EmailCampaign, EmailRecipient
from django.db.models import Count, Q

print("=" * 80)
print("📊 ESTADO ACTUAL DE CAMPAÑAS DE EMAIL")
print("=" * 80)

# Obtener todas las campañas
campanas = EmailCampaign.objects.all().order_by('-created_at')

if not campanas.exists():
    print("\n⚠️ No hay campañas creadas")
    sys.exit(0)

for campana in campanas:
    print(f"\n📧 Campaña: {campana.name}")
    print(f"   ID: {campana.id}")
    print(f"   Estado: {campana.get_status_display()}")
    print(f"   Creada: {campana.created_at.strftime('%Y-%m-%d %H:%M')}")

    # Estadísticas de recipients
    recipients_stats = campana.recipients.aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='pending')),
        sent=Count('id', filter=Q(status='sent')),
        failed=Count('id', filter=Q(status='failed')),
        disabled=Count('id', filter=Q(send_enabled=False))
    )

    total = recipients_stats['total']
    pending = recipients_stats['pending']
    sent = recipients_stats['sent']
    failed = recipients_stats['failed']
    disabled = recipients_stats['disabled']

    print(f"\n   📊 Destinatarios:")
    print(f"      Total: {total}")
    print(f"      ✅ Enviados: {sent} ({(sent/total*100) if total > 0 else 0:.1f}%)")
    print(f"      ⏳ Pendientes: {pending} ({(pending/total*100) if total > 0 else 0:.1f}%)")
    print(f"      ❌ Fallidos: {failed}")
    print(f"      🚫 Deshabilitados: {disabled}")

    # Configuración de envío
    if campana.schedule_config:
        batch_size = campana.schedule_config.get('batch_size', 5)
        interval = campana.schedule_config.get('interval_minutes', 6)
        start_time = campana.schedule_config.get('start_time', '08:00')
        end_time = campana.schedule_config.get('end_time', '21:00')

        print(f"\n   ⚙️ Configuración:")
        print(f"      Lote: {batch_size} emails")
        print(f"      Intervalo: {interval} minutos")
        print(f"      Horario: {start_time} - {end_time}")

    # Estimación de tiempo restante
    if pending > 0 and campana.schedule_config:
        batch_size = campana.schedule_config.get('batch_size', 5)
        interval = campana.schedule_config.get('interval_minutes', 6)

        lotes_restantes = (pending + batch_size - 1) // batch_size  # Round up
        minutos_restantes = lotes_restantes * interval
        horas_restantes = minutos_restantes / 60

        print(f"\n   ⏱️ Estimación:")
        print(f"      Lotes restantes: {lotes_restantes}")
        print(f"      Tiempo estimado: ~{horas_restantes:.1f} horas ({minutos_restantes:.0f} min)")

        if campana.status == 'sending':
            print(f"\n   ✅ El cron job continuará enviando automáticamente")
        elif campana.status == 'ready':
            print(f"\n   ⚠️ Campaña lista pero no iniciada. El cron la iniciará en el próximo ciclo")
        elif campana.status == 'paused':
            print(f"\n   ⏸️ Campaña pausada. Cambiar estado a 'ready' o 'sending' para reanudar")

print("\n" + "=" * 80)
print("🔄 CRON JOB")
print("=" * 80)

# Verificar campañas que el cron procesará
campanas_activas = EmailCampaign.objects.filter(status__in=['ready', 'sending'])
count = campanas_activas.count()

if count > 0:
    print(f"\n✅ El cron job procesará {count} campaña(s) en el próximo ciclo (cada 5 min)")
    for camp in campanas_activas:
        pending_count = camp.recipients.filter(status='pending', send_enabled=True).count()
        print(f"   • {camp.name}: {pending_count} emails pendientes")
else:
    print(f"\n⚠️ No hay campañas activas (status='ready' o 'sending')")
    print(f"   El cron job esperará hasta que haya campañas activas")

print("\n" + "=" * 80)
print("📝 PRÓXIMOS PASOS")
print("=" * 80)
print("\n1. Monitorear logs de Render:")
print("   Buscar: '✅ Cron enviar_campanas_email iniciado'")
print("\n2. Ver progreso en Django Admin:")
print("   /admin/ventas/emailcampaign/")
print("\n3. Si necesitas pausar:")
print("   Cambiar estado de campaña a 'paused'")
print("\n4. Si quieres acelerar:")
print("   Reducir 'interval_minutes' en schedule_config")
print()
