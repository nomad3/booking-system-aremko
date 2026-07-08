# -*- coding: utf-8 -*-
"""Sincroniza el rank-check SEO (DataForSEO, vía aremko-cli GET /api/v1/seo/rankings)
para Aremko Y sus competidores directos, sobre la misma lista de keywords.

Guarda UNA fila SEORankingSnapshot por (keyword, target_domain) en cada
corrida, para poder ver la evolución de la posición orgánica en el tiempo —
tanto de Aremko como de la competencia — no solo la foto del momento. Mismo
criterio que sync_aremko_cli_weekly_brief: respeta la lista fija de keywords
y el location_name que ya decide aremko-cli del lado del servidor (no se
pasan overrides de keywords/ubicación acá, solo el target).

Competidores confirmados 2026-07-06 (análisis de video Semrush + verificación
manual, ver docs/LOOP_SEO.md): cancagua.cl (Frutillar, boutique/biopiscinas —
NO aparece en ninguna de las 8 keywords protegidas, punto ciego real),
termasdelsol.com (Río Puelo, termas naturales — compite en el clúster
"termas"), termascochamo.com (Cochamó, termas naturales — domina el clúster
"termas", ya identificado antes vía competitors_above).

Disparo: mismo cron semanal (lunes 09:10) que ya está configurado en
cron-job.org apuntando a /ventas/api/cron/sync-seo-rankings/ — al agregar
target_domains acá, el cron existente empieza a cubrir los 4 dominios sin
tocar nada en cron-job.org.

Uso manual:
    python manage.py sync_aremko_cli_seo_rankings
    python manage.py sync_aremko_cli_seo_rankings --targets aremko.cl,cancagua.cl
"""
import os
import time

import requests
from django.core.management.base import BaseCommand

from ...models import SEORankingSnapshot

DEFAULT_BASE_URL = 'https://aremko-cli-backend.onrender.com'

# Aremko primero (referencia), luego competidores confirmados. Cambiar esta
# lista es la única acción necesaria para agregar/quitar un competidor del
# tracking — no requiere tocar cron-job.org ni el código de aremko-cli.
DEFAULT_TARGETS = ['aremko.cl', 'cancagua.cl', 'termasdelsol.com', 'termascochamo.com']


class Command(BaseCommand):
    help = "Sincroniza (a demanda o vía cron) el rank-check SEO de Aremko y su competencia desde aremko-cli."

    def add_arguments(self, parser):
        parser.add_argument(
            '--targets', default=None,
            help='Dominios a chequear, separados por coma. Default: aremko.cl + competidores confirmados.',
        )

    def handle(self, *args, **opts):
        base_url = os.getenv('AREMKO_CLI_BASE_URL', DEFAULT_BASE_URL)
        rankings_url = f"{base_url.rstrip('/')}/api/v1/seo/rankings"

        targets_arg = opts.get('targets')
        targets = (
            [t.strip() for t in targets_arg.split(',') if t.strip()]
            if targets_arg else DEFAULT_TARGETS
        )

        total_creados = 0
        for i, target in enumerate(targets):
            if i > 0:
                # Espaciar las llamadas: cada una ya dispara 8 requests en
                # paralelo del lado de aremko-cli hacia DataForSEO — no hace
                # falta golpear los 4 dominios simultáneamente.
                time.sleep(2)

            self.stdout.write(self.style.NOTICE(f'--- {target} ---'))
            try:
                # Timeout generoso: el backend hace 1 request HTTP por keyword
                # en paralelo a DataForSEO (ver nota en aremko-cli/internal/
                # dataforseo/queries.go) — con cache frío puede tardar bastante
                # más que un endpoint simple.
                resp = requests.get(rankings_url, params={'target': target}, timeout=90)
                resp.raise_for_status()
                payload = resp.json()
            except Exception as exc:  # noqa: BLE001 — cualquier falla queda registrada, nunca rompe
                SEORankingSnapshot.objects.create(
                    success=False, target_domain=target, error_message=str(exc)[:2000],
                )
                self.stderr.write(self.style.ERROR(f'  Error consultando aremko-cli ({rankings_url}): {exc}'))
                continue

            data = payload.get('data') or {}
            location_name = data.get('location') or ''
            rankings = data.get('rankings') or []

            if not rankings:
                SEORankingSnapshot.objects.create(
                    success=False, target_domain=target,
                    error_message='Respuesta 200 pero sin rankings reconocibles.',
                )
                self.stderr.write(self.style.WARNING(
                    '  aremko-cli respondió pero no trae rankings reconocibles — '
                    'revisar si cambió el shape de /api/v1/seo/rankings.'
                ))
                continue

            creados = 0
            for r in rankings:
                keyword = (r.get('keyword') or '').strip()
                if not keyword:
                    continue
                SEORankingSnapshot.objects.create(
                    success=True,
                    keyword=keyword,
                    target_domain=r.get('target_domain') or target,
                    location_name=location_name,
                    found=bool(r.get('found')),
                    position=r.get('position') or None,
                    rank_absolute=r.get('rank_absolute') or None,
                    url=r.get('url') or '',
                    competitors_above=r.get('competitors_above') or [],
                )
                creados += 1
                pos_txt = r.get('position') if r.get('found') else 'no encontrado'
                self.stdout.write(f'  {keyword}: {pos_txt}')

            total_creados += creados
            self.stdout.write(self.style.SUCCESS(f'  {target}: {creados} keywords guardadas.'))

        self.stdout.write(self.style.SUCCESS(
            f'SEO rankings sync OK: {total_creados} filas guardadas en total '
            f'({len(targets)} dominios: {", ".join(targets)}).'
        ))
