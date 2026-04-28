"""Lista los 23 Places nuevos creados en la tanda de stub-population (2026-04-27)
con su ID, place_type, partnership_level, link de admin y tipo de foto sugerido
según convención DPV.

Convención fotos (memoria feedback_dpv_fotos_por_place_type):
  - OWNED       → acuarela primary
  - LISTED LODGING/RESTAURANT/CAFE/SHOP/SPA   → foto del local (comercio)
  - LISTED ATTRACTION/VIEWPOINT/PARK/CHURCH/MUSEUM → foto real (Wikimedia/CONAF)

Uso:
    python manage.py list_new_places_to_photo
    python manage.py list_new_places_to_photo --base-url https://destinopuertovaras.cl
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from destino_puerto_varas.models import Place


# 23 slugs creados por los 8 populate_* commands de 2026-04-27
NEW_SLUGS = [
    # #1001 Puerto Varas patrimonial
    "iglesia-sagrado-corazon-puerto-varas",
    "barrio-patrimonial-aleman-puerto-varas",
    # #1033 Castro + Dalcahue + Tocoihue + Putemún
    "iglesia-san-francisco-castro",
    "iglesia-de-putemun",
    "iglesia-de-tocoihue",
    # #1027 Ancud + Puñihuil
    "caulin",
    "fuerte-san-antonio-ancud",
    "punihuil-pinguineras",
    "playa-mar-brava",
    # #1025 Puyehue Aguas Calientes
    "termas-puyehue-hotel",
    "aguas-calientes-conaf",
    "sendero-rapidos-chanleufu",
    "salto-del-indio-anticura",
    "mirador-antillanca",
    # #1045 Puyehue slow
    "lago-puyehue-bahia-escocia",
    # #1017 Cochamó pueblo + Ralún
    "mirador-estuario-reloncavi",
    "ralun",
    # #1005 Las Cascadas y salto
    "salto-la-picada",
    # #1030 Puerto Montt + Tenglo + Angelmó
    "puerto-montt-plaza-catedral",
    "mirador-manuel-montt",
    "caleta-angelmo",
    "mercado-artesanal-angelmo",
    "isla-tenglo",
]

COMERCIO_TYPES = {"LODGING", "RESTAURANT", "CAFE", "SHOP", "SPA", "TOUR_OPERATOR", "BUSINESS"}


def photo_type_hint(p: Place) -> str:
    if p.partnership_level == "OWNED":
        return "ACUARELA (owned)"
    if p.place_type in COMERCIO_TYPES:
        return "FOTO LOCAL (comercio)"
    return "FOTO REAL (Wikimedia/CONAF/turismo)"


class Command(BaseCommand):
    help = "Lista los 23 Places nuevos para fotear, con admin link + tipo de foto."

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-url",
            default="https://destinopuertovaras.cl",
            help="Base URL para construir links de admin (default destinopuertovaras.cl)",
        )

    def handle(self, *args, **options):
        base = options["base_url"].rstrip("/")
        self.stdout.write(self.style.MIGRATE_HEADING(
            "=== 23 Places nuevos para subir foto ==="
        ))
        self.stdout.write("")

        missing = []
        for idx, slug in enumerate(NEW_SLUGS, start=1):
            p = Place.objects.filter(slug=slug).first()
            if not p:
                missing.append(slug)
                continue

            admin_url = f"{base}/admin/destino_puerto_varas/place/{p.id}/change/"
            hint = photo_type_hint(p)

            self.stdout.write(
                self.style.SUCCESS(f"  [{idx:>2}] #{p.id} {p.name}")
            )
            self.stdout.write(f"       slug: {p.slug}")
            self.stdout.write(f"       tipo: {p.place_type}  partnership: {p.partnership_level}")
            self.stdout.write(f"       foto: {hint}")
            self.stdout.write(f"       admin: {admin_url}")
            self.stdout.write("")

        if missing:
            self.stdout.write(self.style.WARNING(
                f"  [warn] No encontrados ({len(missing)}): {', '.join(missing)}"
            ))

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Total a fotear: {len(NEW_SLUGS) - len(missing)} / {len(NEW_SLUGS)}"
        ))
