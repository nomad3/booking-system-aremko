# -*- coding: utf-8 -*-
"""
Análisis IA semanal de encuestas de satisfacción (Tarea 1.4 Fase C).

Cron: cada lunes 9 AM Chile.
Disparo: HTTP via /ventas/api/cron/analyze-surveys/ desde cron-job.org

Funcionamiento:
1. Toma encuestas de los últimos 7 días
2. Si vacío, sale (no envía email)
3. Pasa stats + comentarios a LLM (OpenRouter, modelo configurable)
4. Recibe JSON estructurado con análisis
5. Renderiza template HTML del reporte
6. Envía email a SURVEY_ANALYSIS_RECIPIENT_EMAIL

Uso manual:
    python manage.py analyze_surveys_weekly                   # 7 días, envía email
    python manage.py analyze_surveys_weekly --days 14         # 14 días
    python manage.py analyze_surveys_weekly --dry-run         # NO envía email, solo print
    python manage.py analyze_surveys_weekly --to otro@email.com
"""
import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from ventas.services.survey_ai_analyzer import analyze_week, get_followups_pendientes

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Analiza encuestas de satisfacción de la última semana con IA y envía reporte por email'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7,
                            help='Cantidad de días hacia atrás (default: 7)')
        parser.add_argument('--dry-run', action='store_true',
                            help='No envía email, imprime el reporte JSON en consola')
        parser.add_argument('--to', type=str, default='',
                            help='Email destinatario (default: SURVEY_ANALYSIS_RECIPIENT_EMAIL setting)')

    def handle(self, *args, **opts):
        self.stdout.write(self.style.SUCCESS('\n📊 ANÁLISIS IA SEMANAL DE ENCUESTAS'))

        days = opts['days']
        recipient = opts['to'] or getattr(settings, 'SURVEY_ANALYSIS_RECIPIENT_EMAIL', '')

        try:
            result = analyze_week(days=days)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error en analyze_week: {type(e).__name__}: {e}'))
            logger.exception('Error en analyze_week')
            return

        if result.get('sin_data'):
            self.stdout.write(self.style.WARNING(
                f'⚠️ Sin encuestas en los últimos {days} días. No se envía reporte.'
            ))
            return

        self.stdout.write(f'📊 Encuestas analizadas: {result["encuestas_qs_count"]}')
        self.stdout.write(f'📅 Periodo: {result["periodo_inicio"].date()} → {result["periodo_fin"].date()}')

        if opts['dry_run']:
            import json
            self.stdout.write('\n=== STATS ===')
            self.stdout.write(json.dumps(result['stats'], indent=2, ensure_ascii=False, default=str))
            self.stdout.write('\n=== ANÁLISIS LLM ===')
            self.stdout.write(json.dumps(result['analisis'], indent=2, ensure_ascii=False))
            self.stdout.write(self.style.WARNING('\n[DRY-RUN] No se envió email.'))
            return

        if not recipient:
            self.stdout.write(self.style.ERROR(
                '❌ No hay destinatario. Configura SURVEY_ANALYSIS_RECIPIENT_EMAIL o usa --to'
            ))
            return

        # Followups pendientes para incluir en el email
        followups = list(get_followups_pendientes(days=days)[:10])

        # Render del email
        context = {
            'stats': result['stats'],
            'analisis': result['analisis'],
            'periodo_inicio': result['periodo_inicio'],
            'periodo_fin': result['periodo_fin'],
            'encuestas_count': result['encuestas_qs_count'],
            'followups_pendientes': followups,
            'ga4_disponible': bool(result.get('ga4_snapshot')),
            'reviews_snapshot': result.get('reviews_snapshot'),
        }
        html_body = render_to_string('emails/reporte_semanal_encuestas.html', context)

        nps_str = ''
        if result['stats'].get('nps_score') is not None:
            nps_str = f' · NPS {result["stats"]["nps_score"]}'

        subject = (
            f'📊 Reporte semanal Aremko: {result["encuestas_qs_count"]} encuestas{nps_str} · '
            f'{result["periodo_fin"].strftime("%d/%m/%Y")}'
        )

        text_body = (
            f"Reporte semanal de encuestas de satisfacción Aremko\n"
            f"Periodo: {result['periodo_inicio'].date()} - {result['periodo_fin'].date()}\n"
            f"Encuestas: {result['encuestas_qs_count']}\n\n"
            f"Resumen: {result['analisis'].get('resumen_ejecutivo', '(sin resumen)')}\n\n"
            f"Ver el reporte completo en HTML."
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl'),
            to=[recipient],
        )
        email.attach_alternative(html_body, 'text/html')
        email.send()

        self.stdout.write(self.style.SUCCESS(f'✅ Reporte enviado a {recipient}'))
