"""Limpia el Place legacy 'aremko' (id=17) y corrige el location del hub nuevo.

Acciones:
  1. Corrige location del hub aremko-spa-boutique → 'Río Pescado, Puerto Varas'
  2. Verifica si el Place legacy slug='aremko' tiene paradas en circuitos
     (CircuitPlace.place tiene on_delete=PROTECT — si hay, abortamos)
  3. Si no hay paradas, borra el Place legacy. Las PlacePhoto + drafts caen
     en cascada (on_delete=CASCADE).

Uso:
    python manage.py cleanup_aremko_legacy            # dry-run (default)
    python manage.py cleanup_aremko_legacy --apply    # aplica cambios
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.models import CircuitPlace, Place


HUB_SLUG = "aremko-spa-boutique"
LEGACY_SLUG = "aremko"
CORRECTED_LOCATION = "Río Pescado, Puerto Varas"


class Command(BaseCommand):
    help = "Limpia el Place legacy 'aremko' y corrige location del hub nuevo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica los cambios. Sin esto, dry-run (default).",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(f"=== cleanup_aremko_legacy [{mode}] ==="))

        # 1) Hub nuevo: corregir location
        hub = Place.objects.filter(slug=HUB_SLUG).first()
        if hub is None:
            self.stdout.write(self.style.ERROR(f"  [error] No existe Place slug={HUB_SLUG!r}"))
            return

        self.stdout.write(f"\n[1] Hub id={hub.id} slug={hub.slug!r}")
        self.stdout.write(f"    location actual: {hub.location_label!r}")
        if hub.location_label == CORRECTED_LOCATION:
            self.stdout.write(self.style.SUCCESS("    ✓ ya está correcto, no se modifica"))
        else:
            self.stdout.write(f"    location nueva : {CORRECTED_LOCATION!r}")
            if apply_changes:
                hub.location_label = CORRECTED_LOCATION
                hub.save(update_fields=["location_label"])
                self.stdout.write(self.style.SUCCESS("    [ok] location actualizada"))
            else:
                self.stdout.write("    [dry-run] location sería actualizada")

        # 2) Legacy: verificar uso
        legacy = Place.objects.filter(slug=LEGACY_SLUG).first()
        if legacy is None:
            self.stdout.write(self.style.WARNING(
                f"\n[2] No existe Place legacy slug={LEGACY_SLUG!r} — nada que limpiar"
            ))
            return

        self.stdout.write(f"\n[2] Legacy id={legacy.id} slug={legacy.slug!r} name={legacy.name!r}")
        circuit_stops_count = CircuitPlace.objects.filter(place=legacy).count()
        photos_count = legacy.photos.count()
        drafts_count = legacy.enrichment_drafts.count()
        children_count = legacy.children.count()

        self.stdout.write(f"    circuit_stops (PROTECT): {circuit_stops_count}")
        self.stdout.write(f"    photos        (CASCADE): {photos_count}")
        self.stdout.write(f"    drafts        (CASCADE): {drafts_count}")
        self.stdout.write(f"    children      (parent FK): {children_count}")

        if circuit_stops_count > 0:
            self.stdout.write(self.style.ERROR(
                "    [abort] Tiene paradas en circuitos (on_delete=PROTECT). "
                "Mueve esas paradas a otro Place antes de borrar."
            ))
            return

        if children_count > 0:
            self.stdout.write(self.style.ERROR(
                "    [abort] Tiene Places hijos apuntando a este como parent. "
                "Re-apunta los hijos al hub correcto antes de borrar."
            ))
            return

        # 3) Borrar legacy
        if apply_changes:
            with transaction.atomic():
                deleted_count, deleted_breakdown = legacy.delete()
            self.stdout.write(self.style.SUCCESS(
                f"    [ok] borrado: {deleted_count} objetos en cascada → {deleted_breakdown}"
            ))
        else:
            self.stdout.write(
                f"    [dry-run] se borraría legacy + {photos_count} fotos + {drafts_count} drafts (cascade)"
            )

        self.stdout.write(self.style.MIGRATE_HEADING("=== fin cleanup_aremko_legacy ==="))
