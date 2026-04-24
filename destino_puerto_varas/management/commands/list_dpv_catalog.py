"""Lista el catálogo DPV publicado (circuitos + lugares) para diagnóstico.

Uso en Render Shell:
    python manage.py list_dpv_catalog
    python manage.py list_dpv_catalog --all           # incluye no publicados
    python manage.py list_dpv_catalog --no-places     # solo circuitos
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Lista circuitos y lugares publicados (o todos con --all)."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Incluir no publicados.")
        parser.add_argument("--no-places", action="store_true", help="Solo circuitos.")
        parser.add_argument("--no-circuits", action="store_true", help="Solo lugares.")

    def handle(self, *args, **options):
        from destino_puerto_varas.models import Circuit, Place

        include_all = options["all"]

        if not options["no_circuits"]:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(
                "Circuitos" + (" (TODOS)" if include_all else " (publicados)")
            ))
            qs = Circuit.objects.all() if include_all else Circuit.objects.filter(published=True)
            qs = qs.select_related("duration_case").order_by("sort_order", "number")
            total = qs.count()
            self.stdout.write(f"  Total: {total}")
            self.stdout.write("")
            if total == 0:
                self.stdout.write(self.style.WARNING(
                    "  ⚠ No hay circuitos. Eso explica que el agente diga 'no hay circuitos'."
                ))
            for c in qs:
                days = c.duration_case.days if c.duration_case_id else "?"
                pub = "✓" if c.published else "✗"
                flags = []
                if c.is_romantic: flags.append("romantic")
                if c.is_family_friendly: flags.append("family")
                if c.is_adventure: flags.append("adventure")
                if c.is_rain_friendly: flags.append("rain_ok")
                if c.is_premium: flags.append("premium")
                flags_str = ",".join(flags) or "-"
                self.stdout.write(
                    f"  [{pub}] #{c.number} · {days}d · {c.primary_interest} · "
                    f"{c.recommended_profile or '-'} · {c.name} [{c.slug}] ({flags_str})"
                )

        if not options["no_places"]:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(
                "Lugares" + (" (TODOS)" if include_all else " (publicados)")
            ))
            qs = Place.objects.all() if include_all else Place.objects.filter(published=True)
            qs = qs.order_by("place_type", "name")
            total = qs.count()
            self.stdout.write(f"  Total: {total}")
            self.stdout.write("")
            if total == 0:
                self.stdout.write(self.style.WARNING("  ⚠ No hay lugares publicados."))
            # Agrupa por tipo para lectura rápida
            current_type = None
            for p in qs:
                if p.place_type != current_type:
                    self.stdout.write(f"  · {p.place_type}:")
                    current_type = p.place_type
                pub = "✓" if p.published else "✗"
                has_coords = "📍" if (p.latitude and p.longitude) else "  "
                flags = []
                if p.is_romantic: flags.append("romantic")
                if p.is_family_friendly: flags.append("family")
                if p.is_adventure_related: flags.append("adventure")
                if p.is_rain_friendly: flags.append("rain_ok")
                flags_str = ",".join(flags) or "-"
                self.stdout.write(f"    [{pub}] {has_coords} {p.name} [{p.slug}] ({flags_str})")
