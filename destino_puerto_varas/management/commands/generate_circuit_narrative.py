"""Genera narrativa editorial de un Circuit usando OpenRouter (DPV CMS-IA · Capa 3).

Uso en Render Shell:
    python manage.py generate_circuit_narrative --slug aventura-lago-llanquihue-3d2n
    python manage.py generate_circuit_narrative --number 102 --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Genera un borrador de narrativa para un Circuit consultando el LLM."

    def add_arguments(self, parser):
        parser.add_argument("--slug", help="Slug del circuito.")
        parser.add_argument("--number", type=int, help="Número del circuito.")
        parser.add_argument("--id", type=int, help="ID del circuito.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Llama al LLM pero NO persiste el draft.",
        )

    def handle(self, *args, **options):
        from destino_puerto_varas.models import Circuit
        from destino_puerto_varas.services.circuit_narrative_service import (
            generate_circuit_narrative,
        )

        slug = options.get("slug")
        number = options.get("number")
        circuit_id = options.get("id")
        dry = options.get("dry_run")

        if not (slug or number or circuit_id):
            raise CommandError("Especifica --slug, --number o --id.")

        try:
            if slug:
                circuit = Circuit.objects.get(slug=slug)
            elif number:
                circuit = Circuit.objects.get(number=number)
            else:
                circuit = Circuit.objects.get(pk=circuit_id)
        except Circuit.DoesNotExist:
            raise CommandError("No existe ese Circuit.")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Generando narrativa: #{circuit.number} — {circuit.name}"
        ))
        self.stdout.write(f"  slug: {circuit.slug}")
        signature = circuit.compute_places_signature()
        self.stdout.write(f"  places_signature actual: {signature}")
        if circuit.is_narrative_stale():
            self.stdout.write(self.style.WARNING("  ⚠ narrativa stale (las paradas cambiaron)."))

        days_count = circuit.days.count()
        stops_count = sum(d.place_stops.count() for d in circuit.days.all())
        self.stdout.write(f"  días: {days_count} · paradas: {stops_count}")

        if stops_count == 0:
            self.stdout.write(self.style.ERROR(
                "  ✗ El circuito no tiene paradas. Aborto — no hay nada que narrar."
            ))
            return

        self.stdout.write("")
        self.stdout.write("  Llamando a OpenRouter (puede tardar 10-30s)...")
        draft = generate_circuit_narrative(circuit, save=not dry)

        if not draft:
            self.stdout.write(self.style.ERROR("  ✗ generate_circuit_narrative retornó None."))
            return

        self.stdout.write("")
        self.stdout.write(f"  status: {draft.status}")
        self.stdout.write(f"  modelo: {draft.llm_model}")
        self.stdout.write(f"  tokens in/out: {draft.llm_input_tokens} / {draft.llm_output_tokens}")
        self.stdout.write(f"  latency: {draft.llm_latency_ms} ms")
        if draft.review_notes:
            self.stdout.write(f"  notas: {draft.review_notes}")

        proposed = draft.proposed_data or {}
        long_desc = (proposed.get("circuit_long_description") or "").strip()
        if long_desc:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"circuit_long_description ({len(long_desc)} chars):"
            ))
            preview = long_desc[:600] + ("..." if len(long_desc) > 600 else "")
            for line in preview.splitlines():
                self.stdout.write(f"  {line}")

        summaries = proposed.get("day_summaries") or {}
        if summaries:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("day_summaries:"))
            for k, v in summaries.items():
                self.stdout.write(f"  Día {k}: {(v or '')[:200]}")

        if dry:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("  ⚠ --dry-run: NO se persistió."))
        else:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Draft #{draft.id} guardado. Revísalo en admin → "
                "Borradores de narrativa."
            ))
