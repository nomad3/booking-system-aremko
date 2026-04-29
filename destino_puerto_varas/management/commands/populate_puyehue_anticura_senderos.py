"""Pobla el Circuit #1039 'Puyehue Anticura + senderos concesionados' con
4 stops FULL_DAY NATURE+FAMILY (con toque adventure por sendero ríos).
NO crea Places nuevos — reusa 100% existentes del PN Puyehue.

Itinerario: PV → Lago Puyehue Bahía Escocia (start) → Salto del Indio
(main, sendero clásico) → Sendero Rápidos del Chanleufu → Termas de
Puyehue Hotel (cierre, baño termal day-use).

Uso:
    python manage.py populate_puyehue_anticura_senderos --dry-run
    python manage.py populate_puyehue_anticura_senderos
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


CIRCUIT_SLUG = "puyehue-anticura-senderos"

STOPS = [
    ("lago-puyehue-bahia-escocia", 1, False),
    ("salto-del-indio-anticura", 2, True),
    ("sendero-rapidos-chanleufu", 3, False),
    ("termas-puyehue-hotel", 4, False),
]

DAY_TITLE = "Día 1 · Senderos concesionados de Anticura"
DAY_SUMMARY = (
    "Día completo entre los senderos concesionados del sector Anticura del "
    "Parque Nacional Puyehue. Caminatas en bosque valdiviano, miradores al "
    "lago Puyehue y cierre en piscinas termales del histórico hotel de Puyehue."
)


class Command(BaseCommand):
    help = "Pobla el Circuit #1039 'Puyehue Anticura senderos' (4 stops, FULL_DAY)."

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
            f"=== populate_puyehue_anticura_senderos [{('DRY-RUN' if dry else 'APPLY')}] ==="
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
