"""Setea lat/long de los 4 Places Aremko (mismo punto: Río Pescado km 4).

Coordenadas oficiales: -41.277611, -72.768611

Uso:
    python manage.py set_aremko_coords            # dry-run (default)
    python manage.py set_aremko_coords --apply    # aplica cambios
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Place


AREMKO_SLUGS = [
    "aremko-spa-boutique",
    "aremko-tinas-calientes",
    "aremko-tinas-masajes",
    "aremko-estancia-completa",
]

LAT = Decimal("-41.277611")
LNG = Decimal("-72.768611")


class Command(BaseCommand):
    help = "Setea latitude/longitude en los 4 Places Aremko."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(f"=== set_aremko_coords [{mode}] ==="))

        updated = 0
        for slug in AREMKO_SLUGS:
            place = Place.objects.filter(slug=slug).first()
            if place is None:
                self.stdout.write(self.style.WARNING(f"  [skip] {slug} no existe"))
                continue

            if place.latitude == LAT and place.longitude == LNG:
                self.stdout.write(f"  [ok] {slug} ya tiene las coords correctas")
                continue

            self.stdout.write(
                f"  [change] {slug}: ({place.latitude}, {place.longitude}) → ({LAT}, {LNG})"
            )
            if apply_changes:
                place.latitude = LAT
                place.longitude = LNG
                place.save(update_fields=["latitude", "longitude"])
                self.stdout.write(self.style.SUCCESS(f"    [saved]"))
            updated += 1

        verb = "actualizados" if apply_changes else "se actualizarían"
        self.stdout.write(self.style.SUCCESS(f"\nResumen: {updated} Places {verb}."))
