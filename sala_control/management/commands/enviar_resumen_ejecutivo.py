# -*- coding: utf-8 -*-
"""Envía el resumen ejecutivo del día al dueño.

Corre una vez al día temprano (07:30 Chile). Pensado para leerse en el
teléfono en 30 segundos.

    python manage.py enviar_resumen_ejecutivo --dry-run
    python manage.py enviar_resumen_ejecutivo --to ecolonco@gmail.com
    python manage.py enviar_resumen_ejecutivo
"""
import logging
import os

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand

from sala_control import render, resumen

logger = logging.getLogger(__name__)

DESTINATARIOS_DEFAULT = ('ecolonco@gmail.com', 'atoloza1970@gmail.com')


def destinatarios():
    crudo = os.environ.get('RESUMEN_EJECUTIVO_TO', '')
    lista = [e.strip() for e in crudo.split(',') if e.strip()]
    return lista or list(DESTINATARIOS_DEFAULT)


class Command(BaseCommand):
    help = 'Envía por correo el resumen ejecutivo diario del dueño.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra el resumen sin enviar nada.')
        parser.add_argument('--to', type=str, default='',
                            help='Destinatarios separados por coma '
                                 '(reemplaza a los configurados).')

    def handle(self, *args, **opts):
        datos = resumen.construir()
        texto = render.a_texto(datos)

        # El panel del día lee de acá el gasto en publicidad: son llamadas de
        # red lentas y una página que se refresca sola no puede pedirlas cada
        # vez. Se congela una vez al día, acá, y el panel lo muestra con su
        # hora. Que falle no puede impedir el correo.
        try:
            from sala_control.panel import guardar_corte_ads
            guardar_corte_ads(datos['ads'], datos['fecha'])
        except Exception as exc:
            logger.warning('sala_control: no se pudo guardar el corte de ads: %s', exc)

        if opts['dry_run']:
            self.stdout.write(texto)
            self.stdout.write(self.style.WARNING(
                '\n[DRY-RUN] No se envió ningún correo.'))
            return

        para = ([e.strip() for e in opts['to'].split(',') if e.strip()]
                or destinatarios())
        if not para:
            self.stdout.write(self.style.ERROR('No hay destinatarios.'))
            return

        n = len(datos['alertas'])
        asunto = (f'Aremko · {render.fecha_larga(datos["fecha"])}'
                  + (f' · {n} alerta(s)' if n else ''))

        correo = EmailMultiAlternatives(
            subject=asunto,
            body=texto,
            from_email=getattr(settings, 'VENTAS_FROM_EMAIL',
                               'ventas@aremko.cl'),
            to=para,
        )
        correo.attach_alternative(render.a_html(datos), 'text/html')
        try:
            correo.send(fail_silently=False)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'Error enviando: {exc}'))
            logger.exception('sala_control: falló el envío del resumen')
            return
        self.stdout.write(self.style.SUCCESS(
            f'Resumen enviado a {", ".join(para)} · {n} alerta(s)'))
