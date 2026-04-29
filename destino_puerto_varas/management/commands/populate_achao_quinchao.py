"""Pobla el Circuit #1023 'Achao y Quinchao' con 3 stops FULL_DAY
CULTURE+COUPLE. Crea 2 Places nuevos (curaco-de-velez, achao-iglesia).

Itinerario: Dalcahue (paso ferry) → Curaco de Vélez (pueblo patrimonial,
ostras) → Achao - Iglesia Santa María de Loreto (UNESCO, main).

Uso:
    python manage.py populate_achao_quinchao --dry-run
    python manage.py populate_achao_quinchao
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


CIRCUIT_SLUG = "achao-quinchao"

NEW_PLACES = [
    {
        "slug": "curaco-de-velez",
        "name": "Curaco de Vélez",
        "place_type": "TOWN",
        "partnership_level": "LISTED",
        "location_label": "Isla Quinchao, Archipiélago de Chiloé",
        "latitude": Decimal("-42.443100"),
        "longitude": Decimal("-73.602800"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "is_romantic": True,
        "is_adventure_related": False,
        "short_description": (
            "Pueblo patrimonial de Isla Quinchao con casas centenarias de "
            "tejuelas, mirador a la bahía y fama por sus ostras frescas. "
            "Cuna del marino Galvarino Riveros."
        ),
    },
    {
        "slug": "achao-iglesia-santa-maria-loreto",
        "name": "Iglesia Santa María de Loreto de Achao",
        "place_type": "CHURCH",
        "partnership_level": "LISTED",
        "location_label": "Achao, Isla Quinchao",
        "latitude": Decimal("-42.469700"),
        "longitude": Decimal("-73.491100"),
        "is_family_friendly": True,
        "is_rain_friendly": True,
        "is_romantic": True,
        "is_adventure_related": False,
        "short_description": (
            "La iglesia jesuita más antigua de Chile (c. 1740), Patrimonio "
            "de la Humanidad UNESCO. Construcción en madera ensamblada sin "
            "clavos, con tallas y altares originales del siglo XVIII."
        ),
    },
]

# (place_slug, visit_order, is_main_stop)
STOPS = [
    ("dalcahue", 1, False),
    ("curaco-de-velez", 2, False),
    ("achao-iglesia-santa-maria-loreto", 3, True),
]

DAY_TITLE = "Día 1 · Iglesias jesuitas e islas interiores de Chiloé"
DAY_SUMMARY = (
    "Travesía a Isla Quinchao cruzando en ferry desde Dalcahue. Parada en "
    "Curaco de Vélez para conocer su arquitectura patrimonial y degustar "
    "ostras locales. Cierre en Achao visitando la Iglesia Santa María de "
    "Loreto, joya UNESCO y la más antigua de las iglesias jesuitas de Chiloé."
)


class Command(BaseCommand):
    help = "Pobla el Circuit #1023 'Achao y Quinchao' (3 stops, FULL_DAY CULTURE+COUPLE)."

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
            f"=== populate_achao_quinchao [{('DRY-RUN' if dry else 'APPLY')}] ==="
        ))
        self.stdout.write(f"  Circuit: #{circuit.number} {circuit.name} (slug={circuit.slug})")

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
            self.stdout.write(f"    · CircuitDay día=1 block_type=FULL_DAY")
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
                    "block_type": BlockType.FULL_DAY,
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
