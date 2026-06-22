# -*- coding: utf-8 -*-
"""Pre-carga la lista de servicios web conocidos de Aremko en el tablero de costos.

Idempotente (get_or_create por nombre): crea los que falten con su categoría y
modalidad sugeridas; NO pisa los que ya editaste. Después completas montos,
fechas, tarjeta y saldo desde el admin.

Uso:
    python manage.py cargar_servicios_web
"""
from django.core.management.base import BaseCommand

# (nombre, categoria, modalidad, url_facturacion)
SERVICIOS = [
    ('Render',            'infra',     'suscripcion', 'https://dashboard.render.com/billing'),
    ('Cloudinary',        'infra',     'suscripcion', 'https://console.cloudinary.com/settings/billing'),
    ('Vercel',            'infra',     'suscripcion', 'https://vercel.com/account/billing'),
    ('GitHub',            'infra',     'suscripcion', 'https://github.com/settings/billing'),
    ('Anthropic / Claude', 'ia',       'uso',         'https://console.anthropic.com/settings/billing'),
    ('OpenAI',            'ia',        'uso',         'https://platform.openai.com/account/billing'),
    ('OpenRouter',        'ia',        'uso',         'https://openrouter.ai/credits'),
    ('DeepSeek',          'ia',        'uso',         'https://platform.deepseek.com'),
    ('SendGrid',          'email',     'suscripcion', 'https://app.sendgrid.com/account/billing'),
    ('WhatsApp Cloud API', 'email',    'uso',         'https://business.facebook.com/billing_hub'),
    ('Redvoiss (SMS)',    'email',     'uso',         ''),
    ('Dominio aremko.cl', 'dominio',   'suscripcion', ''),
    ('Dominio destinopuertovaras.cl', 'dominio', 'suscripcion', ''),
    ('Composio',          'marketing', 'suscripcion', 'https://app.composio.dev'),
]


class Command(BaseCommand):
    help = "Pre-carga los servicios web conocidos en el tablero de costos (idempotente)."

    def handle(self, *args, **options):
        from costos_web.models import ServicioWeb
        creados, existentes = 0, 0
        for nombre, categoria, modalidad, url in SERVICIOS:
            obj, created = ServicioWeb.objects.get_or_create(
                nombre=nombre,
                defaults={'categoria': categoria, 'modalidad': modalidad, 'url_facturacion': url},
            )
            if created:
                creados += 1
                self.stdout.write(self.style.SUCCESS(f'+ creado: {nombre}'))
            else:
                existentes += 1
                self.stdout.write(f'= ya existía (se respeta): {nombre}')
        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {creados} creados, {existentes} ya existían. '
            f'Completa montos/fechas/tarjeta/saldo desde el admin → "Costos de Servicios Web".'))
