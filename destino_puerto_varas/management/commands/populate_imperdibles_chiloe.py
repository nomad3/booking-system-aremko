"""Pobla el Circuit #1050 'Imperdibles de Chiloé' con 3 días FULL_DAY
MIXED+FAMILY. Crea 2 Places nuevos (isla-aucar, parque-tantauco).

Día 1: Castro Iglesia + Palafitos + Putemún.
Día 2: Quemchi + Isla Aucar + Dalcahue + Curaco + Achao Iglesia.
Día 3: Parque Tantauco (sector norte).

Uso:
    python manage.py populate_imperdibles_chiloe --dry-run
    python manage.py populate_imperdibles_chiloe
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


CIRCUIT_SLUG = "imperdibles-chiloe"

NEW_PLACES = [
    {
        "slug": "isla-aucar",
        "name": "Isla Aucar",
        "place_type": "ATTRACTION",
        "partnership_level": "LISTED",
        "location_label": "Quemchi, norte de Chiloé",
        "latitude": Decimal("-42.150000"),
        "longitude": Decimal("-73.484700"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "is_romantic": True,
        "is_adventure_related": False,
        "short_description": (
            "Conocida como 'Isla de las almas navegantes', se accede por "
            "una pasarela de madera de 500 m sobre el mar. Iglesia "
            "patrimonial, cementerio histórico y jardín botánico nativo "
            "creado por el escritor chilote Carlos Trujillo."
        ),
    },
    {
        "slug": "parque-tantauco",
        "name": "Parque Tantauco",
        "place_type": "PARK",
        "partnership_level": "LISTED",
        "location_label": "Sur de la Isla Grande de Chiloé",
        "latitude": Decimal("-43.066700"),
        "longitude": Decimal("-74.116700"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "is_romantic": False,
        "is_adventure_related": True,
        "short_description": (
            "Parque privado de conservación de 118.000 hectáreas en el "
            "extremo sur de Chiloé. Bosques milenarios, lagunas, fauna "
            "nativa y senderos desde 2 horas hasta multi-día. Sector "
            "Inio (sur) y Caleta Inio acceso por mar o vuelo."
        ),
    },
]

# (day_number, place_slug, visit_order, is_main_stop)
DAYS_STOPS = [
    (1, "iglesia-san-francisco-castro", 1, True),
    (1, "palafitos-castro", 2, True),
    (1, "iglesia-de-putemun", 3, False),
    (2, "isla-aucar", 1, True),
    (2, "dalcahue", 2, False),
    (2, "curaco-de-velez", 3, False),
    (2, "achao-iglesia-santa-maria-loreto", 4, True),
    (3, "parque-tantauco", 1, True),
]

DAYS = {
    1: {
        "title": "Día 1 · Castro patrimonial",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Llegada a Castro y exploración de su núcleo patrimonial: la "
            "Iglesia San Francisco (UNESCO), los palafitos de Gamboa y "
            "Pedro Montt, y tarde en la Iglesia de Putemún. Pernoctación "
            "en Castro."
        ),
    },
    2: {
        "title": "Día 2 · Norte de Chiloé y Quinchao",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Mañana hacia Quemchi para visitar la Isla Aucar por su "
            "pasarela sobre el mar. Bajada a Dalcahue para tomar el ferry "
            "a Quinchao, almuerzo de ostras en Curaco de Vélez y cierre en "
            "la Iglesia Santa María de Loreto de Achao (UNESCO). Retorno "
            "a Castro."
        ),
    },
    3: {
        "title": "Día 3 · Parque Tantauco al sur",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Día completo en el Parque Tantauco, reserva privada de 118.000 "
            "hectáreas. Sendero por bosque siempreverde, miradores a las "
            "lagunas y posibilidad de avistar pudúes y zorros chilotes "
            "antes del regreso al continente."
        ),
    },
}


class Command(BaseCommand):
    help = "Pobla el Circuit #1050 'Imperdibles de Chiloé' (3D2N, 2 places nuevos)."

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
            f"=== populate_imperdibles_chiloe [{('DRY-RUN' if dry else 'APPLY')}] ==="
        ))
        self.stdout.write(f"  Circuit: #{circuit.number} {circuit.name} (slug={circuit.slug})")

        new_slugs = {p["slug"] for p in NEW_PLACES}
        all_slugs = {slug for _, slug, _, _ in DAYS_STOPS}
        missing_existing = []
        for slug in all_slugs:
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
            for day_num, info in DAYS.items():
                self.stdout.write(f"    · CircuitDay día={day_num} block_type=FULL_DAY")
                for d, slug, order, is_main in DAYS_STOPS:
                    if d != day_num:
                        continue
                    tag = " ⭐ main" if is_main else ""
                    self.stdout.write(f"        stop {order}: {slug}{tag}")
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

            day_objs = {}
            for day_num, info in DAYS.items():
                day, day_created = CircuitDay.objects.get_or_create(
                    circuit=circuit,
                    day_number=day_num,
                    defaults={
                        "title": info["title"],
                        "block_type": info["block_type"],
                        "summary": info["summary"],
                        "sort_order": day_num,
                    },
                )
                day_objs[day_num] = day
                if day_created:
                    self.stdout.write(f"  ✓ CircuitDay día {day_num} creado")
                else:
                    self.stdout.write(f"  · CircuitDay día {day_num} ya existía")

            for day_num, slug, order, is_main in DAYS_STOPS:
                place = Place.objects.get(slug=slug)
                stop, created = CircuitPlace.objects.get_or_create(
                    circuit_day=day_objs[day_num],
                    place=place,
                    defaults={
                        "visit_order": order,
                        "is_main_stop": is_main,
                    },
                )
                if created:
                    self.stdout.write(f"    ✓ stop d{day_num}/{order}: {slug}")
                else:
                    self.stdout.write(f"    · stop d{day_num}/{order}: {slug} (ya existía)")

            if not circuit.published:
                circuit.published = True
                circuit.save(update_fields=["published"])
                self.stdout.write(self.style.SUCCESS("  ✓ Circuit publicado"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Listo."))
