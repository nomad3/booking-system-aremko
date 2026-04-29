"""Pobla el Circuit #1044 'Chiloé central patrimonial' con 2 días FULL_DAY
MIXED+FAMILY. 0 Places nuevos (100% reuso de #1033 y #1023).

Día 1: Castro Iglesia + Palafitos Castro + Putemún.
Día 2: Dalcahue + Curaco de Vélez + Achao Iglesia (UNESCO).

Uso:
    python manage.py populate_chiloe_central_patrimonial --dry-run
    python manage.py populate_chiloe_central_patrimonial
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.models import (
    BlockType,
    Circuit,
    CircuitDay,
    CircuitPlace,
    Place,
)


CIRCUIT_SLUG = "chiloe-central-patrimonial"

NEW_PLACES = []  # 100% reuso

# (day_number, place_slug, visit_order, is_main_stop)
DAYS_STOPS = [
    (1, "iglesia-san-francisco-castro", 1, True),
    (1, "palafitos-castro", 2, True),
    (1, "iglesia-de-putemun", 3, False),
    (2, "dalcahue", 1, False),
    (2, "curaco-de-velez", 2, False),
    (2, "achao-iglesia-santa-maria-loreto", 3, True),
]

DAYS = {
    1: {
        "title": "Día 1 · Castro patrimonial",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Llegada a Castro y exploración de su núcleo patrimonial: la Iglesia "
            "San Francisco (UNESCO), los palafitos de Gamboa y Pedro Montt, y "
            "tarde en la Iglesia de Putemún rodeada de campo chilote. Pernoctación "
            "en Castro."
        ),
    },
    2: {
        "title": "Día 2 · Travesía a Quinchao",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Salida a Dalcahue para tomar el ferry a Quinchao. Almuerzo en Curaco "
            "de Vélez con sus famosas ostras y arquitectura tradicional. Cierre "
            "en Achao visitando la Iglesia Santa María de Loreto, la más antigua "
            "de las iglesias jesuitas de Chiloé. Retorno por ferry y Ruta 5."
        ),
    },
}


class Command(BaseCommand):
    help = "Pobla el Circuit #1044 'Chiloé central patrimonial' (2D1N, 0 places nuevos)."

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
            f"=== populate_chiloe_central_patrimonial [{('DRY-RUN' if dry else 'APPLY')}] ==="
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
