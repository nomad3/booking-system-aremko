"""Mapea cada ScriptWhatsApp a su plantilla Meta `vac_*` por convención de nombre (H-012).

Las plantillas aprobadas en Meta siguen el patrón del script_id:
  A.6 → vac_a_6 · A.1-N → vac_a_1_n · B.refugio-DOR-N → vac_b_refugio_dor_n ·
  C.1-SC → vac_c_1_sc · D.2 → vac_d_2  (puntos/guiones → "_", minúscula, prefijo vac_)
Excepción: Leal/Campeón (E.*) usan vac_e_mesachica_<s|n|sc> según región.

El `meta_variables_orden` se deriva de los placeholders del cuerpo en orden de aparición.

DRY-RUN por defecto (solo muestra la propuesta). Con --aplicar guarda.
  python manage.py mapear_plantillas_vac            # revisar propuesta
  python manage.py mapear_plantillas_vac --aplicar   # aplicar
  python manage.py mapear_plantillas_vac --solo-vacios --aplicar  # no pisar los ya mapeados
"""

import re

from django.core.management.base import BaseCommand


def _template_name(script):
    eid = (script.estado_valor_target or '').strip().lower()
    sid = script.script_id or ''
    if eid in ('leal', 'campeón', 'campeon'):
        if sid.endswith('-N'):
            suf = 'n'
        elif sid.endswith('-SC'):
            suf = 'sc'
        else:
            suf = 's'
        return f'vac_e_mesachica_{suf}'
    base = sid.lower().replace('.', '_').replace('-', '_')
    return f'vac_{base}'


def _variables_orden(script):
    seen = []
    for m in re.findall(r'\{(\w+)\}', script.plantilla_texto or ''):
        if m not in seen:
            seen.append(m)
    return seen


class Command(BaseCommand):
    help = 'Mapea ScriptWhatsApp → plantilla Meta vac_* por convención (dry-run por defecto).'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help='Guarda los cambios.')
        parser.add_argument('--solo-vacios', action='store_true',
                            help='Solo mapea los scripts que aún no tienen plantilla.')

    def handle(self, *args, **opts):
        from ventas.models import ScriptWhatsApp

        scripts = list(ScriptWhatsApp.objects.filter(activo=True).order_by('script_id'))
        if opts.get('solo_vacios'):
            scripts = [s for s in scripts if not (s.meta_template_name or '').strip()]
        if not scripts:
            self.stdout.write(self.style.WARNING('No hay scripts para mapear.'))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'— Propuesta de mapeo ({len(scripts)} scripts) —'))
        cambios = 0
        for s in scripts:
            tmpl = _template_name(s)
            variables = _variables_orden(s)
            actual = (s.meta_template_name or '').strip()
            marca = '' if not actual else (' (ya: ' + actual + ')')
            distinto = actual != tmpl
            estilo = self.style.SUCCESS if distinto else self.style.WARNING
            self.stdout.write(estilo(
                f'  [{s.script_id}] {s.estado_valor_target} salva {s.salva}'))
            self.stdout.write(f'      → plantilla: {tmpl}{marca}')
            self.stdout.write(f'      → variables: {variables or "(sin variables)"}')
            if distinto:
                cambios += 1
                if opts.get('aplicar'):
                    s.meta_template_name = tmpl
                    s.meta_language = s.meta_language or 'es'
                    s.meta_variables_orden = variables
                    s.save(update_fields=['meta_template_name', 'meta_language', 'meta_variables_orden'])

        if opts.get('aplicar'):
            self.stdout.write(self.style.SUCCESS(f'\n✅ Aplicado. {cambios} scripts mapeados/actualizados.'))
            self.stdout.write('Revisa en Meta que cada nombre vac_* exista; los que no, ajústalos en el admin.')
        else:
            self.stdout.write(self.style.WARNING(
                f'\n(DRY-RUN) {cambios} scripts cambiarían. Corre con --aplicar para guardar.'))
