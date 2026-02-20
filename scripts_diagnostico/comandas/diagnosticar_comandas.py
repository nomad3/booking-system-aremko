#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para verificar el estado del sistema de comandas.
Verifica los puntos pendientes mencionados en COMANDAS_TROUBLESHOOTING.md
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.contrib.auth.models import User
from ventas.models import Comanda, DetalleComanda, VentaReserva, ReservaProducto, Producto
from django.utils import timezone
from decimal import Decimal

def verificar_usuarios():
    """Verifica que existan los usuarios Deborah y Ernesto"""
    print("\n=== Verificando Usuarios ===")
    try:
        deborah = User.objects.get(username='Deborah')
        print(f"✅ Usuario Deborah existe (ID: {deborah.id})")
    except User.DoesNotExist:
        print("❌ Usuario Deborah NO existe")

    try:
        ernesto = User.objects.get(username='Ernesto')
        print(f"✅ Usuario Ernesto existe (ID: {ernesto.id})")
    except User.DoesNotExist:
        print("❌ Usuario Ernesto NO existe")

def verificar_productos():
    """Verifica que existan productos con precio_base"""
    print("\n=== Verificando Productos ===")
    productos = Producto.objects.all()[:5]
    if not productos:
        print("❌ No hay productos en el sistema")
        return

    print(f"Total de productos: {Producto.objects.count()}")
    print("\nPrimeros 5 productos:")
    for p in productos:
        print(f"  - {p.nombre}: ${p.precio_base}")

def verificar_ventas_reserva():
    """Verifica VentaReservas recientes"""
    print("\n=== Verificando VentaReservas ===")
    reservas = VentaReserva.objects.all().order_by('-id')[:5]
    if not reservas:
        print("❌ No hay VentaReservas en el sistema")
        return

    print(f"Total de VentaReservas: {VentaReserva.objects.count()}")
    print("\nÚltimas 5 VentaReservas:")
    for r in reservas:
        cliente_nombre = r.cliente.nombre if r.cliente else "Sin cliente"
        print(f"  - ID: {r.id}, Cliente: {cliente_nombre}, Estado: {r.estado_reserva}")

def verificar_comandas():
    """Verifica comandas existentes"""
    print("\n=== Verificando Comandas ===")
    comandas = Comanda.objects.all().order_by('-id')[:5]
    if not comandas:
        print("❓ No hay comandas en el sistema (normal si es primera vez)")
        return

    print(f"Total de comandas: {Comanda.objects.count()}")
    print("\nÚltimas 5 comandas:")
    for c in comandas:
        detalles_count = c.detalles.count()
        vr_id = c.venta_reserva.id if c.venta_reserva else "Sin VR"
        print(f"  - ID: {c.id}, VentaReserva: {vr_id}, Estado: {c.estado}, Productos: {detalles_count}")

def probar_creacion_comanda():
    """Prueba crear una comanda programáticamente"""
    print("\n=== Probando Creación de Comanda (Programática) ===")

    # Buscar una VentaReserva y un producto
    vr = VentaReserva.objects.filter(estado_reserva='confirmada').first()
    if not vr:
        print("❌ No hay VentaReservas confirmadas para probar")
        return

    producto = Producto.objects.first()
    if not producto:
        print("❌ No hay productos para probar")
        return

    try:
        # Crear comanda
        comanda = Comanda.objects.create(
            venta_reserva=vr,
            estado='pendiente',
            fecha_entrega_objetivo=timezone.now() + timezone.timedelta(minutes=30),
            notas_generales="Comanda de prueba desde script"
        )
        print(f"✅ Comanda creada: ID {comanda.id}")

        # Crear detalle
        detalle = DetalleComanda.objects.create(
            comanda=comanda,
            producto=producto,
            cantidad=2,
            especificaciones="Extra caliente"
        )
        print(f"✅ DetalleComanda creado: {detalle}")
        print(f"   - Precio unitario: ${detalle.precio_unitario} (debe ser igual a precio_base: ${producto.precio_base})")

        # Verificar ReservaProducto
        rp_exists = ReservaProducto.objects.filter(
            venta_reserva=vr,
            producto=producto
        ).exists()
        if rp_exists:
            print("✅ ReservaProducto creado automáticamente")
        else:
            print("❌ ReservaProducto NO fue creado")

    except Exception as e:
        print(f"❌ Error al crear comanda: {str(e)}")

def verificar_migraciones():
    """Verifica que las migraciones estén aplicadas"""
    print("\n=== Verificando Migraciones ===")
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    call_command('showmigrations', 'ventas', stdout=out)
    migrations_output = out.getvalue()

    # Buscar migraciones de comandas
    comanda_migrations = [
        '0080_comandas_system',
        '0081_comanda_fecha_entrega_objetivo'
    ]

    for migration in comanda_migrations:
        if f'[X] {migration}' in migrations_output:
            print(f"✅ {migration} aplicada")
        else:
            print(f"❌ {migration} NO aplicada")

def main():
    print("=" * 60)
    print("DIAGNÓSTICO DEL SISTEMA DE COMANDAS")
    print("Fecha:", timezone.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    verificar_migraciones()
    verificar_usuarios()
    verificar_productos()
    verificar_ventas_reserva()
    verificar_comandas()

    # Solo probar creación si el usuario lo confirma
    print("\n¿Deseas probar la creación de una comanda de prueba? (s/n): ", end='')
    respuesta = input().strip().lower()
    if respuesta == 's':
        probar_creacion_comanda()

    print("\n" + "=" * 60)
    print("DIAGNÓSTICO COMPLETADO")
    print("=" * 60)

if __name__ == '__main__':
    main()