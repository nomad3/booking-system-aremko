# -*- coding: utf-8 -*-
"""Sincroniza el rank-check SEO (DataForSEO, vía aremko-cli GET /api/v1/seo/rankings).

Guarda UNA fila SEORankingSnapshot por keyword en cada corrida, para poder ver
la evolución de la posición orgánica en el tiempo — el endpoint en vivo de
aremko-cli solo da la foto del momento (cacheada 12h en memoria, se pierde en
cada redeploy de Render). Mismo criterio que sync_aremko_cli_weekly_brief:
respeta la lista fija de keywords y el location_name que ya decide aremko-cli
del lado del servidor (no se pasan overrides acá).

Disparo sugerido: mismo cron semanal (lunes) que snapshot_weekly_traffic, vía
el endpoint /ventas/api/cron/sync-seo-rankings/ (cron-job.org) — pendiente que
Jorge configure ese job externo. También se puede correr a mano:

Uso manual:
    python manage.py sync_aremko_cli_seo_rankings
"""
import os

import requests
from django.core.management.base import BaseCommand

from ...models import SEORankingSnapshot

DEFAULT_BASE_URL = 'https://aremko-cli-backend.onrender.com'


class Command(BaseCommand):
    help = "Sincroniza (a demanda o vía cron) el rank-check SEO desde aremko-cli y guarda 1 fila histórica por keyword."

    def handle(self, *args, **opts):
        base_url = os.getenv('AREMKO_CLI_BASE_URL', DEFAULT_BASE_URL)
        url = f"{base_url.rstrip('/')}/api/v1/seo/rankings"

        try:
            # Timeout generoso: el backend hace 1 request HTTP por keyword en
            # paralelo a DataForSEO (ver nota en aremko-cli/internal/dataforseo/
            # queries.go) — con cache frío puede tardar bastante más que un
            # endpoint simple.
            resp = requests.get(url, timeout=90)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001 — cualquier falla queda registrada, nunca rompe
            SEORankingSnapshot.objects.create(success=False, error_message=str(exc)[:2000])
            self.stderr.write(self.style.ERROR(f'Error consultando aremko-cli ({url}): {exc}'))
            return

        data = payload.get('data') or {}
        location_name = data.get('location') or ''
        rankings = data.get('rankings') or []

        if not rankings:
            SEORankingSnapshot.objects.create(
                success=False,
                error_message='Respuesta 200 pero sin rankings reconocibles.',
            )
            self.stderr.write(self.style.WARNING(
                'aremko-cli respondió pero no trae rankings reconocibles — '
                'revisar si cambió el shape de /api/v1/seo/rankings.'
            ))
            return

        creados = 0
        for r in rankings:
            keyword = (r.get('keyword') or '').strip()
            if not keyword:
                continue
            SEORankingSnapshot.objects.create(
                success=True,
                keyword=keyword,
                target_domain=r.get('target_domain') or 'aremko.cl',
                location_name=location_name,
                found=bool(r.get('found')),
                position=r.get('position') or None,
                rank_absolute=r.get('rank_absolute') or None,
                url=r.get('url') or '',
                competitors_above=r.get('competitors_above') or [],
            )
            creados += 1
            pos_txt = r.get('position') if r.get('found') else 'no encontrado'
            self.stdout.write(self.style.SUCCESS(f'  {keyword}: {pos_txt}'))

        self.stdout.write(self.style.SUCCESS(
            f'SEO rankings sync OK: {creados} keywords guardadas (location={location_name!r}).'
        ))
