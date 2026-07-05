# -*- coding: utf-8 -*-
"""Carga las descripciones narrativas de los masajes (docs/PROPUESTA_LANDING_MASAJES.md)
en Servicio.descripcion_web — SOLO si el campo está VACÍO (nunca pisa texto existente;
si un masaje ya tiene descripción, se reporta y se salta). Las descripciones las hereda
tanto la landing nueva como el catálogo de Luna.

Uso:
    python manage.py cargar_descripciones_masajes            # dry-run (muestra qué haría)
    python manage.py cargar_descripciones_masajes --aplicar  # escribe de verdad
"""
from django.core.management.base import BaseCommand

# Match por subcadena del nombre (case-insensitive) → descripción narrativa aprobada.
DESCRIPCIONES = [
    ('relajaci', 'Aceite tibio, movimientos largos y rítmicos sobre espalda, cuello y '
                 'hombros. Si hay contracturas, la terapeuta trabaja dentro de tu umbral — '
                 'presión firme sin dolor innecesario. Sales con la mente quieta y el '
                 'cuerpo liviano.'),
    ('piedras', 'Piedras volcánicas tibias que se deslizan y se posan donde la tensión se '
                'acumula. El calor hace la mitad del trabajo; las manos, el resto.'),
    ('drenaje', 'Toques suaves y precisos que ayudan al cuerpo a soltar lo que retiene. '
                'Ideal post-operatorio o para piernas cansadas.'),
    ('tui', 'El masaje de la medicina china: amasa, presiona y moviliza. Más activo que '
            'un relajación — sales despierto y suelto.'),
    ('deportivo', 'Para cuerpos que entrenan: descarga muscular profunda, foco en los '
                  'grupos que más usas.'),
    ('tailand', 'Estiramientos asistidos y presión con todo el cuerpo, sobre futón. Lo '
                'llaman "yoga para flojos" por algo.'),
]


class Command(BaseCommand):
    help = "Carga descripciones narrativas en descripcion_web de los masajes (solo campos vacíos)."

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true',
                            help='Escribir de verdad (sin esto es dry-run)')

    def handle(self, *args, **opts):
        from ventas.models import Servicio

        aplicar = opts['aplicar']
        masajes = Servicio.objects.filter(categoria_id=2, activo=True)
        if not masajes.exists():
            self.stdout.write(self.style.ERROR('No hay servicios en la categoría Masajes (id=2)'))
            return

        for servicio in masajes.order_by('nombre'):
            nombre_lower = (servicio.nombre or '').lower()
            match = next((texto for clave, texto in DESCRIPCIONES if clave in nombre_lower), None)
            actual = (servicio.descripcion_web or '').strip()

            if match is None:
                self.stdout.write(f'  ? {servicio.nombre}: sin descripción definida para este nombre — saltado')
                continue
            if actual:
                self.stdout.write(f'  = {servicio.nombre}: YA tiene descripción ({len(actual)} chars) — NO se pisa')
                continue

            if aplicar:
                servicio.descripcion_web = match
                servicio.save(update_fields=['descripcion_web'])
                self.stdout.write(self.style.SUCCESS(f'  ✓ {servicio.nombre}: descripción cargada'))
            else:
                self.stdout.write(f'  → {servicio.nombre}: SE CARGARÍA (dry-run): "{match[:60]}..."')

        if not aplicar:
            self.stdout.write('\n(dry-run — nada se escribió; usar --aplicar para escribir)')
