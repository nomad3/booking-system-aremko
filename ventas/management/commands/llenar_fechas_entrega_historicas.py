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
            # OPTIMIZACIÓN: Obtener lote con prefetch de servicios (evita N+1 queries)
            productos_sin_fecha = ReservaProducto.objects.filter(
                fecha_entrega__isnull=True
            ).select_related(
                'venta_reserva', 'producto'
            ).prefetch_related(
                'venta_reserva__reservaservicios'
            )[:batch_size]

            # Convertir a lista para poder iterar
            productos_lote = list(productos_sin_fecha)

            if not productos_lote:
                break  # No hay más productos

            batch_num += 1
            self.stdout.write(f'\n📦 Procesando lote {batch_num} ({len(productos_lote)} productos)...')

            # Lista para bulk_update
            productos_a_actualizar = []

            # PROCESAR EN MEMORIA (sin queries individuales)
            for producto in productos_lote:
                try:
                    # Validar que el producto tenga venta_reserva
                    if not producto.venta_reserva:
                        logger.warning(f'Producto {producto.id} sin venta_reserva, saltando')
                        errores += 1
                        continue

                    # Obtener servicios de la reserva (ya cargados con prefetch_related)
                    servicios = list(producto.venta_reserva.reservaservicios.all())

                    if servicios:
                        # Encontrar el servicio con fecha más temprana
                        primer_servicio = min(servicios, key=lambda s: s.fecha_agendamiento)
                        fecha_a_asignar = primer_servicio.fecha_agendamiento
                        productos_actualizados += 1
                    else:
                        # No hay servicios, usar fecha de la reserva como fallback
                        if producto.venta_reserva.fecha_reserva:
                            fecha_a_asignar = producto.venta_reserva.fecha_reserva.date()
                            productos_sin_servicios += 1
                        else:
                            # Fecha de reserva es NULL, usar fecha actual como último fallback
                            from django.utils import timezone
                            fecha_a_asignar = timezone.now().date()
                            logger.warning(
                                f'Producto {producto.id} en Reserva {producto.venta_reserva.id} '
                                f'sin servicios ni fecha_reserva, usando fecha actual'
                            )
                            productos_sin_servicios += 1

                    if dry_run:
                        servicio_info = 'con servicio' if servicios else 'SIN SERVICIOS'
                        self.stdout.write(
                            f'  [DRY RUN] Producto #{producto.id} ({producto.producto.nombre}) '
                            f'en Reserva #{producto.venta_reserva.id} ({servicio_info}) '
                            f'-> fecha_entrega = {fecha_a_asignar}'
                        )
                    else:
                        # Asignar fecha en memoria (no guardar todavía)
                        producto.fecha_entrega = fecha_a_asignar
                        productos_a_actualizar.append(producto)

                except Exception as e:
                    logger.error(f'Error procesando producto {producto.id}: {str(e)}', exc_info=True)
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ Error en Producto #{producto.id}: {str(e)}')
                    )
                    errores += 1

            # OPTIMIZACIÓN: bulk_update en vez de save() individual
            if not dry_run and productos_a_actualizar:
                with transaction.atomic():
                    ReservaProducto.objects.bulk_update(
                        productos_a_actualizar,
                        ['fecha_entrega'],
                        batch_size=500
                    )
                    logger.info(f'Bulk update de {len(productos_a_actualizar)} productos completado')

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
