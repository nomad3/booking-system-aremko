"""Pobla el Circuit #1007 'Monumento Natural Lahuén Ñadi' con 3 stops
HALF_DAY NATURE+FAMILY. Crea 1 Place nuevo (lahuen-nadi).

Itinerario: Lahuén Ñadi sendero alerces (main, 1.5h) → Mirador Manuel Montt
(vista bahía) → Plaza Catedral Pto Montt (café + paseo histórico).

Uso:
    python manage.py populate_lahuen_nadi --dry-run
    python manage.py populate_lahuen_nadi
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.models import (
    BlockType,
    Circuit,
    CircuitDay,
    CircuitPlace,
    Place,
)


CIRCUIT_SLUG = "lahuen-nadi"

NEW_PLACES = [
    {
        "slug": "lahuen-nadi-monumento",
        "name": "Monumento Natural Lahuén Ñadi",
        "place_type": "PARK",
        "partnership_level": "LISTED",
        "location_label": "Sector Trapén, norte de Puerto Montt",
        "latitude": Decimal("-41.395600"),
        "longitude": Decimal("-72.972200"),
        "is_family_friendly": True,
        "is_rain_friendly": True,
        "is_romantic": False,
        "is_adventure_related": False,
        "short_description": (
            "Reserva CONAF de 200 hectáreas con alerces milenarios de hasta 3.500 años. "
            "Sendero accesible de 1-2 km a través de bosque húmedo siempreverde."
        ),
    },
]

# (place_slug, visit_order, is_main_stop)
STOPS = [
    ("lahuen-nadi-monumento", 1, True),
    ("mirador-manuel-montt", 2, False),
    ("puerto-montt-plaza-catedral", 3, False),
]

DAY_TITLE = "Día 1 · Alerces milenarios y casco histórico"
DAY_SUMMARY = (
    "Mañana en el Monumento Natural Lahuén Ñadi recorriendo el sendero entre "
    "alerces milenarios. Almuerzo en Puerto Montt con paseo por la costanera "
    "y la Plaza de Armas con su catedral patrimonial."
)


class Command(BaseCommand):
    help = "Pobla el Circuit #1007 'Lahuén Ñadi' (3 stops, HALF_DAY NATURE+FAMILY)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué se haría sin tocar la BD.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]

        try:
            circuit = Circuit.objects.get(slug=CIRCUIT_SLUG)
        except Circuit.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"  ✗ No existe Circuit con slug {CIRCUIT_SLUG}"
            ))
            return

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== populate_lahuen_nadi [{('DRY-RUN' if dry else 'APPLY')}] ==="
        ))
        self.stdout.write(f"  Circuit: #{circuit.number} {circuit.name} (slug={circuit.slug})")

        # Validar Places existentes (no creados por este comando)
        new_slugs = {p["slug"] for p in NEW_PLACES}
        missing_existing = []
        for slug, _, _ in STOPS:
            if slug in new_slugs:
                continue
            if not Place.objects.filter(slug=slug).exists():
                missing_existing.append(slug)
        if missing_existing:
            self.stdout.write(self.style.ERROR(
                f"  ✗ Faltan Places existentes en BD: {', '.join(missing_existing)}. Aborto."
            ))
            return

        if dry:
            self.stdout.write("")
            self.stdout.write("  [dry-run] Crearía:")
            for p in NEW_PLACES:
                exists = Place.objects.filter(slug=p["slug"]).exists()
                tag = "(ya existe)" if exists else "NUEVO"
                self.stdout.write(f"    · Place {p['slug']} {tag}")
            self.stdout.write(f"    · CircuitDay día=1 block_type=HALF_DAY")
            for slug, order, is_main in STOPS:
                tag = " ⭐ main" if is_main else ""
                self.stdout.write(f"    · stop {order}: {slug}{tag}")
            if not circuit.published:
                self.stdout.write("    · Circuit.published = True")
            return

        with transaction.atomic():
            for p in NEW_PLACES:
                place, created = Place.objects.get_or_create(
                    slug=p["slug"],
                    defaults={
                        "name": p["name"],
                        "place_type": p["place_type"],
                        "partnership_level": p["partnership_level"],
                        "location_label": p["location_label"],
                        "latitude": p["latitude"],
                        "longitude": p["longitude"],
                        "is_family_friendly": p["is_family_friendly"],
                        "is_rain_friendly": p["is_rain_friendly"],
                        "is_romantic": p["is_romantic"],
                        "is_adventure_related": p["is_adventure_related"],
                        "short_description": p["short_description"],
                    },
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Place creado: {p['slug']}"))
                else:
                    self.stdout.write(f"  · Place ya existía: {p['slug']}")

            day, day_created = CircuitDay.objects.get_or_create(
                circuit=circuit,
                day_number=1,
                defaults={
                    "title": DAY_TITLE,
                    "block_type": BlockType.HALF_DAY,
                    "summary": DAY_SUMMARY,
                    "sort_order": 1,
                },
            )
            if day_created:
                self.stdout.write("  ✓ CircuitDay día 1 creado")
            else:
                self.stdout.write("  · CircuitDay día 1 ya existía")

            for slug, order, is_main in STOPS:
                place = Place.objects.get(slug=slug)
                stop, created = CircuitPlace.objects.get_or_create(
                    circuit_day=day,
                    place=place,
                    defaults={
                        "visit_order": order,
                        "is_main_stop": is_main,
                    },
                )
                if created:
                    self.stdout.write(f"    ✓ stop {order}: {slug}")
                else:
                    self.stdout.write(f"    · stop {order}: {slug} (ya existía)")

            if not circuit.published:
                circuit.published = True
                circuit.save(update_fields=["published"])
                self.stdout.write(self.style.SUCCESS("  ✓ Circuit publicado"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Listo."))
