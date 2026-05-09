# -*- coding: utf-8 -*-
"""
Brief semanal de marketing (Tarea 2.4 plan maestro).

Cron: cada lunes 10 AM Chile.
Disparo: HTTP via /ventas/api/cron/marketing-brief/

Funcionamiento:
1. Genera brief con LLM (OpenRouter, modelo configurable) usando como context:
   - Playbook + recurring tasks + calendario Chile
   - Frases reales clientes promotores (encuestas)
   - Análisis IA encuestas semana actual (lunes 9 AM)
   - Reviews TripAdvisor + Google
   - Pipeline reservas semana actual
   - GA4 + GSC snapshots
   - Meta snapshot (FB + IG + Ads, todas las cuentas)
   - Análisis IA Meta pre-procesado
   - Objetivo de la semana definido por Jorge en admin
2. Renderiza email con resumen ejecutivo HTML + .docx adjunto extenso
3. Envía a los 3 emails internos por defecto

Uso manual:
    python manage.py generate_weekly_marketing_brief                      # genera y envía
    python manage.py generate_weekly_marketing_brief --dry-run            # NO envía email
    python manage.py generate_weekly_marketing_brief --to "a@x.cl,b@y.cl" # custom
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand

from ventas.services.marketing_brief_generator import generate_brief
from ventas.services.brief_renderer import (
    render_brief_to_markdown,
    render_brief_to_docx,
    render_executive_summary_html,
)

logger = logging.getLogger(__name__)


DEFAULT_RECIPIENTS = [
    'aremkospa@gmail.com',
    'abonosaremko@gmail.com',
    'atoloza1970@gmail.com',
]


class Command(BaseCommand):
    help = 'Genera el brief semanal de marketing con drafts y lo envía por email'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='No envía email, imprime el brief markdown en consola')
        parser.add_argument('--to', type=str, default='',
                            help='Emails destinatarios separados por coma. Default: 3 emails internos Aremko')

    def handle(self, *args, **opts):
        self.stdout.write(self.style.SUCCESS('\n📋 BRIEF SEMANAL DE MARKETING'))

        # Resolver destinatarios
        if opts['to']:
            recipients = [e.strip() for e in opts['to'].split(',') if e.strip()]
        else:
            recipients = list(DEFAULT_RECIPIENTS)

        try:
            result = generate_brief()
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'❌ Error generando brief: {type(exc).__name__}: {exc}'))
            logger.exception('Error en generate_brief')
            return

        self.stdout.write(f'📅 Semana: {result["semana_inicio"]} → {result["semana_fin"]}')
        self.stdout.write(f'💬 Frases clientes: {result["frases_clientes_count"]} · Blog posts: {result["blog_posts_count"]}')
        self.stdout.write(
            f'📈 GA4: {"✓" if result.get("ga4_snapshot") else "✗"} · '
            f'GSC: {"✓" if result.get("gsc_snapshot") else "✗"} · '
            f'Meta: {"✓" if result.get("meta_snapshot") else "✗"} · '
            f'Meta IA: {"✓" if result.get("meta_analysis") else "✗"}'
        )
        self.stdout.write(
            f'🎯 Objetivo semana: {"✓" if result.get("objetivo_semana") else "✗ (Jorge no lo definió)"} · '
            f'⭐ Reviews: {"✓" if result.get("reviews_resumen") else "✗"} · '
            f'💰 Pipeline: {"✓" if result.get("pipeline_reservas") else "✗"}'
        )

        # Diagnostico explicito del pipeline interno
        pipe = result.get('pipeline_reservas') or {}
        if pipe.get('_errores'):
            self.stdout.write(self.style.WARNING('\n⚠️  Pipeline con errores parciales:'))
            for err in pipe['_errores']:
                self.stdout.write(f'   - {err}')
        if pipe.get('_falla_total'):
            self.stdout.write(self.style.ERROR('   ❌ FALLA TOTAL — ningún bloque produjo datos'))
        if pipe and not pipe.get('_errores') and not pipe.get('_falla_total'):
            us = pipe.get('ultima_semana', {})
            um = pipe.get('ultimo_mes', {})
            self.stdout.write(
                f'   📊 Última semana: {us.get("creadas", 0)} creadas, {us.get("pagadas", 0)} pagadas, '
                f'${int(us.get("total_facturado", 0)):,} CLP'
            )
            self.stdout.write(
                f'   📊 Último mes: {um.get("creadas", 0)} creadas, {um.get("pagadas", 0)} pagadas, '
                f'${int(um.get("total_facturado", 0)):,} CLP'
            )

        brief = result['brief']
        markdown = render_brief_to_markdown(brief, result['semana_inicio'], result['semana_fin'])

        if opts['dry_run']:
            self.stdout.write('\n=== BRIEF EN MARKDOWN ===\n')
            self.stdout.write(markdown[:5000])
            self.stdout.write(f'\n[...truncado a 5000 chars de {len(markdown)} totales]')
            self.stdout.write(self.style.WARNING('\n[DRY-RUN] No se envió email.'))
            return

        if not recipients:
            self.stdout.write(self.style.ERROR('❌ No hay destinatarios.'))
            return

        # Render del email
        executive_html = render_executive_summary_html(brief)
        docx_bytes = render_brief_to_docx(brief, result['semana_inicio'], result['semana_fin'])

        subject = (
            f'📋 Brief semanal Aremko · '
            f'{result["semana_inicio"].strftime("%d/%m")} → '
            f'{result["semana_fin"].strftime("%d/%m")}'
        )

        text_body = (
            f"Brief semanal de marketing Aremko\n"
            f"Semana: {result['semana_inicio']} - {result['semana_fin']}\n\n"
            f"Headline: {brief.get('resumen_ejecutivo', {}).get('headline', '(sin headline)')}\n\n"
            f"El resumen ejecutivo está en el cuerpo HTML del email.\n"
            f"El brief completo (diagnóstico + drafts + acciones) está en el .docx adjunto.\n"
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl'),
            to=recipients,
        )
        email.attach_alternative(executive_html, 'text/html')

        # Adjuntar .docx con el brief completo
        if docx_bytes:
            filename = f'Aremko_Brief_Semanal_{result["semana_inicio"].strftime("%Y-%m-%d")}.docx'
            email.attach(
                filename, docx_bytes,
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            )
            self.stdout.write(f'📎 Adjunto: {filename} ({len(docx_bytes):,} bytes)')
        else:
            # Fallback: adjuntar markdown
            email.attach(
                f'Aremko_Brief_Semanal_{result["semana_inicio"].strftime("%Y-%m-%d")}.md',
                markdown.encode('utf-8'),
                'text/markdown',
            )

        try:
            email.send(fail_silently=False)
            self.stdout.write(self.style.SUCCESS(f'✅ Brief enviado a {len(recipients)} destinatarios: {", ".join(recipients)}'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'❌ Error enviando email: {exc}'))
            logger.exception('Error enviando brief')
