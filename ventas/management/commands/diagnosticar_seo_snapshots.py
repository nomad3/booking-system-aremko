# -*- coding: utf-8 -*-
"""Diagnóstico de solo lectura para el endpoint nuevo `seo_snapshots` (H-057).

Llama al endpoint real vía el test Client (mismo patrón que
diagnosticar_venta_reserva_list.py) para confirmar que responde 200 con datos
reales de GA4Snapshot/SearchConsoleSnapshot, antes de avisarle a aremko-cli que
está listo. No escribe nada en la base de datos.

Uso:
    python manage.py diagnosticar_seo_snapshots
    python manage.py diagnosticar_seo_snapshots --weeks 4
"""
import json
import traceback

from django.core.management.base import BaseCommand
from django.test import Client


class Command(BaseCommand):
    help = "Reproduce (solo lectura) GET /ventas/api/aremko-cli/seo-snapshots/ y muestra la respuesta."

    def add_arguments(self, parser):
        parser.add_argument('--weeks', type=int, default=8)

    def handle(self, *args, **opts):
        from ventas.models import GA4Snapshot, SearchConsoleSnapshot

        n_ga4 = GA4Snapshot.objects.count()
        n_gsc = SearchConsoleSnapshot.objects.count()
        self.stdout.write(f'GA4Snapshot en BD: {n_ga4} | SearchConsoleSnapshot en BD: {n_gsc}')

        client = Client(raise_request_exception=True)
        url = f"/ventas/api/aremko-cli/seo-snapshots/?weeks={opts['weeks']}"
        self.stdout.write(f'\n--- Probando {url} ---')
        try:
            resp = client.get(url, HTTP_HOST='www.aremko.cl', secure=True, follow=True)
            self.stdout.write(self.style.SUCCESS(f'OK, status={resp.status_code}'))
            data = json.loads(resp.content)
            self.stdout.write(f"weeks_requested: {data.get('weeks_requested')}")
            self.stdout.write(f"ga4: {len(data.get('ga4', []))} filas")
            self.stdout.write(f"gsc: {len(data.get('gsc', []))} filas")
            self.stdout.write('\nJSON completo:\n' + json.dumps(data, indent=2, ensure_ascii=False)[:4000])
        except Exception:  # noqa: BLE001 — queremos VER el traceback completo
            self.stdout.write(self.style.ERROR('FALLÓ:'))
            self.stdout.write(traceback.format_exc())
