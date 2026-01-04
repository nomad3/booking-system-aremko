#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para el error 500 en registrar_pago de masajistas
"""

import os
import sys
import django
import traceback

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'booking_system.settings')
django.setup()

from ventas.models import Proveedor, ReservaServicio
from decimal import Decimal

print("=" * 80)
print("DIAGNÓSTICO DE ERROR EN PAGOS A MASAJISTAS")
print("=" * 80)

masajista_id = 3

print(f"\n1. Verificando que el proveedor ID={masajista_id} existe...")
try:
    masajista = Proveedor.objects.get(id=masajista_id)
    print(f"✅ Proveedor encontrado: {masajista.nombre}")
except Proveedor.DoesNotExist:
    print(f"❌ ERROR: No existe proveedor con ID={masajista_id}")
    sys.exit(1)

print(f"\n2. Información del proveedor:")
print(f"   - ID: {masajista.id}")
print(f"   - Nombre: {masajista.nombre}")
print(f"   - Email: {masajista.email}")
print(f"   - Teléfono: {masajista.telefono}")
print(f"   - Es masajista: {masajista.es_masajista}")
print(f"   - Porcentaje comisión: {masajista.porcentaje_comision}%")
print(f"   - RUT: {masajista.rut}")
print(f"   - Banco: {masajista.banco}")
print(f"   - Tipo cuenta: {masajista.tipo_cuenta}")
print(f"   - Número cuenta: {masajista.numero_cuenta}")

print(f"\n3. Verificando método get_servicios_pendientes_pago()...")
try:
    servicios = masajista.get_servicios_pendientes_pago()
    print(f"✅ Método ejecutado correctamente")
    print(f"   - Servicios pendientes: {servicios.count()}")
except Exception as e:
    print(f"❌ ERROR al ejecutar get_servicios_pendientes_pago():")
    print(f"   {type(e).__name__}: {str(e)}")
    traceback.print_exc()
    sys.exit(1)

print(f"\n4. Intentando optimizar con select_related...")
try:
    servicios_optimizados = masajista.get_servicios_pendientes_pago().select_related(
        'servicio',
        'venta_reserva',
        'venta_reserva__cliente'
    )
    print(f"✅ Query optimizado correctamente")
    print(f"   - Servicios con select_related: {servicios_optimizados.count()}")
except Exception as e:
    print(f"❌ ERROR al optimizar query:")
    print(f"   {type(e).__name__}: {str(e)}")
    traceback.print_exc()
    sys.exit(1)

print(f"\n5. Procesando cada servicio (simulando la vista)...")
try:
    servicios_con_montos = []
    total_bruto = Decimal('0')
    total_neto = Decimal('0')

    for i, servicio in enumerate(servicios_optimizados[:5], 1):  # Solo primeros 5 para diagnóstico
        print(f"\n   Servicio {i}:")
        print(f"   - ID: {servicio.id}")
        print(f"   - Servicio: {servicio.servicio.nombre}")
        print(f"   - Fecha: {servicio.fecha_agendamiento}")

        try:
            precio_servicio = servicio.calcular_precio()
            print(f"   - Precio calculado: ${precio_servicio:,.0f}")
        except Exception as e:
            print(f"   ❌ ERROR al calcular precio: {e}")
            traceback.print_exc()
            continue

        try:
            monto_masajista = precio_servicio * (masajista.porcentaje_comision / 100)
            print(f"   - Monto masajista: ${monto_masajista:,.0f}")
        except Exception as e:
            print(f"   ❌ ERROR al calcular monto masajista: {e}")
            traceback.print_exc()
            continue

        try:
            monto_retencion = monto_masajista * Decimal('0.145')
            monto_neto = monto_masajista - monto_retencion
            print(f"   - Retención: ${monto_retencion:,.0f}")
            print(f"   - Monto neto: ${monto_neto:,.0f}")
        except Exception as e:
            print(f"   ❌ ERROR al calcular retención: {e}")
            traceback.print_exc()
            continue

        try:
            cliente = servicio.venta_reserva.cliente
            print(f"   - Cliente: {cliente.nombre}")
        except Exception as e:
            print(f"   ❌ ERROR al obtener cliente: {e}")
            traceback.print_exc()
            continue

        servicios_con_montos.append({
            'servicio': servicio,
            'precio_servicio': precio_servicio,
            'monto_masajista': monto_masajista,
            'monto_neto': monto_neto,
        })

        total_bruto += monto_masajista
        total_neto += monto_neto

    print(f"\n   ✅ Procesados {len(servicios_con_montos)} servicios exitosamente")
    print(f"   - Total bruto: ${total_bruto:,.0f}")
    print(f"   - Total neto: ${total_neto:,.0f}")

except Exception as e:
    print(f"\n❌ ERROR durante el procesamiento:")
    print(f"   {type(e).__name__}: {str(e)}")
    traceback.print_exc()
    sys.exit(1)

print(f"\n6. Verificando atributos necesarios para el template...")
try:
    context = {
        'masajista': masajista,
        'servicios': servicios_con_montos,
        'total_bruto': total_bruto,
        'total_retencion': total_bruto * Decimal('0.145'),
        'total_neto': total_neto,
    }
    print(f"✅ Contexto creado correctamente:")
    print(f"   - Masajista: {context['masajista']}")
    print(f"   - Servicios: {len(context['servicios'])} items")
    print(f"   - Total bruto: ${context['total_bruto']:,.0f}")
    print(f"   - Total retención: ${context['total_retencion']:,.0f}")
    print(f"   - Total neto: ${context['total_neto']:,.0f}")
except Exception as e:
    print(f"❌ ERROR al crear contexto:")
    print(f"   {type(e).__name__}: {str(e)}")
    traceback.print_exc()
    sys.exit(1)

print(f"\n7. Verificando relación reservas_asignadas (related_name)...")
try:
    # Verificar que existe el related_name
    reservas = masajista.reservas_asignadas.all()
    print(f"✅ Related name 'reservas_asignadas' funciona correctamente")
    print(f"   - Total reservas asignadas: {reservas.count()}")
except AttributeError as e:
    print(f"❌ ERROR: El related_name 'reservas_asignadas' no existe")
    print(f"   {str(e)}")
    traceback.print_exc()
except Exception as e:
    print(f"❌ ERROR al acceder a reservas_asignadas:")
    print(f"   {type(e).__name__}: {str(e)}")
    traceback.print_exc()

print(f"\n8. Verificando query SQL generado...")
try:
    query = masajista.get_servicios_pendientes_pago().select_related(
        'servicio',
        'venta_reserva',
        'venta_reserva__cliente'
    ).query
    print(f"✅ Query SQL:")
    print(f"   {query}")
except Exception as e:
    print(f"❌ ERROR al obtener query SQL:")
    print(f"   {type(e).__name__}: {str(e)}")
    traceback.print_exc()

print("\n" + "=" * 80)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 80)
print("\nSi todos los pasos anteriores pasaron ✅, el problema podría estar en:")
print("1. El template registrar_pago.html (error de sintaxis)")
print("2. Middleware o decoradores que interfieren")
print("3. Configuración de URLs")
print("4. Problemas de permisos de usuario")
print("\nSi algún paso falló ❌, el error está en el modelo o la lógica de negocio.")
