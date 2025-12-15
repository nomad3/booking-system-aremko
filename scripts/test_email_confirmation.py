#!/usr/bin/env python3
"""
Script para probar el envío de email de confirmación y detectar errores
Ejecutar desde Render: python scripts/test_email_confirmation.py
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

from ventas.models import VentaReserva, Cliente, ReservaServicio
from ventas.services.communication_service import communication_service
import traceback

print("\n" + "=" * 80)
print("TEST DE ENVÍO DE EMAIL DE CONFIRMACIÓN")
print("=" * 80)

# Buscar una reserva reciente que NO tenga email enviado
print("\n🔍 Buscando una reserva reciente sin email...")
print("-" * 80)

from django.utils import timezone
from datetime import timedelta

hace_7_dias = timezone.now() - timedelta(days=7)
reservas = VentaReserva.objects.filter(
    fecha_reserva__gte=hace_7_dias
).order_by('-id')

# Buscar una que tenga servicios pero no tenga email
reserva_test = None
for r in reservas:
    # Verificar que tenga servicios
    if ReservaServicio.objects.filter(venta_reserva=r).exists():
        # Verificar que tenga cliente con email
        if r.cliente and r.cliente.email:
            # Verificar que no tenga email enviado
            from ventas.models import CommunicationLog
            tiene_email = CommunicationLog.objects.filter(
                booking_id=r.id,
                message_type='BOOKING_CONFIRMATION'
            ).exists()

            if not tiene_email:
                reserva_test = r
                break

if not reserva_test:
    print("❌ No se encontró ninguna reserva sin email para testear")
    print("\nVoy a usar la reserva más reciente con servicios:")
    for r in reservas:
        if ReservaServicio.objects.filter(venta_reserva=r).exists():
            if r.cliente and r.cliente.email:
                reserva_test = r
                break

if not reserva_test:
    print("❌ ERROR: No hay reservas disponibles para testear")
    sys.exit(1)

print(f"✅ Usando Reserva #{reserva_test.id}")
print(f"   Cliente: {reserva_test.cliente.nombre} ({reserva_test.cliente.email})")
print(f"   Fecha: {reserva_test.fecha_reserva.strftime('%d/%m/%Y %H:%M')}")
print(f"   Total: ${reserva_test.total:,.0f}")

# Contar servicios
servicios = ReservaServicio.objects.filter(venta_reserva=reserva_test)
print(f"   Servicios: {servicios.count()}")
for s in servicios:
    print(f"      - {s.servicio.nombre} ({s.fecha_agendamiento} {s.hora_inicio})")

# ==============================================================================
# TEST 1: Verificar que _can_send_communication devuelve True
# ==============================================================================
print("\n\n📋 TEST 1: Verificar _can_send_communication()")
print("-" * 80)

try:
    can_send = communication_service._can_send_communication(
        reserva_test.cliente,
        'EMAIL',
        'BOOKING_CONFIRMATION'
    )

    if can_send:
        print("✅ _can_send_communication() = TRUE")
    else:
        print("❌ _can_send_communication() = FALSE")
        print("   El sistema está bloqueando el envío")

        # Verificar por qué
        from ventas.models import ClientPreferences
        try:
            pref = ClientPreferences.objects.get(cliente=reserva_test.cliente)
            print(f"\n   ClientPreferences:")
            print(f"      - accepts_email: {pref.accepts_email}")
            print(f"      - accepts_booking_confirmations: {pref.accepts_booking_confirmations}")
        except ClientPreferences.DoesNotExist:
            print("   No tiene ClientPreferences (debería crearse con defaults)")

except Exception as e:
    print(f"❌ ERROR en _can_send_communication: {e}")
    traceback.print_exc()

# ==============================================================================
# TEST 2: Intentar enviar el email y capturar cualquier error
# ==============================================================================
print("\n\n📧 TEST 2: Intentar enviar email de confirmación")
print("-" * 80)
print("⚠️  IMPORTANTE: Este test intentará enviar un email REAL")
print(f"    Se enviará a: {reserva_test.cliente.email}")
print()

respuesta = input("¿Continuar con el envío? (escribe 'si' para continuar): ")

if respuesta.lower() not in ['si', 'sí', 's', 'yes', 'y']:
    print("\n❌ Test cancelado por el usuario")
    sys.exit(0)

print("\n🚀 Enviando email...")
print("-" * 80)

try:
    # Intentar enviar usando el método del servicio
    result = communication_service.send_booking_confirmation_dual(
        booking_id=reserva_test.id,
        cliente_id=reserva_test.cliente.id
    )

    print("\n📊 RESULTADO:")
    print(f"   Success: {result.get('success')}")

    if result.get('success'):
        print("\n✅ EMAIL ENVIADO EXITOSAMENTE")

        # Detalles del envío
        if result.get('email_result'):
            email_res = result['email_result']
            print(f"\n   Email result:")
            print(f"      - success: {email_res.get('success')}")
            if not email_res.get('success'):
                print(f"      - error: {email_res.get('error')}")

        if result.get('sms_result'):
            sms_res = result['sms_result']
            print(f"\n   SMS result:")
            print(f"      - success: {sms_res.get('success')}")
            if not sms_res.get('success'):
                print(f"      - error: {sms_res.get('error')}")

    else:
        print("\n❌ EMAIL NO SE ENVIÓ")
        print(f"   Razón: {result.get('reason', 'Desconocida')}")
        print(f"   Error: {result.get('error', 'No especificado')}")

except Exception as e:
    print("\n❌ EXCEPCIÓN AL ENVIAR EMAIL:")
    print(f"   Tipo: {type(e).__name__}")
    print(f"   Mensaje: {str(e)}")
    print("\n📋 Stack trace completo:")
    traceback.print_exc()

# ==============================================================================
# TEST 3: Probar componentes individuales
# ==============================================================================
print("\n\n🔬 TEST 3: Probar componentes individuales")
print("-" * 80)

print("\n1️⃣ Verificando template de email...")
try:
    from django.template.loader import render_to_string

    # Obtener datos del primer servicio
    servicio_rs = servicios.first()

    context = {
        'nombre': reserva_test.cliente.nombre,
        'apellido': '',
        'telefono': reserva_test.cliente.telefono,
        'servicio': servicio_rs.servicio.nombre if servicio_rs else 'Servicio',
        'fecha': servicio_rs.fecha_agendamiento.strftime('%d/%m/%Y') if servicio_rs else '',
        'hora': str(servicio_rs.hora_inicio) if servicio_rs else '',
        'numero_reserva': reserva_test.id,
        'servicios': [],
        'total_monto': f"${reserva_test.total:,.0f}",
        'pagado_monto': f"${reserva_test.pagado:,.0f}",
        'saldo_monto': f"${reserva_test.total - reserva_test.pagado:,.0f}",
        'monto_pagado_cero': reserva_test.pagado <= 0,
    }

    html_content = render_to_string('emails/booking_confirmation_email.html', context)
    print("   ✅ Template renderizado correctamente")
    print(f"   Tamaño del HTML: {len(html_content)} bytes")

except Exception as e:
    print(f"   ❌ ERROR al renderizar template: {e}")
    traceback.print_exc()

print("\n2️⃣ Verificando footer de email...")
try:
    from ventas.utils.email_footer import get_email_footer_html

    footer_html = get_email_footer_html(reserva_test.cliente.email)
    print("   ✅ Footer generado correctamente")
    print(f"   Tamaño del footer: {len(footer_html)} bytes")

    # Verificar que el email no sea None
    if not reserva_test.cliente.email:
        print("   ⚠️  ADVERTENCIA: El cliente no tiene email")

except Exception as e:
    print(f"   ❌ ERROR al generar footer: {e}")
    traceback.print_exc()

print("\n3️⃣ Verificando configuración de SendGrid...")
try:
    from django.conf import settings

    email_backend = settings.EMAIL_BACKEND
    print(f"   EMAIL_BACKEND: {email_backend}")

    if 'sendgrid' in email_backend.lower():
        print("   ✅ Usando SendGrid")

        # Verificar API key
        sendgrid_key = os.getenv('SENDGRID_API_KEY', '')
        if sendgrid_key:
            print(f"   ✅ SENDGRID_API_KEY configurada: {sendgrid_key[:10]}...")
        else:
            print("   ❌ SENDGRID_API_KEY NO encontrada")
    elif 'console' in email_backend.lower():
        print("   ⚠️  Usando console backend (emails NO se envían)")
    else:
        print(f"   ℹ️  Backend: {email_backend}")

except Exception as e:
    print(f"   ❌ ERROR verificando configuración: {e}")

print("\n" + "=" * 80)
print("FIN DEL TEST")
print("=" * 80 + "\n")
