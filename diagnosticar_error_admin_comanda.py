#!/usr/bin/env python
"""
Script para diagnosticar el error al guardar comandas desde el admin
Ejecutar con: python manage.py shell < diagnosticar_error_admin_comanda.py
"""

import os
import sys
import django
import logging
from datetime import datetime, timedelta

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

# Configurar logging detallado
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('ventas')

from django.contrib.auth.models import User
from django.db import connection, transaction
from django.forms.models import inlineformset_factory
from ventas.models import (
    Comanda, DetalleComanda, VentaReserva,
    Producto, ReservaProducto
)
from ventas.admin import ComandaAdmin, DetalleComandaInline

print("=" * 80)
print("DIAGNÓSTICO DE ERROR AL GUARDAR COMANDAS DESDE ADMIN")
print("=" * 80)
print(f"Fecha/Hora: {datetime.now()}")
print()

# 1. Verificar que save_formset esté capturando excepciones
print("1. VERIFICANDO MÉTODO save_formset")
print("-" * 40)

try:
    import inspect
    source = inspect.getsource(ComandaAdmin.save_formset)
    print("Código actual de save_formset:")
    print(source[:500] + "...")  # Mostrar primeras 500 caracteres

    if "try:" in source and "except" in source:
        print("\n✓ save_formset tiene manejo de excepciones")
    else:
        print("\n✗ save_formset NO tiene manejo de excepciones")
except Exception as e:
    print(f"Error al inspeccionar save_formset: {e}")

# 2. Simular el proceso del admin paso a paso
print("\n\n2. SIMULANDO PROCESO DEL ADMIN")
print("-" * 40)

# Obtener una reserva para prueba
reserva = VentaReserva.objects.filter(estado_reserva='confirmada').first()
if not reserva:
    reserva = VentaReserva.objects.first()

if reserva:
    print(f"Usando reserva ID: {reserva.id}")

    # Simular usuario del request
    superuser = User.objects.filter(is_superuser=True).first()
    if not superuser:
        print("✗ No hay superusuarios en el sistema")
    else:
        print(f"Usando superusuario: {superuser.username}")

        # Crear instancia de ComandaAdmin
        from django.contrib.admin.sites import site
        model_admin = ComandaAdmin(Comanda, site)

        # Simular creación de comanda como lo hace el admin
        print("\n3. CREANDO COMANDA (simulando admin)")
        print("-" * 40)

        try:
            with transaction.atomic():
                # Paso 1: Crear comanda (como save_model)
                comanda = Comanda()
                comanda.venta_reserva = reserva
                comanda.estado = 'pendiente'
                comanda.notas_generales = 'Test desde diagnóstico'
                comanda.usuario_solicita = superuser
                comanda.fecha_entrega_objetivo = datetime.now() + timedelta(hours=1)

                # Marcar como desde admin
                comanda._from_admin = True
                comanda._is_new_from_admin = True

                print("Guardando comanda...")
                comanda.save()
                print(f"✓ Comanda guardada con ID: {comanda.id}")

                # Paso 2: Simular formset de detalles
                print("\nCreando detalles (simulando formset)...")

                # Obtener productos
                productos = Producto.objects.filter(publicado_web=True)[:2]
                if not productos:
                    productos = Producto.objects.all()[:2]

                detalles_guardados = []
                for i, producto in enumerate(productos):
                    detalle = DetalleComanda()
                    detalle.comanda = comanda
                    detalle.producto = producto
                    detalle.cantidad = i + 1
                    detalle.precio_unitario = producto.precio_base
                    detalle.especificaciones = f"Test {i+1}"

                    print(f"Guardando detalle: {producto.nombre}...")
                    detalle.save()
                    detalles_guardados.append(detalle)
                    print(f"✓ Detalle guardado")

                # Paso 3: Simular save_formset (crear ReservaProducto)
                print("\nEjecutando lógica de save_formset...")

                if getattr(comanda, '_is_new_from_admin', False):
                    print("Comanda marcada como nueva desde admin")

                    for detalle in detalles_guardados:
                        fecha_entrega = comanda.fecha_entrega_objetivo.date() if comanda.fecha_entrega_objetivo else datetime.now().date()

                        print(f"\nCreando ReservaProducto para: {detalle.producto.nombre}")
                        print(f"  - VentaReserva ID: {comanda.venta_reserva.id}")
                        print(f"  - Producto ID: {detalle.producto.id}")
                        print(f"  - Cantidad: {detalle.cantidad}")
                        print(f"  - Precio: {detalle.precio_unitario}")
                        print(f"  - Fecha entrega: {fecha_entrega}")

                        try:
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
                                print(f"  ✓ ReservaProducto CREADO (ID: {rp.id})")
                            else:
                                print(f"  → ReservaProducto YA EXISTÍA (ID: {rp.id})")
                                print(f"    Cantidad anterior: {rp.cantidad}")
                                print(f"    Precio anterior: {rp.precio_unitario_venta}")

                        except Exception as e:
                            print(f"  ✗ ERROR al crear ReservaProducto: {e}")
                            import traceback
                            traceback.print_exc()

                # Verificar resultados
                print("\n\n4. VERIFICANDO RESULTADOS")
                print("-" * 40)

                # Verificar detalles de comanda
                detalles = DetalleComanda.objects.filter(comanda=comanda)
                print(f"Detalles en comanda: {detalles.count()}")

                # Verificar productos en reserva
                productos_reserva = ReservaProducto.objects.filter(venta_reserva=reserva)
                print(f"Productos en reserva: {productos_reserva.count()}")
                for rp in productos_reserva:
                    print(f"  - {rp.producto.nombre} x{rp.cantidad} (${rp.precio_unitario_venta})")

                # Revertir cambios
                raise Exception("Prueba completada - revirtiendo")

        except Exception as e:
            if "Prueba completada" in str(e):
                print("\n✓ Prueba completada exitosamente")
            else:
                print(f"\n✗ ERROR durante la prueba: {e}")
                import traceback
                traceback.print_exc()

# 3. Verificar campos requeridos que podrían causar error
print("\n\n5. VERIFICANDO CAMPOS QUE PODRÍAN CAUSAR ERROR")
print("-" * 40)

# Verificar ReservaProducto
print("\nCampos requeridos en ReservaProducto:")
for field in ReservaProducto._meta.get_fields():
    if hasattr(field, 'null') and hasattr(field, 'blank'):
        if not field.null and not field.blank and not getattr(field, 'default', None):
            print(f"  - {field.name}: REQUERIDO")

# Verificar si hay constraints únicos
print("\n\nConstraints únicos en ReservaProducto:")
unique_together = ReservaProducto._meta.unique_together
if unique_together:
    print(f"  - unique_together: {unique_together}")
else:
    print("  - No hay unique_together definido")

# 4. Buscar registros con problemas
print("\n\n6. BUSCANDO POSIBLES CONFLICTOS")
print("-" * 40)

# Buscar ReservaProducto duplicados
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT venta_reserva_id, producto_id, COUNT(*) as count
        FROM ventas_reservaproducto
        GROUP BY venta_reserva_id, producto_id
        HAVING COUNT(*) > 1
        LIMIT 10
    """)

    duplicados = cursor.fetchall()
    if duplicados:
        print(f"✗ ENCONTRADOS {len(duplicados)} casos de productos duplicados:")
        for dup in duplicados:
            print(f"  - Reserva {dup[0]}, Producto {dup[1]}: {dup[2]} registros")
    else:
        print("✓ No hay productos duplicados en reservas")

print("\n" + "=" * 80)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 80)