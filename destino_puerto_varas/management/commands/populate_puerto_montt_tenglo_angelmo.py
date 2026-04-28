"""Pobla el circuito #1030 'Puerto Montt + Isla Tenglo + Angelmó' con 5 stops.

Crea 5 Places nuevos (centro histórico Pto Montt, mirador Manuel Montt, Caleta
Angelmó, Mercado Artesanal de Angelmó, Isla Tenglo) y arma 1 día completo
GASTRONOMY+culture+FAMILY+rain_friendly.

Stops orden visita:
  1. Plaza de Armas + Catedral de Puerto Montt
  2. Mirador Manuel Montt
  3. Caleta Angelmó (mariscos al paso, MAIN)
  4. Mercado Artesanal de Angelmó
  5. Isla Tenglo (curanto en hoyo, MAIN)

Uso:
    python manage.py populate_puerto_montt_tenglo_angelmo            # dry-run
    python manage.py populate_puerto_montt_tenglo_angelmo --apply    # aplicar
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.enums import BlockType, PartnershipLevel, PlaceType
from destino_puerto_varas.models import Circuit, CircuitDay, CircuitPlace, Place


CIRCUIT_SLUG = "puerto-montt-isla-tenglo-angelmo"

NEW_PLACES = [
    {
        "slug": "puerto-montt-plaza-catedral",
        "name": "Plaza de Armas y Catedral de Puerto Montt",
        "place_type": PlaceType.ATTRACTION,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Puerto Montt — centro histórico",
        "latitude": Decimal("-41.471667"),
        "longitude": Decimal("-72.942500"),
        "is_family_friendly": True,
        "is_rain_friendly": True,
        "short_description": (
            "Plaza de Armas Buenaventura Martínez con la Catedral de Puerto Montt "
            "(1856), el templo de madera más antiguo del sur de Chile. Punto de "
            "partida del centro cívico, con vista al seno de Reloncaví."
        ),
    },
    {
        "slug": "mirador-manuel-montt",
        "name": "Mirador Manuel Montt",
        "place_type": PlaceType.VIEWPOINT,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Puerto Montt — sector alto, calle Manuel Montt",
        "latitude": Decimal("-41.466944"),
        "longitude": Decimal("-72.939167"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "short_description": (
            "Mirador con vista panorámica de Puerto Montt, el seno de Reloncaví, "
            "Isla Tenglo y los volcanes Calbuco y Osorno al fondo. Parada corta "
            "ideal para fotos antes de bajar a Angelmó."
        ),
    },
    {
        "slug": "caleta-angelmo",
        "name": "Caleta Angelmó",
        "place_type": PlaceType.ATTRACTION,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Puerto Montt — barrio Angelmó",
        "latitude": Decimal("-41.496944"),
        "longitude": Decimal("-72.977500"),
        "is_family_friendly": True,
        "is_rain_friendly": True,
        "short_description": (
            "Caleta de pescadores con cocinerías sobre el mar: pailas marinas, "
            "curanto al pailón, machas a la parmesana, ostras y pescados frescos. "
            "Plato fuerte gastronómico del circuito y postal clásica de Puerto Montt."
        ),
    },
    {
        "slug": "mercado-artesanal-angelmo",
        "name": "Mercado Artesanal de Angelmó",
        "place_type": PlaceType.SHOP,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Puerto Montt — barrio Angelmó, junto a la caleta",
        "latitude": Decimal("-41.497222"),
        "longitude": Decimal("-72.977778"),
        "is_family_friendly": True,
        "is_rain_friendly": True,
        "short_description": (
            "Galpones de artesanía con tejidos a telar de oveja, productos de "
            "cuero, lana de Chiloé, cobre martillado y suvenires. Recorrido "
            "techado, ideal para días de lluvia."
        ),
    },
    {
        "slug": "isla-tenglo",
        "name": "Isla Tenglo",
        "place_type": PlaceType.ATTRACTION,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Frente a Angelmó, Puerto Montt",
        "latitude": Decimal("-41.506667"),
        "longitude": Decimal("-72.978889"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "short_description": (
            "Pequeña isla a 10 minutos en bote desde Angelmó, conocida por sus "
            "restaurantes de curanto en hoyo (preparado con piedras calientes "
            "bajo tierra). Caminata corta a la cruz de la cumbre con vista "
            "panorámica del seno y la ciudad."
        ),
    },
]

STOPS = [
    ("puerto-montt-plaza-catedral", 10, True),
    ("mirador-manuel-montt", 20, False),
    ("caleta-angelmo", 30, True),
    ("mercado-artesanal-angelmo", 40, True),
    ("isla-tenglo", 50, True),
]

DAY_TITLE = "Puerto Montt clásico: centro, Angelmó e Isla Tenglo"
DAY_SUMMARY = (
    "Día completo gastronómico-cultural por Puerto Montt: arrancamos en el centro "
    "histórico (Plaza de Armas + Catedral de madera de 1856), subimos al mirador "
    "Manuel Montt para una panorámica del seno de Reloncaví, bajamos a la Caleta "
    "Angelmó para almuerzo de mariscos al paso, recorremos el mercado artesanal "
    "techado, y cruzamos en bote a Isla Tenglo para el curanto en hoyo y la "
    "vista desde la cruz."
)


class Command(BaseCommand):
    help = "Pobla circuito #1030 con stops + república."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== populate_puerto_montt_tenglo_angelmo [{mode}] ==="
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
                "(dry-run) Para aplicar: `python manage.py populate_puerto_montt_tenglo_angelmo --apply`"
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
