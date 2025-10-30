"""
Management command para procesar premios de bienvenida 3 días después del check-in
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from ventas.models import Cliente, ReservaServicio, ClientePremio
from ventas.services.premio_service import PremioService
from ventas.services.tramo_service import TramoService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Procesa premios de bienvenida para clientes que tuvieron su primer check-in hace 3 días'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar sin hacer cambios en la BD (solo análisis)'
        )
        parser.add_argument(
            '--dias',
            type=int,
            default=3,
            help='Días después del check-in para generar premio (default: 3)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        dias_despues = options['dias']

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🎁 PROCESAMIENTO DE PREMIOS DE BIENVENIDA"))
        self.stdout.write("=" * 80 + "\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODO DRY-RUN: No se harán cambios en la base de datos\n"))

        # Calcular la fecha objetivo (hace X días)
        fecha_objetivo = (timezone.now() - timedelta(days=dias_despues)).date()

        self.stdout.write(f"📅 Buscando clientes con primer check-in el: {fecha_objetivo}")
        self.stdout.write(f"   (hace {dias_despues} días desde hoy)\n")

        # Estadísticas
        stats = {
            'total_reservas_fecha': 0,
            'clientes_evaluados': 0,
            'clientes_elegibles': 0,
            'ya_tienen_premio': 0,
            'no_es_primera_reserva': 0,
            'premios_generados': 0,
            'errores': 0,
        }

        # Buscar todas las reservas de servicios con check-in en la fecha objetivo
        reservas = ReservaServicio.objects.filter(
            fecha_agendamiento=fecha_objetivo
        ).select_related('venta_reserva', 'venta_reserva__cliente').order_by('venta_reserva__cliente_id')

        stats['total_reservas_fecha'] = reservas.count()
        self.stdout.write(f"📊 Total de reservas en esa fecha: {stats['total_reservas_fecha']:,}\n")

        if stats['total_reservas_fecha'] == 0:
            self.stdout.write(self.style.WARNING("No hay reservas para procesar en esa fecha."))
            return

        # Agrupar por cliente para evitar duplicados
        clientes_procesados = set()

        self.stdout.write("─" * 80)
        self.stdout.write("🔍 PROCESANDO CLIENTES")
        self.stdout.write("─" * 80 + "\n")

        for reserva in reservas:
            if not reserva.venta_reserva or not reserva.venta_reserva.cliente:
                continue

            cliente = reserva.venta_reserva.cliente

            # Evitar procesar el mismo cliente múltiples veces
            if cliente.id in clientes_procesados:
                continue

            clientes_procesados.add(cliente.id)
            stats['clientes_evaluados'] += 1

            try:
                # Verificar si esta es su PRIMERA reserva de servicio
                primera_reserva = ReservaServicio.objects.filter(
                    venta_reserva__cliente=cliente
                ).order_by('fecha_agendamiento', 'id').first()

                if not primera_reserva or primera_reserva.fecha_agendamiento != fecha_objetivo:
                    stats['no_es_primera_reserva'] += 1
                    self.stdout.write(
                        f"  ⏭️  {cliente.nombre[:40]:<40} - No es su primera reserva"
                    )
                    continue

                # Verificar si ya tiene un premio de bienvenida
                tiene_premio = ClientePremio.objects.filter(
                    cliente=cliente,
                    premio__tipo='descuento_bienvenida'
                ).exists()

                if tiene_premio:
                    stats['ya_tienen_premio'] += 1
                    self.stdout.write(
                        f"  ⏭️  {cliente.nombre[:40]:<40} - Ya tiene premio de bienvenida"
                    )
                    continue

                # Cliente elegible para premio
                stats['clientes_elegibles'] += 1

                # Calcular gasto total del cliente
                gasto_total = TramoService.calcular_gasto_cliente(cliente)

                self.stdout.write(
                    f"  ✅ {cliente.nombre[:40]:<40} - Elegible (Gasto: ${gasto_total:,.0f})"
                )

                # Generar premio si no es dry-run
                if not dry_run:
                    with transaction.atomic():
                        premio_generado = PremioService.generar_premio_cliente_nuevo(
                            cliente=cliente,
                            gasto_total=gasto_total
                        )

                        if premio_generado:
                            stats['premios_generados'] += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"     🎉 Premio generado: {premio_generado.premio.nombre}"
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"     ⚠️  No se pudo generar premio (verificar logs)"
                                )
                            )

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

        self.stdout.write(f"Reservas en fecha objetivo:       {stats['total_reservas_fecha']:>10,}")
        self.stdout.write(f"Clientes evaluados:               {stats['clientes_evaluados']:>10,}")
        self.stdout.write(f"Clientes elegibles:               {stats['clientes_elegibles']:>10,}")
        self.stdout.write(f"Ya tienen premio:                 {stats['ya_tienen_premio']:>10,}")
        self.stdout.write(f"No es primera reserva:            {stats['no_es_primera_reserva']:>10,}")

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Premios generados:                {stats['premios_generados']:>10,}"))

        if stats['errores'] > 0:
            self.stdout.write(self.style.ERROR(f"Errores:                          {stats['errores']:>10,}"))

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
                f"✅ Proceso completado exitosamente. {stats['premios_generados']:,} premios generados."
            ))

        self.stdout.write("=" * 80 + "\n")

        # Notas importantes
        self.stdout.write(self.style.WARNING("📌 NOTAS IMPORTANTES:"))
        self.stdout.write("   • Este comando debe ejecutarse diariamente")
        self.stdout.write("   • Procesa clientes con check-in hace 3 días (configurable con --dias)")
        self.stdout.write("   • Solo genera premios para clientes en su PRIMERA reserva")
        self.stdout.write("   • No genera duplicados (verifica si ya tienen premio)")
        self.stdout.write("   • Recomendado: Configurar en cron o Celery Beat\n")
