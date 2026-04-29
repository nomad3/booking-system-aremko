"""Pobla el Circuit #1042 'Valle de Cochamó pernocta' con 2 días FULL_DAY
ADVENTURE+FRIENDS. Crea 1 Place nuevo (valle-cochamo-la-junta).

Día 1 (aproximación): Mirador Estuario Reloncaví → Ralún → Cochamó pueblo
→ Sendero El Arcoíris (3-4h hasta La Junta, pernocta).
Día 2 (toboganes + retorno): La Junta toboganes naturales + Cascada
Escondida → retorno a Cochamó.

Uso:
    python manage.py populate_valle_cochamo_pernocta --dry-run
    python manage.py populate_valle_cochamo_pernocta
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


CIRCUIT_SLUG = "valle-cochamo-pernocta"

NEW_PLACES = [
    {
        "slug": "valle-cochamo-la-junta",
        "name": "Valle de Cochamó · Sector La Junta",
        "place_type": "ATTRACTION",
        "partnership_level": "LISTED",
        "location_label": "Valle de Cochamó, Comuna de Cochamó, Región de Los Lagos",
        "latitude": Decimal("-41.500000"),
        "longitude": Decimal("-72.166700"),
        "is_family_friendly": False,
        "is_rain_friendly": False,
        "is_romantic": False,
        "is_adventure_related": True,
        "short_description": (
            "Sector La Junta del Valle de Cochamó, conocido como 'el "
            "Yosemite chileno' por sus paredes graníticas de cientos de "
            "metros. Toboganes naturales en granito pulido, río Cochamó "
            "de aguas cristalinas y campamento histórico de escaladores. "
            "Acceso por sendero de 3-4 horas desde el pueblo."
        ),
    },
]

# (day_number, place_slug, visit_order, is_main_stop)
DAYS_STOPS = [
    (1, "mirador-estuario-reloncavi", 1, False),
    (1, "ralun", 2, False),
    (1, "cochamo", 3, False),
    (1, "sendero-el-arcoiris-cochamo", 4, True),
    (2, "valle-cochamo-la-junta", 1, True),
    (2, "cascada-escondida-cochamo", 2, False),
]

DAYS = {
    1: {
        "title": "Día 1 · Aproximación al Valle de Cochamó",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Salida temprana hacia el Estuario de Reloncaví, parando en "
            "miradores con vista a los volcanes Yates y Hornopirén. Paso "
            "por Ralún y el pueblo de Cochamó para últimos preparativos. "
            "Trekking de 3-4 horas por el Sendero El Arcoíris hasta La "
            "Junta, donde se pernocta en camping o refugio rústico entre "
            "paredes de granito."
        ),
    },
    2: {
        "title": "Día 2 · Toboganes naturales y retorno",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Mañana en los toboganes naturales del río Cochamó, esculpidos "
            "en granito pulido por miles de años. Visita a la Cascada "
            "Escondida en el sector La Junta antes de emprender el "
            "regreso por el mismo sendero. Cierre con cena tardía en "
            "Cochamó pueblo antes del traslado a Puerto Varas."
        ),
    },
}


class Command(BaseCommand):
    help = "Pobla el Circuit #1042 'Valle de Cochamó pernocta' (2D1N, 1 place nuevo)."

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
            f"=== populate_valle_cochamo_pernocta [{('DRY-RUN' if dry else 'APPLY')}] ==="
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
