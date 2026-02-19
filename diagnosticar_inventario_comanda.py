#!/usr/bin/env python
"""
Script para diagnosticar problemas de inventario al crear comandas
Ejecutar con: python manage.py shell < diagnosticar_inventario_comanda.py
"""

import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection
from ventas.models import Producto, ReservaProducto, Comanda, DetalleComanda

print("\n" + "=" * 80)
print("DIAGNÓSTICO DE INVENTARIO Y COMANDAS")
print("=" * 80)
print(f"Fecha/Hora: {datetime.now()}")
print()

# 1. Verificar si existe campo de inventario
print("1. VERIFICANDO CAMPOS DE INVENTARIO EN PRODUCTO")
print("-" * 40)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'ventas_producto'
        AND column_name LIKE '%inventario%' OR column_name LIKE '%stock%' OR column_name LIKE '%cantidad%'
        ORDER BY ordinal_position
    """)

    campos_inventario = cursor.fetchall()
    if campos_inventario:
        for campo in campos_inventario:
            print(f"  - {campo[0]}: {campo[1]} (null: {campo[2]})")
    else:
        print("  No se encontraron campos de inventario/stock")

# 2. Verificar productos con problemas
print("\n\n2. PRODUCTOS CON INVENTARIO BAJO/AGOTADO")
print("-" * 40)

# Buscar productos y su inventario
productos_problematicos = []
for producto in Producto.objects.all()[:20]:  # Primeros 20 productos
    cantidad_disp = getattr(producto, 'cantidad_disponible', None)
    if cantidad_disp is not None:
        if cantidad_disp <= 0:
            productos_problematicos.append((producto, cantidad_disp, "AGOTADO"))
        elif cantidad_disp < 5:
            productos_problematicos.append((producto, cantidad_disp, "BAJO"))

if productos_problematicos:
    print(f"Productos con problemas de inventario: {len(productos_problematicos)}")
    for prod, cant, estado in productos_problematicos[:10]:
        print(f"  - {prod.nombre}: {cant} unidades ({estado})")
else:
    print("  No se encontraron productos con inventario bajo")

# 3. Buscar señales relacionadas
print("\n\n3. VERIFICANDO SEÑALES DE INVENTARIO")
print("-" * 40)

# Buscar archivos de signals
import os
signals_dir = "/app/ventas/signals"
if os.path.exists(signals_dir):
    print(f"Directorio de signals encontrado: {signals_dir}")
    for file in os.listdir(signals_dir):
        if file.endswith('.py'):
            print(f"  - {file}")
else:
    print("  Directorio de signals no encontrado")

# 4. Productos más usados en comandas recientes
print("\n\n4. PRODUCTOS MÁS USADOS EN COMANDAS")
print("-" * 40)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            p.id,
            p.nombre,
            p.cantidad_disponible,
            COUNT(dc.id) as veces_pedido,
            SUM(dc.cantidad) as total_pedido
        FROM ventas_producto p
        INNER JOIN ventas_detallecomanda dc ON p.id = dc.producto_id
        INNER JOIN ventas_comanda c ON dc.comanda_id = c.id
        WHERE c.fecha_solicitud >= NOW() - INTERVAL '7 days'
        GROUP BY p.id, p.nombre, p.cantidad_disponible
        ORDER BY total_pedido DESC
        LIMIT 10
    """)

    productos_populares = cursor.fetchall()
    if productos_populares:
        print("Producto | Inventario | Veces Pedido | Total Pedido")
        print("-" * 60)
        for row in productos_populares:
            print(f"{row[1][:30]:30} | {row[2]:10} | {row[3]:12} | {row[4]:11}")
    else:
        print("  No hay datos de productos en comandas recientes")

# 5. Verificar configuración de actualización de inventario
print("\n\n5. VERIFICANDO SI HAY ACTUALIZACIÓN AUTOMÁTICA DE INVENTARIO")
print("-" * 40)

# Intentar importar señales
try:
    from ventas.signals.main_signals import actualizar_inventario
    print("✓ Señal 'actualizar_inventario' encontrada")

    # Ver si está conectada
    from django.db.models.signals import post_save, post_delete

    print("\nSeñales conectadas a ReservaProducto:")
    if hasattr(post_save, '_live_receivers'):
        for receiver in post_save._live_receivers:
            if 'ReservaProducto' in str(receiver):
                print(f"  - post_save: {receiver}")

    if hasattr(post_delete, '_live_receivers'):
        for receiver in post_delete._live_receivers:
            if 'ReservaProducto' in str(receiver):
                print(f"  - post_delete: {receiver}")

except ImportError:
    print("✗ No se pudo importar la señal 'actualizar_inventario'")

# 6. Simular creación con diferentes productos
print("\n\n6. PROBANDO CREACIÓN CON DIFERENTES PRODUCTOS")
print("-" * 40)

# Producto con inventario disponible
producto_con_stock = Producto.objects.filter(
    cantidad_disponible__gt=10
).first()

# Producto sin inventario
producto_sin_stock = Producto.objects.filter(
    cantidad_disponible__lte=0
).first()

if producto_con_stock:
    print(f"✓ Producto CON stock: {producto_con_stock.nombre} ({producto_con_stock.cantidad_disponible} unidades)")

if producto_sin_stock:
    print(f"✓ Producto SIN stock: {producto_sin_stock.nombre} ({producto_sin_stock.cantidad_disponible} unidades)")

# 7. Verificar si el error es solo warning o detiene el proceso
print("\n\n7. CONFIGURACIÓN DE MANEJO DE ERRORES")
print("-" * 40)

try:
    from django.conf import settings

    # Verificar DEBUG
    print(f"DEBUG: {settings.DEBUG}")

    # Verificar si hay configuración específica para inventario
    inventario_config = getattr(settings, 'INVENTARIO_CONFIG', None)
    if inventario_config:
        print(f"INVENTARIO_CONFIG: {inventario_config}")
    else:
        print("No hay INVENTARIO_CONFIG definido")

    # Verificar si hay validación estricta
    validacion_estricta = getattr(settings, 'VALIDAR_INVENTARIO_ESTRICTO', None)
    if validacion_estricta is not None:
        print(f"VALIDAR_INVENTARIO_ESTRICTO: {validacion_estricta}")
    else:
        print("No hay configuración de validación estricta")

except Exception as e:
    print(f"Error verificando configuración: {e}")

print("\n" + "=" * 80)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 80)