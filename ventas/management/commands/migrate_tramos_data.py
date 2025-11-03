"""
Management command para migrar datos de tramo_hito a tramos_validos
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from ventas.models import Premio


class Command(BaseCommand):
    help = 'Migra los datos de tramo_hito a tramos_validos'

    def handle(self, *args, **options):
        self.stdout.write('=== Migrando datos de tramo_hito a tramos_validos ===\n')

        try:
            with transaction.atomic():
                premios_migrados = 0

                for premio in Premio.objects.all():
                    if premio.tramo_hito and not premio.tramos_validos:
                        premio.tramos_validos = [premio.tramo_hito]
                        premio.save(update_fields=['tramos_validos'])
                        premios_migrados += 1
                        self.stdout.write(
                            f'✅ {premio.nombre}: tramo_hito {premio.tramo_hito} → tramos_validos {premio.tramos_validos}'
                        )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✅ Migración completada: {premios_migrados} premios actualizados'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'❌ Error durante la migración: {e}'
                )
            )