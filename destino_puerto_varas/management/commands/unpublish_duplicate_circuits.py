"""Despublica circuits que duplican contenido de circuits ya poblados.

Decisiones (2026-04-28):
  - #1006 Pto Montt costanera+Angelmó → duplica #1030 Pto Montt+Tenglo+Angelmó
  - #1034 PN Chiloé Cucao/Chanquín → cubierto por #1049 Cucao+Chepu (más completo)
  - #1035 Chacao+Caulín+Ancud → solapa con #1027 Ancud+Puñihuil (incluye Caulín)

Uso:
    python manage.py unpublish_duplicate_circuits --dry-run
    python manage.py unpublish_duplicate_circuits
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Circuit


DUPLICATE_NUMBERS = [1006, 1034, 1035]


class Command(BaseCommand):
    help = "Despublica los 3 stubs duplicados de la fase 2 DPV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra qué se haría.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]

        for n in DUPLICATE_NUMBERS:
            c = Circuit.objects.filter(number=n).first()
            if not c:
                self.stdout.write(self.style.ERROR(f"  ✗ #{n}: no existe"))
                continue
            status = "ya despublicado" if not c.published else "PUBLISHED"
            self.stdout.write(f"  #{n} {c.name} → {status}")

            if dry or not c.published:
                continue

            c.published = False
            c.save(update_fields=["published"])
            self.stdout.write(self.style.SUCCESS(f"    ✓ despublicado"))

        if dry:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("(--dry-run: nada se persistió)"))
