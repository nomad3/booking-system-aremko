#!/usr/bin/env python
"""
Script para capturar el error exacto al guardar comandas
Ejecutar con: python manage.py shell < capturar_error_comanda.py

Este script intenta replicar exactamente lo que hace el admin
y captura cualquier excepción que ocurra.
"""

import os
import sys
import django
import traceback
from datetime import datetime, timedelta

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

# Habilitar logging detallado
import logging
logging.basicConfig(level=logging.DEBUG)

# Capturar todos los logs de Django
django_logger = logging.getLogger('django')
django_logger.setLevel(logging.DEBUG)

# Crear handler para capturar logs en memoria
class MemoryHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)

memory_handler = MemoryHandler()
django_logger.addHandler(memory_handler)

from django.contrib.auth.models import User
from django.db import connection, transaction
from django.core.exceptions import ValidationError
from ventas.models import (
    Comanda, DetalleComanda, VentaReserva,
    Producto, ReservaProducto
)

print("=" * 80)
print("CAPTURANDO ERROR EXACTO AL GUARDAR COMANDAS")
print("=" * 80)
print(f"Fecha/Hora: {datetime.now()}")
print()

# Función para intentar crear comanda con manejo completo de errores
def intentar_crear_comanda():
    """Intenta crear una comanda capturando TODOS los errores posibles"""

    errores_encontrados = []

    try:
        # Buscar datos necesarios
        print("1. Buscando datos necesarios...")

        reserva = VentaReserva.objects.filter(
            estado_reserva='confirmada'
        ).exclude(
            comandas__isnull=False  # Excluir reservas que ya tienen comandas
        ).first()

        if not reserva:
            reserva = VentaReserva.objects.first()

        if not reserva:
            errores_encontrados.append("No hay reservas en el sistema")
            return errores_encontrados

        print(f"   ✓ Reserva encontrada: ID {reserva.id}")

        # Usuario
        usuario = User.objects.filter(username='Deborah').first()
        if not usuario:
            usuario = User.objects.filter(is_superuser=True).first()

        if not usuario:
            errores_encontrados.append("No hay usuarios disponibles")
            return errores_encontrados

        print(f"   ✓ Usuario encontrado: {usuario.username}")

        # Productos
        productos = Producto.objects.filter(publicado_web=True)[:2]
        if not productos:
            productos = Producto.objects.all()[:2]

        if not productos:
            errores_encontrados.append("No hay productos en el sistema")
            return errores_encontrados

        print(f"   ✓ Productos encontrados: {productos.count()}")

        # Intentar crear comanda
        print("\n2. Creando comanda...")

        with transaction.atomic():
            # Crear comanda como lo hace el admin
            comanda = Comanda()

            # Asignar campos uno por uno para detectar errores
            try:
                comanda.venta_reserva = reserva
                print("   ✓ venta_reserva asignada")
            except Exception as e:
                errores_encontrados.append(f"Error asignando venta_reserva: {e}")

            try:
                comanda.estado = 'pendiente'
                print("   ✓ estado asignado")
            except Exception as e:
                errores_encontrados.append(f"Error asignando estado: {e}")

            try:
                comanda.notas_generales = 'Test diagnóstico'
                print("   ✓ notas_generales asignadas")
            except Exception as e:
                errores_encontrados.append(f"Error asignando notas_generales: {e}")

            try:
                comanda.usuario_solicita = usuario
                print("   ✓ usuario_solicita asignado")
            except Exception as e:
                errores_encontrados.append(f"Error asignando usuario_solicita: {e}")

            try:
                comanda.fecha_entrega_objetivo = datetime.now() + timedelta(hours=1)
                print("   ✓ fecha_entrega_objetivo asignada")
            except Exception as e:
                errores_encontrados.append(f"Error asignando fecha_entrega_objetivo: {e}")

            # Marcar como desde admin
            comanda._from_admin = True
            comanda._is_new_from_admin = True

            # Intentar guardar
            try:
                print("\n3. Guardando comanda...")
                comanda.save()
                print(f"   ✓ Comanda guardada con ID: {comanda.id}")
            except ValidationError as e:
                errores_encontrados.append(f"ValidationError al guardar comanda: {e}")
                print(f"   ✗ ValidationError: {e}")
                return errores_encontrados
            except Exception as e:
                errores_encontrados.append(f"Error al guardar comanda: {type(e).__name__}: {e}")
                print(f"   ✗ Error: {type(e).__name__}: {e}")
                traceback.print_exc()
                return errores_encontrados

            # Crear detalles
            print("\n4. Creando detalles...")
            detalles_creados = []

            for i, producto in enumerate(productos):
                try:
                    detalle = DetalleComanda()
                    detalle.comanda = comanda
                    detalle.producto = producto
                    detalle.cantidad = i + 1
                    detalle.precio_unitario = producto.precio_base
                    detalle.especificaciones = f"Test {i+1}"

                    detalle.save()
                    detalles_creados.append(detalle)
                    print(f"   ✓ Detalle creado: {producto.nombre}")

                except Exception as e:
                    error_msg = f"Error creando detalle para {producto.nombre}: {type(e).__name__}: {e}"
                    errores_encontrados.append(error_msg)
                    print(f"   ✗ {error_msg}")
                    traceback.print_exc()

            # Simular save_formset
            print("\n5. Ejecutando lógica de save_formset...")

            if getattr(comanda, '_is_new_from_admin', False) and detalles_creados:
                for detalle in detalles_creados:
                    try:
                        fecha_entrega = comanda.fecha_entrega_objetivo.date() if comanda.fecha_entrega_objetivo else datetime.now().date()

                        print(f"\n   Creando ReservaProducto para {detalle.producto.nombre}...")

                        # Verificar si ya existe
                        existe = ReservaProducto.objects.filter(
                            venta_reserva=comanda.venta_reserva,
                            producto=detalle.producto
                        ).exists()

                        if existe:
                            print(f"     → Ya existe ReservaProducto para este producto")

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
                            print(f"     ✓ ReservaProducto creado (ID: {rp.id})")
                        else:
                            print(f"     → ReservaProducto existente actualizado (ID: {rp.id})")

                    except ValidationError as e:
                        error_msg = f"ValidationError creando ReservaProducto: {e.message_dict if hasattr(e, 'message_dict') else e}"
                        errores_encontrados.append(error_msg)
                        print(f"     ✗ {error_msg}")
                    except Exception as e:
                        error_msg = f"Error creando ReservaProducto: {type(e).__name__}: {e}"
                        errores_encontrados.append(error_msg)
                        print(f"     ✗ {error_msg}")
                        traceback.print_exc()

            # Si llegamos aquí, todo funcionó - revertir
            if not errores_encontrados:
                print("\n✓ TODO FUNCIONÓ CORRECTAMENTE - revirtiendo cambios de prueba")
                raise Exception("Prueba exitosa - revirtiendo")

    except Exception as e:
        if "Prueba exitosa" not in str(e):
            error_msg = f"Error general: {type(e).__name__}: {e}"
            errores_encontrados.append(error_msg)
            print(f"\n✗ {error_msg}")
            traceback.print_exc()

    return errores_encontrados

# Ejecutar diagnóstico
print("\nEJECUTANDO DIAGNÓSTICO...")
print("-" * 40)

errores = intentar_crear_comanda()

# Mostrar resumen
print("\n\n" + "=" * 80)
print("RESUMEN DE ERRORES ENCONTRADOS")
print("=" * 80)

if errores:
    print(f"\nSe encontraron {len(errores)} error(es):\n")
    for i, error in enumerate(errores, 1):
        print(f"{i}. {error}")
else:
    print("\nNO SE ENCONTRARON ERRORES - La comanda se puede crear correctamente")

# Mostrar logs capturados
print("\n\n" + "=" * 80)
print("LOGS DE DJANGO CAPTURADOS")
print("=" * 80)

if memory_handler.records:
    for record in memory_handler.records[-20:]:  # Últimos 20 logs
        if record.levelno >= logging.WARNING:  # Solo warnings y errores
            print(f"\n[{record.levelname}] {record.name}")
            print(f"{record.getMessage()}")
else:
    print("\nNo se capturaron logs de advertencia o error")

print("\n" + "=" * 80)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 80)