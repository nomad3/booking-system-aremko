"""Despublica circuitos stub (sin días/stops) para limpiar el catálogo público.

Un stub es un Circuit sin CircuitDays asociados — solo metadata pero sin
recorrido construido. Al despublicarlos se ocultan del sitio público sin
eliminarlos (para poblarlos más adelante).

Uso:
    python manage.py unpublish_stub_circuits           # dry-run (default)
    python manage.py unpublish_stub_circuits --apply   # aplica cambios
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Count

from destino_puerto_varas.models import Circuit


class Command(BaseCommand):
    help = "Despublica circuitos stub (sin días) — sitio público los oculta."

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
            f"=== unpublish_stub_circuits [{mode}] ==="
        ))

        stubs = (
            Circuit.objects.all()
            .annotate(days_count=Count("days", distinct=True))
            .filter(days_count=0)
            .order_by("number")
        )

        already_unpublished = stubs.filter(published=False).count()
        to_unpublish = stubs.filter(published=True)
        total_stubs = stubs.count()
        count_to_change = to_unpublish.count()

        self.stdout.write(f"  Total stubs: {total_stubs}")
        self.stdout.write(f"    └─ Ya despublicados: {already_unpublished}")
        self.stdout.write(self.style.WARNING(
            f"    └─ Por despublicar:   {count_to_change}"
        ))
        self.stdout.write("")

        if count_to_change == 0:
            self.stdout.write(self.style.SUCCESS("  Nada que hacer — todos los stubs ya están despublicados."))
            return

        self.stdout.write(self.style.MIGRATE_HEADING("--- Circuitos a despublicar ---"))
        for c in to_unpublish:
            self.stdout.write(
                f"  #{c.number} · {c.primary_interest} · "
                f"{c.recommended_profile or '-'} · {c.name} [{c.slug}]"
            )

        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                f"(dry-run) Para aplicar: `python manage.py unpublish_stub_circuits --apply`"
            ))
            return

        updated = to_unpublish.update(published=False)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"  [ok] {updated} circuitos despublicados."
        ))
