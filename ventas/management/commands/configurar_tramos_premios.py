"""
Management command para configurar los rangos de tramos para cada premio
según la nueva lógica de múltiples tramos
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from ventas.models import Premio


class Command(BaseCommand):
    help = 'Configura los rangos de tramos para cada premio'

    def handle(self, *args, **options):
        self.stdout.write('=== Configurando rangos de tramos para premios ===\n')

        # Definir la configuración de tramos para cada tipo de premio
        configuracion_tramos = {
            'Vale $60.000 Tina con masaje para 2': {
                'tramos': [5, 6, 7, 8],
                'tipo': 'tinas_gratis'
            },
            'Noche Gratis en Cabaña (VIP)': {
                'tramos': [9, 10, 11, 12],
                'tipo': 'noche_gratis'
            },
            'Vale Premium Alojamiento con Tinas Gratis': {
                'tramos': [13, 14, 15, 16],
                'tipo': None  # Nuevo tipo que podría necesitarse
            },
            '1 Noche Gratis en Cabaña (ELITE)': {
                'tramos': [17, 18, 19, 20],
                'tipo': None  # Nuevo tipo que podría necesitarse
            }
        }

        with transaction.atomic():
            for nombre_premio, config in configuracion_tramos.items():
                try:
                    # Buscar el premio por nombre
                    premio = Premio.objects.filter(nombre__icontains=nombre_premio.split('(')[0].strip()).first()

                    if not premio and config['tipo']:
                        # Buscar por tipo si no se encuentra por nombre
                        premio = Premio.objects.filter(tipo=config['tipo']).first()

                    if premio:
                        # Actualizar los tramos válidos
                        premio.tramos_validos = config['tramos']
                        premio.save()

                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✅ {premio.nombre}: configurado para tramos {config["tramos"]}'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠️  No se encontró premio: {nombre_premio}'
                            )
                        )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'❌ Error configurando {nombre_premio}: {str(e)}'
                        )
                    )

            # Mostrar resumen de la configuración actual
            self.stdout.write('\n=== Resumen de configuración actual ===')
            for premio in Premio.objects.filter(activo=True):
                tramos = premio.get_tramos_list()
                if tramos:
                    self.stdout.write(
                        f'• {premio.nombre}: {premio.descripcion_tramos_validos()}'
                    )

        self.stdout.write(
            self.style.SUCCESS('\n✅ Configuración de tramos completada')
        )