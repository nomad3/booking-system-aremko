"""Snapshot semanal de GA4 + Search Console.

Persiste el estado actual de tráfico web y visibilidad SEO en GA4Snapshot
y SearchConsoleSnapshot para construir series históricas. Idealmente corre
cada lunes vía cron-job.org.

Idempotente: si ya existe un snapshot para hoy con el mismo `generado_por`,
no crea uno nuevo a menos que se pase --force.

Uso:
    python manage.py snapshot_weekly_traffic              # cron normal
    python manage.py snapshot_weekly_traffic --force      # forzar nuevo aun si ya hay
    python manage.py snapshot_weekly_traffic --only ga4   # solo GA4
    python manage.py snapshot_weekly_traffic --only gsc   # solo Search Console
"""
from __future__ import annotations

import logging
import traceback
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from ventas.models import GA4Snapshot, SearchConsoleSnapshot

logger = logging.getLogger(__name__)


def _extract_ga4_overview(datos: dict) -> dict:
    """Aplana los campos del overview last_7d para los campos planos del modelo."""
    overview = (datos.get('overview') or {}).get('last_7d') or {}
    custom = (datos.get('custom_events') or {}).get('last_7d') or {}
    return {
        'sessions': int(overview.get('sessions') or 0),
        'total_users': int(overview.get('totalUsers') or 0),
        'new_users': int(overview.get('newUsers') or 0),
        'engaged_sessions': int(overview.get('engagedSessions') or 0),
        'avg_session_duration': float(overview.get('averageSessionDuration') or 0),
        'screen_page_views': int(overview.get('screenPageViews') or 0),
        'conversions': int(overview.get('conversions') or 0),
        'whatsapp_clicks': int(custom.get('whatsapp_click') or 0),
        'phone_clicks': int(custom.get('phone_click') or 0),
        'cta_blog_clicks': int(custom.get('cta_blog_click') or 0),
        'reservation_started': int(custom.get('reservation_started') or 0),
        'reservation_completed': int(custom.get('reservation_completed') or 0),
    }


def _extract_gsc_overview(datos: dict) -> dict:
    """Aplana el overview last_7d del snapshot GSC."""
    overview = (datos.get('overview') or {}).get('last_7d') or {}
    return {
        'clicks': int(overview.get('clicks') or 0),
        'impressions': int(overview.get('impressions') or 0),
        'ctr': float(overview.get('ctr') or 0),
        'position': float(overview.get('position') or 0),
    }


def _snapshot_ga4(force: bool, generado_por: str, stdout) -> tuple[GA4Snapshot | None, str | None]:
    today = timezone.now().date()
    if not force:
        existing = GA4Snapshot.objects.filter(
            fecha_snapshot=today, generado_por=generado_por
        ).first()
        if existing:
            return existing, 'skipped_existing'

    try:
        from ventas.services.ga4_reporter import get_full_snapshot
    except Exception as exc:
        return None, f'no se pudo importar ga4_reporter: {exc}'

    try:
        datos = get_full_snapshot() or {}
    except Exception as exc:
        logger.error('ga4_reporter.get_full_snapshot falló', exc_info=True)
        return None, f'reporter falló: {exc}'

    overview = _extract_ga4_overview(datos)
    snap = GA4Snapshot.objects.create(
        fecha_snapshot=today,
        datos=datos,
        generado_por=generado_por,
        error='; '.join(datos.get('errors') or []),
        **overview,
    )
    return snap, None


def _snapshot_gsc(force: bool, generado_por: str, stdout) -> tuple[SearchConsoleSnapshot | None, str | None]:
    today = timezone.now().date()
    if not force:
        existing = SearchConsoleSnapshot.objects.filter(
            fecha_snapshot=today, generado_por=generado_por
        ).first()
        if existing:
            return existing, 'skipped_existing'

    try:
        from ventas.services.gsc_reporter import get_full_snapshot
    except Exception as exc:
        return None, f'no se pudo importar gsc_reporter: {exc}'

    try:
        datos = get_full_snapshot() or {}
    except Exception as exc:
        logger.error('gsc_reporter.get_full_snapshot falló', exc_info=True)
        return None, f'reporter falló: {exc}'

    overview = _extract_gsc_overview(datos)
    snap = SearchConsoleSnapshot.objects.create(
        fecha_snapshot=today,
        datos=datos,
        generado_por=generado_por,
        error='; '.join(datos.get('errors') or []),
        **overview,
    )
    return snap, None


class Command(BaseCommand):
    help = 'Persiste snapshots semanales de GA4 + Search Console para series históricas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Crear nuevo snapshot aunque ya exista uno para hoy con el mismo origen.',
        )
        parser.add_argument(
            '--only', choices=['ga4', 'gsc'], default=None,
            help='Limitar a solo una fuente.',
        )
        parser.add_argument(
            '--generado-por', default='cron_weekly',
            choices=['cron_weekly', 'management_command', 'admin_manual'],
            help='Marcador del origen del snapshot.',
        )

    def handle(self, *args, **opts):
        force = opts['force']
        only = opts['only']
        generado_por = opts['generado_por']

        results = {}

        if only != 'gsc':
            self.stdout.write(self.style.NOTICE('Tomando snapshot GA4...'))
            snap, err = _snapshot_ga4(force, generado_por, self.stdout)
            results['ga4'] = (snap, err)
            if snap and err == 'skipped_existing':
                self.stdout.write(self.style.WARNING(
                    f'  GA4 ya existe para {snap.fecha_snapshot} ({generado_por}). Usa --force para regenerar.'
                ))
            elif snap:
                self.stdout.write(self.style.SUCCESS(
                    f'  GA4 OK: id={snap.id} sessions={snap.sessions} conversions={snap.conversions} '
                    f'reservas_start={snap.reservation_started} reservas_done={snap.reservation_completed}'
                ))
            else:
                self.stdout.write(self.style.ERROR(f'  GA4 FAIL: {err}'))

        if only != 'ga4':
            self.stdout.write(self.style.NOTICE('Tomando snapshot Search Console...'))
            snap, err = _snapshot_gsc(force, generado_por, self.stdout)
            results['gsc'] = (snap, err)
            if snap and err == 'skipped_existing':
                self.stdout.write(self.style.WARNING(
                    f'  GSC ya existe para {snap.fecha_snapshot} ({generado_por}). Usa --force para regenerar.'
                ))
            elif snap:
                self.stdout.write(self.style.SUCCESS(
                    f'  GSC OK: id={snap.id} clicks={snap.clicks} impressions={snap.impressions} '
                    f'ctr={snap.ctr:.2f}% pos={snap.position:.2f}'
                ))
            else:
                self.stdout.write(self.style.ERROR(f'  GSC FAIL: {err}'))

        # Exit non-zero solo si TODO falló (para que cron-job.org pueda alertar)
        all_failed = all(
            (snap is None) for snap, _ in results.values()
        )
        if all_failed:
            self.stderr.write(self.style.ERROR('Todos los snapshots fallaron.'))
            raise SystemExit(1)
