"""Lista los ScriptWhatsApp ordenados de SIMPLE → COMPLEJO para mapearlos a plantillas
Meta aprobadas (H-012). Para cada script muestra: motivo, salva, segmentación, las
variables que usa el texto, si ya tiene plantilla Meta, y el cuerpo actual (el mismo
que se enviaba a mano) — así Jorge calza cada `vac_*` con el contenido existente.

Orden (de más simple a más complejo):
  1) salva 1 antes que 2/3 (el primer contacto es lo más usado)
  2) genéricos (sin estilo ni contexto) antes que segmentados
  3) por estado de valor

  python manage.py scripts_para_mapeo
  python manage.py scripts_para_mapeo --pendientes   # solo los que aún no tienen plantilla
"""

import re

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Lista los scripts de la bandeja ordenados simple→complejo para mapear a plantillas Meta.'

    def add_arguments(self, parser):
        parser.add_argument('--pendientes', action='store_true',
                            help='Mostrar solo los scripts sin plantilla Meta asignada.')

    def handle(self, *args, **opts):
        from ventas.models import ScriptWhatsApp

        scripts = list(ScriptWhatsApp.objects.filter(activo=True))
        if opts.get('pendientes'):
            scripts = [s for s in scripts if not (s.meta_template_name or '').strip()]

        def es_generico(s):
            return not (s.cohorte_estilo or '').strip() and not (s.cohorte_contexto or '').strip()

        # Orden: salva ASC, genérico primero, estado, script_id.
        scripts.sort(key=lambda s: (s.salva, 0 if es_generico(s) else 1,
                                    s.estado_valor_target or '', s.script_id or ''))

        if not scripts:
            self.stdout.write(self.style.WARNING('No hay scripts (o todos ya tienen plantilla).'))
            return

        total = len(scripts)
        con_plantilla = sum(1 for s in scripts if (s.meta_template_name or '').strip())
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'— {total} scripts · {con_plantilla} ya mapeados · {total - con_plantilla} por mapear —'))
        self.stdout.write('(orden: salva 1 primero, genéricos antes que segmentados)\n')

        for i, s in enumerate(scripts, 1):
            seg = 'genérico (cualquier estilo/contexto)'
            detalle = ' · '.join(x for x in [(s.cohorte_estilo or '').strip(),
                                             (s.cohorte_contexto or '').strip()] if x)
            if detalle:
                seg = detalle
            variables = re.findall(r'\{(\w+)\}', s.plantilla_texto or '')
            tiene = self.style.SUCCESS(f'✓ {s.meta_template_name}') if (s.meta_template_name or '').strip() \
                else self.style.ERROR('✗ SIN PLANTILLA')
            self.stdout.write(self.style.MIGRATE_HEADING(
                f'\n{i}. [{s.script_id}] {s.estado_valor_target} · salva {s.salva} · {seg}'))
            self.stdout.write(f'   plantilla Meta: {tiene}')
            self.stdout.write(f'   variables del texto: {", ".join(variables) or "(ninguna)"}')
            if s.meta_variables_orden:
                self.stdout.write(f'   meta_variables_orden: {s.meta_variables_orden}')
            cuerpo = (s.plantilla_texto or '').strip().replace('\n', ' ')
            self.stdout.write(f'   cuerpo actual: {cuerpo[:240]}')
