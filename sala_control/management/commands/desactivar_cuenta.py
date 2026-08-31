"""Desactiva (o reactiva) una cuenta de usuario, mostrando antes qué toca.

Desactivar NO borra: pone `is_active=False`. La persona no puede entrar, pero
todo lo que registró sigue en su lugar y con su nombre — y se puede volver
atrás con --reactivar. Borrar un usuario, en cambio, arrastra o rompe lo que
firmó, y no tiene vuelta.

Uso:
  python manage.py desactivar_cuenta --username admin --solo-mirar
  python manage.py desactivar_cuenta --username admin
  python manage.py desactivar_cuenta --username admin --reactivar
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Desactiva o reactiva una cuenta, informando qué actividad tiene.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--reactivar', action='store_true')
        parser.add_argument('--solo-mirar', action='store_true',
                            help='No cambia nada: solo informa.')

    def handle(self, *args, **opts):
        User = get_user_model()
        try:
            u = User.objects.get(username=opts['username'])
        except User.DoesNotExist:
            raise CommandError(f'No existe la cuenta «{opts["username"]}».')

        visto = u.last_login.strftime('%d-%m-%Y') if u.last_login else 'nunca'
        self.stdout.write(f'Cuenta: {u.username}')
        self.stdout.write(f'  superusuario: {u.is_superuser} · staff: {u.is_staff} '
                          f'· activa: {u.is_active}')
        self.stdout.write(f'  último ingreso: {visto}')
        grupos = ', '.join(g.name for g in u.groups.all()) or 'ninguno'
        self.stdout.write(f'  grupos: {grupos}')

        # ¿Alguien la está usando de verdad? Los pagos llevan quién los registró.
        try:
            from ventas.models import Pago
            desde = timezone.now() - timedelta(days=90)
            recientes = Pago.objects.filter(usuario=u, fecha_pago__gte=desde).count()
            historicos = Pago.objects.filter(usuario=u).count()
            self.stdout.write(f'  pagos registrados con esta cuenta: {historicos} '
                              f'({recientes} en los últimos 90 días)')
        except Exception as exc:
            self.stdout.write(f'  (no se pudo revisar pagos: {exc})')

        if opts['solo_mirar']:
            self.stdout.write('--- solo mirando, no se cambió nada ---')
            return

        u.is_active = bool(opts['reactivar'])
        u.save(update_fields=['is_active'])
        estado = 'REACTIVADA' if u.is_active else 'DESACTIVADA'
        self.stdout.write(f'--- cuenta {estado} (reversible: '
                          f'--{"" if u.is_active else "reactivar"}) ---')
