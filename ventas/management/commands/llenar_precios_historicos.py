# -*- coding: utf-8 -*-
"""
Comando para llenar precios históricos en productos y servicios de reservas.

Para productos/servicios sin precio_unitario_venta, se copia el precio_base
actual del producto/servicio del catálogo.

IMPORTANTE: Este comando pobla con precios ACTUALES, no precios históricos reales
(a menos que tengas backup de precios antiguos).

Uso:
    python manage.py llenar_precios_historicos

    Opciones:
    --dry-run: Muestra qué se haría sin hacer cambios
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from ventas.models import ReservaProducto, ReservaServicio
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Llenar precios históricos para productos/servicios sin precio_unitario_venta'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué se haría sin hacer cambios reales',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Número de registros a procesar por lote (default: 1000)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        batch_size = options.get('batch_size', 1000)

        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Modo DRY RUN - No se harán cambios reales\n'))
        else:
            self.stdout.write(self.style.SUCCESS(f'💰 Llenando precios históricos en lotes de {batch_size}...\n'))

        # ===== PROCESAR PRODUCTOS =====
        self.stdout.write('📦 Procesando ReservaProducto...')
        total_productos = ReservaProducto.objects.filter(precio_unitario_venta__isnull=True).count()
        self.stdout.write(f'Total de productos sin precio_unitario_venta: {total_productos}\n')

        productos_actualizados = 0
        productos_error = 0
        batch_num = 0

        if total_productos > 0:
            while True:
                # Obtener lote con select_related para evitar N+1 queries
                productos_sin_precio = ReservaProducto.objects.filter(
                    precio_unitario_venta__isnull=True
                ).select_related('producto')[:batch_size]

                productos_lote = list(productos_sin_precio)

                if not productos_lote:
                    break

                batch_num += 1
                self.stdout.write(f'\n📦 Procesando lote {batch_num} ({len(productos_lote)} productos)...')

                productos_a_actualizar = []

                for producto_reserva in productos_lote:
                    try:
                        if not producto_reserva.producto:
                            logger.warning(f'ReservaProducto {producto_reserva.id} sin producto asociado, saltando')
                            productos_error += 1
                            continue

                        # Copiar precio_base actual del catálogo
                        precio_a_asignar = producto_reserva.producto.precio_base

                        if dry_run:
                            self.stdout.write(
                                f'  [DRY RUN] ReservaProducto #{producto_reserva.id} '
                                f'({producto_reserva.producto.nombre}) '
                                f'-> precio_unitario_venta = ${precio_a_asignar}'
                            )
                        else:
                            producto_reserva.precio_unitario_venta = precio_a_asignar
                            productos_a_actualizar.append(producto_reserva)

                        productos_actualizados += 1

                    except Exception as e:
                        logger.error(f'Error procesando ReservaProducto {producto_reserva.id}: {str(e)}', exc_info=True)
                        self.stdout.write(
                            self.style.ERROR(f'  ❌ Error en ReservaProducto #{producto_reserva.id}: {str(e)}')
                        )
                        productos_error += 1

                # Bulk update
                if not dry_run and productos_a_actualizar:
                    with transaction.atomic():
                        ReservaProducto.objects.bulk_update(
                            productos_a_actualizar,
                            ['precio_unitario_venta'],
                            batch_size=500
                        )
                        logger.info(f'Bulk update de {len(productos_a_actualizar)} productos completado')

                self.stdout.write(f'   ✅ Lote {batch_num} completado ({len(productos_lote)} productos)')
                self.stdout.write(f'   Progreso: {productos_actualizados}/{total_productos}')

        # ===== PROCESAR SERVICIOS =====
        self.stdout.write('\n\n🛎️  Procesando ReservaServicio...')
        total_servicios = ReservaServicio.objects.filter(precio_unitario_venta__isnull=True).count()
        self.stdout.write(f'Total de servicios sin precio_unitario_venta: {total_servicios}\n')

        servicios_actualizados = 0
        servicios_error = 0
        batch_num = 0

        if total_servicios > 0:
            while True:
                # Obtener lote con select_related para evitar N+1 queries
                servicios_sin_precio = ReservaServicio.objects.filter(
                    precio_unitario_venta__isnull=True
                ).select_related('servicio')[:batch_size]

                servicios_lote = list(servicios_sin_precio)

                if not servicios_lote:
                    break

                batch_num += 1
                self.stdout.write(f'\n🛎️  Procesando lote {batch_num} ({len(servicios_lote)} servicios)...')

                servicios_a_actualizar = []

                for servicio_reserva in servicios_lote:
                    try:
                        if not servicio_reserva.servicio:
                            logger.warning(f'ReservaServicio {servicio_reserva.id} sin servicio asociado, saltando')
                            servicios_error += 1
                            continue

                        # Copiar precio_base actual del catálogo
                        precio_a_asignar = servicio_reserva.servicio.precio_base

                        if dry_run:
                            self.stdout.write(
                                f'  [DRY RUN] ReservaServicio #{servicio_reserva.id} '
                                f'({servicio_reserva.servicio.nombre}) '
                                f'-> precio_unitario_venta = ${precio_a_asignar}'
                            )
                        else:
                            servicio_reserva.precio_unitario_venta = precio_a_asignar
                            servicios_a_actualizar.append(servicio_reserva)

                        servicios_actualizados += 1

                    except Exception as e:
                        logger.error(f'Error procesando ReservaServicio {servicio_reserva.id}: {str(e)}', exc_info=True)
                        self.stdout.write(
                            self.style.ERROR(f'  ❌ Error en ReservaServicio #{servicio_reserva.id}: {str(e)}')
                        )
                        servicios_error += 1

                # Bulk update
                if not dry_run and servicios_a_actualizar:
                    with transaction.atomic():
                        ReservaServicio.objects.bulk_update(
                            servicios_a_actualizar,
                            ['precio_unitario_venta'],
                            batch_size=500
                        )
                        logger.info(f'Bulk update de {len(servicios_a_actualizar)} servicios completado')

                self.stdout.write(f'   ✅ Lote {batch_num} completado ({len(servicios_lote)} servicios)')
                self.stdout.write(f'   Progreso: {servicios_actualizados}/{total_servicios}')

        # ===== RESUMEN FINAL =====
        self.stdout.write('\n' + '=' * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING('📊 RESUMEN (DRY RUN - NO SE HICIERON CAMBIOS):'))
        else:
            self.stdout.write(self.style.SUCCESS('📊 RESUMEN:'))

        self.stdout.write(f'\n📦 PRODUCTOS:')
        self.stdout.write(f'  Total procesados: {total_productos}')
        self.stdout.write(f'  ✅ Actualizados: {productos_actualizados}')
        if productos_error > 0:
            self.stdout.write(self.style.ERROR(f'  ❌ Errores: {productos_error}'))

        self.stdout.write(f'\n🛎️  SERVICIOS:')
        self.stdout.write(f'  Total procesados: {total_servicios}')
        self.stdout.write(f'  ✅ Actualizados: {servicios_actualizados}')
        if servicios_error > 0:
            self.stdout.write(self.style.ERROR(f'  ❌ Errores: {servicios_error}'))

        self.stdout.write('\n' + '=' * 60 + '\n')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('Para aplicar los cambios, ejecuta el comando sin --dry-run')
            )
        else:
            self.stdout.write(self.style.SUCCESS('✅ Proceso completado exitosamente!'))
