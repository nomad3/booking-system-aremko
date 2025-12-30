# -*- coding: utf-8 -*-
"""
Comando para llenar las fechas de entrega históricas de productos en reservas.

Para productos sin fecha_entrega, se asigna la fecha del primer servicio
de la reserva como fecha de entrega por defecto.

Uso:
    python manage.py llenar_fechas_entrega_historicas

    Opciones:
    --dry-run: Muestra qué se haría sin hacer cambios
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from ventas.models import ReservaProducto
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Llenar fechas de entrega históricas para productos sin fecha_entrega'

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
            help='Número de productos a procesar por lote (default: 1000)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        batch_size = options.get('batch_size', 1000)

        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Modo DRY RUN - No se harán cambios reales\n'))
        else:
            self.stdout.write(self.style.SUCCESS(f'📅 Llenando fechas de entrega históricas en lotes de {batch_size}...\n'))

        # Contar productos sin fecha_entrega
        total_productos = ReservaProducto.objects.filter(fecha_entrega__isnull=True).count()
        self.stdout.write(f'Total de productos sin fecha_entrega: {total_productos}\n')

        if total_productos == 0:
            self.stdout.write(self.style.SUCCESS('✅ No hay productos sin fecha de entrega. Todo está actualizado.'))
            return

        productos_actualizados = 0
        productos_sin_servicios = 0
        errores = 0
        batch_num = 0

        # Procesar en lotes
        while True:
            # Obtener siguiente lote de productos sin fecha
            productos_sin_fecha = ReservaProducto.objects.filter(
                fecha_entrega__isnull=True
            ).select_related('venta_reserva')[:batch_size]

            # Convertir a lista para poder iterar
            productos_lote = list(productos_sin_fecha)

            if not productos_lote:
                break  # No hay más productos

            batch_num += 1
            self.stdout.write(f'\n📦 Procesando lote {batch_num} ({len(productos_lote)} productos)...')

            with transaction.atomic():
                for producto in productos_lote:
                    try:
                        # Buscar el primer servicio de la reserva
                        primer_servicio = producto.venta_reserva.reservaservicios.order_by('fecha_agendamiento').first()

                        if primer_servicio:
                            fecha_a_asignar = primer_servicio.fecha_agendamiento

                            if dry_run:
                                self.stdout.write(
                                    f'  [DRY RUN] Producto #{producto.id} ({producto.producto.nombre}) '
                                    f'en Reserva #{producto.venta_reserva.id} '
                                    f'-> fecha_entrega = {fecha_a_asignar}'
                                )
                            else:
                                producto.fecha_entrega = fecha_a_asignar
                                producto.save()
                                logger.info(
                                    f'Producto {producto.id} actualizado con fecha_entrega={fecha_a_asignar}'
                                )

                            productos_actualizados += 1
                        else:
                            # No hay servicios, usar fecha de la reserva como fallback
                            fecha_a_asignar = producto.venta_reserva.fecha_reserva.date()

                            if dry_run:
                                self.stdout.write(
                                    f'  [DRY RUN] ⚠️ Producto #{producto.id} ({producto.producto.nombre}) '
                                    f'en Reserva #{producto.venta_reserva.id} (SIN SERVICIOS) '
                                    f'-> fecha_entrega = {fecha_a_asignar} (fecha de reserva)'
                                )
                            else:
                                producto.fecha_entrega = fecha_a_asignar
                                producto.save()
                                logger.warning(
                                    f'Producto {producto.id} sin servicios, usando fecha_reserva={fecha_a_asignar}'
                                )

                            productos_sin_servicios += 1

                    except Exception as e:
                        logger.error(f'Error procesando producto {producto.id}: {str(e)}', exc_info=True)
                        self.stdout.write(
                            self.style.ERROR(f'  ❌ Error en Producto #{producto.id}: {str(e)}')
                        )
                        errores += 1

                # Si es dry-run, hacer rollback de este lote
                if dry_run:
                    transaction.set_rollback(True)

            # Mostrar progreso del lote
            self.stdout.write(f'   ✅ Lote {batch_num} completado ({len(productos_lote)} productos)')
            self.stdout.write(f'   Progreso total: {productos_actualizados + productos_sin_servicios}/{total_productos}')

        # Resumen
        self.stdout.write('\n' + '=' * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING('📊 RESUMEN (DRY RUN - NO SE HICIERON CAMBIOS):'))
        else:
            self.stdout.write(self.style.SUCCESS('📊 RESUMEN:'))

        self.stdout.write(f'  Total productos procesados: {total_productos}')
        self.stdout.write(f'  ✅ Actualizados con fecha de servicio: {productos_actualizados}')
        if productos_sin_servicios > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Actualizados con fecha de reserva (sin servicios): {productos_sin_servicios}')
            )
        if errores > 0:
            self.stdout.write(self.style.ERROR(f'  ❌ Errores: {errores}'))

        self.stdout.write('=' * 60 + '\n')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('Para aplicar los cambios, ejecuta el comando sin --dry-run')
            )
        else:
            self.stdout.write(self.style.SUCCESS('✅ Proceso completado exitosamente!'))
