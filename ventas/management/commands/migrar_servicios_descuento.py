"""Mueve los servicios de descuento fuera de la categoría/tipo "Tinas".

Aremko usaba un servicio llamado "Descuento_Servicios" (precio_unitario negativo)
para aplicar descuentos sobre reservas. Estos servicios tenían:
  - categoria = "Tinas"
  - tipo_servicio = 'tina'

Esto distorsiona los reportes que agrupan por tipo_servicio (las ventas de Tinas
aparecian artificialmente bajas porque incluian los descuentos).

Este comando reasigna:
  - categoria → "Descuento_Servicio" (la nueva categoría que Jorge creó)
  - tipo_servicio → 'otro'

Modo seguro: dry-run por default. Aplica cambios solo con --apply.

Uso:
    python manage.py migrar_servicios_descuento              # dry-run
    python manage.py migrar_servicios_descuento --apply      # aplica
    python manage.py migrar_servicios_descuento --apply --pattern descuento
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ventas.models import Servicio, CategoriaServicio


CATEGORIA_DESTINO_NOMBRE = 'Descuento_Servicio'
TIPO_DESTINO = 'otro'
PATTERN_DEFAULT = 'descuento_servicios'


class Command(BaseCommand):
    help = 'Mueve servicios de descuento fuera de la categoría/tipo Tinas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Aplica los cambios. Sin este flag, solo muestra qué cambiaría (dry-run).',
        )
        parser.add_argument(
            '--pattern', default=PATTERN_DEFAULT,
            help=f'Patrón de búsqueda en el nombre del servicio (icontains). Default: "{PATTERN_DEFAULT}".',
        )

    def handle(self, *args, **opts):
        apply_changes = opts['apply']
        pattern = opts['pattern']

        # Validar que la categoría destino existe.
        categoria_destino = CategoriaServicio.objects.filter(
            nombre__iexact=CATEGORIA_DESTINO_NOMBRE
        ).first()
        if not categoria_destino:
            raise CommandError(
                f'La categoría destino "{CATEGORIA_DESTINO_NOMBRE}" no existe. '
                f'Créala primero en /admin/ventas/categoriaservicio/.'
            )

        self.stdout.write(self.style.NOTICE(
            f'Categoría destino: "{categoria_destino.nombre}" (id={categoria_destino.id})'
        ))
        self.stdout.write(self.style.NOTICE(
            f'Patrón de búsqueda: nombre icontains "{pattern}"'
        ))
        self.stdout.write('')

        # Buscar servicios candidatos.
        candidatos = Servicio.objects.filter(nombre__icontains=pattern).select_related('categoria')

        if not candidatos.exists():
            self.stdout.write(self.style.WARNING('No se encontraron servicios candidatos.'))
            return

        self.stdout.write(self.style.NOTICE(f'Encontrados {candidatos.count()} servicio(s):'))
        self.stdout.write('')
        header = f'  {"ID":>5}  {"NOMBRE":<35}  {"CATEGORÍA ACTUAL":<25}  {"TIPO ACTUAL":<10}  {"→ CAMBIO":<30}'
        self.stdout.write(header)
        self.stdout.write('  ' + '-' * (len(header) - 2))

        a_modificar = []
        for s in candidatos:
            cat_actual = s.categoria.nombre if s.categoria else '(sin categoría)'
            tipo_actual = s.tipo_servicio
            cambia_cat = (not s.categoria) or (s.categoria_id != categoria_destino.id)
            cambia_tipo = (tipo_actual != TIPO_DESTINO)
            cambios = []
            if cambia_cat:
                cambios.append(f'cat→{CATEGORIA_DESTINO_NOMBRE}')
            if cambia_tipo:
                cambios.append(f'tipo→{TIPO_DESTINO}')
            cambio_str = ', '.join(cambios) if cambios else '(ya estaba OK)'
            self.stdout.write(
                f'  {s.id:>5}  {s.nombre[:35]:<35}  {cat_actual[:25]:<25}  {tipo_actual:<10}  {cambio_str}'
            )
            if cambios:
                a_modificar.append(s)

        self.stdout.write('')
        if not a_modificar:
            self.stdout.write(self.style.SUCCESS('Nada que cambiar — todos los servicios ya están bien.'))
            return

        self.stdout.write(self.style.NOTICE(f'Total a modificar: {len(a_modificar)}'))

        if not apply_changes:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'DRY-RUN: no se modificó nada. Para aplicar los cambios, ejecutá:'
            ))
            self.stdout.write(self.style.WARNING(
                '  python manage.py migrar_servicios_descuento --apply'
            ))
            return

        # Aplicar cambios en una sola transacción para poder revertir si algo falla.
        with transaction.atomic():
            for s in a_modificar:
                s.categoria = categoria_destino
                s.tipo_servicio = TIPO_DESTINO
                s.save(update_fields=['categoria', 'tipo_servicio'])

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'OK — {len(a_modificar)} servicio(s) actualizado(s).'
        ))
        self.stdout.write(self.style.SUCCESS(
            'Los próximos reportes de aremko-cli (by-family, by-family-mtd, weekly-breakdown) '
            'ya van a reflejar este cambio. Reservas históricas NO se modifican.'
        ))
