"""Inspecciona el draft más reciente de un Place y reporta qué campos
prácticos llegaron del LLM y cuáles se persistieron en el Place.

Uso:
    python manage.py inspect_place_draft --slug teatro-del-lago
    python manage.py inspect_place_draft --slug teatro-del-lago --apply  # aplica el draft DRAFT más reciente
"""
import json

from django.core.management.base import BaseCommand, CommandError

from destino_puerto_varas.models import Place, PlaceEnrichmentDraft

PRACTICAL_FIELDS = [
    "entry_fee_text",
    "entry_fee_clp",
    "best_season",
    "requires_reservation",
    "recommended_visit_duration",
    "payment_methods",
    "pet_friendly",
    "has_tourist_info",
    "nearby_food_options",
    "parking_details",
    "phone",
    "website",
    "instagram",
    "opening_hours",
]


class Command(BaseCommand):
    help = "Inspecciona el último draft de un Place y compara con el Place persistido."

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True, help="slug del Place")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Si el último draft está en DRAFT, lo aprueba y aplica.",
        )

    def handle(self, *args, **opts):
        slug = opts["slug"]
        try:
            place = Place.objects.get(slug=slug)
        except Place.DoesNotExist:
            raise CommandError(f"No existe Place con slug={slug}")

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== PLACE: {place.name} (id={place.id}) ==="))
        self.stdout.write("Campos prácticos en el Place persistido:")
        for f in PRACTICAL_FIELDS:
            val = getattr(place, f, None)
            marker = self.style.SUCCESS("✓") if val not in (None, "", {}) else self.style.WARNING("·")
            preview = json.dumps(val, ensure_ascii=False)[:100] if isinstance(val, dict) else str(val)[:100]
            self.stdout.write(f"  {marker} {f:32s} = {preview}")

        drafts = place.enrichment_drafts.order_by("-created_at")[:5]
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== ÚLTIMOS {len(drafts)} DRAFTS ==="))

        for d in drafts:
            self.stdout.write(
                f"\n— Draft #{d.id} | status={d.status} | "
                f"creado={d.created_at:%Y-%m-%d %H:%M} | aplicado={d.applied_at}"
            )
            fields = (d.proposed_data or {}).get("fields") or {}
            self.stdout.write("  Campos prácticos en proposed_data.fields:")
            for f in PRACTICAL_FIELDS:
                if f == "opening_hours":
                    val = (d.proposed_data or {}).get("opening_hours")
                else:
                    val = fields.get(f)
                if val in (None, "", {}):
                    marker = self.style.WARNING("·")
                    preview = "null/empty"
                else:
                    marker = self.style.SUCCESS("✓")
                    preview = json.dumps(val, ensure_ascii=False)[:100]
                self.stdout.write(f"    {marker} {f:30s} = {preview}")

        if opts["apply"]:
            from destino_puerto_varas.services.place_enrichment_service import apply_draft

            d = place.enrichment_drafts.filter(
                status=PlaceEnrichmentDraft.STATUS_DRAFT
            ).order_by("-created_at").first()
            if not d:
                self.stdout.write(self.style.WARNING("\nNo hay drafts en STATUS_DRAFT para aplicar."))
                return
            d.status = PlaceEnrichmentDraft.STATUS_APPROVED
            d.save(update_fields=["status"])
            ok = apply_draft(d, reviewer="inspect_place_draft")
            if ok:
                self.stdout.write(self.style.SUCCESS(f"\n✓ Draft #{d.id} aplicado al Place."))
            else:
                self.stdout.write(self.style.ERROR(f"\n✗ apply_draft retornó False."))
