"""
Management command para calcular y registrar tramos de todos los clientes existentes
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from ventas.models import Cliente, HistorialTramo
from ventas.services.tramo_service import TramoService
from ventas.services.crm_service import CRMService
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Calcula y registra el tramo actual de todos los clientes con historial de compras'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar sin hacer cambios en la BD (solo análisis)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Tamaño del batch para procesamiento (default: 100)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar recálculo incluso si ya tienen historial de tramos'
        )
        parser.add_argument(
            '--min-gasto',
            type=float,
            default=0,
            help='Solo procesar clientes con gasto mínimo (default: 0)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        force = options['force']
        min_gasto = Decimal(str(options['min_gasto']))

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🔢 CÁLCULO DE TRAMOS DE CLIENTES"))
        self.stdout.write("=" * 80 + "\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODO DRY-RUN: No se harán cambios en la base de datos\n"))

        # Estadísticas
        stats = {
            'total_clientes': 0,
            'clientes_procesados': 0,
            'clientes_con_gasto': 0,
            'clientes_sin_gasto': 0,
            'clientes_ya_registrados': 0,
            'registros_creados': 0,
            'errores': 0,
            'tramos_por_nivel': {}
        }

        # Obtener todos los clientes
        clientes = Cliente.objects.all().order_by('id')
        stats['total_clientes'] = clientes.count()

        self.stdout.write(f"📊 Total de clientes a procesar: {stats['total_clientes']:,}\n")

        # Procesar en batches
        for i in range(0, stats['total_clientes'], batch_size):
            batch = clientes[i:i + batch_size]

            self.stdout.write(f"\n{'─' * 80}")
            self.stdout.write(f"📦 Procesando batch {i // batch_size + 1} (clientes {i + 1} - {min(i + batch_size, stats['total_clientes'])})")
            self.stdout.write('─' * 80)

            for cliente in batch:
                try:
                    stats['clientes_procesados'] += 1

                    # Calcular gasto total usando CRMService
                    gasto_total = TramoService.calcular_gasto_cliente(cliente)

                    # Filtrar por gasto mínimo
                    if gasto_total < min_gasto:
                        continue

                    # Si no tiene gasto, saltar
                    if gasto_total <= 0:
                        stats['clientes_sin_gasto'] += 1
                        continue

                    stats['clientes_con_gasto'] += 1

                    # Calcular tramo
                    tramo_actual = TramoService.calcular_tramo(float(gasto_total))

                    # Verificar si ya tiene historial
                    tiene_historial = HistorialTramo.objects.filter(cliente=cliente).exists()

                    if tiene_historial and not force:
                        stats['clientes_ya_registrados'] += 1
                        self.stdout.write(
                            f"  ⏭️  {cliente.nombre[:30]:<30} - Ya tiene historial (Tramo {tramo_actual})"
                        )
                        continue

                    # Registrar en estadísticas
                    if tramo_actual not in stats['tramos_por_nivel']:
                        stats['tramos_por_nivel'][tramo_actual] = 0
                    stats['tramos_por_nivel'][tramo_actual] += 1

                    # Mostrar información
                    self.stdout.write(
                        f"  ✅ {cliente.nombre[:30]:<30} - "
                        f"Gasto: ${gasto_total:>12,.0f} - Tramo: {tramo_actual}"
                    )

                    # Crear registro si no es dry-run
                    if not dry_run:
                        with transaction.atomic():
                            # Si tiene historial y force=True, obtener último tramo
                            if tiene_historial and force:
                                ultimo = HistorialTramo.objects.filter(
                                    cliente=cliente
                                ).order_by('-fecha_cambio').first()
                                tramo_anterior = ultimo.tramo_hasta
                            else:
                                tramo_anterior = 0

                            # Crear registro de tramo
                            HistorialTramo.objects.create(
                                cliente=cliente,
                                tramo_desde=tramo_anterior,
                                tramo_hasta=tramo_actual,
                                gasto_en_momento=gasto_total
                            )

                            stats['registros_creados'] += 1

                except Exception as e:
                    stats['errores'] += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ❌ Error procesando {cliente.nombre}: {str(e)}"
                        )
                    )
                    logger.error(f"Error procesando cliente {cliente.id}: {e}", exc_info=True)

        # Reporte final
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 REPORTE FINAL"))
        self.stdout.write("=" * 80 + "\n")

        self.stdout.write(f"Total de clientes:           {stats['total_clientes']:>10,}")
        self.stdout.write(f"Clientes procesados:         {stats['clientes_procesados']:>10,}")
        self.stdout.write(f"Clientes con gasto:          {stats['clientes_con_gasto']:>10,}")
        self.stdout.write(f"Clientes sin gasto:          {stats['clientes_sin_gasto']:>10,}")

        if not force:
            self.stdout.write(f"Ya registrados (saltados):   {stats['clientes_ya_registrados']:>10,}")

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Registros creados:           {stats['registros_creados']:>10,}"))

        if stats['errores'] > 0:
            self.stdout.write(self.style.ERROR(f"Errores:                     {stats['errores']:>10,}"))

        # Distribución por tramos
        if stats['tramos_por_nivel']:
            self.stdout.write("\n" + "─" * 80)
            self.stdout.write("📈 DISTRIBUCIÓN POR TRAMOS")
            self.stdout.write("─" * 80 + "\n")

            for tramo in sorted(stats['tramos_por_nivel'].keys()):
                cantidad = stats['tramos_por_nivel'][tramo]
                min_gasto, max_gasto = TramoService.obtener_rango_tramo(tramo)
                porcentaje = (cantidad / stats['clientes_con_gasto'] * 100) if stats['clientes_con_gasto'] > 0 else 0

                # Barra visual
                barra_len = int(porcentaje / 2)  # Max 50 caracteres
                barra = '█' * barra_len

                self.stdout.write(
                    f"  Tramo {tramo:>2} (${min_gasto:>9,} - ${max_gasto:>9,}): "
                    f"{cantidad:>4} clientes {barra} {porcentaje:>5.1f}%"
                )

        # Mensaje final
        self.stdout.write("\n" + "=" * 80)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "⚠️  Modo DRY-RUN: No se hicieron cambios en la base de datos"
            ))
            self.stdout.write(self.style.WARNING(
                "   Ejecuta sin --dry-run para aplicar los cambios"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Proceso completado exitosamente. {stats['registros_creados']:,} registros creados."
            ))

        self.stdout.write("=" * 80 + "\n")

        # Notas importantes
        self.stdout.write(self.style.WARNING("📌 NOTAS IMPORTANTES:"))
        self.stdout.write("   • Este comando NO genera premios automáticamente")
        self.stdout.write("   • Solo registra el estado actual de tramos")
        self.stdout.write("   • Los premios se generarán automáticamente con futuros cambios de tramo")
        self.stdout.write("   • Usa --force para recalcular clientes ya registrados")
        self.stdout.write("   • Usa --min-gasto para filtrar por gasto mínimo\n")
