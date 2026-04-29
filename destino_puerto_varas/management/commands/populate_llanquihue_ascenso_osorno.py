"""Pobla el Circuit #1040 'Lago Llanquihue + ascenso Osorno' con 2 días
FULL_DAY ADVENTURE+FRIENDS premium. Crea 1 Place nuevo
(centro-ski-volcan-osorno).

Día 1: Pto Varas costanera + Mirador Philippi + Ensenada mirador +
Volcán Osorno mirador (base, pernocta).
Día 2: Centro Ski Osorno + ascenso técnico + Saltos del Petrohué.

Uso:
    python manage.py populate_llanquihue_ascenso_osorno --dry-run
    python manage.py populate_llanquihue_ascenso_osorno
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


CIRCUIT_SLUG = "lago-llanquihue-ascenso-osorno"

NEW_PLACES = [
    {
        "slug": "centro-ski-volcan-osorno",
        "name": "Centro de Ski y Montaña Volcán Osorno",
        "place_type": "ATTRACTION",
        "partnership_level": "LISTED",
        "location_label": "Volcán Osorno, ladera sur, Comuna de Puerto Varas",
        "latitude": Decimal("-41.106900"),
        "longitude": Decimal("-72.494400"),
        "is_family_friendly": False,
        "is_rain_friendly": False,
        "is_romantic": False,
        "is_adventure_related": True,
        "short_description": (
            "Base de ascenso al volcán Osorno (2.652 m). En verano funciona "
            "andarivel hacia el sector Glaciar (1.670 m), punto de partida "
            "de cumbres técnicas guiadas con crampones y piolet. Cafetería "
            "y arriendo de equipo en la base."
        ),
    },
]

# (day_number, place_slug, visit_order, is_main_stop)
DAYS_STOPS = [
    (1, "puerto-varas-costanera", 1, False),
    (1, "mirador-philippi", 2, False),
    (1, "ensenada-mirador-lago", 3, False),
    (1, "volcan-osorno-mirador", 4, True),
    (2, "centro-ski-volcan-osorno", 1, True),
    (2, "saltos-del-petrohue", 2, False),
]

DAYS = {
    1: {
        "title": "Día 1 · Bordeando el Lago Llanquihue",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Calentamiento bordeando el lago: paseo por la costanera de "
            "Puerto Varas, vista panorámica desde el Mirador Philippi y "
            "fotos en Ensenada con el Volcán Osorno como telón. Ascenso "
            "tarde hasta el mirador del Osorno para reconocimiento del "
            "terreno y briefing con el guía. Pernoctación en lodge de "
            "montaña."
        ),
    },
    2: {
        "title": "Día 2 · Ascenso técnico al Volcán Osorno",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Salida al amanecer desde el Centro de Ski. Ascenso técnico "
            "con crampones y piolet por la ruta sur del Volcán Osorno "
            "(2.652 m), guía especializado y equipo completo. Descenso al "
            "mediodía y celebración en los Saltos del Petrohué con la "
            "cumbre coronada al fondo."
        ),
    },
}


class Command(BaseCommand):
    help = "Pobla el Circuit #1040 'Lago Llanquihue + ascenso Osorno' (2D1N, 1 place nuevo)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

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
            f"=== populate_llanquihue_ascenso_osorno [{('DRY-RUN' if dry else 'APPLY')}] ==="
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
