"""
Comando para generar el premio correcto para Francisca Cuevas Parga
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from ventas.models import Cliente
from ventas.services.tramo_service import TramoService


class Command(BaseCommand):
    help = 'Genera el premio correcto para Francisca Cuevas Parga (Tramo 9 → Premio Hito 10)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sin hacer cambios'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🎁 GENERAR PREMIO CORRECTO PARA FRANCISCA"))
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

        # Verificar si está en un hito
        if tramo_actual not in TramoService.HITOS_PREMIO:
            # Verificar si está en el rango de algún hito
            if 5 <= tramo_actual <= 8:
                hito = 5
            elif 9 <= tramo_actual <= 12:
                hito = 10
            elif 13 <= tramo_actual <= 16:
                hito = 15
            elif 17 <= tramo_actual <= 20:
                hito = 20
            else:
                self.stdout.write(self.style.WARNING(
                    f"⚠️  Tramo {tramo_actual} no está en ningún rango de premio"
                ))
                return

            self.stdout.write(self.style.SUCCESS(
                f"✅ Tramo {tramo_actual} está en rango del Premio Hito {hito}"
            ))
        else:
            hito = tramo_actual

        self.stdout.write(f"Premio que corresponde: Hito {hito}\n")

        # Actualizar tramo del cliente (esto debería generar el premio automáticamente)
        if not dry_run:
            with transaction.atomic():
                self.stdout.write("Ejecutando TramoService.actualizar_tramo_cliente()...")
                resultado = TramoService.actualizar_tramo_cliente(francisca)

                self.stdout.write(f"\nResultado:")
                self.stdout.write(f"  Tramo anterior: {resultado['tramo_anterior']}")
                self.stdout.write(f"  Tramo actual: {resultado['tramo_actual']}")
                self.stdout.write(f"  Cambio de tramo: {resultado['cambio']}")
                self.stdout.write(f"  Hito alcanzado: {resultado['hito_alcanzado']}")
                self.stdout.write(f"  Gasto total: ${resultado['gasto_total']:,.0f}")

                if resultado['premio_generado']:
                    premio = resultado['premio_generado']
                    self.stdout.write(self.style.SUCCESS(
                        f"\n🎉 Premio generado exitosamente:"
                    ))
                    self.stdout.write(f"  ID: #{premio.id}")
                    self.stdout.write(f"  Nombre: {premio.premio.nombre}")
                    self.stdout.write(f"  Tipo: {premio.premio.tipo}")
                    self.stdout.write(f"  Estado: {premio.estado}")
                    self.stdout.write(f"  Tramo: {premio.tramo_al_ganar}")
                else:
                    if not resultado['hito_alcanzado']:
                        self.stdout.write(self.style.WARNING(
                            f"\n⚠️  No se generó premio: No alcanzó un hito"
                        ))
                    else:
                        self.stdout.write(self.style.WARNING(
                            f"\n⚠️  No se generó premio: Posiblemente ya tiene un premio de este tipo"
                        ))
        else:
            self.stdout.write(self.style.WARNING(
                "\n⚠️  DRY-RUN: No se ejecutó actualizar_tramo_cliente()"
            ))
            self.stdout.write("   Ejecuta sin --dry-run para generar el premio")

        self.stdout.write("\n" + "=" * 80)
