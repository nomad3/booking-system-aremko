"""
Management command para poblar el campo max_servicios_simultaneos en servicios existentes.

IMPORTANTE: Este campo NO es la capacidad de personas, sino la cantidad de veces
que un servicio puede reservarse en el mismo slot/horario.

Reglas:
- Masajes de "Relajación" o "Descontracturante": 2 servicios simultáneos (2 masajistas)
- Todos los demás servicios (tinas, cabañas, otros masajes): 1 servicio por slot
"""

from django.core.management.base import BaseCommand
from ventas.models import Servicio


class Command(BaseCommand):
    help = 'Pobla el campo max_servicios_simultaneos para servicios existentes'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Iniciando población de max_servicios_simultaneos...'))

        # Estadísticas
        actualizados_a_1 = 0
        actualizados_a_2 = 0

        # Obtener todos los servicios
        servicios = Servicio.objects.all()

        for servicio in servicios:
            nombre_lower = servicio.nombre.lower()

            # Determinar si es un masaje de relajación/descontracturante (capacidad para 2 servicios simultáneos)
            es_masaje_multiple = (
                ('relajación' in nombre_lower or 'relajacion' in nombre_lower or 'descontracturante' in nombre_lower)
                and 'masaje' in nombre_lower
            )

            if es_masaje_multiple:
                # Este servicio permite 2 servicios simultáneos (2 masajistas)
                self.stdout.write(
                    f'  ✓ "{servicio.nombre}": max_servicios_simultaneos = 2 (masaje con 2 masajistas)'
                )
                servicio.max_servicios_simultaneos = 2
                servicio.save()
                actualizados_a_2 += 1
            else:
                # Todos los demás servicios solo permiten 1 reserva por slot
                self.stdout.write(
                    f'  ✓ "{servicio.nombre}": max_servicios_simultaneos = 1'
                )
                servicio.max_servicios_simultaneos = 1
                servicio.save()
                actualizados_a_1 += 1

        # Mostrar resumen
        self.stdout.write(self.style.SUCCESS('\n=== RESUMEN ==='))
        self.stdout.write(f'Servicios con max_servicios_simultaneos = 1: {actualizados_a_1}')
        self.stdout.write(f'Servicios con max_servicios_simultaneos = 2: {actualizados_a_2}')
        self.stdout.write(self.style.SUCCESS('\n¡Población completada!'))

        # Mostrar servicios con 2 masajistas
        if actualizados_a_2 > 0:
            self.stdout.write(self.style.WARNING('\nServicios que permiten 2 reservas simultáneas:'))
            masajes_multiples = Servicio.objects.filter(max_servicios_simultaneos=2)
            for masaje in masajes_multiples:
                self.stdout.write(f'  - {masaje.nombre}')
