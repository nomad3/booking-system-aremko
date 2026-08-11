# -*- coding: utf-8 -*-
"""Siembra la lista «siempre Aremko» con lo que hasta hoy vivía en el código.

    python manage.py sembrar_reglas_glosa

Idempotente: no pisa lo que Jorge haya cambiado a mano. Si una regla ya
existe, se deja tal como está — la lista es suya desde el momento en que se
crea, y este comando solo pone el piso inicial.
"""
from django.core.management.base import BaseCommand

from finanzas.models import CategoriaFinanciera, ReglaGlosa

# (patrón, categoría, por qué). Salen de los `if` que estaban escritos en
# services.py hasta el 2026-08-10, más el BCI Seguros del mismo día.
SEMILLA = [
    ('GOOGLE ADS', 'publicidad', 'Campañas de Google'),
    ('META PLATFORMS', 'publicidad', 'Campañas de Instagram y Facebook'),
    ('FACEBK', 'publicidad', 'Cargo de Meta con glosa corta'),
    ('TWILIO', 'infraestructura', 'WhatsApp y SMS'),
    ('SENDGRID', 'infraestructura', 'Envío de correos'),
    ('DATAFORSEO', 'infraestructura', 'Datos de posicionamiento'),
    ('ECERT', 'infraestructura', 'Firma electrónica de boletas'),
    ('OPENAI', 'infraestructura', 'IA'),
    ('ANTHROPIC', 'infraestructura', 'IA'),
    ('OPENROUTER', 'infraestructura', 'IA'),
    ('RENDER', 'infraestructura', 'Servidor del sitio'),
    ('CLOUDINARY', 'infraestructura', 'Fotos y videos del sitio'),
    ('VERCEL', 'infraestructura', 'Hosting'),
    ('BCI SEGUROS', 'seguros', 'Seguro del auto; lo paga Jorge y Aremko le devuelve'),
]


class Command(BaseCommand):
    help = 'Crea las reglas de glosa iniciales (no pisa las editadas a mano).'

    def handle(self, *args, **opts):
        faltan = []
        creadas = existentes = 0
        for patron, clave, nota in SEMILLA:
            cat = CategoriaFinanciera.objects.filter(clave=clave).first()
            if cat is None:
                faltan.append(f'{patron} → {clave}')
                continue
            _, creada = ReglaGlosa.objects.get_or_create(
                patron=patron, defaults={'categoria': cat, 'nota': nota})
            if creada:
                creadas += 1
                self.stdout.write(f'  NUEVA: {patron} → {cat.nombre}')
            else:
                existentes += 1

        self.stdout.write(self.style.SUCCESS(
            f'Reglas: {creadas} nuevas · {existentes} ya estaban.'))
        if faltan:
            # Callarse acá dejaría a Jorge creyendo que la lista quedó
            # completa mientras esas glosas siguen cayendo por clasificar.
            self.stdout.write(self.style.WARNING(
                'Sin categoría en el plan de cuentas (corre primero '
                '`aplicar_plan_cuentas --aplicar`): ' + ', '.join(faltan)))
