"""Verifica el estado de enriquecimiento de los 23 Places nuevos creados
en la tanda de stub-population (2026-04-27/28).

Marca cada Place como:
  - OK   → tiene long_description (>100 chars) + practical_tips + best_season
  - GAP  → falta alguno de esos 3 campos
  - MISS → no existe en la BD

Uso:
    python manage.py check_new_places_enrichment
    python manage.py check_new_places_enrichment --only-gaps
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Place


# Mismos 23 slugs que list_new_places_to_photo
NEW_SLUGS = [
    "iglesia-sagrado-corazon-puerto-varas",
    "barrio-patrimonial-aleman-puerto-varas",
    "iglesia-san-francisco-castro",
    "iglesia-de-putemun",
    "iglesia-de-tocoihue",
    "caulin",
    "fuerte-san-antonio-ancud",
    "punihuil-pinguineras",
    "playa-mar-brava",
    "termas-puyehue-hotel",
    "aguas-calientes-conaf",
    "sendero-rapidos-chanleufu",
    "salto-del-indio-anticura",
    "mirador-antillanca",
    "lago-puyehue-bahia-escocia",
    "mirador-estuario-reloncavi",
    "ralun",
    "salto-la-picada",
    "puerto-montt-plaza-catedral",
    "mirador-manuel-montt",
    "caleta-angelmo",
    "mercado-artesanal-angelmo",
    "isla-tenglo",
]


class Command(BaseCommand):
    help = "Reporta cuáles de los 23 Places nuevos están enriquecidos y cuáles no."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-gaps",
            action="store_true",
            help="Solo lista los Places con enrichment incompleto.",
        )

    def handle(self, *args, **options):
        only_gaps = options["only_gaps"]

        ok, gaps, missing = [], [], []

        for slug in NEW_SLUGS:
            p = Place.objects.filter(slug=slug).first()
            if not p:
                missing.append(slug)
                continue

            long_ok = len(p.long_description) > 100
            tips_ok = bool(p.practical_tips)
            season_ok = bool(p.best_season)

            if long_ok and tips_ok and season_ok:
                ok.append((slug, p))
            else:
                gaps.append((slug, p, long_ok, tips_ok, season_ok))

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== Enrichment status ({len(NEW_SLUGS)} places) ==="
        ))
        self.stdout.write(f"  OK:      {len(ok)}")
        self.stdout.write(f"  GAP:     {len(gaps)}")
        self.stdout.write(f"  MISSING: {len(missing)}")
        self.stdout.write("")

        if not only_gaps and ok:
            self.stdout.write(self.style.SUCCESS("[OK — enriquecidos]"))
            for slug, p in ok:
                self.stdout.write(
                    f"  ✓ {slug}  long={len(p.long_description)} "
                    f"tips={len(p.practical_tips)} season={p.best_season!r}"
                )
            self.stdout.write("")

        if gaps:
            self.stdout.write(self.style.WARNING("[GAP — falta enrichment]"))
            for slug, p, long_ok, tips_ok, season_ok in gaps:
                marks = []
                if not long_ok:
                    marks.append(f"long={len(p.long_description)}")
                if not tips_ok:
                    marks.append("tips=∅")
                if not season_ok:
                    marks.append("season=∅")
                self.stdout.write(f"  ⚠ {slug}  ({', '.join(marks)})")
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Comandos enrich_place sugeridos:"))
            for slug, *_ in gaps:
                self.stdout.write(f"  python manage.py enrich_place --slug {slug}")
            self.stdout.write("")

        if missing:
            self.stdout.write(self.style.ERROR("[MISSING — no existe el Place]"))
            for slug in missing:
                self.stdout.write(f"  ✗ {slug}")
