"""
Management command para corregir premios de bienvenida generados incorrectamente
Detecta y corrige casos donde se otorgó premio de primera compra a clientes con historial
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from ventas.models import ClientePremio, Cliente
from ventas.services.tramo_service import TramoService
from ventas.services.crm_service import CRMService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Corrige premios de bienvenida generados incorrectamente para clientes con historial'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar sin hacer cambios en la BD (solo análisis)'
        )
        parser.add_argument(
            '--premio-id',
            type=int,
            help='ID específico de premio a corregir (opcional)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        premio_id = options.get('premio_id')

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🔧 CORRECCIÓN DE PREMIOS INCORRECTOS"))
        self.stdout.write("=" * 80 + "\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODO DRY-RUN: No se harán cambios en la base de datos\n"))

        # Estadísticas
        stats = {
            'total_premios_bienvenida': 0,
            'premios_analizados': 0,
            'premios_incorrectos': 0,
            'premios_corregidos': 0,
            'errores': 0,
        }

        # Buscar premios de bienvenida
        if premio_id:
            premios_query = ClientePremio.objects.filter(
                id=premio_id,
                premio__tipo='descuento_bienvenida'
            )
        else:
            premios_query = ClientePremio.objects.filter(
                premio__tipo='descuento_bienvenida',
                estado__in=['pendiente_aprobacion', 'aprobado']
            )

        premios_query = premios_query.select_related('cliente', 'premio').order_by('id')
        stats['total_premios_bienvenida'] = premios_query.count()

        self.stdout.write(f"📊 Total de premios de bienvenida a analizar: {stats['total_premios_bienvenida']:,}\n")

        if stats['total_premios_bienvenida'] == 0:
            self.stdout.write(self.style.WARNING("No hay premios de bienvenida para analizar."))
            return

        self.stdout.write("─" * 80)
        self.stdout.write("🔍 ANALIZANDO PREMIOS")
        self.stdout.write("─" * 80 + "\n")

        for premio in premios_query:
            stats['premios_analizados'] += 1
            cliente = premio.cliente

            try:
                # Obtener datos 360 del cliente
                datos_360 = CRMService.get_customer_360(cliente.id)
                total_servicios = datos_360['metricas']['total_servicios']
                gasto_total = datos_360['metricas']['gasto_total']

                # Verificar si es realmente cliente nuevo
                es_nuevo = TramoService.es_cliente_nuevo(cliente)

                if not es_nuevo or total_servicios > 1:
                    # ❌ PREMIO INCORRECTO: Cliente tiene servicios previos
                    stats['premios_incorrectos'] += 1

                    self.stdout.write(
                        self.style.ERROR(
                            f"\n❌ Premio #{premio.id} - {cliente.nombre[:40]:<40}"
                        )
                    )
                    self.stdout.write(f"   Total servicios: {total_servicios}")
                    self.stdout.write(f"   Gasto total: ${gasto_total:,.0f}")
                    self.stdout.write(f"   Estado premio: {premio.estado}")
                    self.stdout.write(f"   Fecha generado: {premio.fecha_ganado}")

                    # Calcular tramo correcto
                    tramo_actual = TramoService.calcular_tramo(float(gasto_total))
                    self.stdout.write(f"   Tramo actual: {tramo_actual}")

                    # Determinar acción correctiva
                    if not dry_run:
                        with transaction.atomic():
                            # Anular premio incorrecto
                            premio.estado = 'cancelado'
                            premio.notas = (
                                f"Cancelado automáticamente: Cliente tiene {total_servicios} servicios. "
                                f"No es cliente nuevo. Sistema corregido el {timezone.now().date()}"
                            )
                            premio.save()

                            self.stdout.write(
                                self.style.WARNING(
                                    f"   ✅ Premio cancelado y marcado con nota explicativa"
                                )
                            )

                            # Actualizar tramo del cliente (esto puede generar premio correcto si está en hito)
                            resultado = TramoService.actualizar_tramo_cliente(cliente)

                            if resultado['hito_alcanzado'] and resultado['premio_generado']:
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"   🎉 Nuevo premio generado: {resultado['premio_generado'].premio.nombre} "
                                        f"(Tramo {resultado['tramo_actual']})"
                                    )
                                )
                            else:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"   ℹ️  Tramo actualizado a {resultado['tramo_actual']}. "
                                        f"No genera premio (no está en hito o ya tiene premio de ese tipo)"
                                    )
                                )

                            stats['premios_corregidos'] += 1

                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"   🔄 Acción sugerida: Cancelar premio y actualizar a Tramo {tramo_actual}"
                            )
                        )

                else:
                    # ✅ Premio correcto
                    self.stdout.write(
                        f"  ✅ Premio #{premio.id} - {cliente.nombre[:40]:<40} - Correcto (cliente nuevo)"
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

        self.stdout.write(f"Total premios bienvenida:         {stats['total_premios_bienvenida']:>10,}")
        self.stdout.write(f"Premios analizados:               {stats['premios_analizados']:>10,}")
        self.stdout.write(
            self.style.ERROR(f"Premios incorrectos:              {stats['premios_incorrectos']:>10,}")
        )

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Premios corregidos:               {stats['premios_corregidos']:>10,}")
            )

        if stats['errores'] > 0:
            self.stdout.write(self.style.ERROR(f"Errores:                          {stats['errores']:>10,}"))

        # Mensaje final
        self.stdout.write("\n" + "=" * 80)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "⚠️  Modo DRY-RUN: No se hicieron cambios en la base de datos"
            ))
            self.stdout.write(self.style.WARNING(
                "   Ejecuta sin --dry-run para aplicar las correcciones"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Proceso completado. {stats['premios_corregidos']:,} premios corregidos."
            ))

        self.stdout.write("=" * 80 + "\n")

        # Notas importantes
        if stats['premios_incorrectos'] > 0:
            self.stdout.write(self.style.WARNING("📌 ACCIONES REALIZADAS:"))
            self.stdout.write("   • Premios incorrectos: estado cambiado a 'cancelado'")
            self.stdout.write("   • Nota explicativa agregada al campo 'notas'")
            self.stdout.write("   • Tramo del cliente actualizado automáticamente")
            self.stdout.write("   • Si cliente está en hito, se generó premio correcto\n")
