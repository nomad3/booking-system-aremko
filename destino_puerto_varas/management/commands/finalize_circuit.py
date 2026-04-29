"""Finaliza un Circuit: enriquece sus places + genera/aplica narrativa.

Comando reusable que reemplaza enrich_pending_*.py + generate_narratives_*.py
con uno solo parametrizado por --circuit-number.

Uso:
    # Solo previsualizar
    python manage.py finalize_circuit --circuit-number 1016 --dry-run

    # Generar drafts (sin aplicar)
    python manage.py finalize_circuit --circuit-number 1016

    # Generar + aplicar todo
    python manage.py finalize_circuit --circuit-number 1016 --apply

    # Sólo narrativa (places ya enriquecidos)
    python manage.py finalize_circuit --circuit-number 1016 --apply --skip-places

    # Sólo places (saltar narrativa)
    python manage.py finalize_circuit --circuit-number 1016 --apply --skip-narrative

    # Saltar places que ya tienen draft APPLIED
    python manage.py finalize_circuit --circuit-number 1016 --apply --skip-existing-places
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Enriquece places + genera narrativa de un Circuit en una pasada."

    def add_arguments(self, parser):
        parser.add_argument("--circuit-number", type=int, required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true",
                            help="Aprueba y aplica los drafts generados.")
        parser.add_argument("--skip-existing-places", action="store_true",
                            help="Salta places con draft APPLIED ya.")
        parser.add_argument("--skip-narrative", action="store_true",
                            help="Sólo enriquecer places, no generar narrativa.")
        parser.add_argument("--skip-places", action="store_true",
                            help="Sólo narrativa, no enriquecer places.")

    def handle(self, *args, **options):
        from destino_puerto_varas.models import (
            Circuit,
            CircuitNarrativeDraft,
            Place,
            PlaceEnrichmentDraft,
        )
        from destino_puerto_varas.services.circuit_narrative_service import (
            apply_narrative_draft,
            generate_circuit_narrative,
        )
        from destino_puerto_varas.services.place_enrichment_service import (
            apply_draft,
            enrich_place,
            is_enrichment_available,
        )

        n = options["circuit_number"]
        dry = options["dry_run"]
        do_apply = options["apply"]
        skip_existing_places = options["skip_existing_places"]
        skip_narrative = options["skip_narrative"]
        skip_places = options["skip_places"]

        if dry and do_apply:
            self.stdout.write(self.style.WARNING(
                "(--dry-run + --apply): --apply ignorado"
            ))
            do_apply = False

        circuit = Circuit.objects.filter(number=n).first()
        if not circuit:
            raise CommandError(f"No existe Circuit con número {n}")

        mode = "DRY-RUN" if dry else "APPLY" if do_apply else "DRAFTS-ONLY"
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== finalize_circuit #{n} {circuit.name} [{mode}] ==="
        ))

        if not dry and not is_enrichment_available():
            self.stdout.write(self.style.ERROR(
                "  ✗ Faltan PERPLEXITY_API_KEY u OPENROUTER_API_KEY. Aborto."
            ))
            return

        # Recolectar todos los places del circuit (todos los días, sin duplicados)
        place_ids = set()
        for day in circuit.days.all():
            for cp in day.place_stops.all():
                place_ids.add(cp.place_id)
        places = list(Place.objects.filter(id__in=place_ids).order_by("slug"))

        # ─── Fase 1: Enriquecimiento de Places ───
        e_total, e_done, e_applied, e_skipped, e_failed = len(places), 0, 0, 0, 0
        if not skip_places:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"--- Fase 1: Enriquecer {e_total} places ---"
            ))
            for place in places:
                has_applied = place.enrichment_drafts.filter(
                    status=PlaceEnrichmentDraft.STATUS_APPLIED
                ).exists()
                if skip_existing_places and has_applied:
                    self.stdout.write(f"  · {place.slug}: APPLIED ya, skip")
                    e_skipped += 1
                    continue

                if dry:
                    tag = " (tiene APPLIED)" if has_applied else ""
                    self.stdout.write(f"  [dry-run] enriquecería: {place.slug}{tag}")
                    continue

                self.stdout.write(f"  → {place.slug}")
                try:
                    draft = enrich_place(place, save=True)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"    ✗ enrich falló: {e}"))
                    e_failed += 1
                    continue
                if not draft:
                    self.stdout.write(self.style.ERROR(
                        "    ✗ enrich_place retornó None"
                    ))
                    e_failed += 1
                    continue
                self.stdout.write(self.style.SUCCESS(
                    f"    ✓ Draft #{draft.id} status={draft.status} "
                    f"({draft.llm_input_tokens}/{draft.llm_output_tokens} tk, "
                    f"{draft.llm_latency_ms}ms)"
                ))
                e_done += 1

                if do_apply:
                    if draft.status != PlaceEnrichmentDraft.STATUS_APPROVED:
                        draft.status = PlaceEnrichmentDraft.STATUS_APPROVED
                        draft.save(update_fields=["status"])
                    ok = apply_draft(draft, reviewer="finalize_circuit")
                    if ok:
                        self.stdout.write(self.style.SUCCESS(
                            "    ✓ Draft aplicado al Place"
                        ))
                        e_applied += 1
                    else:
                        self.stdout.write(self.style.ERROR(
                            "    ✗ apply_draft retornó False"
                        ))
                        e_failed += 1

        # ─── Fase 2: Narrativa del Circuit ───
        n_done, n_applied, n_failed = 0, 0, 0
        if not skip_narrative:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(
                "--- Fase 2: Narrativa del Circuit ---"
            ))
            existing_len = len(circuit.long_description or "")
            self.stdout.write(f"  long_description actual: {existing_len} chars")

            if dry:
                self.stdout.write("  [dry-run] generaría narrativa")
            else:
                try:
                    draft = generate_circuit_narrative(circuit, save=True)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"  ✗ generate_circuit_narrative falló: {e}"
                    ))
                    n_failed += 1
                else:
                    if not draft:
                        self.stdout.write(self.style.ERROR(
                            "  ✗ generate retornó None"
                        ))
                        n_failed += 1
                    else:
                        proposed = (draft.proposed_data or {}).get(
                            "circuit_long_description"
                        ) or ""
                        self.stdout.write(self.style.SUCCESS(
                            f"  ✓ Draft #{draft.id} status={draft.status} "
                            f"modelo={draft.llm_model} "
                            f"({draft.llm_input_tokens}/{draft.llm_output_tokens} tk)"
                        ))
                        self.stdout.write(
                            f"  long propuesto: {len(proposed)} chars"
                        )
                        if proposed:
                            preview = proposed[:200] + (
                                "..." if len(proposed) > 200 else ""
                            )
                            self.stdout.write(f"    {preview}")
                        n_done += 1

                        if do_apply and draft.id:
                            if draft.status != CircuitNarrativeDraft.STATUS_APPROVED:
                                draft.status = CircuitNarrativeDraft.STATUS_APPROVED
                                draft.save(update_fields=["status"])
                            ok = apply_narrative_draft(
                                draft, reviewer="finalize_circuit"
                            )
                            if ok:
                                self.stdout.write(self.style.SUCCESS(
                                    "  ✓ Narrativa aplicada al Circuit"
                                ))
                                n_applied += 1
                            else:
                                self.stdout.write(self.style.ERROR(
                                    "  ✗ apply_narrative_draft retornó False"
                                ))
                                n_failed += 1

        # ─── Resumen ───
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("=== Resumen ==="))
        self.stdout.write(
            f"  Places ({e_total}): enriquecidos={e_done}, "
            f"aplicados={e_applied}, skipped={e_skipped}, fallidos={e_failed}"
        )
        self.stdout.write(
            f"  Narrativa: generada={n_done}, aplicada={n_applied}, "
            f"fallida={n_failed}"
        )
