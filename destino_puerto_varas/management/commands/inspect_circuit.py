"""Inspecciona un Circuit y los Places relacionados a un patrón.

Uso:
    python manage.py inspect_circuit 1025
    python manage.py inspect_circuit 1025 --places puyehue,antillanca,anticura
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Circuit, Place


class Command(BaseCommand):
    help = "Muestra metadata de un Circuit + Places que matchean patrones."

    def add_arguments(self, parser):
        parser.add_argument("number", type=int, help="Circuit number (#1025, etc.)")
        parser.add_argument(
            "--places",
            default="",
            help="Patrones (slugs parciales) separados por coma para buscar Places",
        )

    def handle(self, *args, **options):
        number = options["number"]
        patterns = [p.strip() for p in options["places"].split(",") if p.strip()]

        try:
            c = Circuit.objects.get(number=number)
        except Circuit.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Circuit #{number} no existe"))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(f"=== Circuit #{c.number} ==="))
        self.stdout.write(f"  slug: {c.slug}")
        self.stdout.write(f"  name: {c.name}")
        self.stdout.write(f"  published: {c.published}")
        self.stdout.write(f"  duration: {c.duration_case}")
        self.stdout.write(f"  primary_interest: {c.primary_interest}")
        self.stdout.write(f"  recommended_profile: {c.recommended_profile}")
        self.stdout.write(
            "  flags: "
            f"nature={c.is_nature} culture={c.is_culture} adventure={c.is_adventure} "
            f"family={c.is_family_friendly} romantic={c.is_romantic} gastro={c.is_gastronomy} "
            f"rain_friendly={c.is_rain_friendly} premium={c.is_premium}"
        )

        days = list(c.circuit_days.all().prefetch_related("circuitplace_set__place"))
        self.stdout.write(f"  days: {len(days)}")
        for d in days:
            self.stdout.write(f"    Day {d.day_number} — {d.title} [{d.block_type}]")
            for sp in d.circuitplace_set.all().order_by("visit_order"):
                self.stdout.write(f"      - {sp.visit_order:>3} {sp.place.slug} (main={sp.is_main_stop})")

        if patterns:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("=== Places matching ==="))
            from django.db.models import Q
            q = Q()
            for p in patterns:
                q |= Q(slug__icontains=p)
            places = Place.objects.filter(q).order_by("slug")
            if not places:
                self.stdout.write("  (ningún match)")
            for p in places:
                self.stdout.write(f"  {p.slug} | {p.name} | {p.place_type}")
