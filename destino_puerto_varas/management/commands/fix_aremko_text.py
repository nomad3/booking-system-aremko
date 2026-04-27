"""Corrige referencias 'río Maullín' → 'río Pescado' en los Places Aremko.

Aremko Spa Boutique está físicamente en sector Río Pescado de Puerto Varas,
no junto al río Maullín. El seed inicial tenía la descripción incorrecta.

Uso:
    python manage.py fix_aremko_text            # dry-run (default)
    python manage.py fix_aremko_text --apply    # aplica cambios
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Place


AREMKO_SLUGS = [
    "aremko-spa-boutique",
    "aremko-tinas-calientes",
    "aremko-tinas-masajes",
    "aremko-estancia-completa",
]


class Command(BaseCommand):
    help = "Corrige 'río Maullín' → 'río Pescado' en los Places Aremko."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(f"=== fix_aremko_text [{mode}] ==="))

        changed = 0
        for slug in AREMKO_SLUGS:
            place = Place.objects.filter(slug=slug).first()
            if place is None:
                self.stdout.write(self.style.WARNING(f"  [skip] {slug} no existe"))
                continue

            updates = {}
            for field in ("long_description", "short_description"):
                old = getattr(place, field) or ""
                if "Maullín" in old or "maullín" in old.lower():
                    new = old.replace("río Maullín", "río Pescado").replace("Río Maullín", "Río Pescado")
                    updates[field] = new

            if not updates:
                self.stdout.write(f"  [ok] {slug} sin cambios")
                continue

            self.stdout.write(f"  [change] {slug}")
            for field, new in updates.items():
                self.stdout.write(f"    {field}: ...{new[:120]}...")

            if apply_changes:
                for field, new in updates.items():
                    setattr(place, field, new)
                place.save(update_fields=list(updates.keys()))
                self.stdout.write(self.style.SUCCESS(f"    [saved]"))
            changed += 1

        verb = "actualizados" if apply_changes else "se actualizarían"
        self.stdout.write(self.style.SUCCESS(f"\nResumen: {changed} Places {verb}."))
