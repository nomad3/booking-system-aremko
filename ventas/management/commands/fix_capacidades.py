"""
Management command para corregir las capacidades máximas de servicios.

Solo los masajes de "Relajación o Descontracturante" deben tener capacidad_maxima=2
Todos los demás servicios (tinas, cabañas, otros masajes) deben tener capacidad_maxima=1
"""

from django.core.management.base import BaseCommand
from ventas.models import Servicio, CategoriaServicio


class Command(BaseCommand):
    help = 'Corrige las capacidades máximas de servicios: solo masajes de relajación tienen capacidad 2'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Iniciando corrección de capacidades...'))

        # Estadísticas
        actualizados_a_1 = 0
        actualizados_a_2 = 0
        sin_cambios = 0

        # Obtener todos los servicios activos
        servicios = Servicio.objects.filter(activo=True)

        for servicio in servicios:
            nombre_lower = servicio.nombre.lower()

            # Determinar si es un masaje de relajación/descontracturante
            es_masaje_multiple = (
                ('relajación' in nombre_lower or 'relajacion' in nombre_lower or 'descontracturante' in nombre_lower)
                and 'masaje' in nombre_lower
            )

            if es_masaje_multiple:
                # Este servicio DEBE tener capacidad_maxima=2
                if servicio.capacidad_maxima != 2:
                    self.stdout.write(
                        f'  Actualizando "{servicio.nombre}": {servicio.capacidad_maxima} -> 2'
                    )
                    servicio.capacidad_maxima = 2
                    servicio.save()
                    actualizados_a_2 += 1
                else:
                    sin_cambios += 1
            else:
                # Todos los demás servicios DEBEN tener capacidad_maxima=1
                if servicio.capacidad_maxima != 1:
                    self.stdout.write(
                        f'  Actualizando "{servicio.nombre}": {servicio.capacidad_maxima} -> 1'
                    )
                    servicio.capacidad_maxima = 1
                    servicio.save()
                    actualizados_a_1 += 1
                else:
                    sin_cambios += 1

        # Mostrar resumen
        self.stdout.write(self.style.SUCCESS('\n=== RESUMEN ==='))
        self.stdout.write(f'Servicios actualizados a capacidad 1: {actualizados_a_1}')
        self.stdout.write(f'Servicios actualizados a capacidad 2: {actualizados_a_2}')
        self.stdout.write(f'Servicios sin cambios: {sin_cambios}')
        self.stdout.write(self.style.SUCCESS('\n¡Corrección completada!'))
