"""Pobla el circuito #1025 'Puyehue Aguas Calientes' con 5 stops.

Crea los 5 Places del PN Puyehue (todos nuevos: Termas Puyehue Hotel,
Aguas Calientes CONAF, Sendero Rápidos del Chanleufu, Salto del Indio
(Anticura), Mirador Antillanca) y arma día completo NATURE+FAMILY+romantic.

Stops orden visita:
  1. Termas de Puyehue (hotel — parada bienvenida)
  2. Aguas Calientes CONAF (pozones + pasarelas, MAIN)
  3. Sendero Rápidos del Chanleufu (caminata corta)
  4. Salto del Indio — Sector Anticura
  5. Mirador Antillanca / Volcán Casablanca

Uso:
    python manage.py populate_puyehue_aguas_calientes            # dry-run
    python manage.py populate_puyehue_aguas_calientes --apply    # aplicar
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.enums import BlockType, PartnershipLevel, PlaceType
from destino_puerto_varas.models import Circuit, CircuitDay, CircuitPlace, Place


CIRCUIT_SLUG = "puyehue-aguas-calientes"

NEW_PLACES = [
    {
        "slug": "termas-puyehue-hotel",
        "name": "Termas de Puyehue Hotel",
        "place_type": PlaceType.LODGING,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Sector Aguas Calientes — entrada PN Puyehue",
        "latitude": Decimal("-40.719444"),
        "longitude": Decimal("-72.316389"),
        "is_family_friendly": True,
        "is_rain_friendly": True,
        "is_romantic": True,
        "short_description": (
            "Hotel termal histórico (1908) en la entrada del Parque Nacional Puyehue. "
            "Arquitectura colonial alemana, piscinas termales, spa y restaurantes. "
            "Parada de bienvenida con jardines y vista al bosque siempreverde."
        ),
    },
    {
        "slug": "aguas-calientes-conaf",
        "name": "Aguas Calientes CONAF",
        "place_type": PlaceType.PARK,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "PN Puyehue — sector Aguas Calientes",
        "latitude": Decimal("-40.728056"),
        "longitude": Decimal("-72.296389"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "is_romantic": True,
        "short_description": (
            "Centro turístico de CONAF con piscinas termales al aire libre, río "
            "Chanleufu y pasarelas en bosque húmedo. Foco principal del circuito: "
            "baño termal en plena naturaleza, ideal para parejas y familias."
        ),
    },
    {
        "slug": "sendero-rapidos-chanleufu",
        "name": "Sendero Rápidos del Chanleufu",
        "place_type": PlaceType.ATTRACTION,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "PN Puyehue — sector Aguas Calientes",
        "latitude": Decimal("-40.730000"),
        "longitude": Decimal("-72.293000"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "short_description": (
            "Sendero corto (~1 km) por bosque valdiviano que sigue los rápidos del "
            "río Chanleufu. Pasarelas accesibles, ideal para todas las edades. "
            "Complemento perfecto al baño termal."
        ),
    },
    {
        "slug": "salto-del-indio-anticura",
        "name": "Salto del Indio — Sector Anticura",
        "place_type": PlaceType.ATTRACTION,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "PN Puyehue — sector Anticura, ruta a Argentina",
        "latitude": Decimal("-40.660833"),
        "longitude": Decimal("-72.183889"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "is_romantic": True,
        "short_description": (
            "Cascada del río Anticura enmarcada por bosque siempreverde. Sendero "
            "corto y bien señalizado dentro del sector Anticura del Parque Nacional "
            "Puyehue. Vegetación densa, musgos y aire puro de bosque templado lluvioso."
        ),
    },
    {
        "slug": "mirador-antillanca",
        "name": "Mirador Antillanca / Volcán Casablanca",
        "place_type": PlaceType.VIEWPOINT,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Antillanca — PN Puyehue, sector sur",
        "latitude": Decimal("-40.778889"),
        "longitude": Decimal("-72.196111"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "is_romantic": True,
        "short_description": (
            "Vista panorámica al Volcán Casablanca y las lagunas Espejo y El Toro "
            "desde el camino a Antillanca. Bosque andino, cierre de día con foto "
            "de horizonte volcánico y atmósfera serena."
        ),
    },
]

# (place_slug, visit_order, is_main_stop)
STOPS = [
    ("termas-puyehue-hotel", 10, False),
    ("aguas-calientes-conaf", 20, True),
    ("sendero-rapidos-chanleufu", 30, True),
    ("salto-del-indio-anticura", 40, True),
    ("mirador-antillanca", 50, True),
]

DAY_TITLE = "Termas y bosques del Parque Nacional Puyehue"
DAY_SUMMARY = (
    "Día completo en el PN Puyehue con foco en agua caliente y bosque valdiviano: "
    "comenzamos en las históricas Termas de Puyehue (parada de bienvenida), "
    "seguimos al sector Aguas Calientes de CONAF para el baño termal en pozones "
    "junto al río Chanleufu, recorremos el sendero corto de los rápidos, viajamos "
    "al sector Anticura para visitar el Salto del Indio entre bosque siempreverde, "
    "y cerramos en el mirador del camino a Antillanca con vista al Volcán Casablanca."
)


class Command(BaseCommand):
    help = "Pobla circuito #1025 con stops + república."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== populate_puyehue_aguas_calientes [{mode}] ==="
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
                "(dry-run) Para aplicar: `python manage.py populate_puyehue_aguas_calientes --apply`"
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
