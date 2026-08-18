# -*- coding: utf-8 -*-
"""Clasifica de qué hablan las conversaciones que no llegaron a cotización (P-31).

    python manage.py clasificar_conversaciones --dry-run          # qué haría
    python manage.py clasificar_conversaciones --limit 25         # primer lote barato
    python manage.py clasificar_conversaciones --limit 1000       # el resto

`--limit` está a propósito SIN default alto: cada conversación es una llamada
al modelo y se paga. Conviene mirar el primer lote de 25 antes de soltar los
966 — si la taxonomía está mal, se ve ahí y no después de pagar todo.

Por defecto solo mira conversaciones con `--min-mensajes 4` o más: de los 1.655
teléfonos sin cotizar, 966 están en ese grupo y son los que tuvieron
conversación de verdad. Los de 1 mensaje suelen ser equivocados o spam y
clasificarlos cuesta lo mismo que los que importan.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ventas.models import WhatsAppMessage
from whatsapp_agent.embudo import candidatos_sin_cotizar
from whatsapp_agent.models import TemaConversacion
from whatsapp_agent.temas import VERSION_TAXONOMIA, clasificar_conversacion


DIAS_POR_DEFECTO = 60
MIN_MENSAJES = 4

# Los 'otro' de confianza baja cuyo motivo delata un problema de la llamada y no
# de la conversación. Se reintentan en la corrida siguiente.
_MOTIVOS_TECNICOS = ('respuesta del modelo ilegible', 'falló la llamada al modelo',
                     'el modelo devolvió una respuesta vacía')


def _fue_falla_tecnica(fila):
    return (fila.tema == 'otro'
            and any(fila.motivo.startswith(m) for m in _MOTIVOS_TECNICOS))


class Command(BaseCommand):
    help = 'Clasifica el tema de las conversaciones de WhatsApp sin cotización.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=DIAS_POR_DEFECTO)
        parser.add_argument('--limit', type=int, default=25,
                            help='Cuántas clasificar en esta corrida (cada una se paga).')
        parser.add_argument('--min-mensajes', type=int, default=MIN_MENSAJES,
                            help='Mínimo de mensajes entrantes para que valga clasificar.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra a cuántas les tocaría, sin llamar al modelo.')

    def handle(self, *args, **opts):
        hasta = timezone.localdate()
        desde = hasta - timedelta(days=opts['dias'])

        # Misma función que usa el panel de temas del embudo (whatsapp_agent.
        # embudo): una sola definición de «sin cotizar», no dos que puedan
        # empezar a contar distinto con el tiempo.
        candidatos = candidatos_sin_cotizar(desde, hasta, opts['min_mensajes'])

        # Ya clasificadas y sin mensajes nuevos: no se vuelven a pagar.
        ya = {c.telefono: c for c in TemaConversacion.objects.filter(
            telefono__in=[t for t, _, _ in candidatos])}
        pendientes = [(t, n, u) for t, n, u in candidatos
                      if t not in ya
                      or (ya[t].ultimo_mensaje_visto or timezone.now()) < u
                      # Etiquetada con una taxonomía vieja: hay que rehacerla,
                      # o el informe sumaría categorías que ya no significan
                      # lo mismo.
                      or ya[t].version_taxonomia != VERSION_TAXONOMIA
                      # Quedó en 'otro' porque la respuesta no se pudo leer, no
                      # porque la conversación no calzara: merece otro intento.
                      or _fue_falla_tecnica(ya[t])]
        pendientes.sort(key=lambda c: -c[1])  # las más conversadas primero

        self.stdout.write(
            f'{len(candidatos)} conversaciones sin cotizar con '
            f'{opts["min_mensajes"]}+ mensajes · {len(candidatos) - len(pendientes)} '
            f'ya clasificadas · {len(pendientes)} pendientes')
        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Clasificaría {min(len(pendientes), opts["limit"])} en esta corrida '
                f'— dry-run, sin llamar al modelo.'))
            return

        lote = pendientes[:opts['limit']]
        if not lote:
            self.stdout.write(self.style.SUCCESS('Nada pendiente. Listo.'))
            return

        hechas, fallidas = 0, 0
        for tel, n, ultimo in lote:
            mensajes = list(WhatsAppMessage.objects
                            .filter(phone=tel, timestamp__date__gte=desde)
                            .order_by('timestamp'))
            r = clasificar_conversacion(mensajes)
            if r is None:
                fallidas += 1
                continue
            tema, motivo, confianza, modelo = r
            TemaConversacion.objects.update_or_create(
                telefono=tel,
                defaults={'tema': tema, 'motivo': motivo, 'confianza': confianza,
                          'mensajes_vistos': n, 'ultimo_mensaje_visto': ultimo,
                          'modelo': modelo,
                          'version_taxonomia': VERSION_TAXONOMIA})
            hechas += 1

        self.stdout.write(self.style.SUCCESS(
            f'{hechas} conversaciones clasificadas'
            + (f' · {fallidas} fallaron (quedan pendientes)' if fallidas else '')))
        restan = len(pendientes) - len(lote)
        if restan:
            self.stdout.write(f'Quedan {restan} sin clasificar. '
                              f'Volvé a correrlo con --limit para seguir.')
