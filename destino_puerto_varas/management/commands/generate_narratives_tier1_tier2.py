"""Genera narrativas IA (long_description) para los 4 circuits de Tier 1
fase 2 (sin narrativa) + 4 circuits de Tier 2 Chiloé.

Uso:
    python manage.py generate_narratives_tier1_tier2 --dry-run
    python manage.py generate_narratives_tier1_tier2 --apply
    python manage.py generate_narratives_tier1_tier2 --skip-existing --apply
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Circuit


PENDING_CIRCUIT_NUMBERS = [
    # Tier 1 fase 2 (poblados 2026-04-28 sin narrativa)
    1032,  # Vuelta este Llanquihue
    1007,  # Lahuén Ñadi
    1037,  # Valle Cochamó + Cascada Escondida
    1039,  # Puyehue Anticura senderos
    # Tier 2 Chiloé extendido (poblados 2026-04-29)
    1023,  # Achao + Quinchao
    1044,  # Chiloé central patrimonial
    1049,  # PN Chiloé + Cucao + Chepu
    1050,  # Imperdibles de Chiloé
]


class Command(BaseCommand):
    help = "Genera narrativas IA para los 8 circuits Tier 1 fase 2 + Tier 2 Chiloé."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Llama al LLM pero NO persiste los drafts.",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Salta circuits que ya tienen long_description > 200 chars.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Tras generar el draft, lo aprueba y aplica al Circuit.",
        )

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
                "(--dry-run + --apply): --apply ignorado (no hay draft persistido)"
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
                ok = apply_narrative_draft(
                    draft, reviewer="generate_narratives_tier1_tier2"
                )
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
            f"Resumen: generados={generated}, "
            f"aplicados={applied_count}, skipped={skipped}, failed={failed}"
        ))
        if dry:
            self.stdout.write(self.style.WARNING("(--dry-run: no se persistió ningún draft)"))
