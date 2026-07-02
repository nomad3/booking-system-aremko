# -*- coding: utf-8 -*-
"""Diagnóstico de solo lectura para el 500 reportado en /ventas/venta_reservas/
(H-058 Parte B). Los tracebacks de excepciones NO llegan a los logs de Render
(el logger 'django.request' de Django solo manda a mail_admins, no a consola, y
este proyecto no tiene handlers propios para él) — por eso hace falta reproducir
el error directo, vía el test Client de Django, que SÍ re-lanza la excepción real
con su traceback completo en vez de convertirla en una respuesta 500 silenciosa.

No escribe nada en la base de datos. Usa client.get() de solo lectura.

Uso:
    python manage.py diagnosticar_venta_reserva_list
    python manage.py diagnosticar_venta_reserva_list --fecha-inicio 2026-05-07 --fecha-fin 2026-06-30
"""
import traceback

from django.core.management.base import BaseCommand
from django.test import Client
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = "Reproduce (solo lectura) el 500 de /ventas/venta_reservas/ probando los filtros de programa."

    def add_arguments(self, parser):
        parser.add_argument('--fecha-inicio', default=None, help='YYYY-MM-DD (default: hoy - 56 días)')
        parser.add_argument('--fecha-fin', default=None, help='YYYY-MM-DD (default: hoy)')

    def handle(self, *args, **opts):
        hoy = timezone.localdate()
        fecha_inicio = opts['fecha_inicio'] or (hoy - timedelta(days=56)).isoformat()
        fecha_fin = opts['fecha_fin'] or hoy.isoformat()

        client = Client(raise_request_exception=True)
        casos = [None, 'ritual', 'refugio', 'pausa', 'aguas_calientes', 'otros']

        for programa in casos:
            url = f'/ventas/venta_reservas/?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}'
            if programa:
                url += f'&programa={programa}'
            etiqueta = programa or '(sin filtro de programa)'
            self.stdout.write(f'\n--- Probando {etiqueta}: {url} ---')
            try:
                # secure=True evita el 301 de SecurityMiddleware (SECURE_SSL_REDIRECT);
                # follow=True sigue cualquier otro redirect hasta la respuesta final.
                resp = client.get(url, HTTP_HOST='www.aremko.cl', secure=True, follow=True)
                self.stdout.write(self.style.SUCCESS(
                    f'  OK, status={resp.status_code}'
                    + (f' (via {[r[0] for r in resp.redirect_chain]})' if resp.redirect_chain else '')
                ))
            except Exception:  # noqa: BLE001 — queremos VER el traceback completo, no ocultarlo
                self.stdout.write(self.style.ERROR(f'  FALLÓ con {etiqueta}:'))
                self.stdout.write(traceback.format_exc())
