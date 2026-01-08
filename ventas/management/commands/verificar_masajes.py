"""
Comando para verificar la configuración de servicios de masajes
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from ventas.models import Servicio, CategoriaServicio
import json


class Command(BaseCommand):
    help = 'Verifica la configuración de los servicios de masajes'

    def handle(self, *args, **options):
        # Buscar categoría de masajes
        cat_masajes = CategoriaServicio.objects.filter(nombre__icontains='masaje').first()

        if not cat_masajes:
            self.stdout.write(self.style.ERROR('No se encontró categoría de masajes'))
            return

        self.stdout.write(self.style.SUCCESS(f'\nCategoría: {cat_masajes.nombre} (ID: {cat_masajes.id})'))
        self.stdout.write('=' * 80)

        # Obtener TODOS los servicios de masajes (activos e inactivos)
        masajes = Servicio.objects.filter(categoria=cat_masajes).order_by('nombre')

        for masaje in masajes:
            self.stdout.write(f'\n📋 Servicio: {masaje.nombre} (ID: {masaje.id})')
            self.stdout.write(f'   - Activo: {masaje.activo}')
            self.stdout.write(f'   - Visible en matriz: {masaje.visible_en_matriz}')

            if masaje.slots_disponibles:
                self.stdout.write(f'   - Slots disponibles: {json.dumps(masaje.slots_disponibles, indent=6, ensure_ascii=False)}')
            else:
                self.stdout.write(self.style.WARNING('   - Slots disponibles: VACÍO o NULL'))

        self.stdout.write('\n' + '=' * 80)

        # Mostrar resumen
        total = masajes.count()
        activos = masajes.filter(activo=True).count()
        visibles = masajes.filter(visible_en_matriz=True).count()
        con_slots = masajes.filter(slots_disponibles__isnull=False).exclude(slots_disponibles={}).count()

        self.stdout.write(f'\n📊 RESUMEN:')
        self.stdout.write(f'   Total servicios: {total}')
        self.stdout.write(f'   Activos: {activos}')
        self.stdout.write(f'   Visibles en matriz: {visibles}')
        self.stdout.write(f'   Con slots configurados: {con_slots}')

        # Verificar servicios con problemas
        problemas = masajes.filter(
            activo=True,
            visible_en_matriz=True
        ).filter(
            Q(slots_disponibles__isnull=True) | Q(slots_disponibles={})
        )

        if problemas.exists():
            self.stdout.write(self.style.WARNING(f'\n⚠️  SERVICIOS CON PROBLEMAS (activos y visibles pero sin slots):'))
            for p in problemas:
                self.stdout.write(f'   - {p.nombre} (ID: {p.id})')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Todos los servicios activos y visibles tienen slots configurados'))
