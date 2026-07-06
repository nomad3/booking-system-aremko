# -*- coding: utf-8 -*-
"""Reproduce el GET /admin/ventas/ventareserva/add/ (que da 500 en prod,
2026-07-06) con el test client y muestra el TRACEBACK real — el logger
django.request no lo está sacando a los logs de Render.

SOLO LECTURA (un GET; lo único que escribe es la sesión del force_login).
Uso (Render Shell):  python manage.py diagnosticar_admin_add
"""
import traceback

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.test import Client


class Command(BaseCommand):
    help = "Reproduce el 500 del formulario Añadir reserva y muestra el traceback"

    def add_arguments(self, parser):
        parser.add_argument('--url', default='/admin/ventas/ventareserva/add/',
                            help='Ruta a probar (default: añadir reserva)')

    def handle(self, *args, **opts):
        su = User.objects.filter(is_superuser=True, is_active=True).first()
        if not su:
            self.stdout.write(self.style.ERROR('No hay superusuario activo'))
            return

        # HTTP_HOST real: el middleware de host-routing elige el urlconf por
        # dominio — sin esto probaríamos el sitio equivocado.
        client = Client(raise_request_exception=True)
        client.force_login(su)
        url = opts['url']
        self.stdout.write(f'GET {url} como {su.username}...')
        try:
            r = client.get(url, HTTP_HOST='www.aremko.cl')
            self.stdout.write(self.style.SUCCESS(f'HTTP {r.status_code}'))
            if r.status_code >= 400:
                self.stdout.write(r.content[:800].decode('utf-8', 'replace'))
        except Exception:
            tb = traceback.format_exc()
            # las últimas líneas son las que importan (excepción + frame culpable)
            self.stdout.write(self.style.ERROR('EXCEPCIÓN REPRODUCIDA:'))
            self.stdout.write(tb[-4000:])
