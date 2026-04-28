"""Pobla el Circuit #1032 'Vuelta este Lago Llanquihue' con 4 stops del
east shore del lago. NO crea Places nuevos — reusa 100% existentes.

Ruta este: Puerto Varas → Ensenada (Mirador del Lago) → Las Cascadas pueblo →
Salto La Picada → Puerto Octay (almuerzo + paseo histórico).

Uso:
    python manage.py populate_vuelta_este_llanquihue --dry-run
    python manage.py populate_vuelta_este_llanquihue
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


CIRCUIT_SLUG = "vuelta-este-llanquihue"

# (place_slug, visit_order, is_main_stop)
STOPS = [
    ("ensenada-mirador-lago", 1, False),
    ("cascadas", 2, False),
    ("salto-la-picada", 3, True),
    ("puerto-octay", 4, True),
]

DAY_TITLE = "Día 1 · Vuelta este del Llanquihue"
DAY_SUMMARY = (
    "Recorrido por la ribera oriental del lago: vista al Osorno desde Ensenada, "
    "pueblo de Las Cascadas, Salto La Picada en bosque siempreverde y cierre "
    "en Puerto Octay con almuerzo y arquitectura colona."
)


class Command(BaseCommand):
    help = "Pobla el Circuit #1032 'Vuelta este Lago Llanquihue' (4 stops, FAMILY)."

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
            f"=== populate_vuelta_este_llanquihue [{('DRY-RUN' if dry else 'APPLY')}] ==="
        ))
        self.stdout.write(f"  Circuit: #{circuit.number} {circuit.name} (slug={circuit.slug})")

        missing = []
        for slug, _, _ in STOPS:
            if not Place.objects.filter(slug=slug).exists():
                missing.append(slug)
        if missing:
            self.stdout.write(self.style.ERROR(
                f"  ✗ Faltan Places en BD: {', '.join(missing)}. Aborto."
            ))
            return

        self.stdout.write(self.style.SUCCESS("  ✓ Todos los Places existen"))

        if dry:
            self.stdout.write("")
            self.stdout.write("  [dry-run] Crearía:")
            self.stdout.write(f"    · CircuitDay día=1 block_type=FULL_DAY")
            for slug, order, is_main in STOPS:
                tag = " ⭐ main" if is_main else ""
                self.stdout.write(f"    · stop {order}: {slug}{tag}")
            if not circuit.published:
                self.stdout.write("    · Circuit.published = True")
            return

        with transaction.atomic():
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
                self.stdout.write(f"  ✓ CircuitDay día 1 creado")
            else:
                self.stdout.write(f"  · CircuitDay día 1 ya existía")

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
