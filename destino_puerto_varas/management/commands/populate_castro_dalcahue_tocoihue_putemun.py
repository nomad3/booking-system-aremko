"""Pobla el circuito #1033 'Castro + Dalcahue + Tocoihue + Putemún' con 5 stops.

Crea Places faltantes (Iglesia San Francisco de Castro + Iglesia de Putemún +
Iglesia de Tocoihue), arma un CircuitDay de día completo con paradas patrimoniales
romántico-culturales y re-publica el circuito.

Stops orden visita:
  1. Iglesia San Francisco de Castro (UNESCO)
  2. Palafitos de Castro (vista de la ciudad colgada)
  3. Iglesia de Putemún (Monumento Nacional, ruta patrimonial)
  4. Iglesia de Dalcahue + feria (UNESCO)
  5. Iglesia de Tocoihue (UNESCO, sector rural íntimo)

Uso:
    python manage.py populate_castro_dalcahue_tocoihue_putemun            # dry-run
    python manage.py populate_castro_dalcahue_tocoihue_putemun --apply    # aplicar
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.enums import BlockType, PartnershipLevel, PlaceType
from destino_puerto_varas.models import Circuit, CircuitDay, CircuitPlace, Place


CIRCUIT_SLUG = "castro-dalcahue-tocoihue-putemun"

NEW_PLACES = [
    {
        "slug": "iglesia-san-francisco-castro",
        "name": "Iglesia San Francisco de Castro",
        "place_type": PlaceType.CHURCH,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Castro — Plaza de Armas",
        "latitude": Decimal("-42.479444"),
        "longitude": Decimal("-73.763611"),
        "is_family_friendly": True,
        "is_rain_friendly": True,
        "is_romantic": True,
        "short_description": (
            "Iglesia de madera (1912) declarada Patrimonio de la Humanidad por UNESCO. "
            "Fachada amarilla y violeta frente a la Plaza de Armas, ícono mayor del "
            "patrimonio chilote y una de las 16 iglesias de la Escuela Chilota."
        ),
    },
    {
        "slug": "iglesia-de-putemun",
        "name": "Iglesia de Putemún",
        "place_type": PlaceType.CHURCH,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Putemún — 4 km al norte de Castro",
        "latitude": Decimal("-42.444167"),
        "longitude": Decimal("-73.745278"),
        "is_family_friendly": True,
        "is_rain_friendly": True,
        "is_romantic": True,
        "short_description": (
            "Iglesia de Putemún (siglo XIX), Monumento Nacional. Parada tranquila "
            "camino a Dalcahue, en sector rural sobre el canal de Castro. Ejemplo "
            "puro de la Escuela Chilota de arquitectura en madera."
        ),
    },
    {
        "slug": "iglesia-de-tocoihue",
        "name": "Iglesia de Tocoihue",
        "place_type": PlaceType.CHURCH,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Tocoihue — sector rural, comuna de Dalcahue",
        "latitude": Decimal("-42.388333"),
        "longitude": Decimal("-73.566667"),
        "is_family_friendly": True,
        "is_rain_friendly": True,
        "is_romantic": True,
        "short_description": (
            "Iglesia rural de Tocoihue, parte del conjunto de 16 iglesias declaradas "
            "Patrimonio de la Humanidad por UNESCO. Acceso por camino interior desde "
            "Dalcahue; entorno silencioso, vista al estero y bosque siempreverde."
        ),
    },
]

# (place_slug, visit_order, is_main_stop)
STOPS = [
    ("iglesia-san-francisco-castro", 10, True),
    ("palafitos-castro", 20, True),
    ("iglesia-de-putemun", 30, True),
    ("dalcahue", 40, True),
    ("iglesia-de-tocoihue", 50, True),
]

DAY_TITLE = "Ruta patrimonial Castro–Dalcahue–Tocoihue–Putemún"
DAY_SUMMARY = (
    "Día completo recorriendo cuatro joyas patrimoniales del archipiélago: partimos "
    "en la Iglesia San Francisco de Castro (UNESCO) y los palafitos de la ciudad "
    "colgada, subimos por el canal a la Iglesia de Putemún en sector rural, llegamos "
    "a Dalcahue para visitar su iglesia (UNESCO) y la feria artesanal, y cerramos "
    "internándonos por camino rural hacia la Iglesia de Tocoihue, otra de las 16 "
    "iglesias Patrimonio de la Humanidad — una jornada lenta, fotogénica y muy chilota."
)


class Command(BaseCommand):
    help = "Pobla circuito #1033 con stops + república."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== populate_castro_dalcahue_tocoihue_putemun [{mode}] ==="
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
                "(dry-run) Para aplicar: `python manage.py populate_castro_dalcahue_tocoihue_putemun --apply`"
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
                    "block_type": BlockType.FULL_DAY,
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
