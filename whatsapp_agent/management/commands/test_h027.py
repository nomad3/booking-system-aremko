from django.core.management.base import BaseCommand
from whatsapp_agent.availability import disponibilidad_alojamiento_multinoche


class Command(BaseCommand):
    help = 'Prueba H-027: disponibilidad de alojamiento multi-noche'

    def handle(self, *args, **options):
        # Test 1: Rango de fechas (25 al 30 de julio 2026)
        self.stdout.write('\n=== TEST 1: Del 25 al 30 de julio (3 noches) ===')
        result = disponibilidad_alojamiento_multinoche(
            fecha_llegada='2026-07-25',
            personas=2,
            noches=5,  # 25,26,27,28,29 (salida 30)
        )
        self.stdout.write(f'Resultado: {result}')

        # Test 2: Con fecha_salida en lugar de noches
        self.stdout.write('\n=== TEST 2: Con fecha_salida ===')
        result = disponibilidad_alojamiento_multinoche(
            fecha_llegada='2026-07-25',
            personas=2,
            fecha_salida='2026-07-30',
        )
        self.stdout.write(f'Resultado: {result}')

        # Test 3: Próximos 7 días desde hoy
        self.stdout.write('\n=== TEST 3: Próximos 7 días desde el 18 de junio ===')
        result = disponibilidad_alojamiento_multinoche(
            fecha_llegada='2026-06-18',
            personas=2,
            noches=7,
        )
        self.stdout.write(f'Resultado: {result}')

        self.stdout.write('\n✅ Pruebas completadas')
