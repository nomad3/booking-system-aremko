"""
Management command para revertir premios cancelados incorrectamente
Detecta premios de bienvenida que fueron cancelados pero el cliente SÍ es de primera reserva
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from ventas.models import ClientePremio
from ventas.services.crm_service import CRMService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Revierte cancelaciones incorrectas de premios de bienvenida'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar sin hacer cambios en la BD (solo análisis)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🔄 REVERTIR CANCELACIONES INCORRECTAS"))
        self.stdout.write("=" * 80 + "\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODO DRY-RUN: No se harán cambios en la base de datos\n"))

        # Estadísticas
        stats = {
            'total_cancelados': 0,
            'cancelaciones_incorrectas': 0,
            'premios_revertidos': 0,
            'errores': 0,
        }

        # Buscar premios de bienvenida CANCELADOS
        premios_cancelados = ClientePremio.objects.filter(
            premio__tipo='descuento_bienvenida',
            estado='cancelado',
            notas__icontains='Cancelado automáticamente'  # Solo los que fueron cancelados por el script
        ).select_related('cliente', 'premio').order_by('id')

        stats['total_cancelados'] = premios_cancelados.count()

        self.stdout.write(f"📊 Total de premios cancelados automáticamente: {stats['total_cancelados']:,}\n")

        if stats['total_cancelados'] == 0:
            self.stdout.write(self.style.WARNING("No hay premios cancelados automáticamente para revisar."))
            return

        self.stdout.write("─" * 80)
        self.stdout.write("🔍 ANALIZANDO PREMIOS CANCELADOS")
        self.stdout.write("─" * 80 + "\n")

        for premio in premios_cancelados:
            cliente = premio.cliente

            try:
                # Obtener datos 360 del cliente
                datos_360 = CRMService.get_customer_360(cliente.id)
                total_servicios = datos_360['metricas']['total_servicios']
                servicios_historicos = datos_360['metricas']['servicios_historicos']
                servicios_actuales = datos_360['metricas']['servicios_actuales']
                gasto_total = datos_360['metricas']['gasto_total']

                # Verificar si la cancelación fue INCORRECTA
                # Un premio de bienvenida es correcto si el cliente NO tiene servicios históricos
                if servicios_historicos == 0:
                    # ❌ CANCELACIÓN INCORRECTA: Cliente SÍ debería tener el premio
                    stats['cancelaciones_incorrectas'] += 1

                    self.stdout.write(
                        self.style.ERROR(
                            f"\n❌ Premio #{premio.id} - {cliente.nombre[:40]:<40} - CANCELADO INCORRECTAMENTE"
                        )
                    )
                    self.stdout.write(f"   Total servicios: {total_servicios}")
                    self.stdout.write(f"   Servicios históricos: {servicios_historicos} ✅")
                    self.stdout.write(f"   Servicios actuales: {servicios_actuales}")
                    self.stdout.write(f"   Gasto total: ${gasto_total:,.0f}")
                    self.stdout.write(f"   Fecha ganado: {premio.fecha_ganado}")
                    self.stdout.write(f"   Notas: {premio.notas[:80]}...")

                    # Revertir cancelación
                    if not dry_run:
                        with transaction.atomic():
                            # Restaurar a estado pendiente de aprobación
                            premio.estado = 'pendiente_aprobacion'
                            premio.notas = (
                                f"[REVERTIDO] Premio restaurado el {timezone.now().date()}. "
                                f"Cancelación anterior fue incorrecta (cliente SÍ es de primera reserva). "
                                f"Nota original: {premio.notas}"
                            )
                            premio.save()

                            stats['premios_revertidos'] += 1

                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"   ✅ Premio revertido a estado 'pendiente_aprobacion'"
                                )
                            )

                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"   🔄 Acción sugerida: Revertir a 'pendiente_aprobacion'"
                            )
                        )

                else:
                    # ✅ Cancelación correcta
                    self.stdout.write(
                        f"  ✅ Premio #{premio.id} - {cliente.nombre[:40]:<40} - Cancelación correcta (históricos: {servicios_historicos})"
                    )

            except Exception as e:
                stats['errores'] += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  ❌ Error analizando Premio #{premio.id}: {str(e)}"
                    )
                )
                logger.error(f"Error analizando premio {premio.id}: {e}", exc_info=True)

        # Reporte final
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 REPORTE FINAL"))
        self.stdout.write("=" * 80 + "\n")

        self.stdout.write(f"Total cancelados automáticamente: {stats['total_cancelados']:>10,}")
        self.stdout.write(
            self.style.ERROR(f"Cancelaciones incorrectas:        {stats['cancelaciones_incorrectas']:>10,}")
        )

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Premios revertidos:                {stats['premios_revertidos']:>10,}")
            )

        if stats['errores'] > 0:
            self.stdout.write(self.style.ERROR(f"Errores:                           {stats['errores']:>10,}"))

        # Mensaje final
        self.stdout.write("\n" + "=" * 80)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "⚠️  Modo DRY-RUN: No se hicieron cambios en la base de datos"
            ))
            self.stdout.write(self.style.WARNING(
                "   Ejecuta sin --dry-run para aplicar las reversiones"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Proceso completado. {stats['premios_revertidos']:,} premios revertidos."
            ))

        self.stdout.write("=" * 80 + "\n")

        # Notas importantes
        if stats['cancelaciones_incorrectas'] > 0:
            self.stdout.write(self.style.WARNING("📌 ACCIONES REALIZADAS:"))
            self.stdout.write("   • Premios revertidos: estado cambiado a 'pendiente_aprobacion'")
            self.stdout.write("   • Nota explicativa agregada al campo 'notas'")
            self.stdout.write("   • Estos premios ahora pueden ser aprobados manualmente\n")
