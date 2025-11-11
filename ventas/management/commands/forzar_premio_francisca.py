"""
Comando para FORZAR la generación del premio para Francisca Cuevas Parga
Genera el premio directamente usando PremioService sin depender del cambio de tramo
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from ventas.models import Cliente
from ventas.services.tramo_service import TramoService
from ventas.services.premio_service import PremioService


class Command(BaseCommand):
    help = 'Fuerza la generación del Premio Hito 10 para Francisca Cuevas Parga'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sin hacer cambios'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🎁 FORZAR GENERACIÓN DE PREMIO - FRANCISCA"))
        self.stdout.write("=" * 80 + "\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODO DRY-RUN: No se harán cambios\n"))

        # Buscar a Francisca
        francisca = Cliente.objects.filter(nombre__icontains="Francisca Cuevas").first()

        if not francisca:
            self.stdout.write(self.style.ERROR("❌ No se encontró a Francisca Cuevas"))
            return

        self.stdout.write(f"Cliente: {francisca.nombre}")
        self.stdout.write(f"ID: {francisca.id}\n")

        # Calcular gasto total y tramo
        gasto_total = TramoService.calcular_gasto_cliente(francisca)
        tramo_actual = TramoService.calcular_tramo(float(gasto_total))

        self.stdout.write(f"Gasto total: ${gasto_total:,.0f}")
        self.stdout.write(f"Tramo calculado: {tramo_actual}")
        self.stdout.write(f"Rango del tramo: ${(tramo_actual-1)*50000 + 1:,} - ${tramo_actual*50000:,}\n")

        # Verificar que está en rango de Premio Hito 10
        if tramo_actual not in [9, 10, 11, 12]:
            self.stdout.write(self.style.ERROR(
                f"❌ Tramo {tramo_actual} NO está en rango de Premio Hito 10 [9,10,11,12]"
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f"✅ Tramo {tramo_actual} está en rango del Premio Hito 10 [9,10,11,12]\n"
        ))

        # Verificar si puede recibir premio de este tipo
        puede_recibir = PremioService.puede_recibir_premio_tipo(francisca, 'premio_hito_10')

        if not puede_recibir:
            self.stdout.write(self.style.WARNING(
                "⚠️  Cliente ya tiene un premio de tipo 'premio_hito_10' activo"
            ))
            self.stdout.write("   No se puede generar otro premio del mismo tipo\n")
            return

        self.stdout.write("✅ Cliente puede recibir Premio Hito 10\n")

        # Generar premio directamente
        if not dry_run:
            with transaction.atomic():
                self.stdout.write("Ejecutando PremioService.generar_premio_por_hito()...\n")

                premio_generado = PremioService.generar_premio_por_hito(
                    cliente=francisca,
                    tramo_actual=tramo_actual,
                    tramo_anterior=1,  # Era Tramo 1 originalmente
                    gasto_total=gasto_total
                )

                if premio_generado:
                    self.stdout.write(self.style.SUCCESS(
                        f"\n🎉 PREMIO GENERADO EXITOSAMENTE:\n"
                    ))
                    self.stdout.write(f"  ID: #{premio_generado.id}")
                    self.stdout.write(f"  Nombre: {premio_generado.premio.nombre}")
                    self.stdout.write(f"  Tipo: {premio_generado.premio.tipo}")
                    self.stdout.write(f"  Estado: {premio_generado.estado}")
                    self.stdout.write(f"  Tramo al ganar: {premio_generado.tramo_al_ganar}")
                    self.stdout.write(f"  Tramo anterior: {premio_generado.tramo_anterior}")
                    self.stdout.write(f"  Gasto total: ${premio_generado.gasto_total_al_ganar:,.0f}")
                    self.stdout.write(f"  Fecha ganado: {premio_generado.fecha_ganado}")
                    self.stdout.write(f"  Fecha expiración: {premio_generado.fecha_expiracion}")
                else:
                    self.stdout.write(self.style.ERROR(
                        "\n❌ No se pudo generar el premio"
                    ))
                    self.stdout.write("   Posibles causas:")
                    self.stdout.write("   - No existe premio activo de tipo 'premio_hito_10'")
                    self.stdout.write("   - Cliente ya tiene premio de ese tipo")
                    self.stdout.write("   - Error en la base de datos")
        else:
            self.stdout.write(self.style.WARNING(
                "\n⚠️  DRY-RUN: No se ejecutó PremioService.generar_premio_por_hito()"
            ))
            self.stdout.write("   Ejecuta sin --dry-run para generar el premio")

        self.stdout.write("\n" + "=" * 80)
