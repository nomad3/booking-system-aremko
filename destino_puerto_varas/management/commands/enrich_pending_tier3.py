"""Enriquece los 2 Places nuevos de Tier 3 (#1040 y #1042).

Uso:
    python manage.py enrich_pending_tier3 --dry-run
    python manage.py enrich_pending_tier3 --apply
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


PENDING_SLUGS = [
    "centro-ski-volcan-osorno",
    "valle-cochamo-la-junta",
]


class Command(BaseCommand):
    help = "Enriquece los 2 places nuevos de Tier 3 (centro-ski-osorno + valle-cochamo-la-junta)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true",
                            help="Tras enriquecer, aprueba y aplica el draft.")
        parser.add_argument("--skip-existing", action="store_true",
                            help="Salta places con draft APPLIED ya.")

    def handle(self, *args, **options):
        from destino_puerto_varas.models import Place, PlaceEnrichmentDraft
        from destino_puerto_varas.services.place_enrichment_service import (
            enrich_place,
            apply_draft,
            is_enrichment_available,
        )

        dry = options["dry_run"]
        do_apply = options["apply"]
        skip_existing = options["skip_existing"]

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== enrich_pending_tier3 "
            f"[{'DRY-RUN' if dry else 'APPLY' if do_apply else 'ENRICH-ONLY'}] ==="
        ))

        if not dry and not is_enrichment_available():
            self.stdout.write(self.style.ERROR(
                "  ✗ Faltan PERPLEXITY_API_KEY u OPENROUTER_API_KEY. Aborto."
            ))
            return

        enriched, applied, skipped, missing, failed = 0, 0, 0, 0, 0

        for slug in PENDING_SLUGS:
            place = Place.objects.filter(slug=slug).first()
            if not place:
                self.stdout.write(self.style.ERROR(f"  ✗ MISSING: {slug}"))
                missing += 1
                continue

            if skip_existing and place.enrichment_drafts.filter(
                status=PlaceEnrichmentDraft.STATUS_APPLIED
            ).exists():
                self.stdout.write(f"  · {slug}: ya tiene draft APPLIED, skip")
                skipped += 1
                continue

            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(f"  → {slug} (id={place.id})"))

            if dry:
                self.stdout.write(f"    [dry-run] enrich + apply" if do_apply else "    [dry-run] enrich")
                continue

            try:
                draft = enrich_place(place, save=True)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    ✗ enrich falló: {e}"))
                failed += 1
                continue

            if not draft:
                self.stdout.write(self.style.ERROR("    ✗ enrich_place retornó None"))
                failed += 1
                continue

            self.stdout.write(self.style.SUCCESS(
                f"    ✓ Draft #{draft.id} status={draft.status} "
                f"({draft.llm_input_tokens}/{draft.llm_output_tokens} tk, "
                f"{draft.llm_latency_ms}ms)"
            ))
            enriched += 1

            if do_apply:
                if draft.status != PlaceEnrichmentDraft.STATUS_APPROVED:
                    draft.status = PlaceEnrichmentDraft.STATUS_APPROVED
                    draft.save(update_fields=["status"])
                ok = apply_draft(draft, reviewer="enrich_pending_tier3")
                if ok:
                    self.stdout.write(self.style.SUCCESS("    ✓ Draft aplicado al Place"))
                    applied += 1
                else:
                    self.stdout.write(self.style.ERROR("    ✗ apply_draft retornó False"))
                    failed += 1

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Resumen: enriquecidos={enriched}, aplicados={applied}, "
            f"saltados={skipped}, missing={missing}, fallidos={failed}"
        ))
