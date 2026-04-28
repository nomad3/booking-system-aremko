"""Pobla el circuito #1027 'Ancud + Puñihuil' con 5 stops.

Crea Places faltantes (Caulín, Fuerte San Antonio, Pingüineras de Puñihuil,
Playa Mar Brava), arma un CircuitDay de día completo orientado a
naturaleza-family y re-publica el circuito.

Stops orden visita:
  1. Caulín (camino, cisnes negros + ostras)
  2. Fuerte San Antonio (Ancud)
  3. Ancud — centro/plaza
  4. Pingüineras de Puñihuil (paseo en bote, MAIN)
  5. Playa Mar Brava

Uso:
    python manage.py populate_ancud_punihuil            # dry-run
    python manage.py populate_ancud_punihuil --apply    # aplicar
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.enums import BlockType, PartnershipLevel, PlaceType
from destino_puerto_varas.models import Circuit, CircuitDay, CircuitPlace, Place


CIRCUIT_SLUG = "ancud-punihuil"

NEW_PLACES = [
    {
        "slug": "caulin",
        "name": "Caulín",
        "place_type": PlaceType.ATTRACTION,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Caulín — comuna de Ancud, norte de Chiloé",
        "latitude": Decimal("-41.832000"),
        "longitude": Decimal("-73.625000"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "short_description": (
            "Bahía tranquila famosa por sus cisnes de cuello negro, ostras frescas y "
            "playa de baja marea. Parada gastronómica natural en el camino entre "
            "Chacao y Ancud, ideal para fotografía de aves y mariscos al paso."
        ),
    },
    {
        "slug": "fuerte-san-antonio-ancud",
        "name": "Fuerte San Antonio",
        "place_type": PlaceType.ATTRACTION,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Ancud — punta noroeste de la ciudad",
        "latitude": Decimal("-41.865556"),
        "longitude": Decimal("-73.831111"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "short_description": (
            "Última fortaleza española en suelo chileno (1770). Cañones originales "
            "frente al canal de Chacao, vista panorámica de la bahía de Ancud y "
            "marco histórico para entender la conquista tardía del archipiélago."
        ),
    },
    {
        "slug": "punihuil-pinguineras",
        "name": "Pingüineras de Puñihuil",
        "place_type": PlaceType.ATTRACTION,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Puñihuil — costa oeste, 27 km al SO de Ancud",
        "latitude": Decimal("-41.918333"),
        "longitude": Decimal("-74.029167"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "short_description": (
            "Monumento Natural Islotes de Puñihuil: única colonia mixta del mundo "
            "donde anidan pingüinos de Magallanes y Humboldt. Paseo en bote (~30 min) "
            "para ver pingüinos, lobos marinos, chungungos y nutrias. Temporada "
            "septiembre–marzo."
        ),
    },
    {
        "slug": "playa-mar-brava",
        "name": "Playa Mar Brava",
        "place_type": PlaceType.VIEWPOINT,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Mar Brava — costa pacífica de Ancud",
        "latitude": Decimal("-41.911111"),
        "longitude": Decimal("-74.054444"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "short_description": (
            "Playa abierta al Pacífico con dunas, oleaje fuerte y cielos amplios. "
            "Cierre del día con paisaje de fin de mundo, ideal para caminata corta "
            "y atardecer. No apta para baño por corrientes."
        ),
    },
]

# (place_slug, visit_order, is_main_stop)
STOPS = [
    ("caulin", 10, True),
    ("fuerte-san-antonio-ancud", 20, True),
    ("ancud", 30, False),
    ("punihuil-pinguineras", 40, True),
    ("playa-mar-brava", 50, True),
]

DAY_TITLE = "Norte de Chiloé: Ancud + pingüineras de Puñihuil"
DAY_SUMMARY = (
    "Día completo cruzando a Chiloé: partimos en Caulín con cisnes y ostras, "
    "subimos al Fuerte San Antonio para entender la historia colonial de Ancud, "
    "pasamos por el centro de la ciudad y nos vamos al plato fuerte: paseo en "
    "bote por las pingüineras de Puñihuil (Magallanes + Humboldt en una misma "
    "colonia, único en el mundo). Cerramos en Playa Mar Brava con paisaje de "
    "fin de mundo frente al Pacífico."
)


class Command(BaseCommand):
    help = "Pobla circuito #1027 con stops + república."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== populate_ancud_punihuil [{mode}] ==="
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
                "(dry-run) Para aplicar: `python manage.py populate_ancud_punihuil --apply`"
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
                    "block_type": BlockType.FULL_DAY,
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
