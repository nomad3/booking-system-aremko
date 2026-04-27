"""Audita qué circuitos tienen días/stops construidos vs son stubs vacíos.

Uso:
    python manage.py audit_circuit_stubs                # solo resumen
    python manage.py audit_circuit_stubs --list-empty   # lista circuitos sin días
    python manage.py audit_circuit_stubs --list-all     # lista todos con conteos
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Count

from destino_puerto_varas.models import Circuit


class Command(BaseCommand):
    help = "Audita circuitos: cuántos tienen días/stops vs son stubs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--list-empty",
            action="store_true",
            help="Lista los circuitos sin días (stubs).",
        )
        parser.add_argument(
            "--list-all",
            action="store_true",
            help="Lista todos los circuitos con sus conteos.",
        )

    def handle(self, *args, **options):
        list_empty = options["list_empty"]
        list_all = options["list_all"]

        qs = (
            Circuit.objects.all()
            .annotate(
                days_count=Count("days", distinct=True),
                stops_count=Count("days__place_stops", distinct=True),
            )
            .order_by("number")
        )

        total = qs.count()
        empty = qs.filter(days_count=0).count()
        with_days = total - empty

        # Categorización adicional
        thin = qs.filter(days_count__gt=0, stops_count__lte=2).count()
        rich = qs.filter(stops_count__gte=3).count()

        self.stdout.write(self.style.MIGRATE_HEADING("=== Auditoría de circuitos ==="))
        self.stdout.write(f"  Total circuitos: {total}")
        self.stdout.write(self.style.WARNING(f"  Sin días (stubs):    {empty}"))
        self.stdout.write(f"  Con días:            {with_days}")
        self.stdout.write(f"    └─ Thin (≤2 stops): {thin}")
        self.stdout.write(f"    └─ Rich (≥3 stops): {rich}")
        self.stdout.write("")

        if list_empty:
            self.stdout.write(self.style.MIGRATE_HEADING("--- Circuitos sin días (stubs) ---"))
            for c in qs.filter(days_count=0):
                pub = "✓" if c.published else "✗"
                self.stdout.write(
                    f"  [{pub}] #{c.number} · {c.primary_interest} · "
                    f"{c.recommended_profile or '-'} · {c.name} [{c.slug}]"
                )

        if list_all:
            self.stdout.write(self.style.MIGRATE_HEADING("--- Todos los circuitos con conteos ---"))
            for c in qs:
                pub = "✓" if c.published else "✗"
                tag = "STUB" if c.days_count == 0 else (
                    "thin" if c.stops_count <= 2 else "rich"
                )
                self.stdout.write(
                    f"  [{pub}] #{c.number} [{tag:4}] {c.days_count}d/{c.stops_count}s · "
                    f"{c.name} [{c.slug}]"
                )
