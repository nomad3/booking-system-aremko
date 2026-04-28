"""Pobla el circuito #1001 'Puerto Varas patrimonial' con 5 stops.

Crea Places faltantes (Iglesia Sagrado Corazón + Barrio patrimonial alemán),
arma un CircuitDay con 5 paradas y re-publica el circuito.

Stops orden visita:
  1. Plaza de Armas + Iglesia del Sagrado Corazón
  2. Barrio patrimonial alemán (Decher/Klenner/Quintanilla)
  3. Mercado de Puerto Varas
  4. Costanera de Puerto Varas
  5. Mirador del Cerro Philippi

Uso:
    python manage.py populate_puerto_varas_patrimonial            # dry-run
    python manage.py populate_puerto_varas_patrimonial --apply    # aplicar
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.enums import BlockType, PartnershipLevel, PlaceType
from destino_puerto_varas.models import Circuit, CircuitDay, CircuitPlace, Place


CIRCUIT_SLUG = "puerto-varas-patrimonial"

NEW_PLACES = [
    {
        "slug": "iglesia-sagrado-corazon-puerto-varas",
        "name": "Iglesia del Sagrado Corazón de Jesús",
        "place_type": PlaceType.CHURCH,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Puerto Varas — Plaza de Armas",
        "latitude": Decimal("-41.319167"),
        "longitude": Decimal("-72.985000"),
        "is_family_friendly": True,
        "is_rain_friendly": True,
        "short_description": (
            "Iglesia patrimonial de 1918 inspirada en la Marienkirche de Marienberg, Alemania. "
            "Monumento Histórico Nacional, ícono visual del cerro frente a la Plaza de Armas."
        ),
    },
    {
        "slug": "barrio-patrimonial-aleman-puerto-varas",
        "name": "Barrio patrimonial alemán",
        "place_type": PlaceType.ATTRACTION,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Puerto Varas — calles Decher, Klenner, María Brunn",
        "latitude": Decimal("-41.318500"),
        "longitude": Decimal("-72.987000"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "short_description": (
            "Recorrido caminable por las casas declaradas Monumento Nacional (Casa Kuschel, "
            "Casa Yunge, Casa Maldonado, entre otras) en las calles Decher, Klenner, San "
            "Francisco y María Brunn. Arquitectura colona alemana de fines del XIX y XX."
        ),
    },
]

# (place_slug, visit_order, is_main_stop)
STOPS = [
    ("iglesia-sagrado-corazon-puerto-varas", 10, True),
    ("barrio-patrimonial-aleman-puerto-varas", 20, True),
    ("mercado-puerto-varas", 30, False),
    ("puerto-varas-costanera", 40, True),
    ("mirador-philippi", 50, True),
]

DAY_TITLE = "Centro patrimonial de Puerto Varas"
DAY_SUMMARY = (
    "Recorrido caminable por el casco histórico de Puerto Varas: arrancamos en la "
    "Plaza de Armas frente a la Iglesia del Sagrado Corazón (Monumento Histórico), "
    "exploramos las casas patrimoniales alemanas, pasamos por el mercado para una "
    "pausa, bajamos a la costanera con vista al Lago Llanquihue y al Volcán Osorno "
    "y cerramos subiendo al Mirador Cerro Philippi para la panorámica completa."
)


class Command(BaseCommand):
    help = "Pobla circuito #1001 con stops + república."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== populate_puerto_varas_patrimonial [{mode}] ==="
        ))

        circuit = Circuit.objects.filter(slug=CIRCUIT_SLUG).first()
        if circuit is None:
            self.stdout.write(self.style.ERROR(
                f"  [error] Circuito {CIRCUIT_SLUG!r} no existe."
            ))
            return
        self.stdout.write(f"  Circuito: #{circuit.number} {circuit.name!r} (published={circuit.published})")

        # Validar Places existentes
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
                "(dry-run) Para aplicar: `python manage.py populate_puerto_varas_patrimonial --apply`"
            ))
            return

        with transaction.atomic():
            # 1. Upsert Places nuevos
            for spec in NEW_PLACES:
                place, created = Place.objects.get_or_create(
                    slug=spec["slug"],
                    defaults=spec,
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"  [ok place] {place.slug} creado"))
                else:
                    self.stdout.write(f"  [skip place] {place.slug} ya existía")

            # 2. CircuitDay (idempotente: 1 día, day_number=1)
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

            # 3. Stops
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

            # 4. Re-publicar
            if not circuit.published:
                circuit.published = True
                circuit.save(update_fields=["published"])
                self.stdout.write(self.style.SUCCESS(f"  [ok publish] #{circuit.number} re-publicado"))
            else:
                self.stdout.write(f"  [skip publish] ya estaba published=True")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Listo."))
