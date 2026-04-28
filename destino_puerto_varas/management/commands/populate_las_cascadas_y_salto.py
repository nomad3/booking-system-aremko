"""Pobla el circuito #1005 'Las Cascadas y salto' (medio día, FAMILY).

Reusa 3 Places existentes (ensenada-mirador-lago, cascadas, volcan-osorno-mirador)
y agrega 1 nuevo (Salto La Picada, sendero CONAF). Arma 1 CircuitDay tipo
HALF_DAY orientado a familia con foco en el salto.

Stops orden visita:
  1. Ensenada – Mirador del Lago
  2. Cascadas (pueblo costa Llanquihue)
  3. Salto La Picada (sendero CONAF, MAIN)
  4. Mirador Volcán Osorno

Uso:
    python manage.py populate_las_cascadas_y_salto            # dry-run
    python manage.py populate_las_cascadas_y_salto --apply    # aplicar
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.enums import BlockType, PartnershipLevel, PlaceType
from destino_puerto_varas.models import Circuit, CircuitDay, CircuitPlace, Place


CIRCUIT_SLUG = "las-cascadas-y-salto"

NEW_PLACES = [
    {
        "slug": "salto-la-picada",
        "name": "Salto La Picada",
        "place_type": PlaceType.ATTRACTION,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "PN Vicente Pérez Rosales — sector Las Cascadas / Volcán Osorno",
        "latitude": Decimal("-41.083333"),
        "longitude": Decimal("-72.516667"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "short_description": (
            "Sendero corto (~1,5 km, ida) que termina en una cascada de ~50 m por "
            "una pared de roca volcánica. Bosque siempreverde dentro del Parque "
            "Nacional Vicente Pérez Rosales. Caminata sencilla apta para familias."
        ),
    },
]

# (place_slug, visit_order, is_main_stop)
STOPS = [
    ("ensenada-mirador-lago", 10, False),
    ("cascadas", 20, True),
    ("salto-la-picada", 30, True),
    ("volcan-osorno-mirador", 40, True),
]

DAY_TITLE = "Las Cascadas + Salto La Picada"
DAY_SUMMARY = (
    "Medio día por la costa norte del Lago Llanquihue: paramos en el mirador de "
    "Ensenada, recorremos el pueblo de Las Cascadas con sus playas de arena "
    "volcánica, internamos por bosque siempreverde para llegar al Salto La Picada "
    "(plato fuerte: cascada de unos 50 m sobre roca volcánica) y cerramos con "
    "vista panorámica del Volcán Osorno antes de regresar."
)


class Command(BaseCommand):
    help = "Pobla circuito #1005 con stops + república."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== populate_las_cascadas_y_salto [{mode}] ==="
        ))

        circuit = Circuit.objects.filter(slug=CIRCUIT_SLUG).first()
        if circuit is None:
            self.stdout.write(self.style.ERROR(
                f"  [error] Circuito {CIRCUIT_SLUG!r} no existe."
            ))
            return
        self.stdout.write(f"  Circuito: #{circuit.number} {circuit.name!r} (published={circuit.published})")

        for slug in [s for s, _, _ in STOPS]:
            exists = Place.objects.filter(slug=slug).exists()
            in_new = any(p["slug"] == slug for p in NEW_PLACES)
            if exists:
                self.stdout.write(f"  [ok place] {slug} (existente)")
            elif in_new:
                self.stdout.write(f"  [new place] {slug} (se creará)")
            else:
                self.stdout.write(self.style.ERROR(f"  [missing] {slug} no existe ni está en NEW_PLACES"))
                return

        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "(dry-run) Para aplicar: `python manage.py populate_las_cascadas_y_salto --apply`"
            ))
            return

        with transaction.atomic():
            for spec in NEW_PLACES:
                place, created = Place.objects.get_or_create(
                    slug=spec["slug"],
                    defaults=spec,
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"  [ok place] {place.slug} creado"))
                else:
                    self.stdout.write(f"  [skip place] {place.slug} ya existía")

            day, day_created = CircuitDay.objects.get_or_create(
                circuit=circuit,
                day_number=1,
                defaults={
                    "title": DAY_TITLE,
                    "block_type": BlockType.HALF_DAY,
                    "summary": DAY_SUMMARY,
                    "sort_order": 10,
                },
            )
            if day_created:
                self.stdout.write(self.style.SUCCESS(f"  [ok day] Day 1 creado"))
            else:
                self.stdout.write(f"  [skip day] Day 1 ya existía")

            for slug, order, is_main in STOPS:
                place = Place.objects.get(slug=slug)
                stop, stop_created = CircuitPlace.objects.get_or_create(
                    circuit_day=day,
                    place=place,
                    defaults={"visit_order": order, "is_main_stop": is_main},
                )
                if stop_created:
                    self.stdout.write(self.style.SUCCESS(
                        f"    [ok stop] {slug} (orden={order})"
                    ))
                else:
                    self.stdout.write(f"    [skip stop] {slug} ya existía")

            if not circuit.published:
                circuit.published = True
                circuit.save(update_fields=["published"])
                self.stdout.write(self.style.SUCCESS(f"  [ok publish] #{circuit.number} re-publicado"))
            else:
                self.stdout.write(f"  [skip publish] ya estaba published=True")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Listo."))
