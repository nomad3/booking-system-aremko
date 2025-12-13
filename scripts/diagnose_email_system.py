#!/usr/bin/env python3
"""
Script para diagnosticar el sistema de envío de emails
Ejecutar desde Render: python scripts/diagnose_email_system.py
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from django.conf import settings
from ventas.models import VentaReserva, Cliente, CommunicationLog, ClientePremio
from datetime import timedelta
from django.utils import timezone

print("\n" + "=" * 80)
print("DIAGNÓSTICO DEL SISTEMA DE EMAILS")
print("=" * 80)

# ==============================================================================
# 1. CONFIGURACIÓN DE EMAIL
# ==============================================================================
print("\n📧 1. CONFIGURACIÓN DE EMAIL")
print("-" * 80)

email_backend = getattr(settings, 'EMAIL_BACKEND', 'No configurado')
print(f"EMAIL_BACKEND: {email_backend}")

if 'console' in email_backend.lower():
    print("⚠️  PROBLEMA: EMAIL_BACKEND está configurado en 'console'")
    print("   Esto significa que los emails NO se envían realmente,")
    print("   solo se muestran en la consola/logs.")
    print()
    print("   SOLUCIÓN: Configurar SendGrid o SMTP en las variables de entorno")
elif 'sendgrid' in email_backend.lower():
    print("✅ Usando SendGrid para envío de emails")
    sendgrid_key = os.getenv('SENDGRID_API_KEY', '')
    if sendgrid_key:
        print(f"   API Key configurada: {sendgrid_key[:10]}...")
    else:
        print("   ⚠️ SENDGRID_API_KEY no encontrada en variables de entorno")
elif 'smtp' in email_backend.lower():
    print("✅ Usando SMTP para envío de emails")
    print(f"   EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', 'No configurado')}")
    print(f"   EMAIL_PORT: {getattr(settings, 'EMAIL_PORT', 'No configurado')}")
    print(f"   EMAIL_HOST_USER: {getattr(settings, 'EMAIL_HOST_USER', 'No configurado')}")
else:
    print(f"⚠️  Backend desconocido: {email_backend}")

print(f"\nVENTAS_FROM_EMAIL: {getattr(settings, 'VENTAS_FROM_EMAIL', 'No configurado')}")
print(f"COMMUNICATION_SMS_ENABLED: {getattr(settings, 'COMMUNICATION_SMS_ENABLED', False)}")

# ==============================================================================
# 2. VERIFICAR SIGNALS ACTIVOS
# ==============================================================================
print("\n\n🔔 2. SIGNALS DE EMAILS")
print("-" * 80)

try:
    from django.db.models.signals import post_save
    from ventas.models import VentaReserva, Pago, ReservaServicio

    # Verificar si hay receivers registrados
    venta_receivers = post_save._live_receivers(VentaReserva)
    pago_receivers = post_save._live_receivers(Pago)
    reserva_receivers = post_save._live_receivers(ReservaServicio)

    print(f"✅ Signals VentaReserva: {len(venta_receivers)} receivers activos")
    print(f"✅ Signals Pago: {len(pago_receivers)} receivers activos")
    print(f"✅ Signals ReservaServicio: {len(reserva_receivers)} receivers activos")

    # Mostrar nombres de receivers
    print("\nReceivers de VentaReserva:")
    for receiver in venta_receivers:
        print(f"   - {receiver.__name__ if hasattr(receiver, '__name__') else receiver}")

except Exception as e:
    print(f"❌ Error verificando signals: {e}")

# ==============================================================================
# 3. LOGS DE COMUNICACIÓN RECIENTES
# ==============================================================================
print("\n\n📊 3. LOGS DE COMUNICACIÓN (Últimos 7 días)")
print("-" * 80)

try:
    hace_7_dias = timezone.now() - timedelta(days=7)
    logs = CommunicationLog.objects.filter(created_at__gte=hace_7_dias)

    print(f"Total de comunicaciones: {logs.count()}")

    # Por tipo
    emails = logs.filter(communication_type='EMAIL')
    sms = logs.filter(communication_type='SMS')

    print(f"\n📧 Emails enviados: {emails.count()}")
    print(f"📱 SMS enviados: {sms.count()}")

    # Por estado
    print(f"\nPor estado:")
    for status in ['SENT', 'PENDING', 'FAILED', 'BLOCKED']:
        count = logs.filter(status=status).count()
        if count > 0:
            print(f"   {status}: {count}")

    # Por tipo de mensaje
    print(f"\nPor tipo de mensaje (emails):")
    tipos = emails.values('message_type').distinct()
    for tipo in tipos:
        tipo_name = tipo['message_type']
        count = emails.filter(message_type=tipo_name).count()
        print(f"   {tipo_name}: {count}")

    # Últimos 5 emails
    print(f"\n📋 Últimos 5 emails:")
    ultimos = emails.order_by('-created_at')[:5]
    for log in ultimos:
        print(f"   {log.created_at.strftime('%d/%m %H:%M')} - {log.message_type}")
        print(f"      Para: {log.destination}")
        print(f"      Estado: {log.status}")
        if log.subject:
            print(f"      Asunto: {log.subject[:50]}...")
        print()

except Exception as e:
    print(f"❌ Error obteniendo logs: {e}")
    import traceback
    traceback.print_exc()

# ==============================================================================
# 4. VERIFICAR RESERVAS RECIENTES SIN EMAILS
# ==============================================================================
print("\n\n🔍 4. RESERVAS RECIENTES SIN CONFIRMACIÓN POR EMAIL")
print("-" * 80)

try:
    hace_7_dias = timezone.now() - timedelta(days=7)
    reservas_recientes = VentaReserva.objects.filter(fecha_reserva__gte=hace_7_dias)

    print(f"Reservas últimos 7 días: {reservas_recientes.count()}")

    sin_email = []
    for reserva in reservas_recientes:
        # Verificar si tiene log de email de confirmación
        tiene_email = CommunicationLog.objects.filter(
            booking_id=reserva.id,
            communication_type='EMAIL',
            message_type='BOOKING_CONFIRMATION'
        ).exists()

        if not tiene_email and reserva.cliente and reserva.cliente.email:
            sin_email.append(reserva)

    print(f"\n⚠️  Reservas SIN email de confirmación: {len(sin_email)}")

    if sin_email:
        print("\nDetalles:")
        for reserva in sin_email[:10]:  # Mostrar máximo 10
            print(f"   Reserva #{reserva.id} - {reserva.fecha_reserva.strftime('%d/%m/%Y')}")
            print(f"      Cliente: {reserva.cliente.nombre} ({reserva.cliente.email})")
            print(f"      Total: ${reserva.total:,.0f}")
            print()

except Exception as e:
    print(f"❌ Error: {e}")

# ==============================================================================
# 5. SISTEMA DE PREMIOS
# ==============================================================================
print("\n\n🎁 5. SISTEMA DE PREMIOS")
print("-" * 80)

try:
    premios_pendientes = ClientePremio.objects.filter(
        estado='pendiente',
        fecha_creacion__gte=timezone.now() - timedelta(days=30)
    )

    premios_aprobados = ClientePremio.objects.filter(
        estado='aprobado',
        fecha_aprobacion__gte=timezone.now() - timedelta(days=30)
    )

    print(f"Premios pendientes (último mes): {premios_pendientes.count()}")
    print(f"Premios aprobados (último mes): {premios_aprobados.count()}")

    # Verificar si los aprobados tienen email enviado
    sin_email_premio = []
    for premio in premios_aprobados:
        tiene_email = CommunicationLog.objects.filter(
            cliente=premio.cliente,
            message_type__icontains='PREMIO'
        ).exists()

        if not tiene_email and premio.cliente.email:
            sin_email_premio.append(premio)

    print(f"\n⚠️  Premios aprobados SIN email: {len(sin_email_premio)}")

    if sin_email_premio:
        print("\nDetalles:")
        for premio in sin_email_premio[:5]:
            print(f"   Premio #{premio.id} - {premio.tipo_premio}")
            print(f"      Cliente: {premio.cliente.nombre} ({premio.cliente.email})")
            print(f"      Aprobado: {premio.fecha_aprobacion.strftime('%d/%m/%Y') if premio.fecha_aprobacion else 'N/A'}")
            print()

except Exception as e:
    print(f"❌ Error: {e}")

# ==============================================================================
# 6. EMAILS DE PAGO
# ==============================================================================
print("\n\n💳 6. NOTIFICACIONES DE PAGO")
print("-" * 80)

try:
    hace_7_dias = timezone.now() - timedelta(days=7)

    # Reservas completamente pagadas
    reservas_pagadas = VentaReserva.objects.filter(
        fecha_reserva__gte=hace_7_dias,
        estado_pago='pagado'
    )

    print(f"Reservas pagadas (últimos 7 días): {reservas_pagadas.count()}")

    # Verificar cuáles tienen email de pago
    sin_email_pago = []
    for reserva in reservas_pagadas:
        tiene_email_pago = CommunicationLog.objects.filter(
            booking_id=reserva.id,
            communication_type='EMAIL',
            subject__icontains='pago'
        ).exists()

        if not tiene_email_pago and reserva.cliente and reserva.cliente.email:
            sin_email_pago.append(reserva)

    print(f"\n⚠️  Reservas pagadas SIN email de confirmación de pago: {len(sin_email_pago)}")

    if sin_email_pago:
        print("\nDetalles:")
        for reserva in sin_email_pago[:5]:
            print(f"   Reserva #{reserva.id}")
            print(f"      Cliente: {reserva.cliente.nombre} ({reserva.cliente.email})")
            print(f"      Pagado: ${reserva.pagado:,.0f} / ${reserva.total:,.0f}")
            print()

except Exception as e:
    print(f"❌ Error: {e}")

# ==============================================================================
# RESUMEN Y RECOMENDACIONES
# ==============================================================================
print("\n" + "=" * 80)
print("📋 RESUMEN Y RECOMENDACIONES")
print("=" * 80)

if 'console' in email_backend.lower():
    print("\n🚨 PROBLEMA CRÍTICO:")
    print("   El EMAIL_BACKEND está en modo 'console'")
    print("   Los emails NO se están enviando a los clientes")
    print()
    print("   SOLUCIÓN:")
    print("   Configurar en Render las siguientes variables de entorno:")
    print("   - SENDGRID_API_KEY=tu_api_key_de_sendgrid")
    print("   O alternativamente:")
    print("   - EMAIL_HOST_USER=tu_email@gmail.com")
    print("   - EMAIL_HOST_PASSWORD=tu_app_password")
else:
    print("\n✅ Backend de email configurado correctamente")

print("\n" + "=" * 80 + "\n")
