"""Corrige el responsable de comunidad: Daniela (CM anterior) → Angélica (CM actual).

One-off: los briefs ya generados guardaron 'Daniela' en el JSON de cada pieza,
así que re-explotar no basta (releería 'Daniela'). Este comando actualiza las
filas ya creadas y, de paso, parcha el JSON archivado para que un re-explode
futuro no revierta el nombre.

Sin argumentos (el Shell de Render parte los comandos con args/multi-línea).

    python manage.py fix_responsable_cm
"""
from django.core.management.base import BaseCommand

from marketing_briefs.models import PublicacionPlanificada, WeeklyBriefArchive

VIEJO = 'Daniela'
NUEVO = 'Angélica'


class Command(BaseCommand):
    help = 'Reemplaza el CM Daniela por Angélica en publicaciones y briefs archivados.'

    def handle(self, *args, **opts):
        # 1. Filas de la cola (lo visible en la página de Angélica).
        n_pub = PublicacionPlanificada.objects.filter(responsable=VIEJO).update(responsable=NUEVO)
        self.stdout.write(self.style.SUCCESS(f'{n_pub} publicaciones: responsable {VIEJO} → {NUEVO}.'))

        # 2. JSON de briefs archivados (para que un re-explode no revierta).
        n_brief = 0
        for archive in WeeklyBriefArchive.objects.all():
            brief = archive.brief_json or {}
            drafts = brief.get('drafts_completos') or {}
            tocado = False
            for pieza in drafts.values():
                if isinstance(pieza, dict) and pieza.get('responsable') == VIEJO:
                    pieza['responsable'] = NUEVO
                    tocado = True
            if tocado:
                archive.brief_json = brief
                archive.save(update_fields=['brief_json'])
                n_brief += 1
        self.stdout.write(self.style.SUCCESS(f'{n_brief} briefs archivados parchados.'))
