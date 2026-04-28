"""Pobla el Circuit #1037 'Valle de Cochamó base + Cascada Escondida' con
3 stops FULL_DAY ADVENTURE+FRIENDS. Crea 2 Places nuevos.

Itinerario: PV → Cochamó pueblo → Sendero El Arcoíris (trailhead) →
Cascada Escondida (main, trekking ~3h ida).

Uso:
    python manage.py populate_valle_cochamo_cascada --dry-run
    python manage.py populate_valle_cochamo_cascada
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


CIRCUIT_SLUG = "valle-cochamo-cascada-escondida"

NEW_PLACES = [
    {
        "slug": "sendero-el-arcoiris-cochamo",
        "name": "Sendero El Arcoíris — entrada Valle de Cochamó",
        "place_type": "ATTRACTION",
        "partnership_level": "LISTED",
        "location_label": "Cochamó, ruta hacia La Junta",
        "latitude": Decimal("-41.498000"),
        "longitude": Decimal("-72.282000"),
        "is_family_friendly": False,
        "is_rain_friendly": False,
        "is_romantic": False,
        "is_adventure_related": True,
        "short_description": (
            "Punto de inicio del sendero histórico al Valle de Cochamó. Registro obligatorio "
            "con guardaparques en la garita El Arcoíris antes de comenzar el trekking."
        ),
    },
    {
        "slug": "cascada-escondida-cochamo",
        "name": "Cascada Escondida (Valle de Cochamó)",
        "place_type": "ATTRACTION",
        "partnership_level": "LISTED",
        "location_label": "Sendero Valle de Cochamó",
        "latitude": Decimal("-41.485000"),
        "longitude": Decimal("-72.255000"),
        "is_family_friendly": False,
        "is_rain_friendly": False,
        "is_romantic": False,
        "is_adventure_related": True,
        "short_description": (
            "Cascada en bosque siempreverde a unas 3 horas de trekking desde El Arcoíris. "
            "Punto de retorno habitual para visitas de un día al Valle de Cochamó."
        ),
    },
]

# (place_slug, visit_order, is_main_stop)
STOPS = [
    ("cochamo", 1, False),
    ("sendero-el-arcoiris-cochamo", 2, False),
    ("cascada-escondida-cochamo", 3, True),
]

DAY_TITLE = "Día 1 · Trekking al Valle de Cochamó"
DAY_SUMMARY = (
    "Día completo de aventura: paso por Cochamó pueblo, registro en la garita "
    "El Arcoíris y trekking hasta Cascada Escondida en bosque siempreverde, "
    "con vistas a las paredes de granito del 'Yosemite chileno'."
)


class Command(BaseCommand):
    help = "Pobla el Circuit #1037 'Valle de Cochamó + Cascada Escondida' (3 stops, ADVENTURE)."

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
            f"=== populate_valle_cochamo_cascada [{('DRY-RUN' if dry else 'APPLY')}] ==="
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
                f"  ✗ Faltan Places existentes: {', '.join(missing_existing)}. Aborto."
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
