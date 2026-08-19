# -*- coding: utf-8 -*-
"""Genera los recordatorios de Luna y avisa al Go para que los envíe (H-109).

Pensado para correr por cron cada hora. Sin `LUNA_NUDGES_RUN_URL` configurada
solo genera la bitácora (nadie envía nada) — el interruptor general es esa
env var, igual que el patrón de la campaña de plantillas (H-012).

Uso:
    python manage.py generar_recordatorios_luna --dry-run   # solo lista
    python manage.py generar_recordatorios_luna             # genera + dispara
    python manage.py generar_recordatorios_luna --sin-disparo
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from whatsapp_agent.recordatorios import TOPE_POR_CORRIDA, candidatos, persistir


class Command(BaseCommand):
    help = 'Genera recordatorios de Luna (cotizaciones/pagos) y dispara el envío vía Go'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo mostrar qué se enviaría; no escribe ni dispara.')
        parser.add_argument('--limit', type=int, default=TOPE_POR_CORRIDA,
                            help=f'Tope de recordatorios nuevos (default {TOPE_POR_CORRIDA}).')
        parser.add_argument('--sin-disparo', action='store_true',
                            help='Generar la bitácora pero NO llamar al Go.')

    def handle(self, *args, **opts):
        ahora = timezone.now()
        items = candidatos(ahora)

        if opts['dry_run']:
            self.stdout.write(f'DRY-RUN · {len(items)} candidato(s):')
            for it in items:
                self.stdout.write(f"  [{it['tipo']}] {it['phone']}")
                self.stdout.write(f"    {it['texto'].splitlines()[0]}")
            return

        creados = persistir(items, tope=opts['limit'])
        self.stdout.write(f'{len(creados)} recordatorio(s) nuevo(s) en bitácora.')

        # Disparo al Go: también cuando no hubo nuevos pero quedaron pendientes
        # de una corrida anterior (Go caído, timeout) — el pull es idempotente.
        from whatsapp_agent.models import RecordatorioLuna
        pendientes = RecordatorioLuna.objects.filter(estado='pendiente_envio').count()
        url = getattr(settings, 'LUNA_NUDGES_RUN_URL', '')
        if opts['sin_disparo'] or not pendientes:
            self.stdout.write(f'Sin disparo (pendientes: {pendientes}).')
            return
        if not url:
            self.stdout.write(self.style.WARNING(
                f'{pendientes} pendiente(s) SIN enviar: falta LUNA_NUDGES_RUN_URL '
                '(el runner del Go, handoff H-109).'))
            return
        api_key = getattr(settings, 'LUNA_API_KEY', '') or ''
        if not api_key:
            self.stdout.write(self.style.WARNING(
                f'{pendientes} pendiente(s) SIN enviar: falta LUNA_API_KEY.'))
            return

        import requests
        try:
            # Mismo patrón que _disparar_campana_plantillas (H-012): el runner
            # del Go exige X-API-Key = LUNA_API_KEY. Sin el header responde 401
            # (bug real del primer ciclo, 2026-08-19).
            r = requests.post(url, headers={'X-API-Key': api_key},
                              timeout=getattr(settings, 'LUNA_NUDGES_TIMEOUT', 60))
            self.stdout.write(f'Disparo al Go: HTTP {r.status_code} · {r.text[:200]}')
        except Exception as e:  # noqa: BLE001 — el cron no debe morir por el Go
            self.stdout.write(self.style.WARNING(
                f'Disparo al Go falló ({e}) — los recordatorios quedan '
                'pendiente_envio y la próxima corrida reintenta.'))
