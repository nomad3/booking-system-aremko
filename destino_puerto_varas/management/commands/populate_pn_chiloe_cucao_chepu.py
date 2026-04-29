"""Pobla el Circuit #1049 'PN Chiloé + Cucao + Chepu' con 2 días FULL_DAY
NATURE+FAMILY. Crea 3 Places nuevos.

Día 1: PN Chiloé sector Anay (Cucao) + Lago Cucao.
Día 2: Humedales de Chepu (avistamiento + bote opcional).

Uso:
    python manage.py populate_pn_chiloe_cucao_chepu --dry-run
    python manage.py populate_pn_chiloe_cucao_chepu
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


CIRCUIT_SLUG = "pn-chiloe-cucao-chepu"

NEW_PLACES = [
    {
        "slug": "pn-chiloe-cucao",
        "name": "Parque Nacional Chiloé · Sector Anay (Cucao)",
        "place_type": "PARK",
        "partnership_level": "LISTED",
        "location_label": "Cucao, comuna de Chonchi, Isla Grande de Chiloé",
        "latitude": Decimal("-42.633500"),
        "longitude": Decimal("-74.108300"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "is_romantic": False,
        "is_adventure_related": True,
        "short_description": (
            "Sector Anay del PN Chiloé, con senderos El Tepual y Dunas de "
            "Cucao a través de bosque siempreverde y costa pacífica. "
            "Administrado por CONAF, con centro de visitantes y miradores."
        ),
    },
    {
        "slug": "lago-cucao",
        "name": "Lago Cucao",
        "place_type": "ATTRACTION",
        "partnership_level": "LISTED",
        "location_label": "Cucao, costa oeste de Chiloé",
        "latitude": Decimal("-42.629400"),
        "longitude": Decimal("-74.099400"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "is_romantic": True,
        "is_adventure_related": False,
        "short_description": (
            "Gran lago de origen glaciar separado del Pacífico solo por "
            "dunas. Aguas oscuras, kayak posible, bordes con bosque nativo "
            "y entrada al PN Chiloé."
        ),
    },
    {
        "slug": "humedales-chepu",
        "name": "Humedales de Chepu",
        "place_type": "ATTRACTION",
        "partnership_level": "LISTED",
        "location_label": "Chepu, comuna de Ancud, norte de Chiloé",
        "latitude": Decimal("-42.073900"),
        "longitude": Decimal("-74.025000"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "is_romantic": False,
        "is_adventure_related": True,
        "short_description": (
            "Sistema de humedales y bosque hundido formado por el terremoto "
            "de 1960. Avistamiento de aves al amanecer, kayak por los "
            "esteros y comunidades rurales con turismo sustentable."
        ),
    },
]

# (day_number, place_slug, visit_order, is_main_stop)
DAYS_STOPS = [
    (1, "pn-chiloe-cucao", 1, True),
    (1, "lago-cucao", 2, False),
    (2, "humedales-chepu", 1, True),
]

DAYS = {
    1: {
        "title": "Día 1 · Bosque y costa en PN Chiloé",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Llegada a Cucao y entrada al sector Anay del Parque Nacional "
            "Chiloé. Sendero El Tepual entre tepúes centenarios y caminata "
            "por las dunas hasta la playa abierta al Pacífico. Cierre en el "
            "Lago Cucao con opción de kayak. Pernoctación en Cucao o Chonchi."
        ),
    },
    2: {
        "title": "Día 2 · Humedales y bosque hundido en Chepu",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Traslado al sector de Chepu en el norte de la isla. Recorrido "
            "por los humedales al amanecer para avistamiento de aves, "
            "navegación opcional en bote o kayak por los esteros del bosque "
            "hundido y almuerzo en operadores locales antes del retorno."
        ),
    },
}


class Command(BaseCommand):
    help = "Pobla el Circuit #1049 'PN Chiloé + Cucao + Chepu' (2D1N, 3 places nuevos)."

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
            f"=== populate_pn_chiloe_cucao_chepu [{('DRY-RUN' if dry else 'APPLY')}] ==="
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
