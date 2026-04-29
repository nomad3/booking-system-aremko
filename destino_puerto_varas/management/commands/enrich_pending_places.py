"""Enriquece (Perplexity + OpenRouter) los Places nuevos creados en
Tier 1 (3 places de #1007/#1037 — yesterday's leftovers) y Tier 2
Chiloé (7 places de #1023/#1049/#1050).

Genera drafts en DRAFT y opcionalmente los aprueba+aplica con --apply.

Uso:
    python manage.py enrich_pending_places --dry-run     # solo lista
    python manage.py enrich_pending_places               # genera drafts
    python manage.py enrich_pending_places --apply       # genera + aplica
    python manage.py enrich_pending_places --skip-existing  # skip los que ya tienen draft aplicado
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


PENDING_SLUGS = [
    # Tier 1 leftovers (2026-04-28)
    "lahuen-nadi-monumento",
    "sendero-el-arcoiris-cochamo",
    "cascada-escondida-cochamo",
    # Tier 2 — Chiloé extendido (2026-04-29)
    "curaco-de-velez",
    "achao-iglesia-santa-maria-loreto",
    "pn-chiloe-cucao",
    "lago-cucao",
    "humedales-chepu",
    "isla-aucar",
    "parque-tantauco",
]


class Command(BaseCommand):
    help = "Enriquece Places nuevos pendientes (Tier 1 leftovers + Tier 2 Chiloé)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo lista los slugs sin llamar al LLM.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Tras enriquecer, aprueba y aplica el draft al Place.",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Saltar places que ya tengan al menos un draft APPLIED.",
        )

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
            f"=== enrich_pending_places "
            f"[{'DRY-RUN' if dry else 'APPLY' if do_apply else 'ENRICH-ONLY'}] ==="
        ))
        self.stdout.write(f"  Places en cola: {len(PENDING_SLUGS)}")

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
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"  → {slug} (id={place.id})"
            ))

            if dry:
                self.stdout.write(f"    [dry-run] enrich_place({slug})")
                if do_apply:
                    self.stdout.write(f"    [dry-run] apply_draft(latest)")
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
                ok = apply_draft(draft, reviewer="enrich_pending_places")
                if ok:
                    self.stdout.write(self.style.SUCCESS("    ✓ Draft aplicado al Place"))
                    applied += 1
                else:
                    self.stdout.write(self.style.ERROR(
                        "    ✗ apply_draft retornó False"
                    ))
                    failed += 1

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Resumen: enriquecidos={enriched}, aplicados={applied}, "
            f"saltados={skipped}, missing={missing}, fallidos={failed}"
        ))
