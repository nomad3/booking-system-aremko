"""Carga catálogo Aremko Spa Boutique en DPV (Alternativa C — Hybrid Places).

Crea:
  - 1 Place padre: aremko-spa-boutique (hub SEO + branding)
  - 3 Places hijo (parent_place=padre):
      • aremko-tinas-calientes (3h, medio día)
      • aremko-tinas-masajes (4h, medio día)
      • aremko-estancia-completa (24h, 2D1N)
  - 3 Circuits con stops apuntando al hijo correspondiente:
      • aremko-tarde-tinas (HALF_DAY)
      • aremko-tarde-tinas-masajes (HALF_DAY)
      • aremko-experiencia-completa (2D1N)

Idempotente: get_or_create por slug. Re-ejecutable sin duplicados.
Drift-safe: no toca apps `ventas/` ni `control_gestion/`.

Uso:
    python manage.py load_aremko [--dry-run]
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from destino_puerto_varas.enums import (
    BlockType,
    InterestType,
    PartnershipLevel,
    PlaceType,
    ProfileType,
)
from destino_puerto_varas.models import (
    Circuit,
    CircuitDay,
    CircuitPlace,
    DurationCase,
    Place,
)


# ─── Datos Aremko ─────────────────────────────────────────────────────────────
AREMKO_HUB = {
    "slug": "aremko-spa-boutique",
    "name": "Aremko Spa Boutique",
    "place_type": PlaceType.SPA,
    "partnership_level": PartnershipLevel.OWNED,
    "location_label": "Río Pescado, Puerto Varas",
    "latitude": Decimal("-41.277611"),
    "longitude": Decimal("-72.768611"),
    "short_description": (
        "Spa boutique con tinas calientes al aire libre, masajes y cabañas frente al río. "
        "Aguas calientes junto al río."
    ),
    "long_description": (
        "Aremko Spa Boutique combina aguas termales, masajes terapéuticos y cabañas "
        "boutique en un entorno natural junto al río Pescado, a pocos minutos de Puerto "
        "Varas centro. El spa ofrece tres experiencias diferenciadas según el tiempo "
        "disponible: tinas calientes (medio día), tinas + masajes (medio día extendido) "
        "o estancia completa con alojamiento."
    ),
    "is_romantic": True,
    "is_rain_friendly": True,
    "website": "https://www.aremko.cl",
    "reservations_url": "https://www.aremko.cl",
    "instagram": "aremkospa",
}

AREMKO_CHILDREN = [
    {
        "slug": "aremko-tinas-calientes",
        "name": "Aremko · Tinas Calientes",
        "place_type": PlaceType.SPA,
        "partnership_level": PartnershipLevel.OWNED,
        "location_label": "Aremko Spa Boutique, Puerto Varas",
        "latitude": Decimal("-41.277611"),
        "longitude": Decimal("-72.768611"),
        "short_description": (
            "Tinas calientes al aire libre frente al río. 2 horas de tinas en un spa de 3 horas total."
        ),
        "long_description": (
            "Experiencia de tinas calientes en Aremko Spa Boutique. Duración total ~3 horas "
            "(incluye 2 horas de inmersión en tinas más cambio y descanso). Ideal como "
            "cierre de un día de circuito turístico por la tarde."
        ),
        "is_romantic": True,
        "is_rain_friendly": True,
        "recommended_visit_duration": "3 horas",
        "requires_reservation": True,
        "reservations_url": "https://www.aremko.cl",
    },
    {
        "slug": "aremko-tinas-masajes",
        "name": "Aremko · Tinas + Masajes",
        "place_type": PlaceType.SPA,
        "partnership_level": PartnershipLevel.OWNED,
        "location_label": "Aremko Spa Boutique, Puerto Varas",
        "latitude": Decimal("-41.277611"),
        "longitude": Decimal("-72.768611"),
        "short_description": (
            "Combo de tinas calientes y masaje para 2. Experiencia de spa de 4 horas."
        ),
        "long_description": (
            "Combinación de tinas calientes al aire libre + masaje terapéutico para 2 personas. "
            "Duración total ~4 horas. Cierre romántico de un día de paseo."
        ),
        "is_romantic": True,
        "is_rain_friendly": True,
        "recommended_visit_duration": "4 horas",
        "requires_reservation": True,
        "reservations_url": "https://www.aremko.cl",
    },
    {
        "slug": "aremko-estancia-completa",
        "name": "Aremko · Estancia Completa",
        "place_type": PlaceType.LODGING,
        "partnership_level": PartnershipLevel.OWNED,
        "location_label": "Aremko Spa Boutique, Puerto Varas",
        "latitude": Decimal("-41.277611"),
        "longitude": Decimal("-72.768611"),
        "short_description": (
            "Cabaña boutique + tinas calientes + masajes para 2. Estadía de 1 noche con desayuno."
        ),
        "long_description": (
            "Estancia completa de 1 noche en cabaña boutique frente al río Pescado. Incluye "
            "tinas calientes al atardecer, masajes para 2 personas y desayuno. Experiencia "
            "de 24 horas pensada para parejas que buscan un retiro romántico cerca de Puerto Varas."
        ),
        "is_romantic": True,
        "is_rain_friendly": True,
        "recommended_visit_duration": "24 horas (2D1N)",
        "requires_reservation": True,
        "reservations_url": "https://www.aremko.cl",
    },
]

# ─── Circuitos Aremko ─────────────────────────────────────────────────────────
# duration_code se resuelve a DurationCase via slug pre-existente del seed DPV.
AREMKO_CIRCUITS = [
    {
        "slug": "aremko-tarde-tinas",
        "name": "Tarde de tinas en Aremko",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": InterestType.RELAX_ROMANTIC,
        "recommended_profile": ProfileType.COUPLE,
        "short_description": (
            "Cierre del día con tinas calientes al aire libre frente al río. "
            "3 horas de spa para parejas."
        ),
        "flags": {
            "is_romantic": True,
            "is_rain_friendly": True,
            "is_premium": True,
        },
        "child_slug": "aremko-tinas-calientes",
        "day_title": "Tarde de tinas",
        "day_summary": (
            "Llegas a Aremko Spa Boutique a media tarde. Tinas calientes al aire libre "
            "junto al río Pescado durante 2 horas. Cambio y descanso. Total ~3 horas."
        ),
    },
    {
        "slug": "aremko-tarde-tinas-masajes",
        "name": "Tarde de tinas y masajes en Aremko",
        "duration_code": "DPV_HALF_DAY",
        "primary_interest": InterestType.RELAX_ROMANTIC,
        "recommended_profile": ProfileType.COUPLE,
        "short_description": (
            "Combo romántico: tinas calientes + masaje para 2. 4 horas de spa boutique."
        ),
        "flags": {
            "is_romantic": True,
            "is_rain_friendly": True,
            "is_premium": True,
        },
        "child_slug": "aremko-tinas-masajes",
        "day_title": "Tarde de tinas y masajes",
        "day_summary": (
            "Llegas a Aremko a media tarde. Masaje terapéutico para 2, seguido de tinas "
            "calientes al aire libre. Total ~4 horas. Ideal cierre de un día de circuito."
        ),
    },
    {
        "slug": "aremko-experiencia-completa",
        "name": "Experiencia completa en Aremko (2D1N)",
        "duration_code": "DPV_2D1N",
        "primary_interest": InterestType.RELAX_ROMANTIC,
        "recommended_profile": ProfileType.COUPLE,
        "short_description": (
            "Estancia romántica de 1 noche: tinas, masajes y cabaña boutique frente al río."
        ),
        "flags": {
            "is_romantic": True,
            "is_rain_friendly": True,
            "is_premium": True,
        },
        # Día 1: tinas + masajes; Día 2: cabaña + desayuno
        "days": [
            {
                "day_number": 1,
                "title": "Día 1 · Llegada y spa",
                "block_type": BlockType.AREMKO_MOMENT,
                "summary": (
                    "Llegada a Aremko Spa Boutique a media tarde. Masaje para 2 + tinas "
                    "calientes al aire libre. Cena libre y noche en cabaña boutique."
                ),
                "child_slug": "aremko-tinas-masajes",
            },
            {
                "day_number": 2,
                "title": "Día 2 · Despertar junto al río",
                "block_type": BlockType.AREMKO_MOMENT,
                "summary": (
                    "Desayuno en la cabaña, mañana libre frente al río Pescado. "
                    "Checkout al mediodía."
                ),
                "child_slug": "aremko-estancia-completa",
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Carga catálogo Aremko Spa Boutique en DPV (4 Places + 3 Circuits)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué se haría sin tocar la base de datos.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # 1) Place padre
        hub = self._upsert_place(AREMKO_HUB, parent=None, dry_run=dry_run)

        # 2) Places hijo
        children_by_slug: dict[str, Place] = {}
        for spec in AREMKO_CHILDREN:
            child = self._upsert_place(spec, parent=hub, dry_run=dry_run)
            children_by_slug[spec["slug"]] = child

        # 3) Circuits + Days + Stops
        next_number = self._next_circuit_number()
        for entry in AREMKO_CIRCUITS:
            circuit, was_created = self._upsert_circuit(entry, next_number, dry_run=dry_run)
            # Avanzar solo si se intentó crear nuevo (real o dry-run); skip si ya existía.
            if was_created:
                next_number += 1
            self._ensure_days_and_stops(circuit, entry, children_by_slug, dry_run=dry_run)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            "Aremko cargado. Recordá generar acuarelas hero y narrativas con IA."
        ))

    # ─── helpers ─────────────────────────────────────────────────────────────

    def _upsert_place(self, spec: dict, parent: Place | None, dry_run: bool) -> Place | None:
        slug = spec["slug"]
        existing = Place.objects.filter(slug=slug).first()
        if existing:
            self.stdout.write(self.style.WARNING(f"  [skip place] {slug} ya existe"))
            # Si existe pero parent no coincide, lo actualizamos (idempotente).
            if not dry_run and parent and existing.parent_place_id != getattr(parent, "id", None):
                existing.parent_place = parent
                existing.save(update_fields=["parent_place"])
                self.stdout.write(f"    parent_place actualizado → {parent.slug}")
            return existing

        if dry_run:
            self.stdout.write(f"  [dry-run] crearía Place {slug}")
            return None

        payload = {k: v for k, v in spec.items() if k != "slug"}
        with transaction.atomic():
            place = Place.objects.create(slug=slug, parent_place=parent, **payload)
        self.stdout.write(self.style.SUCCESS(f"  [ok place] {slug}"))
        return place

    def _upsert_circuit(
        self, entry: dict, number: int, dry_run: bool
    ) -> tuple[Circuit | None, bool]:
        """Devuelve (circuit_or_None, was_created).

        was_created=True si se creó (o se crearía en dry-run) un Circuit nuevo.
        was_created=False si ya existía (skip) o si hubo error.
        """
        slug = entry["slug"]
        existing = Circuit.objects.filter(slug=slug).first()
        if existing:
            self.stdout.write(self.style.WARNING(f"  [skip circuit] {slug} ya existe"))
            return existing, False

        duration = DurationCase.objects.filter(code=entry["duration_code"]).first()
        if duration is None:
            self.stdout.write(self.style.ERROR(
                f"  [error] DurationCase {entry['duration_code']} no existe. "
                "Corré load_dpv_circuits_from_study primero."
            ))
            return None, False

        if dry_run:
            self.stdout.write(f"  [dry-run] crearía Circuit #{number} {slug}")
            return None, True

        payload = dict(
            number=number,
            name=entry["name"][:200],
            slug=slug,
            short_description=entry["short_description"][:255],
            long_description="",
            duration_case=duration,
            primary_interest=entry["primary_interest"],
            recommended_profile=entry.get("recommended_profile", ""),
            published=True,
            featured=False,
            sort_order=600 + (number % 100) * 10,
        )
        payload.update(entry["flags"])

        with transaction.atomic():
            circuit = Circuit.objects.create(**payload)
        self.stdout.write(self.style.SUCCESS(f"  [ok circuit] #{number} {slug}"))
        return circuit, True

    def _ensure_days_and_stops(
        self,
        circuit: Circuit,
        entry: dict,
        children_by_slug: dict[str, Place],
        dry_run: bool,
    ) -> None:
        if dry_run or circuit is None:
            return

        # Caso single-day (HALF_DAY) o multi-day (2D1N)
        if "days" in entry:
            days_specs = entry["days"]
        else:
            days_specs = [{
                "day_number": 1,
                "title": entry["day_title"],
                "block_type": BlockType.HALF_DAY,
                "summary": entry["day_summary"],
                "child_slug": entry["child_slug"],
            }]

        for day_spec in days_specs:
            place = children_by_slug.get(day_spec["child_slug"])
            if place is None:
                self.stdout.write(self.style.ERROR(
                    f"  [error] child_slug {day_spec['child_slug']} no encontrado"
                ))
                continue

            day, day_created = CircuitDay.objects.get_or_create(
                circuit=circuit,
                day_number=day_spec["day_number"],
                defaults=dict(
                    title=day_spec["title"][:200],
                    block_type=day_spec["block_type"],
                    summary=day_spec["summary"],
                    sort_order=day_spec["day_number"] * 10,
                ),
            )
            if day_created:
                self.stdout.write(f"    [ok day] {circuit.slug} día {day.day_number}")

            stop_exists = CircuitPlace.objects.filter(circuit_day=day, place=place).exists()
            if not stop_exists:
                CircuitPlace.objects.create(
                    circuit_day=day,
                    place=place,
                    visit_order=1,
                    is_main_stop=True,
                )
                self.stdout.write(f"    [ok stop] {place.slug} → día {day.day_number}")

    def _next_circuit_number(self) -> int:
        """Aremko empieza en 2001 para no chocar con seeds previos."""
        max_existing = (
            Circuit.objects.filter(number__gte=2000)
            .order_by("-number")
            .values_list("number", flat=True)
            .first()
        )
        return (max_existing or 2000) + 1
