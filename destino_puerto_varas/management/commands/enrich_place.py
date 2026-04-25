"""Enriquece un Place vía Perplexity (DPV CMS-IA · Capa 2).

Uso en Render Shell:
    python manage.py enrich_place --slug volcan-osorno
    python manage.py enrich_place --slug volcan-osorno --dry-run    # no persiste
    python manage.py enrich_place --id 5
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Genera un PlaceEnrichmentDraft consultando Perplexity para el lugar indicado."

    def add_arguments(self, parser):
        parser.add_argument("--slug", help="Slug del Place a enriquecer.")
        parser.add_argument("--id", type=int, help="ID del Place (alternativo a --slug).")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Hace la llamada pero NO persiste el draft (solo imprime).",
        )

    def handle(self, *args, **options):
        from destino_puerto_varas.models import Place
        from destino_puerto_varas.services.place_enrichment_service import (
            enrich_place,
            is_enrichment_available,
        )

        slug = options.get("slug")
        place_id = options.get("id")
        dry = options.get("dry_run")

        if not slug and not place_id:
            raise CommandError("Especifica --slug o --id.")

        if slug:
            try:
                place = Place.objects.get(slug=slug)
            except Place.DoesNotExist:
                raise CommandError(f"No existe Place con slug '{slug}'.")
        else:
            try:
                place = Place.objects.get(pk=place_id)
            except Place.DoesNotExist:
                raise CommandError(f"No existe Place con id={place_id}.")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"Enriqueciendo: {place.name}"))
        self.stdout.write(f"  slug: {place.slug}")
        self.stdout.write(f"  tipo: {place.place_type}")
        self.stdout.write(f"  ubicación: {place.location_label}")

        if not is_enrichment_available():
            self.stdout.write(self.style.ERROR(
                "  ✗ Faltan credenciales: necesito PERPLEXITY_API_KEY (search) "
                "y OPENROUTER_API_KEY (synthesis). Aborto."
            ))
            return

        self.stdout.write("")
        self.stdout.write("  [1/2] Buscando en web (Perplexity Search)...")
        self.stdout.write("  [2/2] Sintetizando JSON (OpenRouter Claude)...")
        self.stdout.write("  (puede tardar 15-40s en total)")
        draft = enrich_place(place, save=not dry)

        if not draft:
            self.stdout.write(self.style.ERROR("  ✗ enrich_place retornó None."))
            return

        self.stdout.write("")
        self.stdout.write(f"  status: {draft.status}")
        self.stdout.write(f"  modelo: {draft.llm_model}")
        self.stdout.write(f"  tokens in/out: {draft.llm_input_tokens} / {draft.llm_output_tokens}")
        self.stdout.write(f"  latency: {draft.llm_latency_ms} ms")
        if draft.review_notes:
            self.stdout.write(f"  notas: {draft.review_notes}")

        proposed = draft.proposed_data or {}
        if proposed:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Datos propuestos:"))
            fields = proposed.get("fields") or {}
            for k, v in fields.items():
                self.stdout.write(f"  {k}: {v}")

            extra = proposed.get("extra_data") or {}
            if extra:
                self.stdout.write("")
                self.stdout.write("  extra_data keys:")
                for k in extra:
                    self.stdout.write(f"    · {k}")

            photos = proposed.get("photos") or []
            self.stdout.write("")
            self.stdout.write(f"  photos: {len(photos)}")
            for i, p in enumerate(photos):
                self.stdout.write(f"    [{i}] {p.get('url', '?')[:80]}")

            long_desc = (proposed.get("long_description") or "").strip()
            if long_desc:
                self.stdout.write("")
                self.stdout.write(f"  long_description ({len(long_desc)} chars):")
                preview = long_desc[:300] + ("..." if len(long_desc) > 300 else "")
                self.stdout.write(f"    {preview}")

        if dry:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("  ⚠ --dry-run: NO se persistió el draft."))
        else:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Draft #{draft.id} guardado. Revísalo en admin → "
                "Borradores de enriquecimiento."
            ))
