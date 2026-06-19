"""Recalcula fecha_programada de los SeguimientoBienestarMasaje PENDIENTES,
anclando la cadencia a la FECHA DE LA VISITA en vez de a cuándo se completó la
ficha. Arregla los seguimientos que quedaron "para enviar" antes de la visita.

Uso:
    python manage.py recalcular_seguimientos_masaje --dry-run   # ver cambios sin guardar
    python manage.py recalcular_seguimientos_masaje             # aplicar
"""

from django.core.management.base import BaseCommand

from ventas.models import SeguimientoBienestarMasaje
from ventas.services.masaje_seguimiento_service import (
    CADENCIA, fecha_programada_seguimiento,
)


class Command(BaseCommand):
    help = 'Recalcula fecha_programada de seguimientos de masaje pendientes (anclado a la visita)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostrar los cambios sin guardarlos')

    def handle(self, *args, **options):
        dry = options['dry_run']
        offsets = {tipo: offset for tipo, offset, _ in CADENCIA}

        qs = (SeguimientoBienestarMasaje.objects
              .filter(estado='pendiente', tipo_email__in=offsets.keys())
              .select_related('reserva'))
        total = qs.count()
        self.stdout.write(f'Seguimientos pendientes (cadencia) a revisar: {total}')

        cambiados = 0
        for seg in qs:
            nueva = fecha_programada_seguimiento(seg.reserva, seg.tipo_email, offsets[seg.tipo_email])
            if nueva is None or nueva == seg.fecha_programada:
                continue
            self.stdout.write(
                f'  #{seg.id} {seg.tipo_email}: {seg.fecha_programada:%Y-%m-%d %H:%M} → {nueva:%Y-%m-%d %H:%M}'
            )
            if not dry:
                seg.fecha_programada = nueva
                seg.save(update_fields=['fecha_programada'])
            cambiados += 1

        prefijo = '(dry-run) ' if dry else ''
        self.stdout.write(self.style.SUCCESS(f'{prefijo}Recalculados: {cambiados}/{total}'))
