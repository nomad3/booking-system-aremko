"""
Management command para enviar emails de premios aprobados
Envía UN premio aprobado por ejecución (para usar con cron cada 30 min)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from ventas.services.email_premio_service import EmailPremioService
from ventas.models import ClientePremio
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envía el próximo premio aprobado pendiente de envío'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=1,
            help='Número de premios a enviar en esta ejecución (default: 1)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular envío sin enviar emails reales'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        dry_run = options['dry_run']

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📧 ENVÍO DE PREMIOS APROBADOS"))
        self.stdout.write("=" * 80 + "\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODO DRY-RUN: No se enviarán emails reales\n"))

        # Obtener premios aprobados pendientes de envío
        premios_pendientes = ClientePremio.objects.filter(
            estado='aprobado'
        ).select_related('cliente', 'premio').order_by('fecha_aprobacion')[:limit]

        total_pendientes = ClientePremio.objects.filter(estado='aprobado').count()

        self.stdout.write(f"📊 Premios aprobados pendientes de envío: {total_pendientes:,}")
        self.stdout.write(f"📨 Límite para esta ejecución: {limit}\n")

        if premios_pendientes.count() == 0:
            self.stdout.write(self.style.WARNING("ℹ️  No hay premios aprobados pendientes de envío."))
            self.stdout.write("=" * 80 + "\n")
            return

        # Procesar cada premio
        self.stdout.write("─" * 80)
        self.stdout.write("📤 PROCESANDO ENVÍOS")
        self.stdout.write("─" * 80 + "\n")

        stats = {
            'procesados': 0,
            'enviados': 0,
            'errores': 0,
        }

        for premio in premios_pendientes:
            stats['procesados'] += 1

            self.stdout.write(
                f"\n{stats['procesados']}. Cliente: {premio.cliente.nombre[:40]:<40}"
            )
            self.stdout.write(f"   Email: {premio.cliente.email}")
            self.stdout.write(f"   Premio: {premio.premio.nombre}")
            self.stdout.write(f"   Fecha aprobación: {premio.fecha_aprobacion.strftime('%Y-%m-%d %H:%M')}")

            if dry_run:
                self.stdout.write(self.style.WARNING("   🔸 [DRY-RUN] Email NO enviado"))
                stats['enviados'] += 1
            else:
                try:
                    # Enviar email
                    resultado = EmailPremioService.enviar_premio(
                        cliente_premio_id=premio.id,
                        force=False  # Respetar rate limiting
                    )

                    if resultado['success']:
                        stats['enviados'] += 1
                        wait_time = resultado['wait_time']

                        self.stdout.write(
                            self.style.SUCCESS(f"   ✅ Email enviado exitosamente")
                        )

                        if wait_time > 0:
                            self.stdout.write(
                                self.style.WARNING(f"   ⏱️  Rate limiting: Esperó {wait_time:.0f} segundos")
                            )
                    else:
                        stats['errores'] += 1
                        self.stdout.write(
                            self.style.ERROR(f"   ❌ Error: {resultado['message']}")
                        )

                except Exception as e:
                    stats['errores'] += 1
                    self.stdout.write(
                        self.style.ERROR(f"   ❌ Excepción: {str(e)}")
                    )
                    logger.error(f"Error enviando premio {premio.id}: {e}", exc_info=True)

        # Reporte final
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 REPORTE FINAL"))
        self.stdout.write("=" * 80 + "\n")

        self.stdout.write(f"Premios procesados:               {stats['procesados']:>10,}")
        self.stdout.write(self.style.SUCCESS(f"Emails enviados exitosamente:     {stats['enviados']:>10,}"))

        if stats['errores'] > 0:
            self.stdout.write(self.style.ERROR(f"Errores:                          {stats['errores']:>10,}"))

        # Premios restantes
        premios_restantes = total_pendientes - stats['enviados']
        if premios_restantes > 0:
            self.stdout.write(f"\nPremios restantes por enviar:     {premios_restantes:>10,}")

        self.stdout.write("\n" + "=" * 80)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "⚠️  Modo DRY-RUN: No se enviaron emails reales"
            ))
        else:
            if stats['enviados'] > 0:
                self.stdout.write(self.style.SUCCESS(
                    f"✅ Proceso completado. {stats['enviados']:,} email(s) enviado(s)."
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    "⚠️  No se enviaron emails. Revisa los errores arriba."
                ))

        self.stdout.write("=" * 80 + "\n")

        # Notas
        self.stdout.write(self.style.WARNING("📌 NOTAS:"))
        self.stdout.write("   • Este comando debe ejecutarse cada 30 minutos (cron)")
        self.stdout.write("   • Envía 1 premio por ejecución (respeta rate limiting de 30 min)")
        self.stdout.write("   • Solo procesa premios con estado='aprobado'")
        self.stdout.write("   • Después del envío, estado cambia a 'enviado' automáticamente\n")
