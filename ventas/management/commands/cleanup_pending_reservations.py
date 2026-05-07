"""Marca como 'expirado' las PendingReservation que excedieron su TTL sin confirmacion.

Se ejecuta como Render Cron Job (recomendado cada 30 min).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from ventas.models import PendingReservation


class Command(BaseCommand):
    help = 'Marca como expirados los PendingReservation cuyo TTL ya paso sin confirmacion de pago Flow.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra cuantos serian afectados, no actualiza nada.',
        )

    def handle(self, *args, **options):
        ahora = timezone.now()
        qs = PendingReservation.objects.filter(estado='iniciado', expires_at__lt=ahora)
        count = qs.count()

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'[dry-run] {count} pendings expirarian'))
            for p in qs[:20]:
                self.stdout.write(f'  - #{p.id} {p.cliente.nombre} ${p.monto:,} (creado {p.created_at})')
            return

        if count == 0:
            self.stdout.write('No hay pendings expirados.')
            return

        updated = qs.update(estado='expirado', updated_at=ahora)
        self.stdout.write(self.style.SUCCESS(f'{updated} PendingReservation marcadas como expiradas.'))
