"""Aplica el draft más reciente (DRAFT/APPROVED) de los 5 places que quedaron
con gaps de enrichment tras la tanda 2026-04-28.

Uso:
    python manage.py apply_drafts_for_gap_places
    python manage.py apply_drafts_for_gap_places --dry-run
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Place, PlaceEnrichmentDraft


GAP_SLUGS = [
    "iglesia-san-francisco-castro",
    "iglesia-de-putemun",
    "iglesia-de-tocoihue",
    "mirador-estuario-reloncavi",
    "ralun",
]


class Command(BaseCommand):
    help = "Aplica el último draft pendiente de los 5 places con gaps."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo lista qué se aplicaría, sin tocar BD.",
        )

    def handle(self, *args, **options):
        from destino_puerto_varas.services.place_enrichment_service import apply_draft

        dry = options["dry_run"]
        applied, skipped, missing = 0, 0, 0

        for slug in GAP_SLUGS:
            p = Place.objects.filter(slug=slug).first()
            if not p:
                self.stdout.write(self.style.ERROR(f"  ✗ MISSING: {slug}"))
                missing += 1
                continue

            d = (
                p.enrichment_drafts.filter(
                    status__in=[
                        PlaceEnrichmentDraft.STATUS_DRAFT,
                        PlaceEnrichmentDraft.STATUS_APPROVED,
                    ]
                )
                .order_by("-created_at")
                .first()
            )

            if not d:
                self.stdout.write(self.style.WARNING(
                    f"  · {slug}: sin drafts pendientes (DRAFT/APPROVED)"
                ))
                skipped += 1
                continue

            self.stdout.write(
                f"  → {slug}: draft #{d.id} (status={d.status}, "
                f"creado={d.created_at:%Y-%m-%d %H:%M})"
            )

            if dry:
                continue

            if d.status != PlaceEnrichmentDraft.STATUS_APPROVED:
                d.status = PlaceEnrichmentDraft.STATUS_APPROVED
                d.save(update_fields=["status"])

            ok = apply_draft(d, reviewer="apply_drafts_for_gap_places")
            if ok:
                self.stdout.write(self.style.SUCCESS(f"    ✓ aplicado"))
                applied += 1
            else:
                self.stdout.write(self.style.ERROR(f"    ✗ apply_draft retornó False"))

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Resumen: aplicados={applied}, sin-draft={skipped}, missing={missing}"
        ))
        if dry:
            self.stdout.write(self.style.WARNING("(--dry-run: nada se persistió)"))
