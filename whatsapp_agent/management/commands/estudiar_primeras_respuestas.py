# -*- coding: utf-8 -*-
"""P-34: estudio de primeras respuestas — SOLO LECTURA.

Compara la primera respuesta CON PRECIO entre las conversaciones que murieron
(`silencio_tras_info`, P-31) y las que llegaron a cotizar (PropuestaReserva).
Imprime agregados por grupo + muestras reales para leer.

Uso (Shell de Render):
    python manage.py estudiar_primeras_respuestas
    python manage.py estudiar_primeras_respuestas --muestras 10
"""
from django.core.management.base import BaseCommand

from whatsapp_agent.embudo import INICIO_DATOS_REALES
from whatsapp_agent.estudio_respuestas import analizar_conversacion, resumen_grupo


def _mensajes_de(phone):
    from ventas.models import WhatsAppMessage

    qs = (WhatsAppMessage.objects
          .filter(phone=phone[:20], timestamp__date__gte=INICIO_DATOS_REALES)
          .exclude(msg_type='reaction')
          # H-045: avisos operativos al staff en el mismo hilo — no son parte
          # de la conversación con el cliente (misma exclusión que usa Luna).
          .exclude(direction='out', body__contains='Nueva tarea ·')
          .order_by('timestamp')
          .values_list('direction', 'body', 'timestamp'))
    return list(qs)


class Command(BaseCommand):
    help = 'P-34: compara primeras respuestas entre conversaciones muertas y cotizadas (read-only)'

    def add_arguments(self, parser):
        parser.add_argument('--muestras', type=int, default=6,
                            help='Ejemplos reales a imprimir por grupo (default 6).')
        parser.add_argument('--max-conversaciones', type=int, default=400,
                            help='Tope de conversaciones a analizar por grupo.')

    def handle(self, *args, **opts):
        from whatsapp_agent.models import PropuestaReserva, TemaConversacion
        from whatsapp_agent.temas import VERSION_TAXONOMIA

        tope = opts['max_conversaciones']

        murio = list(TemaConversacion.objects
                     .filter(tema='silencio_tras_info',
                             version_taxonomia=VERSION_TAXONOMIA)
                     .order_by('telefono')
                     .values_list('telefono', flat=True)[:tope])
        cotizo = list(PropuestaReserva.objects
                      .filter(canal='whatsapp')
                      .exclude(external_id='')
                      .order_by('external_id')
                      .values_list('external_id', flat=True)
                      .distinct()[:tope])

        grupos = [('MURIÓ (silencio_tras_info)', murio),
                  ('COTIZÓ (PropuestaReserva)', cotizo)]

        for nombre, telefonos in grupos:
            analisis, sin_precio, sin_mensajes, muestras = [], 0, 0, []
            for tel in telefonos:
                msgs = _mensajes_de(tel)
                if not msgs:
                    sin_mensajes += 1
                    continue
                a = analizar_conversacion(msgs)
                if a is None:
                    sin_precio += 1
                    continue
                a['telefono'] = tel
                analisis.append(a)
                if len(muestras) < opts['muestras']:
                    primer_in = next((b for d, b, _ in msgs if d == 'in'), '')
                    muestras.append((tel, primer_in, a))

            r = resumen_grupo(analisis)
            self.stdout.write(f'\n===== {nombre} =====')
            self.stdout.write(
                f'{len(telefonos)} conversaciones · {r["n"]} con respuesta con precio · '
                f'{sin_precio} murieron SIN precio · {sin_mensajes} sin mensajes en ventana')
            if r['n']:
                self.stdout.write(
                    f'  largo promedio: {r["largo_promedio"]} chars · '
                    f'precios por mensaje: {r["promedio_precios_por_mensaje"]}')
                self.stdout.write(
                    f'  termina preguntando: {r["pct_termina_preguntando"]}% · '
                    f'alguna pregunta: {r["pct_tiene_pregunta"]}%')
                self.stdout.write(
                    f'  menciona horarios: {r["pct_menciona_horarios"]}% · '
                    f'con link: {r["pct_tiene_link"]}%')
                self.stdout.write(
                    f'  respuesta <90s: {r["pct_respuesta_rapida"]}% · '
                    f'gap mediano: {r["gap_mediano_seg"]}s')
                self.stdout.write(
                    f'  el cliente escribió DESPUÉS de esa respuesta: '
                    f'{r["pct_cliente_respondio"]}%')

            self.stdout.write(f'\n--- {len(muestras)} muestras de {nombre} ---')
            for tel, primer_in, a in muestras:
                marcas = []
                if a['termina_preguntando']:
                    marcas.append('TERMINA-PREGUNTANDO')
                if a['menciona_horarios']:
                    marcas.append('HORARIOS')
                if a['respuesta_rapida']:
                    marcas.append('<90s')
                self.stdout.write(f'\n[{tel}] {" ".join(marcas) or "sin-marcas"} · '
                                  f'respondió después: {a["cliente_respondio"]}')
                self.stdout.write(f'  CLIENTE ABRIÓ: {(primer_in or "")[:160]}')
                self.stdout.write(f'  RESPUESTA CON PRECIO: {a["texto"][:400]}')
