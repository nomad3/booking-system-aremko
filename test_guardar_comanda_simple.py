#!/usr/bin/env python
"""
Script simple para probar el guardado de comandas
Ejecutar con: python manage.py shell < test_guardar_comanda_simple.py
"""

import os
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.contrib.auth.models import User
from ventas.models import Comanda, DetalleComanda, VentaReserva, Producto, ReservaProducto

print("\n=== TEST SIMPLE DE GUARDADO DE COMANDAS ===\n")

try:
    # 1. Obtener datos básicos
    print("1. Obteniendo datos...")
    reserva = VentaReserva.objects.first()
    usuario = User.objects.filter(username__in=['Deborah', 'Ernesto']).first() or User.objects.first()
    producto = Producto.objects.filter(disponible=True).first() or Producto.objects.first()

    if not all([reserva, usuario, producto]):
        print("ERROR: Faltan datos básicos")
        print(f"  Reserva: {reserva}")
        print(f"  Usuario: {usuario}")
        print(f"  Producto: {producto}")
        exit()

    print(f"  ✓ Reserva ID: {reserva.id}")
    print(f"  ✓ Usuario: {usuario.username}")
    print(f"  ✓ Producto: {producto.nombre}")

    # 2. Crear comanda
    print("\n2. Creando comanda...")
    comanda = Comanda(
        venta_reserva=reserva,
        estado='pendiente',
        notas_generales='Test simple',
        usuario_solicita=usuario,
        fecha_entrega_objetivo=datetime.now() + timedelta(hours=1)
    )
    comanda._from_admin = True
    comanda._is_new_from_admin = True

    comanda.save()
    print(f"  ✓ Comanda creada ID: {comanda.id}")

    # 3. Crear detalle
    print("\n3. Creando detalle...")
    detalle = DetalleComanda(
        comanda=comanda,
        producto=producto,
        cantidad=1,
        precio_unitario=producto.precio_base
    )
    detalle.save()
    print(f"  ✓ Detalle creado")

    # 4. Verificar ReservaProducto
    print("\n4. Verificando ReservaProducto...")

    # Simular lo que hace save_formset
    fecha_entrega = comanda.fecha_entrega_objetivo.date() if comanda.fecha_entrega_objetivo else datetime.now().date()

    print(f"  Intentando crear ReservaProducto:")
    print(f"    - venta_reserva_id: {comanda.venta_reserva.id}")
    print(f"    - producto_id: {detalle.producto.id}")
    print(f"    - cantidad: {detalle.cantidad}")
    print(f"    - precio: {detalle.precio_unitario}")
    print(f"    - fecha_entrega: {fecha_entrega}")

    rp, created = ReservaProducto.objects.get_or_create(
        venta_reserva=comanda.venta_reserva,
        producto=detalle.producto,
        defaults={
            'cantidad': detalle.cantidad,
            'precio_unitario_venta': detalle.precio_unitario,
            'fecha_entrega': fecha_entrega
        }
    )

    if created:
        print(f"  ✓ ReservaProducto CREADO - ID: {rp.id}")
    else:
        print(f"  → ReservaProducto YA EXISTÍA - ID: {rp.id}")

    print("\n✓ TEST COMPLETADO EXITOSAMENTE")

    # Limpiar datos de prueba
    print("\n5. Limpiando datos de prueba...")
    if created:
        rp.delete()
    detalle.delete()
    comanda.delete()
    print("  ✓ Datos de prueba eliminados")

except Exception as e:
    print(f"\n✗ ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n=== FIN DEL TEST ===\n")