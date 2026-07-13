"""
Diagnóstico de solo lectura del endpoint de alternativas de horario (H-061).

Llama a construir_alternativas() para cada tipo de Fase 1 en una fecha dada y
resume cuántas alternativas salen + un ejemplo de texto_sugerido. No escribe nada.
Se corre como job de Render contra los datos reales para verificar que los
builders funcionan (lo que los tests con datos sintéticos no pueden cubrir).

Uso: python manage.py diagnostico_alternativas --fecha 2026-07-16 [--personas 2]
"""
from django.core.management.base import BaseCommand

from whatsapp_agent import alternativas


class Command(BaseCommand):
    help = 'Verifica los builders de alternativas de horario (H-061) contra datos reales.'

    def add_arguments(self, parser):
        parser.add_argument('--fecha', required=True, help='YYYY-MM-DD')
        parser.add_argument('--personas', type=int, default=2)

    def handle(self, *args, **options):
        fecha, personas = options['fecha'], options['personas']
        self.stdout.write(f"Alternativas para {fecha}, {personas} personas:\n")
        for tipo in alternativas.TIPOS_FASE1:
            res = alternativas.construir_alternativas(tipo, fecha, personas)
            if res.get('error'):
                self.stdout.write(self.style.WARNING(f"  {tipo}: ERROR — {res['error']}"))
                continue
            alts = res.get('alternativas', [])
            linea = f"  {tipo}: {len(alts)} alternativa(s)"
            self.stdout.write(self.style.SUCCESS(linea) if alts else linea)
            if alts:
                a = alts[0]
                self.stdout.write(f"      ej: {a['titulo']} — {a['texto_sugerido']}")
        # Fase 2 debe rechazarse limpio
        for tipo in alternativas.TIPOS_FASE2:
            res = alternativas.construir_alternativas(tipo, fecha, personas)
            estado = 'rechaza OK' if res.get('error') else 'NO rechaza (revisar!)'
            self.stdout.write(f"  {tipo} (Fase 2): {estado}")
