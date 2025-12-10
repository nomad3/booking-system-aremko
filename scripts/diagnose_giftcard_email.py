#!/usr/bin/env python
"""
Script para diagnosticar por qué no se envían emails de GiftCards
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from ventas.models import GiftCard, VentaReserva, Pago, Cliente
from django.conf import settings

print("=" * 80)
print("DIAGNÓSTICO DE EMAILS DE GIFTCARDS")
print("=" * 80)

# 1. Verificar configuración de email
print("\n📧 1. CONFIGURACIÓN DE EMAIL")
print("-" * 40)
print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', 'No configurado')}")
print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
sendgrid_key = os.getenv('SENDGRID_API_KEY')
print(f"SENDGRID_API_KEY: {'✅ Configurada' if sendgrid_key else '❌ No configurada'}")

# 2. GiftCards recientes
print("\n🎁 2. GIFTCARDS RECIENTES (últimas 24 horas)")
print("-" * 40)
ayer = datetime.now() - timedelta(days=1)
giftcards_recientes = GiftCard.objects.filter(
    fecha_emision__gte=ayer
).order_by('-fecha_emision')

if not giftcards_recientes.exists():
    print("⚠️ No hay GiftCards creadas en las últimas 24 horas")
else:
    for gc in giftcards_recientes:
        print(f"\nCódigo: {gc.codigo}")
        print(f"  Estado: {gc.estado}")
        print(f"  Experiencia: {gc.servicio_asociado}")
        print(f"  Destinatario: {gc.destinatario_nombre}")
        print(f"  Comprador email: {gc.comprador_email}")
        print(f"  Enviado por email: {gc.enviado_email}")
        print(f"  Fecha emisión: {gc.fecha_emision}")

        # Verificar VentaReserva asociada
        if hasattr(gc, 'venta_reserva') and gc.venta_reserva:
            venta = gc.venta_reserva
            print(f"  VentaReserva: #{venta.id}")
            print(f"  Estado pago: {venta.estado_pago}")
            print(f"  Total: ${venta.total_con_descuento}")
            print(f"  Pagado: ${venta.monto_pagado}")

            # Verificar cliente
            if venta.cliente:
                print(f"  Cliente: {venta.cliente.nombre}")
                print(f"  Cliente email: {venta.cliente.email or '❌ Sin email'}")
            else:
                print(f"  ❌ Sin cliente asociado")

            # Verificar pagos
            pagos = venta.pagos.all().order_by('-fecha_pago')
            if pagos.exists():
                print(f"  Pagos registrados: {pagos.count()}")
                for pago in pagos:
                    print(f"    - ${pago.monto} - {pago.metodo} - {pago.fecha_pago}")
            else:
                print(f"  ❌ No hay pagos registrados")
        else:
            print(f"  ❌ Sin VentaReserva asociada")

# 3. Verificar señales
print("\n⚡ 3. VERIFICACIÓN DE SEÑALES")
print("-" * 40)
from django.db.models import signals
from ventas.signals import giftcard_signals

# Verificar que la señal esté conectada
signal_receivers = signals.post_save.receivers
pago_receivers = [r for r in signal_receivers if 'pago' in str(r).lower()]
print(f"Señales post_save conectadas a Pago: {len(pago_receivers)}")
if pago_receivers:
    print("✅ Señal conectada")
else:
    print("❌ Señal NO conectada")

# 4. Buscar GiftCards con problemas
print("\n🔍 4. GIFTCARDS CON POSIBLES PROBLEMAS")
print("-" * 40)

# GiftCards cobradas pero no enviadas
no_enviadas = GiftCard.objects.filter(
    estado='cobrado',
    enviado_email=False
)

if no_enviadas.exists():
    print(f"\n⚠️ {no_enviadas.count()} GiftCards cobradas pero NO enviadas por email:")
    for gc in no_enviadas[:5]:  # Mostrar máximo 5
        print(f"  - {gc.codigo} ({gc.destinatario_nombre}) - {gc.fecha_emision}")
else:
    print("✅ No hay GiftCards cobradas sin enviar")

# GiftCards por cobrar con ventas pagadas
por_cobrar_pagadas = GiftCard.objects.filter(
    estado='por_cobrar',
    venta_reserva__estado_pago__in=['pagado', 'parcial']
)

if por_cobrar_pagadas.exists():
    print(f"\n⚠️ {por_cobrar_pagadas.count()} GiftCards por_cobrar con ventas ya pagadas:")
    for gc in por_cobrar_pagadas[:5]:
        print(f"  - {gc.codigo} - VentaReserva #{gc.venta_reserva.id} ({gc.venta_reserva.estado_pago})")
else:
    print("✅ No hay GiftCards con inconsistencias de estado")

# 5. Sugerencias
print("\n💡 5. SUGERENCIAS")
print("-" * 40)

if not sendgrid_key:
    print("❌ Configurar SENDGRID_API_KEY en variables de entorno")

if no_enviadas.exists():
    print("⚠️ Hay GiftCards que deberían haberse enviado. Posibles causas:")
    print("   - Error en el envío de email (revisar logs)")
    print("   - Señal no se ejecutó correctamente")
    print("   - Email del comprador no válido")

if por_cobrar_pagadas.exists():
    print("⚠️ Hay GiftCards con estado inconsistente")
    print("   - La señal probablemente no se ejecutó")
    print("   - Revisar que las señales estén registradas en apps.py")

print("\n" + "=" * 80)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 80)
