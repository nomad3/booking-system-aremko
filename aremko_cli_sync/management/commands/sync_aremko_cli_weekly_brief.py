# -*- coding: utf-8 -*-
"""Sincroniza el snapshot de aremko-cli (gasto Google/Meta Ads por programa, semanal).

Llama `GET /api/v1/brief/weekly` en aremko-cli (~64s medido en vivo el 2026-07-01 —
llama a Google Ads + Meta Ads + Django), extrae SOLO los campos que usa el dashboard
interno de estadísticas (H-058: campaign_name, activity_label, y spend/activity por
semana — descarta `reservas`/`ingresos` del lado ads porque Django ya los calcula
directo y con más autoridad vía `calcular_reservas_por_programa_semanal`), y guarda
un WeeklyBriefSnapshot nuevo.

SIN CRON (decisión de Jorge 2026-07-01): se dispara manual, a demanda, con el botón
"Actualizar gasto en Ads" del dashboard (`ventas/views/analytics_views.py`,
`actualizar_gasto_ads_aremko_cli`) — corre en un thread de background para no bloquear
el único worker Gunicorn del sitio durante el fetch largo.

Uso manual (equivalente al botón):
    python manage.py sync_aremko_cli_weekly_brief
"""
import os

import requests
from django.core.management.base import BaseCommand

# aremko-cli hoy solo mapea estos 3 (por nombre de campaña) — "Noche de Aguas
# Calientes" (H-055, este repo) todavía no tiene campaña propia mapeada del lado
# de aremko-cli/Go (attachProgramWeeklyGoogle en brief.go). Cuando se agregue ahí,
# esta lista se actualiza sola (solo copia las claves presentes en la respuesta).
PROGRAMAS_AREMKO_CLI = ('ritual', 'refugio', 'pausa')

DEFAULT_BASE_URL = 'https://aremko-cli-backend.onrender.com'


class Command(BaseCommand):
    help = "Sincroniza (a demanda) el gasto en Ads (Google+Meta) por programa desde aremko-cli."

    def handle(self, *args, **opts):
        from ...models import WeeklyBriefSnapshot

        base_url = os.getenv('AREMKO_CLI_BASE_URL', DEFAULT_BASE_URL)
        url = f"{base_url.rstrip('/')}/api/v1/brief/weekly"

        try:
            # Timeout generoso: medido en vivo 64s (2026-07-01) — llama en vivo a
            # Google Ads + Meta Ads + Django. Un timeout corto SIEMPRE fallaría.
            resp = requests.get(url, timeout=100)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001 — cualquier falla queda registrada, nunca rompe
            WeeklyBriefSnapshot.objects.create(success=False, error_message=str(exc)[:2000])
            self.stderr.write(self.style.ERROR(f'Error consultando aremko-cli ({url}): {exc}'))
            return

        data = payload.get('data') or {}
        google_ads_raw = data.get('google_ads') or {}
        meta_ads_raw = data.get('meta_ads') or {}

        def _extraer(raw):
            """Se queda SOLO con lo que el dashboard necesita: nombre de campaña, la
            etiqueta de la métrica de actividad (varía: "Clics" en Google, "Conversac."
            o "Leads" en Meta según el objetivo de la campaña), y por semana SOLO
            label/spend/activity — `reservas`/`ingresos` que trae aremko-cli se
            descartan a propósito (Django los calcula directo, no hay que confiar en
            una copia que podría desalinearse)."""
            out = {}
            for prog in PROGRAMAS_AREMKO_CLI:
                bloque = raw.get(prog)
                if not bloque:
                    continue
                out[prog] = {
                    'campaign_name': bloque.get('campaign_name'),
                    'activity_label': bloque.get('activity_label') or 'Actividad',
                    'weekly': [
                        {
                            'label': semana.get('label'),
                            'spend': semana.get('spend') or 0,
                            'activity': semana.get('activity') or 0,
                        }
                        for semana in (bloque.get('weekly') or [])
                    ],
                }
            return out

        google_ads = _extraer(google_ads_raw)
        meta_ads = _extraer(meta_ads_raw)

        if not google_ads and not meta_ads:
            WeeklyBriefSnapshot.objects.create(
                success=False,
                error_message='Respuesta 200 pero sin bloques google_ads/meta_ads reconocibles.',
            )
            self.stderr.write(self.style.WARNING(
                'aremko-cli respondió pero no trae datos de programa reconocibles — '
                'revisar si cambió el shape de /api/v1/brief/weekly.'
            ))
            return

        WeeklyBriefSnapshot.objects.create(success=True, google_ads=google_ads, meta_ads=meta_ads)
        self.stdout.write(self.style.SUCCESS(
            f'Snapshot creado OK. Google Ads: {list(google_ads.keys())}, '
            f'Meta Ads: {list(meta_ads.keys())}'
        ))
