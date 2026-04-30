"""Marca como is_romantic=True todos los circuitos y places donde Aremko está presente.

Por defecto corre en --dry-run (solo muestra qué cambiaría).
Para aplicar, pasar --apply.

Criterios:
- Place: slug contiene 'aremko' (parent + cabañas hijas).
- Circuit: itinerario incluye al menos un place de Aremko.

Idempotente: re-ejecutar no cambia nada si ya están marcados.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Circuit, Place


class Command(BaseCommand):
    help = "Marca is_romantic=True en circuitos y places donde Aremko está presente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica los cambios. Sin esta flag, solo muestra qué pasaría (dry-run).",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        mode = "APPLY" if apply else "DRY-RUN"
        self.stdout.write(self.style.NOTICE(f"=== Modo: {mode} ==="))

        # ─── Places Aremko ───
        aremko_places = Place.objects.filter(slug__icontains="aremko")
        places_to_update = aremko_places.filter(is_romantic=False)
        self.stdout.write(
            f"\nPlaces Aremko encontrados: {aremko_places.count()} "
            f"(ya marcados: {aremko_places.count() - places_to_update.count()}, "
            f"a actualizar: {places_to_update.count()})"
        )
        for p in places_to_update:
            self.stdout.write(f"  → {p.slug} ({p.place_type})")

        # ─── Circuitos con Aremko en itinerario ───
        aremko_circuits = (
            Circuit.objects.filter(
                days__place_stops__place__slug__icontains="aremko"
            )
            .distinct()
        )
        circuits_to_update = aremko_circuits.filter(is_romantic=False)
        self.stdout.write(
            f"\nCircuitos con Aremko en itinerario: {aremko_circuits.count()} "
            f"(ya marcados: {aremko_circuits.count() - circuits_to_update.count()}, "
            f"a actualizar: {circuits_to_update.count()})"
        )
        for c in circuits_to_update:
            self.stdout.write(f"  → #{c.number} {c.name} (published={c.published})")

        if not apply:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry-run: no se escribió nada. Re-ejecutar con --apply para confirmar."
                )
            )
            return

        # ─── APPLY ───
        places_count = places_to_update.update(is_romantic=True)
        circuits_count = circuits_to_update.update(is_romantic=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Aplicado: {places_count} places + {circuits_count} circuitos marcados como is_romantic=True"
            )
        )
