"""Pobla el circuito #1017 'Cochamó pueblo + Ralún' con 5 stops.

Reusa 3 Places existentes (cochamo, termas-cochamo, puelo) y agrega 2 nuevos
(Mirador Estuario Reloncaví + Ralún) para armar 1 día completo NATURE+culture
orientado a COUPLE: ruta panorámica del estuario de Reloncaví.

Stops orden visita:
  1. Mirador Estuario Reloncaví
  2. Ralún (capilla + desembocadura Petrohué)
  3. Cochamó pueblo (iglesia patrimonial, MAIN)
  4. Termas de Cochamó
  5. Puelo (cierre)

Uso:
    python manage.py populate_cochamo_pueblo_ralun            # dry-run
    python manage.py populate_cochamo_pueblo_ralun --apply    # aplicar
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.enums import BlockType, PartnershipLevel, PlaceType
from destino_puerto_varas.models import Circuit, CircuitDay, CircuitPlace, Place


CIRCUIT_SLUG = "cochamo-pueblo-ralun"

NEW_PLACES = [
    {
        "slug": "mirador-estuario-reloncavi",
        "name": "Mirador Estuario de Reloncaví",
        "place_type": PlaceType.VIEWPOINT,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Ruta V-69 — entre Ralún y Cochamó",
        "latitude": Decimal("-41.460000"),
        "longitude": Decimal("-72.310000"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "is_romantic": True,
        "short_description": (
            "Mirador panorámico sobre el estuario de Reloncaví, único fiordo "
            "geológico de Chile continental. Vista a las aguas verdes encajadas "
            "entre cordillera y bosque siempreverde, con balsas salmoneras y "
            "cumbres nevadas al fondo."
        ),
    },
    {
        "slug": "ralun",
        "name": "Ralún",
        "place_type": PlaceType.ATTRACTION,
        "partnership_level": PartnershipLevel.LISTED,
        "location_label": "Ralún — desembocadura del río Petrohué en el estuario",
        "latitude": Decimal("-41.396944"),
        "longitude": Decimal("-72.300833"),
        "is_family_friendly": True,
        "is_rain_friendly": False,
        "short_description": (
            "Pequeña localidad rural en la desembocadura del río Petrohué donde "
            "se forma el estuario de Reloncaví. Capilla de madera, paisaje fluvial "
            "y silencio: parada lenta que marca el inicio de la ruta sur por "
            "Cochamó y Puelo."
        ),
    },
]

# (place_slug, visit_order, is_main_stop)
STOPS = [
    ("mirador-estuario-reloncavi", 10, True),
    ("ralun", 20, True),
    ("cochamo", 30, True),
    ("termas-cochamo", 40, True),
    ("puelo", 50, True),
]

DAY_TITLE = "Estuario de Reloncaví: Ralún, Cochamó y Puelo"
DAY_SUMMARY = (
    "Ruta panorámica de día completo recorriendo el único fiordo continental de "
    "Chile: nos detenemos en el mirador del estuario, exploramos Ralún en la "
    "desembocadura del Petrohué, llegamos al pueblo de Cochamó con su iglesia "
    "patrimonial frente al mar interior, hacemos una pausa termal y cerramos en "
    "Puelo, fin del camino y umbral de la Patagonia húmeda."
)


class Command(BaseCommand):
    help = "Pobla circuito #1017 con stops + república."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== populate_cochamo_pueblo_ralun [{mode}] ==="
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
                "(dry-run) Para aplicar: `python manage.py populate_cochamo_pueblo_ralun --apply`"
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
