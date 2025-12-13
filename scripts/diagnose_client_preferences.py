#!/usr/bin/env python3
"""
Script para diagnosticar problemas con ClientPreferences bloqueando emails
Ejecutar desde Render: python scripts/diagnose_client_preferences.py
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

from ventas.models import ClientPreferences, Cliente, VentaReserva, CommunicationLog
from django.utils import timezone
from datetime import timedelta

print("\n" + "=" * 80)
print("DIAGNÓSTICO: CLIENT PREFERENCES Y BLOQUEO DE EMAILS")
print("=" * 80)

# ==============================================================================
# 1. VERIFICAR ESTADO DE CLIENT PREFERENCES
# ==============================================================================
print("\n📊 1. ESTADO DE CLIENT PREFERENCES")
print("-" * 80)

total_preferences = ClientPreferences.objects.count()
total_clientes = Cliente.objects.count()

print(f"Total ClientPreferences: {total_preferences}")
print(f"Total Clientes: {total_clientes}")
print(f"Clientes SIN preferences: {total_clientes - total_preferences}")

# Buscar clientes con preferencias que bloquean emails
bloqueados_email_general = ClientPreferences.objects.filter(accepts_email=False)
bloqueados_confirmacion = ClientPreferences.objects.filter(accepts_booking_confirmations=False)
bloqueados_reminders = ClientPreferences.objects.filter(accepts_booking_reminders=False)

print(f"\n⚠️  Clientes con accepts_email=False: {bloqueados_email_general.count()}")
print(f"⚠️  Clientes con accepts_booking_confirmations=False: {bloqueados_confirmacion.count()}")
print(f"⚠️  Clientes con accepts_booking_reminders=False: {bloqueados_reminders.count()}")

if bloqueados_email_general.exists():
    print("\n🚨 CLIENTES CON accepts_email=False (NO RECIBEN NINGÚN EMAIL):")
    for pref in bloqueados_email_general[:10]:
        print(f"   - {pref.cliente.nombre} ({pref.cliente.email})")
        print(f"     Creado: {pref.created_at.strftime('%d/%m/%Y %H:%M')}")
        print(f"     Actualizado: {pref.updated_at.strftime('%d/%m/%Y %H:%M')}")
        print()

if bloqueados_confirmacion.exists():
    print("\n🚨 CLIENTES CON accepts_booking_confirmations=False:")
    for pref in bloqueados_confirmacion[:10]:
        print(f"   - {pref.cliente.nombre} ({pref.cliente.email})")
        print(f"     Creado: {pref.created_at.strftime('%d/%m/%Y %H:%M')}")
        print()

# ==============================================================================
# 2. ANALIZAR LAS 25 RESERVAS SIN EMAIL
# ==============================================================================
print("\n📋 2. ANÁLISIS DE LAS 25 RESERVAS SIN EMAIL")
print("-" * 80)

hace_7_dias = timezone.now() - timedelta(days=7)
reservas_recientes = VentaReserva.objects.filter(fecha_reserva__gte=hace_7_dias)

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

print(f"Total reservas sin email: {len(sin_email)}")

# Analizar por qué no se enviaron
print("\n🔍 ANÁLISIS DETALLADO (primeras 10):")
print("-" * 80)

from ventas.services.communication_service import communication_service

for reserva in sin_email[:10]:
    cliente = reserva.cliente
    print(f"\nReserva #{reserva.id} - {cliente.nombre} ({cliente.email})")
    print(f"   Fecha reserva: {reserva.fecha_reserva.strftime('%d/%m/%Y %H:%M')}")
    print(f"   Total: ${reserva.total:,.0f}")

    # Verificar si tiene servicios
    from ventas.models import ReservaServicio
    servicios = ReservaServicio.objects.filter(venta_reserva=reserva)
    print(f"   Servicios asociados: {servicios.count()}")

    if servicios.count() == 0:
        print(f"   ❌ CAUSA: No tiene servicios asociados (el signal no se dispara)")
        continue

    # Verificar ClientPreferences
    try:
        preferences = ClientPreferences.objects.get(cliente=cliente)
        print(f"   ClientPreferences existe: Sí")
        print(f"      - accepts_email: {preferences.accepts_email}")
        print(f"      - accepts_booking_confirmations: {preferences.accepts_booking_confirmations}")

        # Simular la validación
        can_send = communication_service._can_send_communication(
            cliente, 'EMAIL', 'BOOKING_CONFIRMATION'
        )

        if not can_send:
            print(f"   ❌ CAUSA: _can_send_communication() retorna FALSE")
            if not preferences.accepts_email:
                print(f"      → accepts_email=False")
            if not preferences.accepts_booking_confirmations:
                print(f"      → accepts_booking_confirmations=False")
        else:
            print(f"   ✅ _can_send_communication() retorna TRUE")
            print(f"   ❓ Causa desconocida - revisar logs del servidor")

    except ClientPreferences.DoesNotExist:
        print(f"   ClientPreferences existe: No")
        print(f"   ✅ Se debería crear con defaults (todo True)")
        print(f"   ❓ El email debería haberse enviado")

# ==============================================================================
# 3. VERIFICAR PATRÓN TEMPORAL
# ==============================================================================
print("\n\n📅 3. PATRÓN TEMPORAL DE ENVÍO DE EMAILS")
print("-" * 80)

# Últimos emails de confirmación enviados
ultimos_confirmacion = CommunicationLog.objects.filter(
    message_type='BOOKING_CONFIRMATION',
    communication_type='EMAIL'
).order_by('-created_at')[:20]

print("Últimos 20 emails de confirmación enviados:")
for log in ultimos_confirmacion:
    print(f"   {log.created_at.strftime('%d/%m/%Y %H:%M')} - Booking #{log.booking_id} - {log.destination}")

# Fecha del último email de confirmación
if ultimos_confirmacion.exists():
    ultimo = ultimos_confirmacion.first()
    print(f"\n📌 Último email de confirmación: {ultimo.created_at.strftime('%d/%m/%Y %H:%M')}")

    # Ver si hay reservas después de esa fecha sin email
    reservas_despues = VentaReserva.objects.filter(
        fecha_reserva__gt=ultimo.created_at
    ).exclude(
        id__in=CommunicationLog.objects.filter(
            message_type='BOOKING_CONFIRMATION'
        ).values_list('booking_id', flat=True)
    )

    if reservas_despues.exists():
        print(f"\n⚠️  HAY {reservas_despues.count()} RESERVAS DESPUÉS DE ESA FECHA SIN EMAIL")
        print(f"    Esto sugiere que algo cambió después del {ultimo.created_at.strftime('%d/%m/%Y %H:%M')}")

# ==============================================================================
# 4. VERIFICAR CAMBIOS RECIENTES EN CLIENT PREFERENCES
# ==============================================================================
print("\n\n🔄 4. CAMBIOS RECIENTES EN CLIENT PREFERENCES")
print("-" * 80)

# ClientPreferences modificados recientemente
hace_30_dias = timezone.now() - timedelta(days=30)
modificados = ClientPreferences.objects.filter(
    updated_at__gte=hace_30_dias
).order_by('-updated_at')[:20]

print(f"ClientPreferences modificados en últimos 30 días: {modificados.count()}")

if modificados.exists():
    print("\nÚltimas modificaciones:")
    for pref in modificados[:10]:
        print(f"   {pref.updated_at.strftime('%d/%m/%Y %H:%M')} - {pref.cliente.nombre}")
        print(f"      accepts_email: {pref.accepts_email}")
        print(f"      accepts_booking_confirmations: {pref.accepts_booking_confirmations}")

# ==============================================================================
# RESUMEN Y DIAGNÓSTICO
# ==============================================================================
print("\n" + "=" * 80)
print("📋 RESUMEN DEL DIAGNÓSTICO")
print("=" * 80)

problema_encontrado = False

if bloqueados_email_general.exists():
    print("\n🚨 PROBLEMA ENCONTRADO:")
    print(f"   {bloqueados_email_general.count()} clientes tienen accepts_email=False")
    print("   Estos clientes NO RECIBEN NINGÚN EMAIL")
    problema_encontrado = True

if bloqueados_confirmacion.exists():
    print("\n🚨 PROBLEMA ENCONTRADO:")
    print(f"   {bloqueados_confirmacion.count()} clientes tienen accepts_booking_confirmations=False")
    print("   Estos clientes NO RECIBEN CONFIRMACIONES DE RESERVA")
    problema_encontrado = True

# Contar reservas sin servicios
sin_servicios = 0
for reserva in sin_email:
    if not ReservaServicio.objects.filter(venta_reserva=reserva).exists():
        sin_servicios += 1

if sin_servicios > 0:
    print(f"\n⚠️  {sin_servicios} de {len(sin_email)} reservas sin email NO TIENEN SERVICIOS ASOCIADOS")
    print("   El signal espera que existan ReservaServicio antes de enviar")

if not problema_encontrado:
    print("\n✅ No se encontraron ClientPreferences bloqueando emails")
    print("   El problema puede ser:")
    print("   - Reservas creadas sin ReservaServicio")
    print("   - Error en el signal que no se está ejecutando")
    print("   - Problema temporal de conexión con SendGrid")

print("\n" + "=" * 80 + "\n")
