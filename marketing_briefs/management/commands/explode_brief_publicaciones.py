"""Explota (o re-explota) un brief archivado en publicaciones planificadas.

Uso normal: no hace falta — generate_brief lo hace solo tras cada brief.
Este comando es para casos manuales: re-generar la cola de una semana, o
generarla desde un brief archivado antes de que existiera la explosión.

Uso:
    python manage.py explode_brief_publicaciones                    # último brief archivado
    python manage.py explode_brief_publicaciones --semana 2026-07-13
"""
from datetime import date

from django.core.management.base import BaseCommand

from marketing_briefs.models import WeeklyBriefArchive
from marketing_briefs.services import explode_brief_to_publicaciones


class Command(BaseCommand):
    help = 'Explota un brief archivado en filas de PublicacionPlanificada (cola de la semana).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--semana', default=None,
            help='Lunes de la semana (YYYY-MM-DD). Default: el último brief archivado con éxito.',
        )

    def handle(self, *args, **opts):
        semana = opts.get('semana')
        qs = WeeklyBriefArchive.objects.filter(exito=True)
        if semana:
            qs = qs.filter(semana_inicio=date.fromisoformat(semana))
        archive = qs.order_by('-generated_at').first()

        if archive is None:
            self.stderr.write(self.style.ERROR(
                'No hay brief archivado' + (f' para la semana {semana}' if semana else '') + '.'
            ))
            return

        n = explode_brief_to_publicaciones(archive.semana_inicio, archive.brief_json or {})
        self.stdout.write(self.style.SUCCESS(
            f'{n} publicaciones creadas/actualizadas para la semana {archive.semana_inicio} '
            f'(brief generado {archive.generated_at:%Y-%m-%d %H:%M}).'
        ))
