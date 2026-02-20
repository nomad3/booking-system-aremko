#!/usr/bin/env python
"""
Diagnóstico completo del sistema de comandas
Ejecutar con: python manage.py shell < diagnostico_comandas_completo.py
"""
import os
import sys
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection
from ventas.models import Comanda, DetalleComanda, VentaReserva, ReservaProducto, Producto
from django.contrib.auth import get_user_model

print("\n" + "=" * 80)
print("DIAGNÓSTICO COMPLETO DEL SISTEMA DE COMANDAS")
print("=" * 80)

# 1. Estado del modelo Comanda
print("\n1. VERIFICANDO MODELO COMANDA")
print("-" * 40)

try:
    # Verificar campos del modelo
    fields = Comanda._meta.get_fields()
    print(f"✓ Campos del modelo Comanda: {len(fields)}")
    for field in fields:
        print(f"  - {field.name}: {field.get_internal_type()}")
except Exception as e:
    print(f"✗ Error verificando modelo: {e}")

# 2. Verificar propiedades
print("\n2. VERIFICANDO PROPIEDADES DE COMANDA")
print("-" * 40)

try:
    # Crear una comanda de prueba en memoria
    comanda_test = Comanda()
    properties_to_test = ['total_items', 'total_precio', 'lugar_entrega', 'es_urgente']

    for prop in properties_to_test:
        try:
            value = getattr(comanda_test, prop, 'NO EXISTE')
            print(f"✓ {prop}: {value}")
        except Exception as e:
            print(f"✗ {prop}: Error - {e}")
except Exception as e:
    print(f"✗ Error creando comanda de prueba: {e}")

# 3. Estadísticas de comandas existentes
print("\n3. ESTADÍSTICAS DE COMANDAS")
print("-" * 40)

try:
    total_comandas = Comanda.objects.count()
    print(f"Total de comandas en BD: {total_comandas}")

    if total_comandas > 0:
        # Por estado
        for estado in ['pendiente', 'procesando', 'entregada', 'cancelada']:
            count = Comanda.objects.filter(estado=estado).count()
            print(f"  - {estado}: {count}")

        # Comandas recientes
        from django.utils import timezone
        hoy = timezone.now().date()
        comandas_hoy = Comanda.objects.filter(fecha_solicitud__date=hoy).count()
        print(f"\nComandas de hoy: {comandas_hoy}")

        # Última comanda
        ultima = Comanda.objects.order_by('-fecha_solicitud').first()
        if ultima:
            print(f"\nÚltima comanda:")
            print(f"  ID: {ultima.id}")
            print(f"  Fecha: {ultima.fecha_solicitud}")
            print(f"  Estado: {ultima.estado}")
            print(f"  VentaReserva ID: {ultima.venta_reserva_id if ultima.venta_reserva else 'Sin reserva'}")
except Exception as e:
    print(f"✗ Error obteniendo estadísticas: {e}")

# 4. Verificar relación con VentaReserva
print("\n4. RELACIÓN COMANDA-VENTARESERVA")
print("-" * 40)

try:
    # Comandas sin VentaReserva
    sin_reserva = Comanda.objects.filter(venta_reserva__isnull=True).count()
    print(f"Comandas sin VentaReserva asociada: {sin_reserva}")

    # VentaReservas con comandas
    from django.db.models import Count
    reservas_con_comandas = VentaReserva.objects.annotate(
        num_comandas=Count('comandas')
    ).filter(num_comandas__gt=0).count()
    print(f"VentaReservas con comandas: {reservas_con_comandas}")
except Exception as e:
    print(f"✗ Error verificando relaciones: {e}")

# 5. Verificar DetalleComanda
print("\n5. VERIFICANDO DETALLES DE COMANDA")
print("-" * 40)

try:
    total_detalles = DetalleComanda.objects.count()
    print(f"Total de DetalleComanda en BD: {total_detalles}")

    # Verificar integridad
    detalles_sin_producto = DetalleComanda.objects.filter(producto__isnull=True).count()
    print(f"Detalles sin producto: {detalles_sin_producto}")

    detalles_sin_comanda = DetalleComanda.objects.filter(comanda__isnull=True).count()
    print(f"Detalles sin comanda: {detalles_sin_comanda}")
except Exception as e:
    print(f"✗ Error verificando detalles: {e}")

# 6. Verificar inventario y productos
print("\n6. VERIFICANDO INVENTARIO")
print("-" * 40)

