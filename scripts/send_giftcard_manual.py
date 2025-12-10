#!/usr/bin/env python
"""
Script para enviar manualmente el email de una GiftCard cuando la señal no se ejecutó
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from ventas.models import GiftCard, VentaReserva, Pago
from ventas.services.giftcard_pdf_service import GiftCardPDFService
from ventas.signals.giftcard_signals import enviar_email_giftcards
import logging

logger = logging.getLogger(__name__)

print("=" * 80)
print("ENVÍO MANUAL DE GIFTCARD POR EMAIL")
print("=" * 80)

# Verificar VentaReserva #4159
venta_id = 4159
print(f"\n🔍 Buscando VentaReserva #{venta_id}...")

try:
    venta = VentaReserva.objects.get(id=venta_id)
    print(f"✅ VentaReserva encontrada:")
    print(f"   Cliente: {venta.cliente.nombre}")
    print(f"   Email: {venta.cliente.email}")
    print(f"   Total: ${venta.total_con_descuento}")
    print(f"   Estado pago: {venta.estado_pago}")
    print(f"   Monto pagado: ${venta.monto_pagado}")
except VentaReserva.DoesNotExist:
    print(f"❌ VentaReserva #{venta_id} no encontrada")
    sys.exit(1)

# Verificar GiftCards
print(f"\n🎁 Buscando GiftCards asociadas...")
giftcards = venta.giftcards.all()

if not giftcards.exists():
    print("❌ No hay GiftCards asociadas a esta venta")
    sys.exit(1)

print(f"✅ {giftcards.count()} GiftCard(s) encontrada(s):")
for gc in giftcards:
    print(f"   - {gc.codigo} ({gc.estado}) - {gc.destinatario_nombre}")
    print(f"     Email enviado: {gc.enviado_email}")
    print(f"     Experiencia: {gc.servicio_asociado}")

# Verificar pagos
print(f"\n💰 Verificando pagos...")
pagos = venta.pagos.all()

if not pagos.exists():
    print("⚠️ No hay pagos registrados para esta venta")
    print("   Para que se envíe el email automáticamente, debe haber un pago registrado.")
    print("   Puedes:")
    print("   1. Crear un pago manualmente en el admin de Django")
    print("   2. O continuar con este script para enviar el email manualmente")
else:
    print(f"✅ {pagos.count()} pago(s) registrado(s):")
    for pago in pagos:
        print(f"   - ${pago.monto} - {pago.metodo} - {pago.fecha_pago}")

# Preguntar si quiere enviar el email
print("\n" + "=" * 80)
respuesta = input("¿Deseas enviar el email de GiftCard manualmente? (s/n): ")

if respuesta.lower() != 's':
    print("❌ Operación cancelada")
    sys.exit(0)

# Cambiar estado de las GiftCards si están en 'por_cobrar'
giftcards_pendientes = giftcards.filter(estado='por_cobrar')
if giftcards_pendientes.exists():
    print(f"\n📝 Cambiando estado de {giftcards_pendientes.count()} GiftCard(s) a 'cobrado'...")
    for gc in giftcards_pendientes:
        gc.estado = 'cobrado'
        gc.save()
        print(f"   ✅ {gc.codigo} → cobrado")

# Enviar email
print(f"\n📧 Enviando email...")
try:
    enviar_email_giftcards(venta, list(giftcards))
    print("✅ Email enviado exitosamente")
    print(f"   Destinatario: {venta.cliente.email}")
    print(f"   GiftCards incluidas: {giftcards.count()}")
except Exception as e:
    print(f"❌ Error al enviar email: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("PROCESO COMPLETADO")
print("=" * 80)
