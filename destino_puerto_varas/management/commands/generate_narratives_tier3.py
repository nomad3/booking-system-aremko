"""Genera narrativas IA para los 2 circuits de Tier 3 (#1040 y #1042).

Uso:
    python manage.py generate_narratives_tier3 --dry-run
    python manage.py generate_narratives_tier3 --apply
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Circuit


PENDING_CIRCUIT_NUMBERS = [
    1040,  # Lago Llanquihue + ascenso Osorno
    1042,  # Valle de Cochamó pernocta
]


class Command(BaseCommand):
    help = "Genera narrativas IA para los 2 circuits Tier 3."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--skip-existing", action="store_true",
                            help="Salta circuits con long_description > 200 chars.")
        parser.add_argument("--apply", action="store_true",
                            help="Tras generar, aprueba y aplica el draft.")

    def handle(self, *args, **options):
        from destino_puerto_varas.models import CircuitNarrativeDraft
        from destino_puerto_varas.services.circuit_narrative_service import (
            apply_narrative_draft,
            generate_circuit_narrative,
        )

        dry = options["dry_run"]
        skip_existing = options["skip_existing"]
        apply = options["apply"]

        if dry and apply:
            self.stdout.write(self.style.WARNING(
                "(--dry-run + --apply): --apply ignorado"
            ))
            apply = False

        generated, applied_count, skipped, failed = 0, 0, 0, 0

        for n in PENDING_CIRCUIT_NUMBERS:
            c = Circuit.objects.filter(number=n).first()
            if not c:
                self.stdout.write(self.style.ERROR(f"  ✗ #{n}: no existe"))
                failed += 1
                continue

            existing_len = len(c.long_description or "")
            if skip_existing and existing_len > 200:
                self.stdout.write(self.style.SUCCESS(
                    f"  · #{n} {c.name}: long={existing_len} (skip)"
                ))
                skipped += 1
                continue

            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"=== #{n} {c.name} (long actual: {existing_len} chars) ==="
            ))

            try:
                draft = generate_circuit_narrative(c, save=not dry)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ error: {e}"))
                failed += 1
                continue

            if not draft:
                self.stdout.write(self.style.ERROR("  ✗ generate retornó None"))
                failed += 1
                continue

            self.stdout.write(f"  status: {draft.status}")
            self.stdout.write(f"  modelo: {draft.llm_model}")
            self.stdout.write(
                f"  tokens in/out: {draft.llm_input_tokens} / {draft.llm_output_tokens}"
            )
            proposed = (draft.proposed_data or {}).get("circuit_long_description") or ""
            self.stdout.write(f"  long_description propuesto: {len(proposed)} chars")
            if proposed:
                preview = proposed[:200] + ("..." if len(proposed) > 200 else "")
                self.stdout.write(f"    {preview}")

            generated += 1

            if apply and draft.id:
                if draft.status != CircuitNarrativeDraft.STATUS_APPROVED:
                    draft.status = CircuitNarrativeDraft.STATUS_APPROVED
                    draft.save(update_fields=["status"])
                ok = apply_narrative_draft(draft, reviewer="generate_narratives_tier3")
                if ok:
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✓ draft #{draft.id} aplicado al Circuit"
                    ))
                    applied_count += 1
                else:
                    self.stdout.write(self.style.ERROR(
                        f"  ✗ apply_narrative_draft retornó False"
                    ))

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Resumen: generados={generated}, aplicados={applied_count}, "
            f"skipped={skipped}, failed={failed}"
        ))
