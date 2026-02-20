#!/usr/bin/env python
"""
Script para probar creación de comanda con producto sin stock
Ejecutar con: python manage.py shell < test_comanda_sin_stock.py
"""

import os
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import transaction
from ventas.models import Comanda, DetalleComanda, VentaReserva, Producto, ReservaProducto

print("\n=== TEST DE COMANDA CON PRODUCTO SIN STOCK ===\n")

# 1. Buscar producto sin stock o con stock bajo
print("1. Buscando productos para test...")
producto_sin_stock = Producto.objects.filter(cantidad_disponible__lte=0).first()
producto_con_stock = Producto.objects.filter(cantidad_disponible__gt=10).first()

if producto_sin_stock:
    print(f"  ✓ Producto SIN stock: {producto_sin_stock.nombre} (disponible: {producto_sin_stock.cantidad_disponible})")
else:
    print("  ✗ No hay productos sin stock en el sistema")

if producto_con_stock:
    print(f"  ✓ Producto CON stock: {producto_con_stock.nombre} (disponible: {producto_con_stock.cantidad_disponible})")

# 2. Obtener datos para la prueba
reserva = VentaReserva.objects.first()
usuario = User.objects.filter(username='Deborah').first() or User.objects.first()

print(f"\n2. Datos de prueba:")
print(f"  - Reserva ID: {reserva.id}")
print(f"  - Usuario: {usuario.username}")

# 3. Probar con producto CON stock
if producto_con_stock:
    print(f"\n3. Test con producto CON stock ({producto_con_stock.nombre})...")
    try:
        with transaction.atomic():
            # Crear comanda
            comanda = Comanda.objects.create(
                venta_reserva=reserva,
                estado='pendiente',
                notas_generales='Test con stock',
                usuario_solicita=usuario,
                fecha_entrega_objetivo=datetime.now() + timedelta(hours=1)
            )

            # Crear detalle
            detalle = DetalleComanda.objects.create(
                comanda=comanda,
                producto=producto_con_stock,
                cantidad=1,
                precio_unitario=producto_con_stock.precio_base
            )

            # Simular save_formset
            comanda._from_admin = True
            comanda._is_new_from_admin = True

            # Crear ReservaProducto
            rp = ReservaProducto.objects.create(
                venta_reserva=comanda.venta_reserva,
                producto=detalle.producto,
                cantidad=detalle.cantidad,
                precio_unitario_venta=detalle.precio_unitario,
                fecha_entrega=datetime.now().date()
            )

            print(f"  ✓ ÉXITO: Comanda creada con producto CON stock")

            # Limpiar
            raise Exception("Rollback test con stock")

    except Exception as e:
        if "Rollback" not in str(e):
            print(f"  ✗ ERROR: {e}")

# 4. Probar con producto SIN stock
if producto_sin_stock:
    print(f"\n4. Test con producto SIN stock ({producto_sin_stock.nombre})...")
    try:
        with transaction.atomic():
            # Crear comanda
            comanda = Comanda.objects.create(
                venta_reserva=reserva,
                estado='pendiente',
                notas_generales='Test sin stock',
                usuario_solicita=usuario,
                fecha_entrega_objetivo=datetime.now() + timedelta(hours=1)
            )

            # Crear detalle
            detalle = DetalleComanda.objects.create(
                comanda=comanda,
                producto=producto_sin_stock,
                cantidad=1,
                precio_unitario=producto_sin_stock.precio_base
            )

            # Simular save_formset
            comanda._from_admin = True
            comanda._is_new_from_admin = True

            print(f"  Intentando crear ReservaProducto con producto sin stock...")

            # Aquí debería fallar
            rp = ReservaProducto.objects.create(
                venta_reserva=comanda.venta_reserva,
                producto=detalle.producto,
                cantidad=detalle.cantidad,
                precio_unitario_venta=detalle.precio_unitario,
                fecha_entrega=datetime.now().date()
            )

            print(f"  ✓ ReservaProducto creado (pero no debería actualizar inventario)")

            # Limpiar
            raise Exception("Rollback test sin stock")

    except ValueError as e:
        if "No hay suficiente inventario" in str(e):
            print(f"  ✗ ERROR ESPERADO: {e}")
            print(f"  → Este es el error que causa el problema en el admin")
        else:
            print(f"  ✗ ERROR INESPERADO: {e}")
    except Exception as e:
        if "Rollback" not in str(e):
            print(f"  ✗ ERROR: {type(e).__name__}: {e}")

# 5. Verificar comportamiento de la señal
print(f"\n5. Verificando si la señal detiene el proceso...")

# Desactivar temporalmente la señal para probar
from django.db.models.signals import post_save
from ventas.signals.main_signals import actualizar_inventario

# Desconectar la señal
post_save.disconnect(actualizar_inventario, sender=ReservaProducto)

if producto_sin_stock:
    try:
        with transaction.atomic():
            print(f"  Probando SIN la señal de inventario...")

            # Crear comanda y ReservaProducto sin la señal
            comanda = Comanda.objects.create(
                venta_reserva=reserva,
                estado='pendiente',
                notas_generales='Test sin señal',
                usuario_solicita=usuario,
                fecha_entrega_objetivo=datetime.now() + timedelta(hours=1)
            )

            rp = ReservaProducto.objects.create(
                venta_reserva=reserva,
                producto=producto_sin_stock,
                cantidad=1,
                precio_unitario_venta=producto_sin_stock.precio_base,
                fecha_entrega=datetime.now().date()
            )

            print(f"  ✓ SIN la señal, ReservaProducto se crea correctamente")

            # Rollback
            raise Exception("Rollback test sin señal")

    except Exception as e:
        if "Rollback" not in str(e):
            print(f"  ✗ ERROR: {e}")

# Reconectar la señal
post_save.connect(actualizar_inventario, sender=ReservaProducto)

print("\n=== CONCLUSIÓN ===")
print("\nEl error ocurre porque:")
print("1. La señal 'actualizar_inventario' intenta reducir el inventario")
print("2. Si no hay stock suficiente, lanza ValueError")
print("3. Esto causa el Error 500 en el admin")
print("\nPOSIBLES SOLUCIONES:")
print("- Validar stock ANTES de crear la comanda")
print("- Hacer que la reducción de inventario sea opcional")
print("- Mostrar advertencia en lugar de error")
print("\n=== FIN DEL TEST ===\n")