# -*- coding: utf-8 -*-
"""Marca como expiradas las propuestas pendientes que ya vencieron (P-29).

Por qué existe: `PropuestaReserva` solo se marca `expirada` cuando alguien la
vuelve a abrir (`reserva_service.obtener_propuesta`). La que nadie toca se
queda `pendiente` para siempre. Medido el 2026-08-17: de 56 «pendientes»,
**55 estaban vencidas** —la más vieja del 19 de junio— y solo 1 era cola viva.
Eso convertía $7,9M en una cifra sin significado y ensuciaba cualquier lectura
del embudo.

No cambia nada visible: la bandeja y Luna ya llaman a `esta_vigente()` antes de
usar una propuesta, así que las vencidas hoy son invisibles igual. Lo que
arregla es el estado GUARDADO, que es el que leen los informes.

De yapa corrige un borde de `rollback._restaurar_propuesta`, que filtra por
`estado='pendiente'` sin mirar vigencia: una propuesta muerta de hace dos meses
podía terminar marcada «descartada» por un rollback de hoy, que es una causa de
muerte distinta y falsea el análisis de por qué no se vende.

Correr:  python manage.py expirar_propuestas_vencidas [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from whatsapp_agent.models import PropuestaReserva


class Command(BaseCommand):
    help = 'Marca expiradas las PropuestaReserva pendientes ya vencidas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra cuántas marcaría, sin escribir.')

    def handle(self, *args, **opts):
        vencidas = PropuestaReserva.objects.filter(
            estado='pendiente', expires_at__lt=timezone.now())
        total = vencidas.count()
        if not total:
            self.stdout.write('No hay propuestas pendientes vencidas.')
            return

        mas_vieja = vencidas.order_by('created_at').values_list(
            'created_at', flat=True).first()
        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'{total} propuestas pendientes ya vencidas '
                f'(la más vieja del {mas_vieja:%d-%m-%Y}) — dry-run, sin escribir.'))
            return

        # update() en bloque: no hay señales sobre PropuestaReserva y son
        # decenas de filas; recorrerlas de a una no aporta nada.
        actualizadas = vencidas.update(estado='expirada')
        self.stdout.write(self.style.SUCCESS(
            f'{actualizadas} propuestas marcadas como expiradas '
            f'(la más vieja era del {mas_vieja:%d-%m-%Y}).'))
