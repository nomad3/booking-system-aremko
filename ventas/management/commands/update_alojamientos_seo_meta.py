"""Actualiza SOLO el meta_description del SEOContent de Alojamientos.

Contexto (Ciclo 2 del loop SEO, 2026-07-14): el cluster `cabañas con tinaja(s)
puerto varas` está creciendo en GSC (pos 9-11, ~42 imp/sem) y la meta de
/alojamientos/ era genérica y sin la grafía "tinaja" (con J) que la gente
busca. Esta meta nueva incorpora "tinaja", "junto al río Pescado" y "hasta
medianoche".

⚠️ Por qué un comando quirúrgico y NO editar `populate_seo_content.py`:
ese seed masivo usa `update_or_create` (pisa TODOS los campos) y está
desactualizado respecto a producción — su meta de Masajes es la vieja, no la
que Jorge aplicó a mano en el admin en el Ciclo 1. Re-correrlo revertiría ese
trabajo. Este comando toca únicamente `meta_description` de la fila de
Alojamientos (categoria_id=3, la misma que usa `alojamientos_view` →
`categoria_detail_view(categoria_id=3)`), nada más. Es idempotente.

Uso:
    python manage.py update_alojamientos_seo_meta --dry-run   # muestra el cambio
    python manage.py update_alojamientos_seo_meta             # aplica
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from ventas.models import SEOContent


CATEGORIA_ID = 3  # Alojamientos (igual que en alojamientos_view y populate_seo_content)

NEW_META_DESCRIPTION = (
    "Cabañas con tina caliente (tinaja) en Puerto Varas, junto al río "
    "Pescado. Alojamiento privado con spa, desayuno y tinas hasta medianoche. "
    "Reserva online."
)


class Command(BaseCommand):
    help = (
        "Actualiza solo el meta_description del SEOContent de Alojamientos "
        "(categoria_id=3). Idempotente. Usá --dry-run para previsualizar."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra el cambio, sin escribir en la BD.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        if len(NEW_META_DESCRIPTION) > 160:
            self.stderr.write(
                self.style.ERROR(
                    f"meta_description tiene {len(NEW_META_DESCRIPTION)} char (>160). Abortado."
                )
            )
            return

        seo = (
            SEOContent.objects.select_related("categoria")
            .filter(categoria_id=CATEGORIA_ID)
            .first()
        )
        if seo is None:
            self.stderr.write(
                self.style.ERROR(
                    f"No hay SEOContent para categoria_id={CATEGORIA_ID}. "
                    "Verificá que Alojamientos exista y tenga contenido SEO."
                )
            )
            return

        self.stdout.write(f"Categoría: {seo.categoria.nombre} (id={CATEGORIA_ID})")
        self.stdout.write(f"  Actual  ({len(seo.meta_description)}): {seo.meta_description}")
        self.stdout.write(f"  Nuevo   ({len(NEW_META_DESCRIPTION)}): {NEW_META_DESCRIPTION}")

        if seo.meta_description == NEW_META_DESCRIPTION:
            self.stdout.write(self.style.SUCCESS("Sin cambios: la meta ya es la nueva. Idempotente."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("[dry-run] No se escribió nada."))
            return

        seo.meta_description = NEW_META_DESCRIPTION
        seo.save(update_fields=["meta_description", "updated_at"])
        self.stdout.write(self.style.SUCCESS("meta_description de Alojamientos actualizado."))
