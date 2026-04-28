"""Pobla el circuito #1045 'Puyehue slow' (2 días / 1 noche, COUPLE).

Reusa 4 Places del sector Puyehue (creados por #1025) y agrega 1 nuevo
(Bahía Escocia — costa Lago Puyehue). Arma 2 CircuitDays con foco en
relax-romántico y bosque andino.

Día 1 — Lago + termas:
  1. Lago Puyehue — Bahía Escocia
  2. Termas Puyehue Hotel (check-in)
  3. Aguas Calientes CONAF (atardecer termal)

Día 2 — Bosque + volcán:
  1. Sendero Rápidos del Chanleufu
  2. Salto del Indio — Sector Anticura
  3. Mirador Antillanca / Volcán Casablanca

Uso:
    python manage.py populate_puyehue_slow            # dry-run
    python manage.py populate_puyehue_slow --apply    # aplicar
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.enums import BlockType, PartnershipLevel, PlaceType
from destino_puerto_varas.models import Circuit, CircuitDay, CircuitPlace, Place


CIRCUIT_SLUG = "puyehue-slow"

NEW_PLACES = [
    {
        "slug": "lago-puyehue-bahia-escocia",
        "name": "Lago Puyehue — Bahía Escocia",
        "place_type": PlaceType.VIEWPOINT,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Lago Puyehue — costa suroeste, comuna de Puyehue",
        "latitude": Decimal("-40.703889"),
        "longitude": Decimal("-72.460278"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "is_romantic": True,
        "short_description": (
            "Bahía tranquila del Lago Puyehue con vista a los volcanes Puntiagudo y "
            "Casablanca. Playa de arena oscura, muelles pequeños y atardeceres "
            "abiertos: parada perfecta para una pausa lenta antes de las termas."
        ),
    },
]

# Estructura: {day_number: (title, summary, [(slug, order, is_main), ...])}
DAYS = {
    1: {
        "title": "Lago Puyehue + termas al atardecer",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Día 1 lento: paramos primero en Bahía Escocia para una caminata corta a "
            "orillas del Lago Puyehue con vista a los volcanes, hacemos check-in en "
            "el histórico Hotel Termas de Puyehue, y cerramos con baño termal en los "
            "pozones de Aguas Calientes CONAF al atardecer. Cena y noche en el hotel."
        ),
        "stops": [
            ("lago-puyehue-bahia-escocia", 10, True),
            ("termas-puyehue-hotel", 20, True),
            ("aguas-calientes-conaf", 30, True),
        ],
    },
    2: {
        "title": "Bosque siempreverde y Volcán Casablanca",
        "block_type": BlockType.FULL_DAY,
        "summary": (
            "Día 2 conectamos con la naturaleza profunda del Parque Nacional Puyehue: "
            "caminata corta por los rápidos del Chanleufu, traslado al sector "
            "Anticura para visitar el Salto del Indio entre bosque siempreverde, y "
            "subida al mirador Antillanca para la panorámica del Volcán Casablanca y "
            "las lagunas Espejo y El Toro antes del regreso."
        ),
        "stops": [
            ("sendero-rapidos-chanleufu", 10, True),
            ("salto-del-indio-anticura", 20, True),
            ("mirador-antillanca", 30, True),
        ],
    },
}


class Command(BaseCommand):
    help = "Pobla circuito #1045 con 2 days + república."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== populate_puyehue_slow [{mode}] ==="
        ))

        circuit = Circuit.objects.filter(slug=CIRCUIT_SLUG).first()
        if circuit is None:
            self.stdout.write(self.style.ERROR(
                f"  [error] Circuito {CIRCUIT_SLUG!r} no existe."
            ))
            return
        self.stdout.write(f"  Circuito: #{circuit.number} {circuit.name!r} (published={circuit.published})")

        all_stop_slugs = {slug for d in DAYS.values() for slug, _, _ in d["stops"]}
        for slug in all_stop_slugs:
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
                "(dry-run) Para aplicar: `python manage.py populate_puyehue_slow --apply`"
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

            for day_number, dspec in DAYS.items():
                day, day_created = CircuitDay.objects.get_or_create(
                    circuit=circuit,
                    day_number=day_number,
                    defaults={
                        "title": dspec["title"],
                        "block_type": dspec["block_type"],
                        "summary": dspec["summary"],
                        "sort_order": day_number * 10,
                    },
                )
                if day_created:
                    self.stdout.write(self.style.SUCCESS(f"  [ok day] Day {day_number} creado"))
                else:
                    self.stdout.write(f"  [skip day] Day {day_number} ya existía")

                for slug, order, is_main in dspec["stops"]:
                    place = Place.objects.get(slug=slug)
                    stop, stop_created = CircuitPlace.objects.get_or_create(
                        circuit_day=day,
                        place=place,
                        defaults={"visit_order": order, "is_main_stop": is_main},
                    )
                    if stop_created:
                        self.stdout.write(self.style.SUCCESS(
                            f"    [ok stop] D{day_number} {slug} (orden={order})"
                        ))
                    else:
                        self.stdout.write(f"    [skip stop] D{day_number} {slug} ya existía")

            if not circuit.published:
                circuit.published = True
                circuit.save(update_fields=["published"])
                self.stdout.write(self.style.SUCCESS(f"  [ok publish] #{circuit.number} re-publicado"))
            else:
                self.stdout.write(f"  [skip publish] ya estaba published=True")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Listo."))
