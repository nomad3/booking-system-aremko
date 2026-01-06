# -*- coding: utf-8 -*-
"""
Management command para gestionar horarios de servicios (slots_disponibles)

Uso:
    # Ver horarios actuales de todos los servicios
    python manage.py gestionar_horarios_servicios

    # Ver horarios de una categoría específica
    python manage.py gestionar_horarios_servicios --categoria="Tinas Calientes"

    # Configurar horarios para un servicio específico
    python manage.py gestionar_horarios_servicios --servicio="Tina Calbuco" --slots="12:00,14:30,17:00,19:30,22:00"

    # Configurar horarios para todos los servicios de una categoría
    python manage.py gestionar_horarios_servicios --categoria="Masajes" --slots="10:30,11:45,13:00,14:15,15:30,16:45,18:00,19:15,20:30,21:45"
"""

from django.core.management.base import BaseCommand
from ventas.models import Servicio, CategoriaServicio


class Command(BaseCommand):
    help = 'Gestiona los horarios (slots_disponibles) de los servicios'

    def add_arguments(self, parser):
        parser.add_argument(
            '--categoria',
            type=str,
            help='Nombre de la categoría de servicios'
        )
        parser.add_argument(
            '--servicio',
            type=str,
            help='Nombre exacto del servicio'
        )
        parser.add_argument(
            '--slots',
            type=str,
            help='Horarios separados por coma (ej: "12:00,14:30,17:00,19:30,22:00")'
        )

    def handle(self, *args, **options):
        categoria_nombre = options.get('categoria')
        servicio_nombre = options.get('servicio')
        slots_str = options.get('slots')

        # MODO 1: Configurar horarios de un servicio específico
        if servicio_nombre and slots_str:
            self.configurar_servicio(servicio_nombre, slots_str)
            return

        # MODO 2: Configurar horarios de toda una categoría
        if categoria_nombre and slots_str:
            self.configurar_categoria(categoria_nombre, slots_str)
            return

        # MODO 3: Ver horarios actuales
        self.mostrar_horarios(categoria_nombre)

    def configurar_servicio(self, servicio_nombre, slots_str):
        """Configura horarios de un servicio específico"""
        try:
            servicio = Servicio.objects.get(nombre=servicio_nombre)
        except Servicio.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Servicio "{servicio_nombre}" no encontrado'))
            return

        # Parsear slots
        slots = [slot.strip() for slot in slots_str.split(',')]

        # Actualizar servicio
        servicio.slots_disponibles = slots
        servicio.save()

        self.stdout.write(self.style.SUCCESS(f'\n✅ Horarios actualizados para "{servicio.nombre}"'))
        self.stdout.write(f'   Slots: {slots}')

    def configurar_categoria(self, categoria_nombre, slots_str):
        """Configura horarios de todos los servicios de una categoría"""
        try:
            categoria = CategoriaServicio.objects.get(nombre__iexact=categoria_nombre)
        except CategoriaServicio.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Categoría "{categoria_nombre}" no encontrada'))
            self.stdout.write('\nCategorías disponibles:')
            for cat in CategoriaServicio.objects.all():
                self.stdout.write(f'  - {cat.nombre}')
            return

        # Parsear slots
        slots = [slot.strip() for slot in slots_str.split(',')]

        # Actualizar todos los servicios activos de la categoría
        servicios = Servicio.objects.filter(categoria=categoria, activo=True)

        if not servicios.exists():
            self.stdout.write(self.style.WARNING(f'⚠️ No hay servicios activos en la categoría "{categoria.nombre}"'))
            return

        count = 0
        for servicio in servicios:
            servicio.slots_disponibles = slots
            servicio.save()
            count += 1
            self.stdout.write(self.style.SUCCESS(f'✅ {servicio.nombre}'))

        self.stdout.write(self.style.SUCCESS(f'\n✅ {count} servicio(s) actualizados con los horarios: {slots}'))

    def mostrar_horarios(self, categoria_nombre=None):
        """Muestra los horarios actuales de los servicios"""
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("📅 HORARIOS DE SERVICIOS (slots_disponibles)"))
        self.stdout.write("=" * 80)

        # Filtrar por categoría si se especifica
        if categoria_nombre:
            try:
                categoria = CategoriaServicio.objects.get(nombre__iexact=categoria_nombre)
                categorias = [categoria]
            except CategoriaServicio.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'\n❌ Categoría "{categoria_nombre}" no encontrada'))
                return
        else:
            # Mostrar solo categorías principales
            categorias = CategoriaServicio.objects.filter(
                nombre__in=[
                    'Tinas Calientes',
                    'Tinas Empresariales',
                    'Masajes',
                    'Cabañas',
                    'Packs y Promociones'
                ]
            )

        for categoria in categorias:
            servicios = Servicio.objects.filter(
                categoria=categoria,
                activo=True,
                visible_en_matriz=True
            ).order_by('nombre')

            if not servicios.exists():
                continue

            self.stdout.write(f"\n📂 {categoria.nombre}")
            self.stdout.write("-" * 80)

            for servicio in servicios:
                if servicio.slots_disponibles and len(servicio.slots_disponibles) > 0:
                    # Tiene horarios configurados
                    slots_str = ', '.join(servicio.slots_disponibles)
                    self.stdout.write(f"  ✅ {servicio.nombre}")
                    self.stdout.write(f"     Horarios: {slots_str}")
                else:
                    # NO tiene horarios configurados
                    self.stdout.write(f"  ⚠️  {servicio.nombre}")
                    self.stdout.write(self.style.WARNING(f"     Sin horarios configurados - usará valores por defecto"))

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("💡 EJEMPLOS DE USO"))
        self.stdout.write("=" * 80)
        self.stdout.write('\nConfigurar horarios de una tina específica:')
        self.stdout.write('  python manage.py gestionar_horarios_servicios --servicio="Tina Calbuco" --slots="12:00,14:30,17:00,19:30,22:00"')
        self.stdout.write('\nConfigurar horarios de todas las tinas:')
        self.stdout.write('  python manage.py gestionar_horarios_servicios --categoria="Tinas Calientes" --slots="12:00,14:30,17:00,19:30,22:00"')
        self.stdout.write('\nConfigurar horarios de masajes:')
        self.stdout.write('  python manage.py gestionar_horarios_servicios --categoria="Masajes" --slots="10:30,11:45,13:00,14:15,15:30,16:45,18:00,19:15,20:30,21:45"')
        self.stdout.write('')
