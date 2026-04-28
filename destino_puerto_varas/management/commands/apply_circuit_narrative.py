"""Aprueba y aplica el último draft de narrativa de un Circuit.

Uso:
    python manage.py apply_circuit_narrative --number 1032
    python manage.py apply_circuit_narrative --slug vuelta-este-llanquihue
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from destino_puerto_varas.models import Circuit, CircuitNarrativeDraft


class Command(BaseCommand):
    help = "Aprueba y aplica el último draft de narrativa de un Circuit."

    def add_arguments(self, parser):
        parser.add_argument("--number", type=int, help="Número del circuit.")
        parser.add_argument("--slug", help="Slug del circuit.")
        parser.add_argument("--id", type=int, help="ID del circuit.")

    def handle(self, *args, **options):
        from destino_puerto_varas.services.circuit_narrative_service import (
            apply_narrative_draft,
        )

        number = options.get("number")
        slug = options.get("slug")
        circuit_id = options.get("id")

        if not (number or slug or circuit_id):
            raise CommandError("Especifica --number, --slug o --id.")

        try:
            if number:
                circuit = Circuit.objects.get(number=number)
            elif slug:
                circuit = Circuit.objects.get(slug=slug)
            else:
                circuit = Circuit.objects.get(pk=circuit_id)
        except Circuit.DoesNotExist:
            raise CommandError("No existe ese Circuit.")

        d = (
            circuit.narrative_drafts.filter(
                status__in=[
                    CircuitNarrativeDraft.STATUS_DRAFT,
                    CircuitNarrativeDraft.STATUS_APPROVED,
                ]
            )
            .order_by("-created_at")
            .first()
        )
        if not d:
            self.stdout.write(self.style.WARNING(
                f"#{circuit.number} {circuit.name}: sin drafts pendientes."
            ))
            return

        self.stdout.write(
            f"#{circuit.number} {circuit.name} → draft #{d.id} "
            f"(status={d.status}, creado={d.created_at:%Y-%m-%d %H:%M})"
        )

        if d.status != CircuitNarrativeDraft.STATUS_APPROVED:
            d.status = CircuitNarrativeDraft.STATUS_APPROVED
            d.save(update_fields=["status"])

        ok = apply_narrative_draft(d, reviewer="apply_circuit_narrative")
        if ok:
            self.stdout.write(self.style.SUCCESS(f"  ✓ aplicado al Circuit"))
        else:
            self.stdout.write(self.style.ERROR(f"  ✗ apply_narrative_draft retornó False"))
