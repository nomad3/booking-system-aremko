#!/usr/bin/env python
"""
Script de diagnóstico para problemas al guardar comandas
Ejecutar con: python manage.py shell < diagnosticar_comanda_guardado.py
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import connection, transaction
from ventas.models import (
    Comanda, DetalleComanda, VentaReserva,
    Producto, ReservaProducto, Cliente
)

print("=" * 80)
print("DIAGNÓSTICO DE PROBLEMAS AL GUARDAR COMANDAS")
print("=" * 80)
print(f"Fecha/Hora: {datetime.now()}")
print()

# 1. Verificar estructura de tablas
print("1. VERIFICANDO ESTRUCTURA DE TABLAS")
print("-" * 40)

with connection.cursor() as cursor:
    # Verificar tabla comandas
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'ventas_comanda'
        ORDER BY ordinal_position
    """)
    print("\nTabla ventas_comanda:")
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]} (null: {row[2]})")

    # Verificar tabla detalles
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'ventas_detallecomanda'
        ORDER BY ordinal_position
    """)
    print("\nTabla ventas_detallecomanda:")
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]} (null: {row[2]})")

    # Verificar tabla reserva_producto
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'ventas_reservaproducto'
        ORDER BY ordinal_position
    """)
    print("\nTabla ventas_reservaproducto:")
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]} (null: {row[2]})")

# 2. Verificar comandas existentes
print("\n\n2. VERIFICANDO COMANDAS EXISTENTES")
print("-" * 40)

comandas_count = Comanda.objects.count()
print(f"Total de comandas: {comandas_count}")

if comandas_count > 0:
    print("\nÚltimas 5 comandas:")
    for comanda in Comanda.objects.order_by('-id')[:5]:
        print(f"  - ID: {comanda.id}")
        print(f"    Reserva: {comanda.venta_reserva_id}")
        print(f"    Estado: {comanda.estado}")
        print(f"    Fecha: {comanda.fecha_solicitud}")
        print(f"    Detalles: {comanda.detalles.count()} items")

# 3. Verificar usuarios del sistema
print("\n\n3. VERIFICANDO USUARIOS PARA COMANDAS")
print("-" * 40)

usuarios_comandas = ['Deborah', 'Ernesto', 'deborah', 'ernesto']
for username in usuarios_comandas:
    try:
        user = User.objects.get(username=username)
        print(f"✓ Usuario '{username}' encontrado (ID: {user.id})")
    except User.DoesNotExist:
        print(f"✗ Usuario '{username}' NO encontrado")

# 4. Simular creación de comanda
print("\n\n4. SIMULANDO CREACIÓN DE COMANDA")
print("-" * 40)

# Buscar una reserva de prueba
try:
    reserva = VentaReserva.objects.filter(estado_reserva='confirmada').first()
    if not reserva:
        reserva = VentaReserva.objects.first()

    if reserva:
        print(f"Usando reserva ID: {reserva.id} - Cliente: {reserva.cliente}")

        # Buscar productos para la comanda
        productos = Producto.objects.filter(disponible=True)[:3]
        if not productos:
            productos = Producto.objects.all()[:3]

        print(f"\nProductos disponibles: {productos.count()}")
        for prod in productos[:3]:
            print(f"  - {prod.nombre} (${prod.precio_base})")

        # Intentar crear comanda
        print("\nIntentando crear comanda...")
        try:
            with transaction.atomic():
                # Crear comanda
                comanda = Comanda(
                    venta_reserva=reserva,
                    estado='pendiente',
                    notas_generales='Comanda de prueba - diagnóstico',
                    usuario_solicita=User.objects.filter(is_superuser=True).first(),
                    fecha_entrega_objetivo=datetime.now() + timedelta(hours=1)
                )
                comanda._from_admin = False  # Simular creación programática
                comanda.save()
                print(f"✓ Comanda creada con ID: {comanda.id}")

                # Crear detalles
                for i, prod in enumerate(productos[:2]):
                    detalle = DetalleComanda(
                        comanda=comanda,
                        producto=prod,
                        cantidad=i + 1,
                        precio_unitario=prod.precio_base,
                        especificaciones=f"Prueba {i+1}"
                    )
                    detalle.save()
                    print(f"✓ Detalle creado: {detalle}")

                # Verificar ReservaProducto
                print("\nVerificando ReservaProducto creados:")
                reserva_productos = ReservaProducto.objects.filter(
                    venta_reserva=reserva
                ).order_by('-id')[:5]

                for rp in reserva_productos:
                    print(f"  - Producto: {rp.producto.nombre}")
                    print(f"    Cantidad: {rp.cantidad}")
                    print(f"    Precio: ${rp.precio_unitario_venta}")

                # Revertir cambios (solo prueba)
                raise Exception("Prueba completada - revirtiendo cambios")

        except Exception as e:
            if "Prueba completada" in str(e):
                print("\n✓ Prueba completada exitosamente")
            else:
                print(f"\n✗ ERROR al crear comanda: {e}")
                import traceback
                traceback.print_exc()
    else:
        print("✗ No se encontraron reservas para prueba")

except Exception as e:
    print(f"✗ Error en la simulación: {e}")
    import traceback
    traceback.print_exc()

# 5. Verificar configuración del admin
print("\n\n5. VERIFICANDO CONFIGURACIÓN DEL ADMIN")
print("-" * 40)

try:
    from ventas.admin import ComandaAdmin
    print("✓ ComandaAdmin importado correctamente")

    # Verificar métodos importantes
    metodos = ['save_model', 'save_formset', 'get_form']
    for metodo in metodos:
        if hasattr(ComandaAdmin, metodo):
            print(f"✓ Método '{metodo}' existe")
        else:
            print(f"✗ Método '{metodo}' NO existe")

except Exception as e:
    print(f"✗ Error al importar ComandaAdmin: {e}")

# 6. Verificar campos requeridos
print("\n\n6. VERIFICANDO CAMPOS REQUERIDOS")
print("-" * 40)

print("\nCampos de Comanda:")
for field in Comanda._meta.get_fields():
    if not field.many_to_many and not field.one_to_many:
        null_ok = getattr(field, 'null', False)
        blank_ok = getattr(field, 'blank', False)
        default = getattr(field, 'default', 'NO_DEFAULT')
        print(f"  - {field.name}: null={null_ok}, blank={blank_ok}, default={default}")

print("\nCampos de DetalleComanda:")
for field in DetalleComanda._meta.get_fields():
    if not field.many_to_many and not field.one_to_many:
        null_ok = getattr(field, 'null', False)
        blank_ok = getattr(field, 'blank', False)
        default = getattr(field, 'default', 'NO_DEFAULT')
        print(f"  - {field.name}: null={null_ok}, blank={blank_ok}, default={default}")

# 7. Buscar errores recientes en logs
print("\n\n7. ERRORES RECIENTES")
print("-" * 40)

# Buscar comandas con problemas
comandas_problematicas = Comanda.objects.filter(
    estado='pendiente',
    fecha_solicitud__gte=datetime.now() - timedelta(days=1)
).order_by('-id')[:5]

if comandas_problematicas:
    print(f"Comandas pendientes últimas 24h: {comandas_problematicas.count()}")
    for comanda in comandas_problematicas:
        print(f"  - ID: {comanda.id}")
        print(f"    Creada: {comanda.fecha_solicitud}")
        print(f"    Detalles: {comanda.detalles.count()}")
        print(f"    Usuario: {comanda.usuario_solicita}")
else:
    print("No hay comandas pendientes en las últimas 24 horas")

print("\n" + "=" * 80)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 80)