try:
    # Productos con stock
    productos = Producto.objects.filter(publicado_web=True).order_by('stock')[:5]
    print("Productos con menor stock:")
    for prod in productos:
        print(f"  - {prod.nombre}: Stock={prod.stock}, Precio=${prod.precio}")

    # Productos sin stock
    sin_stock = Producto.objects.filter(stock=0, publicado_web=True).count()
    print(f"\nProductos publicados sin stock: {sin_stock}")
except Exception as e:
    print(f"✗ Error verificando inventario: {e}")

# 7. Probar creación de comanda
print("\n7. PRUEBA DE CREACIÓN DE COMANDA")
print("-" * 40)

try:
    # Buscar una reserva reciente para prueba
    reserva_prueba = VentaReserva.objects.filter(
        fecha__date=timezone.now().date()
    ).first()

    if reserva_prueba:
        print(f"Usando reserva {reserva_prueba.id} para prueba")

        # Intentar crear comanda
        try:
            comanda_nueva = Comanda(
                venta_reserva=reserva_prueba,
                usuario_solicita=reserva_prueba.usuario,
                estado='pendiente',
                notas='Comanda de prueba diagnóstico'
            )
            # No guardamos, solo verificamos que se puede crear
            print("✓ Comanda se puede crear en memoria")

            # Verificar propiedades
            for prop in ['total_items', 'total_precio', 'lugar_entrega', 'es_urgente']:
                try:
                    value = getattr(comanda_nueva, prop)
                    print(f"  {prop}: {value}")
                except Exception as e:
                    print(f"  {prop}: ERROR - {e}")

        except Exception as e:
            print(f"✗ Error creando comanda: {e}")
    else:
        print("No hay reservas de hoy para prueba")

except Exception as e:
    print(f"✗ Error en prueba de creación: {e}")

# 8. Verificar signals
print("\n8. VERIFICANDO SIGNALS")
print("-" * 40)

try:
    from django.db.models import signals
    from ventas import signals as ventas_signals

    print("Signals registrados en ventas:")
    # Intentar listar signals (esto es aproximado)
    print("✓ Módulo de signals importado correctamente")

    # Verificar si existe el signal actualizar_inventario
    if hasattr(ventas_signals, 'actualizar_inventario'):
        print("✓ Signal actualizar_inventario existe")
    else:
        print("✗ Signal actualizar_inventario NO encontrado")

except Exception as e:
    print(f"✗ Error verificando signals: {e}")

# 9. Verificar configuración del admin
print("\n9. VERIFICANDO CONFIGURACIÓN ADMIN")
print("-" * 40)

try:
    from ventas.admin import VentaReservaAdmin

    # Verificar inlines
    inlines = getattr(VentaReservaAdmin, 'inlines', [])
    print(f"Inlines en VentaReservaAdmin: {len(inlines)}")
    for inline in inlines:
        print(f"  - {inline.__name__}")

    # Verificar si ComandaInline está deshabilitado
    inline_names = [inline.__name__ for inline in inlines]
    if 'ComandaInline' in inline_names:
        print("⚠ ComandaInline ESTÁ habilitado")
    else:
        print("ℹ ComandaInline está deshabilitado")

except Exception as e:
    print(f"✗ Error verificando admin: {e}")

# 10. Resumen y recomendaciones
print("\n" + "=" * 80)
print("RESUMEN Y RECOMENDACIONES")
print("=" * 80)

print("\nPROBLEMAS IDENTIFICADOS:")
print("-" * 40)

# Analizar resultados
problemas = []

if sin_stock > 0:
    problemas.append(f"- Hay {sin_stock} productos publicados sin stock")

if detalles_sin_producto > 0:
    problemas.append(f"- Hay {detalles_sin_producto} detalles sin producto asociado")

if sin_reserva > 0:
    problemas.append(f"- Hay {sin_reserva} comandas sin reserva asociada")

if not problemas:
    print("✓ No se encontraron problemas estructurales graves")
else:
    for problema in problemas:
        print(problema)

print("\nRECOMENDACIONES:")
print("-" * 40)
print("1. Verificar el comportamiento del signal actualizar_inventario")
print("2. Considerar re-habilitar ComandaInline cuando se solucione el inventario")
print("3. Implementar las propiedades de Comanda correctamente:")
print("   - total_items: debe calcular sum de cantidades en detalles")
print("   - total_precio: debe calcular sum de subtotales en detalles")
print("   - lugar_entrega: lógica según tipo de reserva")
print("   - es_urgente: lógica según tiempo o flag")

print("\n" + "=" * 80)