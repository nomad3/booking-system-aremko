"""Pobla un Circuit desde un archivo JSON con la estructura completa.

Reemplaza el patrón populate_<circuit>.py: en vez de un archivo Python por
circuit, datos puros en JSON committed al repo.

Uso:
    python manage.py populate_circuit_from_json --file destino_puerto_varas/data/circuits/calbuco_pedraplen.json --dry-run
    python manage.py populate_circuit_from_json --file destino_puerto_varas/data/circuits/calbuco_pedraplen.json

Schema del JSON:
{
  "circuit_slug": "calbuco-pedraplen-costanera",
  "publish": true,
  "new_places": [
    {
      "slug": "pedraplen-calbuco",
      "name": "Pedraplén de Calbuco",
      "place_type": "ATTRACTION",
      "partnership_level": "LISTED",
      "location_label": "Calbuco, Región de Los Lagos",
      "latitude": "-41.7710",
      "longitude": "-73.1370",
      "is_family_friendly": true,
      "is_rain_friendly": false,
      "is_romantic": false,
      "is_adventure_related": false,
      "short_description": "Camino que conecta la isla de Calbuco con el continente. <250 chars."
    }
  ],
  "days": [
    {
      "day_number": 1,
      "title": "Día 1 · Pedraplén y costanera de Calbuco",
      "block_type": "FULL_DAY",
      "summary": "...",
      "stops": [
        {"slug": "pedraplen-calbuco", "visit_order": 1, "is_main_stop": false},
        {"slug": "costanera-calbuco", "visit_order": 2, "is_main_stop": true}
      ]
    }
  ]
}
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from destino_puerto_varas.models import (
    BlockType,
    Circuit,
    CircuitDay,
    CircuitPlace,
    Place,
)


PLACE_FIELDS = {
    "name", "place_type", "partnership_level", "location_label",
    "latitude", "longitude", "is_family_friendly", "is_rain_friendly",
    "is_romantic", "is_adventure_related", "short_description",
}
DECIMAL_FIELDS = {"latitude", "longitude"}
SHORT_DESC_MAX = 255


class Command(BaseCommand):
    help = "Pobla un Circuit desde un archivo JSON (places nuevos + days + stops)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True,
                            help="Ruta al JSON con la definición del circuit.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"No existe el archivo: {path}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON inválido: {e}")

        self._validate_schema(data)

        circuit_slug = data["circuit_slug"]
        new_places = data.get("new_places") or []
        days = data["days"]
        publish = bool(data.get("publish", True))

        try:
            circuit = Circuit.objects.get(slug=circuit_slug)
        except Circuit.DoesNotExist:
            raise CommandError(f"No existe Circuit con slug {circuit_slug}")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== populate_circuit_from_json [{('DRY-RUN' if dry else 'APPLY')}] ==="
        ))
        self.stdout.write(f"  Circuit: #{circuit.number} {circuit.name}")
        self.stdout.write(f"  Archivo: {path}")

        new_slugs = {p["slug"] for p in new_places}
        all_slugs = {s["slug"] for d in days for s in d["stops"]}
        missing = [s for s in all_slugs if s not in new_slugs
                   and not Place.objects.filter(slug=s).exists()]
        if missing:
            raise CommandError(
                f"Faltan Places existentes en BD: {', '.join(missing)}"
            )

        long_desc_overflow = [
            p["slug"] for p in new_places
            if len(p.get("short_description") or "") > SHORT_DESC_MAX
        ]
        if long_desc_overflow:
            raise CommandError(
                f"short_description > {SHORT_DESC_MAX} chars en: "
                f"{', '.join(long_desc_overflow)}"
            )

        if dry:
            self._print_dry_run(new_places, days, publish, circuit)
            return

        with transaction.atomic():
            for p in new_places:
                self._upsert_place(p)

            day_objs = {}
            for d in days:
                day_obj = self._upsert_day(circuit, d)
                day_objs[d["day_number"]] = day_obj

            for d in days:
                day_obj = day_objs[d["day_number"]]
                for stop in d["stops"]:
                    self._upsert_stop(day_obj, stop)

            if publish and not circuit.published:
                circuit.published = True
                circuit.save(update_fields=["published"])
                self.stdout.write(self.style.SUCCESS("  ✓ Circuit publicado"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Listo."))

    def _validate_schema(self, data):
        for key in ("circuit_slug", "days"):
            if key not in data:
                raise CommandError(f"JSON inválido: falta '{key}'")
        if not isinstance(data["days"], list) or not data["days"]:
            raise CommandError("JSON inválido: 'days' debe ser lista no vacía")
        for d in data["days"]:
            for key in ("day_number", "title", "block_type", "summary", "stops"):
                if key not in d:
                    raise CommandError(
                        f"JSON inválido: día {d.get('day_number')} sin '{key}'"
                    )
            if d["block_type"] not in BlockType.values:
                raise CommandError(
                    f"block_type inválido en día {d['day_number']}: "
                    f"{d['block_type']} (válidos: {list(BlockType.values)})"
                )

    def _upsert_place(self, p):
        defaults = {}
        for f in PLACE_FIELDS:
            if f not in p:
                continue
            v = p[f]
            if f in DECIMAL_FIELDS and v is not None:
                v = Decimal(str(v))
            defaults[f] = v
        place, created = Place.objects.get_or_create(
            slug=p["slug"], defaults=defaults
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"  ✓ Place creado: {p['slug']}"))
        else:
            self.stdout.write(f"  · Place ya existía: {p['slug']}")

    def _upsert_day(self, circuit, d):
        day, created = CircuitDay.objects.get_or_create(
            circuit=circuit,
            day_number=d["day_number"],
            defaults={
                "title": d["title"],
                "block_type": d["block_type"],
                "summary": d["summary"],
                "sort_order": d["day_number"],
            },
        )
        if created:
            self.stdout.write(f"  ✓ CircuitDay día {d['day_number']} creado")
        else:
            self.stdout.write(f"  · CircuitDay día {d['day_number']} ya existía")
        return day

    def _upsert_stop(self, day_obj, stop):
        place = Place.objects.get(slug=stop["slug"])
        _, created = CircuitPlace.objects.get_or_create(
            circuit_day=day_obj,
            place=place,
            defaults={
                "visit_order": stop["visit_order"],
                "is_main_stop": bool(stop.get("is_main_stop", False)),
            },
        )
        tag = "✓" if created else "·"
        suffix = "" if created else " (ya existía)"
        self.stdout.write(
            f"    {tag} stop d{day_obj.day_number}/{stop['visit_order']}: "
            f"{stop['slug']}{suffix}"
        )

    def _print_dry_run(self, new_places, days, publish, circuit):
        self.stdout.write("")
        self.stdout.write("  [dry-run] Crearía:")
        for p in new_places:
            exists = Place.objects.filter(slug=p["slug"]).exists()
            tag = "(ya existe)" if exists else "NUEVO"
            self.stdout.write(f"    · Place {p['slug']} {tag}")
        for d in days:
            self.stdout.write(
                f"    · CircuitDay día={d['day_number']} block_type={d['block_type']}"
            )
            for stop in d["stops"]:
                main = " ⭐ main" if stop.get("is_main_stop") else ""
                self.stdout.write(
                    f"        stop {stop['visit_order']}: {stop['slug']}{main}"
                )
        if publish and not circuit.published:
            self.stdout.write("    · Circuit.published = True")
