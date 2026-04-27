"""Crea 3 circuitos NUEVOS (clones de circuitos DPV clásicos) con Aremko al cierre.

Mantiene el catálogo DPV neutro intacto y crea variantes "+ Aremko" con:
  - primary_interest=RELAX_ROMANTIC, recommended_profile=COUPLE
  - is_romantic=True, is_premium=True
  - Stop final en aremko-tinas-calientes (Day último, visit_order=último)
  - Día Aremko marcado como block_type=AREMKO_MOMENT

Numeración 2010+ (separada de los Aremko puros 2001-2003).

Circuitos clonados:
  - #1029 Volcán Osorno + Saltos del Petrohué        → #2010
  - #1028 Ensenada + Saltos + Lago Todos los Santos  → #2011
  - #1020 Navegación a Peulla desde Petrohué         → #2012

Uso:
    python manage.py load_aremko_finale_circuits            # dry-run (default)
    python manage.py load_aremko_finale_circuits --apply    # aplica cambios
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.enums import (
    BlockType,
    InterestType,
    ProfileType,
)
from destino_puerto_varas.models import (
    Circuit,
    CircuitDay,
    CircuitPlace,
    Place,
)


# (base_slug, new_number, new_slug, new_name)
FINALE_CIRCUITS = [
    (
        "volcan-osorno-saltos-petrohue",
        2010,
        "volcan-osorno-saltos-aremko",
        "Volcán Osorno + Saltos del Petrohué con cierre en Aremko",
    ),
    (
        "ensenada-saltos-todos-los-santos",
        2011,
        "ensenada-saltos-tls-aremko",
        "Ensenada + Saltos + Lago Todos los Santos con cierre en Aremko",
    ),
    (
        "navegacion-peulla-petrohue",
        2012,
        "peulla-aremko",
        "Navegación a Peulla con cierre romántico en Aremko",
    ),
]

AREMKO_FINALE_PLACE_SLUG = "aremko-tinas-calientes"

AREMKO_DAY_TITLE = "Tarde de tinas calientes en Aremko"
AREMKO_DAY_SUMMARY = (
    "Tras el recorrido turístico, cierre del día en Aremko Spa Boutique con "
    "tinas calientes al aire libre frente al río Pescado. ~3 horas (incluye 2 "
    "horas de inmersión más cambio y descanso)."
)
AREMKO_FINALE_PARAGRAPH = (
    "\n\nEl día cierra con una tarde de tinas calientes al aire libre frente "
    "al río Pescado, en Aremko Spa Boutique — para descansar piernas, soltar "
    "el estrés del recorrido y rematar la jornada en pareja."
)


class Command(BaseCommand):
    help = "Crea 3 circuitos clonados con cierre Aremko (RELAX_ROMANTIC, COUPLE)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica los cambios. Sin esto, dry-run (default).",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== load_aremko_finale_circuits [{mode}] ==="
        ))

        # Validar Place destino
        aremko_place = Place.objects.filter(slug=AREMKO_FINALE_PLACE_SLUG).first()
        if aremko_place is None:
            self.stdout.write(self.style.ERROR(
                f"  [error] No existe Place slug={AREMKO_FINALE_PLACE_SLUG!r}. "
                "Corre primero `load_aremko --apply`."
            ))
            return

        created_count = 0
        skipped_count = 0
        for base_slug, new_number, new_slug, new_name in FINALE_CIRCUITS:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(f"→ {new_slug} (#{new_number})"))

            # 1. Validar circuito base
            base = Circuit.objects.filter(slug=base_slug).first()
            if base is None:
                self.stdout.write(self.style.ERROR(
                    f"  [error] Circuito base {base_slug!r} no existe. Skip."
                ))
                continue
            self.stdout.write(f"  Base: #{base.number} {base.name!r}")

            # 2. Skip si el clon ya existe
            existing = Circuit.objects.filter(slug=new_slug).first()
            if existing:
                self.stdout.write(self.style.WARNING(
                    f"  [skip] Ya existe #{existing.number} {existing.slug!r}"
                ))
                skipped_count += 1
                continue

            if not apply_changes:
                self.stdout.write(
                    f"  [dry-run] crearía circuito clon + cierre Aremko"
                )
                created_count += 1
                continue

            # 3. APPLY — clone + add Aremko stop
            with transaction.atomic():
                new_long_desc = (base.long_description or "").rstrip() + AREMKO_FINALE_PARAGRAPH

                clone = Circuit.objects.create(
                    number=new_number,
                    name=new_name[:200],
                    slug=new_slug,
                    short_description=base.short_description,
                    long_description=new_long_desc,
                    duration_case=base.duration_case,
                    primary_interest=InterestType.RELAX_ROMANTIC,
                    recommended_profile=ProfileType.COUPLE,
                    is_romantic=True,
                    is_family_friendly=False,
                    is_adventure=False,
                    is_rain_friendly=base.is_rain_friendly,
                    is_premium=True,
                    is_nature=base.is_nature,
                    is_culture=base.is_culture,
                    is_gastronomy=base.is_gastronomy,
                    published=True,
                    featured=False,
                    sort_order=base.sort_order,
                )
                self.stdout.write(self.style.SUCCESS(
                    f"  [ok circuit] #{clone.number} {clone.slug}"
                ))

                # Clonar todos los días + stops del base
                for base_day in base.days.all().order_by("day_number"):
                    new_day = CircuitDay.objects.create(
                        circuit=clone,
                        day_number=base_day.day_number,
                        title=base_day.title,
                        block_type=base_day.block_type,
                        summary=base_day.summary,
                        sort_order=base_day.sort_order,
                    )
                    for stop in base_day.place_stops.all().order_by("visit_order"):
                        CircuitPlace.objects.create(
                            circuit_day=new_day,
                            place=stop.place,
                            visit_order=stop.visit_order,
                            is_main_stop=stop.is_main_stop,
                        )
                    self.stdout.write(
                        f"    [ok day {new_day.day_number}] {new_day.place_stops.count()} stops clonados"
                    )

                # Determinar el último día (donde va el cierre Aremko)
                last_day = clone.days.order_by("-day_number").first()
                if last_day is None:
                    # Circuito 0d sin días — creamos Day 1 con block AREMKO_MOMENT
                    last_day = CircuitDay.objects.create(
                        circuit=clone,
                        day_number=1,
                        title=AREMKO_DAY_TITLE[:200],
                        block_type=BlockType.AREMKO_MOMENT,
                        summary=AREMKO_DAY_SUMMARY,
                        sort_order=10,
                    )
                    self.stdout.write(
                        f"    [ok day 1] día Aremko-only creado (base era 0d)"
                    )
                else:
                    # Anexamos summary Aremko al último día existente
                    if last_day.summary and "Aremko" not in last_day.summary:
                        last_day.summary = last_day.summary.rstrip() + " " + AREMKO_DAY_SUMMARY
                        last_day.save(update_fields=["summary"])

                # Append stop Aremko al último día
                max_order = (
                    CircuitPlace.objects.filter(circuit_day=last_day)
                    .order_by("-visit_order")
                    .values_list("visit_order", flat=True)
                    .first()
                ) or 0
                CircuitPlace.objects.create(
                    circuit_day=last_day,
                    place=aremko_place,
                    visit_order=max_order + 10,
                    is_main_stop=False,
                )
                self.stdout.write(self.style.SUCCESS(
                    f"    [ok finale] {aremko_place.slug} → día {last_day.day_number} "
                    f"(visit_order={max_order + 10})"
                ))

            created_count += 1

        self.stdout.write("")
        verb = "creados" if apply_changes else "se crearían"
        self.stdout.write(self.style.SUCCESS(
            f"Resumen: {created_count} circuitos {verb}, {skipped_count} ya existían."
        ))
        if not apply_changes and created_count > 0:
            self.stdout.write(self.style.WARNING(
                "(dry-run) Para aplicar: `python manage.py load_aremko_finale_circuits --apply`"
            ))
