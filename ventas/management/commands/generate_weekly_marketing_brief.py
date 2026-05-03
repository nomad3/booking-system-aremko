# -*- coding: utf-8 -*-
"""
Brief semanal de marketing (Tarea 2.4 plan maestro).

Cron: cada lunes 10 AM Chile.
Disparo: HTTP via /ventas/api/cron/marketing-brief/

Funcionamiento:
1. Genera brief con LLM (OpenRouter, modelo configurable) usando como context
   el playbook + recurring tasks + frases reales de clientes promotores
2. Renderiza email HTML con calendario semanal + drafts listos para copiar
3. Envía a MARKETING_BRIEF_RECIPIENT_EMAIL

Uso manual:
    python manage.py generate_weekly_marketing_brief                  # genera y envía
    python manage.py generate_weekly_marketing_brief --dry-run        # NO envía email
    python manage.py generate_weekly_marketing_brief --to otro@email.com
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from ventas.services.marketing_brief_generator import generate_brief

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Genera el brief semanal de marketing con drafts y lo envía por email'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='No envía email, imprime el brief JSON en consola')
        parser.add_argument('--to', type=str, default='',
                            help='Email destinatario (default: MARKETING_BRIEF_RECIPIENT_EMAIL)')

    def handle(self, *args, **opts):
        self.stdout.write(self.style.SUCCESS('\n📋 BRIEF SEMANAL DE MARKETING'))

        recipient = opts['to'] or getattr(settings, 'MARKETING_BRIEF_RECIPIENT_EMAIL', '')

        try:
            result = generate_brief()
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'❌ Error generando brief: {type(exc).__name__}: {exc}'))
            logger.exception('Error en generate_brief')
            return

        self.stdout.write(f'📅 Semana: {result["semana_inicio"]} → {result["semana_fin"]}')
        self.stdout.write(f'💬 Frases de clientes promotores cargadas: {result["frases_clientes_count"]}')
        self.stdout.write(f'📝 Blog posts recientes cargados: {result["blog_posts_count"]}')

        if opts['dry_run']:
            import json
            self.stdout.write('\n=== BRIEF GENERADO ===')
            self.stdout.write(json.dumps(result['brief'], indent=2, ensure_ascii=False))
            self.stdout.write(self.style.WARNING('\n[DRY-RUN] No se envió email.'))
            return

        if not recipient:
            self.stdout.write(self.style.ERROR(
                '❌ No hay destinatario. Configura MARKETING_BRIEF_RECIPIENT_EMAIL o usa --to'
            ))
            return

        # Render del email
        context = {
            'brief': result['brief'],
            'semana_inicio': result['semana_inicio'],
            'semana_fin': result['semana_fin'],
            'frases_count': result['frases_clientes_count'],
            'posts_count': result['blog_posts_count'],
        }
        html_body = render_to_string('emails/brief_marketing_semanal.html', context)

        subject = f'📋 Brief semanal Aremko · {result["semana_inicio"].strftime("%d/%m")} → {result["semana_fin"].strftime("%d/%m")}'

        text_body = (
            f"Brief semanal de marketing Aremko\n"
            f"Semana: {result['semana_inicio']} - {result['semana_fin']}\n\n"
            f"Resumen: {result['brief'].get('resumen_semana', '(sin resumen)')}\n\n"
            f"Ver el brief completo en HTML para copy listo de cada canal."
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl'),
            to=[recipient],
        )
        email.attach_alternative(html_body, 'text/html')
        email.send()

        self.stdout.write(self.style.SUCCESS(f'✅ Brief enviado a {recipient}'))
