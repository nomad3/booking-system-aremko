"""Genera narrativas IA (long_description) para los 8 circuits poblados
en la tanda 2026-04-27/28.

Crea drafts vía generate_circuit_narrative para cada uno. Los drafts
quedan en estado DRAFT y deben revisarse/aplicarse vía admin.

Uso:
    python manage.py generate_narratives_for_new_circuits --dry-run
    python manage.py generate_narratives_for_new_circuits
    python manage.py generate_narratives_for_new_circuits --skip-existing
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Circuit


NEW_CIRCUIT_NUMBERS = [
    1001,  # Puerto Varas patrimonial
    1005,  # Las Cascadas y salto
    1017,  # Cochamó pueblo + Ralún
    1025,  # Puyehue Aguas Calientes
    1027,  # Ancud + Puñihuil
    1030,  # Puerto Montt + Tenglo + Angelmó
    1033,  # Castro + Dalcahue + Tocoihue + Putemún
    1045,  # Puyehue slow
]


class Command(BaseCommand):
    help = "Genera narrativas IA para los 8 circuits poblados en la tanda 2026-04-27/28."

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

    def handle(self, *args, **options):
        from destino_puerto_varas.services.circuit_narrative_service import (
            generate_circuit_narrative,
        )

        dry = options["dry_run"]
        skip_existing = options["skip_existing"]

        generated, skipped, failed = 0, 0, 0

        for n in NEW_CIRCUIT_NUMBERS:
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

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Resumen: generados={generated}, skipped={skipped}, failed={failed}"
        ))
        if dry:
            self.stdout.write(self.style.WARNING("(--dry-run: no se persistió ningún draft)"))
        elif generated:
            self.stdout.write(
                "Revisa los drafts en admin → "
                "Borradores de narrativa de Circuit y aplícalos."
            )
