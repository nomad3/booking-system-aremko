"""Lista QUIÉNES pueden entrar hoy a la Sala de control.

La pregunta «¿quién ve esto?» no se contesta leyendo el decorador: se contesta
mirando qué cuentas existen de verdad. Un superusuario olvidado de hace dos años
ve la caja igual que el dueño.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from sala_control.panel import GRUPO_COLABORADOR, puede_ver_sala


class Command(BaseCommand):
    help = 'Quiénes pueden ver la Sala de control (y quién queda fuera).'

    def handle(self, *args, **opts):
        User = get_user_model()
        dentro, fuera = [], []
        for u in User.objects.all().order_by('username'):
            via = []
            if u.is_superuser:
                via.append('superusuario')
            if u.groups.filter(name=GRUPO_COLABORADOR).exists():
                via.append(f'grupo «{GRUPO_COLABORADOR}»')
            visto = u.last_login.strftime('%d-%m-%Y') if u.last_login else 'nunca entró'
            linea = (f'  {u.username:<24} {"ACTIVO " if u.is_active else "INACTIVO"} '
                     f'· último ingreso {visto}')
            if puede_ver_sala(u) and u.is_active:
                dentro.append(f'{linea} · por {" y ".join(via)}')
            else:
                fuera.append(linea + ('' if u.is_active else ' · (deshabilitado)'))

        self.stdout.write(f'VEN LA SALA ({len(dentro)}):')
        for l in dentro:
            self.stdout.write(l)
        self.stdout.write(f'\nNO LA VEN ({len(fuera)}):')
        for l in fuera[:25]:
            self.stdout.write(l)
        if len(fuera) > 25:
            self.stdout.write(f'  … y {len(fuera) - 25} más')
