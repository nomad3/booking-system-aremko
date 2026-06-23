# -*- coding: utf-8 -*-
"""Analiza las combinaciones vendibles de pack TINA + MASAJE por día de la semana.

Para cada día (los horarios cambian según el día), cruza los slots de cada tina
(capacidad 2) con los de cada masaje, respetando la duración de la tina + un buffer
máximo, y lista los packs válidos (tina → masaje) con su buffer, etiquetados A/B/C…

Uso:
    python manage.py analizar_packs_tina_masaje
    python manage.py analizar_packs_tina_masaje --buffer-max 75
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand

DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def _hhmm(m):
    return f'{m // 60:02d}:{m % 60:02d}'


class Command(BaseCommand):
    help = "Tabla de packs tina+masaje vendibles por día (slots + buffer)."

    def add_arguments(self, parser):
        parser.add_argument('--buffer-max', type=int, default=75,
                            help='Gap máximo en minutos entre fin de tina e inicio de masaje (default 75).')
        parser.add_argument('--buffer-min', type=int, default=0,
                            help='Gap mínimo en minutos (default 0).')

    def handle(self, *args, **opts):
        from ventas.models import Servicio
        from ventas.views.calendario_matriz_view import extraer_slots_para_fecha
        from whatsapp_agent.availability import _es_masaje_agendable, _hhmm_min

        bmax, bmin = opts['buffer_max'], opts['buffer_min']
        hoy = date.today()

        tinas = list(Servicio.objects.filter(
            activo=True, publicado_web=True, tipo_servicio='tina',
            capacidad_minima__lte=2, capacidad_maxima__gte=2).order_by('nombre'))
        masajes = [m for m in Servicio.objects.filter(
            activo=True, publicado_web=True, tipo_servicio='masaje').order_by('nombre')
            if _es_masaje_agendable(m)]

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Buffer permitido: {bmin}–{bmax} min entre fin de tina e inicio de masaje\n'))
        self.stdout.write('Tinas (cap 2): ' + ', '.join(f'{t.nombre} [{t.duracion or 120}min]' for t in tinas))
        self.stdout.write('Masajes: ' + ', '.join(f'{m.nombre} [{m.duracion or 0}min]' for m in masajes))

        for wd in range(7):
            d = hoy + timedelta(days=(wd - hoy.weekday()) % 7)
            self.stdout.write(self.style.SUCCESS(f'\n=== {DIAS[wd]} ==='))
            packs = []
            for t in tinas:
                t_dur = t.duracion or 120
                for ts in (extraer_slots_para_fecha(t.slots_disponibles, d) or []):
                    ti = _hhmm_min(ts)
                    if ti is None:
                        continue
                    t_end = ti + t_dur
                    for m in masajes:
                        for ms in (extraer_slots_para_fecha(m.slots_disponibles, d) or []):
                            mi = _hhmm_min(ms)
                            if mi is None:
                                continue
                            gap = mi - t_end
                            if bmin <= gap <= bmax:
                                packs.append((ti, t.nombre, t_dur, mi, m.nombre, gap))
            packs.sort()
            if not packs:
                self.stdout.write('  (sin packs válidos ese día con este buffer)')
                continue
            for i, (ti, tn, td, mi, mn, gap) in enumerate(packs):
                letra = chr(65 + i) if i < 26 else f'#{i + 1}'
                self.stdout.write(
                    f'  {letra}) Tina {tn}: {_hhmm(ti)}–{_hhmm(ti + td)}  →  Masaje {mn}: {_hhmm(mi)}'
                    f'   (buffer {gap} min)')
        self.stdout.write('')
