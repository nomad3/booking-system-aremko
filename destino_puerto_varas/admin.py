import json
import logging

from django.contrib import admin, messages
from django import forms
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    AgentPromptTemplate,
    AremkoRecommendation,
    Circuit,
    CircuitDay,
    CircuitNarrativeDraft,
    CircuitPlace,
    ConversationMessage,
    DurationCase,
    LeadConversation,
    Place,
    PlaceEnrichmentDraft,
    PlacePhoto,
    RecommendationRule,
    TravelTip,
)

logger = logging.getLogger(__name__)


class CircuitPlaceInline(admin.TabularInline):
    model = CircuitPlace
    extra = 0
    autocomplete_fields = ("place",)
    fields = ("place", "visit_order", "is_main_stop")


class CircuitDayInline(admin.StackedInline):
    model = CircuitDay
    extra = 0
    fields = ("day_number", "title", "block_type", "summary", "sort_order")
    ordering = ("day_number", "sort_order")


class ConversationMessageInline(admin.TabularInline):
    model = ConversationMessage
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("sender_type", "text", "metadata", "created_at")


@admin.register(DurationCase)
class DurationCaseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "duration_type", "days", "nights", "is_active", "sort_order")
    list_filter = ("duration_type", "is_active")
    search_fields = ("code", "name")
    ordering = ("sort_order", "days")


@admin.register(Circuit)
class CircuitAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "name",
        "duration_case",
        "primary_interest",
        "recommended_profile",
        "narrative_status",
        "published",
        "featured",
    )
    list_filter = (
        "published",
        "featured",
        "primary_interest",
        "recommended_profile",
        "is_romantic",
        "is_family_friendly",
        "is_adventure",
        "is_rain_friendly",
        "is_premium",
        "duration_case",
    )
    search_fields = ("number", "name", "slug", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CircuitDayInline]
    ordering = ("sort_order", "number")
    readonly_fields = (
        "places_signature",
        "last_narrative_at",
        "narrative_status_display",
        "created_at",
        "updated_at",
    )
    actions = ["accion_generar_narrativa"]

    def narrative_status(self, obj):
        if not obj.last_narrative_at:
            return format_html('<span style="color:#888;">— sin narrativa —</span>')
        if obj.is_narrative_stale():
            return format_html('<span style="color:#c00;">⚠ stale (paradas cambiaron)</span>')
        return format_html('<span style="color:#080;">✓ vigente</span>')
    narrative_status.short_description = "Narrativa IA"

    def narrative_status_display(self, obj):
        if not obj.pk:
            return "—"
        return self.narrative_status(obj)
    narrative_status_display.short_description = "Estado narrativa"

    @admin.action(description="📝 Generar narrativa con IA (genera borrador)")
    def accion_generar_narrativa(self, request, queryset):
        from .services.circuit_narrative_service import generate_circuit_narrative
        from django.conf import settings

        if not getattr(settings, "OPENROUTER_API_KEY", ""):
            self.message_user(
                request,
                "OPENROUTER_API_KEY no configurada en Render.",
                level=messages.ERROR,
            )
            return

        ok, fail = 0, 0
        for circuit in queryset:
            try:
                draft = generate_circuit_narrative(circuit)
                if draft and draft.status == CircuitNarrativeDraft.STATUS_DRAFT:
                    ok += 1
                else:
                    fail += 1
            except Exception:
                logger.exception("Error generando narrativa circuit_id=%s", circuit.id)
                fail += 1

        if ok:
            self.message_user(
                request,
                f"✓ {ok} borrador(es) de narrativa generado(s). Revísalos en "
                "'Borradores de narrativa'.",
                level=messages.SUCCESS,
            )
        if fail:
            self.message_user(
                request,
                f"✗ {fail} circuito(s) fallaron.",
                level=messages.WARNING,
            )


@admin.register(CircuitDay)
class CircuitDayAdmin(admin.ModelAdmin):
    list_display = ("circuit", "day_number", "title", "block_type", "sort_order")
    list_filter = ("block_type", "circuit")
    search_fields = ("title", "circuit__name")
    inlines = [CircuitPlaceInline]
    ordering = ("circuit", "day_number", "sort_order")


class PlacePhotoInline(admin.TabularInline):
    model = PlacePhoto
    extra = 0
    fields = ("preview", "is_primary", "order", "image", "source_url", "caption", "credit")
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 80px;" />', obj.image.url)
        if obj.source_url:
            return format_html('<img src="{}" style="max-height: 80px;" />', obj.source_url)
        return "—"
    preview.short_description = "Vista previa"


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "place_type",
        "location_label",
        "elevation_m",
        "entry_fee_clp",
        "last_enriched_at",
        "published",
    )
    list_filter = (
        "place_type",
        "published",
        "is_rain_friendly",
        "is_romantic",
        "is_family_friendly",
        "is_adventure_related",
        "has_parking",
        "has_restrooms",
        "has_conaf_office",
    )
    search_fields = ("name", "slug", "location_label", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    readonly_fields = ("last_enriched_at", "created_at", "updated_at", "drafts_link")
    inlines = [PlacePhotoInline]
    actions = ["accion_enriquecer_con_ia"]
    fieldsets = (
        ("Identidad", {
            "fields": ("name", "slug", "place_type", "location_label", "published"),
        }),
        ("Ubicación", {
            "fields": ("latitude", "longitude", "distance_from_pv_km", "drive_time_from_pv_min"),
        }),
        ("Descripción editorial", {
            "fields": ("short_description", "long_description"),
        }),
        ("Datos estructurados (enriquecibles por IA)", {
            "fields": (
                ("elevation_m", "year_established"),
                ("has_parking", "has_restrooms", "has_conaf_office", "has_food_service"),
                ("entry_fee_clp", "best_season"),
                "accessibility_notes",
            ),
            "description": (
                "Estos campos los puede llenar la IA. Para hacerlo: selecciona el lugar "
                "en la lista y aplica la acción 'Enriquecer con IA'. Genera un borrador "
                "para revisar antes de publicar."
            ),
        }),
        ("Información extra (JSON libre)", {
            "fields": ("extra_data",),
            "classes": ("collapse",),
            "description": "Estructura libre — fauna, flora, datos curiosos, etc.",
        }),
        ("Etiquetas / filtros", {
            "fields": (
                ("is_rain_friendly", "is_romantic", "is_family_friendly", "is_adventure_related"),
            ),
        }),
        ("Tips editoriales", {
            "fields": ("practical_tips", "safety_notes", "did_you_know", "nobody_tells_you"),
            "classes": ("collapse",),
        }),
        ("Auditoría", {
            "fields": ("last_enriched_at", "drafts_link", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def drafts_link(self, obj):
        if not obj.pk:
            return "—"
        url = (
            reverse("admin:destino_puerto_varas_placeenrichmentdraft_changelist")
            + f"?place__id__exact={obj.pk}"
        )
        count = obj.enrichment_drafts.count()
        return format_html('<a href="{}">Ver borradores IA ({})</a>', url, count)
    drafts_link.short_description = "Borradores de IA"

    @admin.action(description="🤖 Enriquecer con IA (genera borrador para revisar)")
    def accion_enriquecer_con_ia(self, request, queryset):
        from .services.place_enrichment_service import enrich_place, is_enrichment_available

        if not is_enrichment_available():
            self.message_user(
                request,
                "PERPLEXITY_API_KEY no está configurada. Setéala en Render Dashboard.",
                level=messages.ERROR,
            )
            return

        ok, fail = 0, 0
        for place in queryset:
            try:
                draft = enrich_place(place)
                if draft and draft.status == PlaceEnrichmentDraft.STATUS_DRAFT:
                    ok += 1
                else:
                    fail += 1
            except Exception:
                logger.exception("Error enriqueciendo place_id=%s", place.id)
                fail += 1

        if ok:
            self.message_user(
                request,
                f"✓ {ok} borrador(es) generado(s). Revísalos en 'Borradores de enriquecimiento'.",
                level=messages.SUCCESS,
            )
        if fail:
            self.message_user(
                request,
                f"✗ {fail} lugar(es) fallaron. Revisa logs.",
                level=messages.WARNING,
            )


@admin.register(CircuitPlace)
class CircuitPlaceAdmin(admin.ModelAdmin):
    list_display = ("circuit_day", "place", "visit_order", "is_main_stop")
    list_filter = ("is_main_stop",)
    search_fields = ("place__name", "circuit_day__title", "circuit_day__circuit__name")
    autocomplete_fields = ("circuit_day", "place")
    ordering = ("circuit_day", "visit_order")


@admin.register(AremkoRecommendation)
class AremkoRecommendationAdmin(admin.ModelAdmin):
    list_display = ("context_key", "name", "title", "recommended_service_type", "priority", "is_active")
    list_filter = ("is_active",)
    search_fields = ("context_key", "name", "title", "recommended_service_type")
    ordering = ("priority", "name")


@admin.register(TravelTip)
class TravelTipAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "interest",
        "profile",
        "duration_case",
        "applies_when_raining",
        "applies_when_sunny",
        "sort_order",
        "is_active",
    )
    list_filter = (
        "is_active",
        "interest",
        "profile",
        "applies_when_raining",
        "applies_when_sunny",
        "duration_case",
    )
    search_fields = ("title", "tip_text")
    ordering = ("sort_order", "title")


@admin.register(RecommendationRule)
class RecommendationRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "duration_case",
        "interest",
        "profile",
        "is_rainy",
        "recommended_circuit",
        "priority",
        "is_active",
    )
    list_filter = ("is_active", "duration_case", "interest", "profile", "is_rainy")
    search_fields = ("name", "recommended_circuit__name")
    autocomplete_fields = ("duration_case", "recommended_circuit")
    ordering = ("priority", "name")


@admin.register(LeadConversation)
class LeadConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "channel",
        "contact_name",
        "contact_phone",
        "status",
        "detected_interest",
        "detected_profile",
        "referred_to_aremko",
        "created_at",
    )
    list_filter = (
        "channel",
        "status",
        "detected_interest",
        "detected_profile",
        "referred_to_aremko",
    )
    search_fields = (
        "contact_name",
        "contact_phone",
        "contact_email",
        "external_id",
        "notes",
    )
    autocomplete_fields = ("detected_duration_case", "recommended_circuit")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ConversationMessageInline]
    ordering = ("-created_at",)


@admin.register(ConversationMessage)
class ConversationMessageAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "conversation",
        "sender_type",
        "message_preview",
        "llm_model",
        "llm_input_tokens",
        "llm_output_tokens",
        "llm_cost_usd",
        "llm_latency_ms",
    )
    list_filter = ("sender_type", "llm_model")
    search_fields = ("text", "conversation__contact_name", "conversation__contact_phone")
    readonly_fields = (
        "created_at",
        "conversation",
        "llm_model",
        "llm_input_tokens",
        "llm_output_tokens",
        "llm_cost_usd",
        "llm_latency_ms",
        "llm_error",
    )
    ordering = ("-created_at",)

    def message_preview(self, obj):
        t = obj.text or ""
        return (t[:80] + "…") if len(t) > 80 else t
    message_preview.short_description = "Mensaje (preview)"


class AgentPromptTemplateForm(forms.ModelForm):
    class Meta:
        model = AgentPromptTemplate
        fields = "__all__"
        widgets = {
            "system_prompt": forms.Textarea(attrs={"rows": 28, "cols": 100, "style": "font-family: monospace;"}),
            "notes": forms.Textarea(attrs={"rows": 4, "cols": 100}),
        }


class PlaceEnrichmentDraftForm(forms.ModelForm):
    class Meta:
        model = PlaceEnrichmentDraft
        fields = "__all__"
        widgets = {
            "review_notes": forms.Textarea(attrs={"rows": 4, "cols": 100}),
        }


@admin.register(PlaceEnrichmentDraft)
class PlaceEnrichmentDraftAdmin(admin.ModelAdmin):
    form = PlaceEnrichmentDraftForm
    list_display = (
        "place",
        "status",
        "search_provider",
        "llm_model",
        "created_at",
        "reviewed_at",
        "applied_at",
    )
    list_filter = ("status", "search_provider", "llm_model")
    search_fields = ("place__name", "place__slug", "review_notes")
    readonly_fields = (
        "place",
        "search_provider",
        "llm_model",
        "llm_input_tokens",
        "llm_output_tokens",
        "llm_latency_ms",
        "raw_search_response",
        "created_at",
        "updated_at",
        "applied_at",
        "reviewed_at",
        "proposed_data_pretty",
    )
    ordering = ("-created_at",)
    actions = ["accion_aprobar", "accion_rechazar", "accion_aplicar_aprobados"]
    fieldsets = (
        ("Lugar", {"fields": ("place", "status")}),
        (
            "Datos propuestos por la IA (revísalos)",
            {
                "fields": ("proposed_data_pretty", "proposed_data"),
                "description": (
                    "El bloque 'pretty' es solo lectura (formateado). El bloque 'proposed_data' "
                    "es editable: corrige aquí lo que quieras antes de aprobar."
                ),
            },
        ),
        (
            "Revisión humana",
            {
                "fields": ("review_notes", "reviewed_by", "reviewed_at", "applied_at"),
                "description": (
                    "Reviewer: setéalo manualmente o usa la acción 'Aplicar aprobados'. "
                    "Una vez aplicado, los campos se vuelcan al Place."
                ),
            },
        ),
        (
            "Auditoría",
            {
                "fields": (
                    "search_provider",
                    "llm_model",
                    "llm_input_tokens",
                    "llm_output_tokens",
                    "llm_latency_ms",
                    "raw_search_response",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def proposed_data_pretty(self, obj):
        if not obj.proposed_data:
            return "—"
        try:
            return format_html(
                "<pre style='font-family: monospace; font-size: 12px; "
                "background:#f5f5f5; padding:10px; border-radius:4px; "
                "max-height:500px; overflow:auto;'>{}</pre>",
                json.dumps(obj.proposed_data, indent=2, ensure_ascii=False),
            )
        except (TypeError, ValueError):
            return str(obj.proposed_data)
    proposed_data_pretty.short_description = "Vista formateada"

    @admin.action(description="✓ Aprobar (sin aplicar todavía)")
    def accion_aprobar(self, request, queryset):
        from django.utils import timezone

        ok = 0
        for draft in queryset.filter(status=PlaceEnrichmentDraft.STATUS_DRAFT):
            draft.status = PlaceEnrichmentDraft.STATUS_APPROVED
            draft.reviewed_by = request.user.username
            draft.reviewed_at = timezone.now()
            draft.save()
            ok += 1
        self.message_user(
            request,
            f"{ok} borrador(es) aprobado(s). Aplícalos con la acción 'Aplicar aprobados'.",
            level=messages.SUCCESS,
        )

    @admin.action(description="✗ Rechazar")
    def accion_rechazar(self, request, queryset):
        from django.utils import timezone

        n = queryset.filter(status=PlaceEnrichmentDraft.STATUS_DRAFT).update(
            status=PlaceEnrichmentDraft.STATUS_REJECTED,
            reviewed_by=request.user.username,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{n} borrador(es) rechazado(s).", level=messages.SUCCESS)

    @admin.action(description="🚀 Aplicar borradores aprobados al Place")
    def accion_aplicar_aprobados(self, request, queryset):
        from .services.place_enrichment_service import apply_draft

        ok, fail = 0, 0
        for draft in queryset.filter(status=PlaceEnrichmentDraft.STATUS_APPROVED):
            try:
                if apply_draft(draft, reviewer=request.user.username):
                    ok += 1
                else:
                    fail += 1
            except Exception:
                logger.exception("Error aplicando draft #%s", draft.id)
                fail += 1
        if ok:
            self.message_user(
                request,
                f"✓ {ok} borrador(es) aplicado(s). Los Places se actualizaron y se "
                "crearon PlacePhotos.",
                level=messages.SUCCESS,
            )
        if fail:
            self.message_user(
                request,
                f"✗ {fail} borrador(es) fallaron al aplicar.",
                level=messages.WARNING,
            )


class CircuitNarrativeDraftForm(forms.ModelForm):
    class Meta:
        model = CircuitNarrativeDraft
        fields = "__all__"
        widgets = {
            "review_notes": forms.Textarea(attrs={"rows": 4, "cols": 100}),
        }


@admin.register(CircuitNarrativeDraft)
class CircuitNarrativeDraftAdmin(admin.ModelAdmin):
    form = CircuitNarrativeDraftForm
    list_display = (
        "circuit",
        "status",
        "stale_indicator",
        "llm_model",
        "created_at",
        "applied_at",
    )
    list_filter = ("status", "llm_model")
    search_fields = ("circuit__name", "circuit__slug", "review_notes")
    readonly_fields = (
        "circuit",
        "places_signature",
        "stale_indicator",
        "llm_model",
        "llm_input_tokens",
        "llm_output_tokens",
        "llm_latency_ms",
        "created_at",
        "updated_at",
        "applied_at",
        "reviewed_at",
        "proposed_data_pretty",
    )
    ordering = ("-created_at",)
    actions = [
        "accion_aprobar_narrativa",
        "accion_rechazar_narrativa",
        "accion_aplicar_narrativas_aprobadas",
    ]
    fieldsets = (
        ("Circuito", {"fields": ("circuit", "status", "stale_indicator")}),
        (
            "Narrativa propuesta (revísala)",
            {
                "fields": ("proposed_data_pretty", "proposed_data"),
                "description": (
                    "El bloque 'pretty' es solo lectura (formateado). El bloque "
                    "'proposed_data' es editable: corrige el texto antes de aprobar."
                ),
            },
        ),
        (
            "Revisión humana",
            {
                "fields": ("review_notes", "reviewed_by", "reviewed_at", "applied_at"),
            },
        ),
        (
            "Auditoría",
            {
                "fields": (
                    "places_signature",
                    "llm_model",
                    "llm_input_tokens",
                    "llm_output_tokens",
                    "llm_latency_ms",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def proposed_data_pretty(self, obj):
        if not obj.proposed_data:
            return "—"
        try:
            return format_html(
                "<pre style='font-family: monospace; font-size: 12px; "
                "background:#f5f5f5; padding:10px; border-radius:4px; "
                "max-height:600px; overflow:auto; white-space:pre-wrap;'>{}</pre>",
                json.dumps(obj.proposed_data, indent=2, ensure_ascii=False),
            )
        except (TypeError, ValueError):
            return str(obj.proposed_data)
    proposed_data_pretty.short_description = "Vista formateada"

    def stale_indicator(self, obj):
        if not obj.places_signature:
            return "—"
        current = obj.circuit.compute_places_signature()
        if current == obj.places_signature:
            return format_html('<span style="color:#080;">✓ paradas no han cambiado</span>')
        return format_html(
            '<span style="color:#c00;">⚠ las paradas del circuito cambiaron desde '
            'que se generó este draft — la narrativa puede estar desfasada</span>'
        )
    stale_indicator.short_description = "Vigencia respecto a paradas"

    @admin.action(description="✓ Aprobar narrativa")
    def accion_aprobar_narrativa(self, request, queryset):
        from django.utils import timezone
        n = 0
        for d in queryset.filter(status=CircuitNarrativeDraft.STATUS_DRAFT):
            d.status = CircuitNarrativeDraft.STATUS_APPROVED
            d.reviewed_by = request.user.username
            d.reviewed_at = timezone.now()
            d.save()
            n += 1
        self.message_user(request, f"{n} narrativa(s) aprobada(s).", level=messages.SUCCESS)

    @admin.action(description="✗ Rechazar narrativa")
    def accion_rechazar_narrativa(self, request, queryset):
        from django.utils import timezone
        n = queryset.filter(status=CircuitNarrativeDraft.STATUS_DRAFT).update(
            status=CircuitNarrativeDraft.STATUS_REJECTED,
            reviewed_by=request.user.username,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{n} narrativa(s) rechazada(s).", level=messages.SUCCESS)

    @admin.action(description="🚀 Aplicar narrativas aprobadas al Circuit")
    def accion_aplicar_narrativas_aprobadas(self, request, queryset):
        from .services.circuit_narrative_service import apply_narrative_draft

        ok, fail = 0, 0
        for draft in queryset.filter(status=CircuitNarrativeDraft.STATUS_APPROVED):
            try:
                if apply_narrative_draft(draft, reviewer=request.user.username):
                    ok += 1
                else:
                    fail += 1
            except Exception:
                logger.exception("Error aplicando narrativa #%s", draft.id)
                fail += 1
        if ok:
            self.message_user(
                request,
                f"✓ {ok} narrativa(s) aplicada(s) a sus circuitos.",
                level=messages.SUCCESS,
            )
        if fail:
            self.message_user(
                request,
                f"✗ {fail} narrativa(s) fallaron.",
                level=messages.WARNING,
            )


@admin.register(PlacePhoto)
class PlacePhotoAdmin(admin.ModelAdmin):
    list_display = ("place", "is_primary", "order", "caption", "credit", "created_at")
    list_filter = ("is_primary",)
    search_fields = ("place__name", "caption", "credit", "source_url")
    autocomplete_fields = ("place",)
    ordering = ("place", "order", "id")


@admin.register(AgentPromptTemplate)
class AgentPromptTemplateAdmin(admin.ModelAdmin):
    form = AgentPromptTemplateForm
    list_display = ("slug", "name", "is_active", "model_name", "temperature", "max_output_tokens", "history_window", "updated_at")
    list_filter = ("is_active", "model_name")
    search_fields = ("slug", "name", "system_prompt")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Identidad", {
            "fields": ("slug", "name", "is_active"),
            "description": (
                "El agente busca el template con slug 'dpv-main-guide' y is_active=True. "
                "Cambiar el slug desvincula el template del agente."
            ),
        }),
        ("Prompt de sistema", {
            "fields": ("system_prompt",),
            "description": "Este texto se envía como 'system' al LLM en cada turno de conversación.",
        }),
        ("Parámetros del LLM", {
            "fields": ("model_name", "temperature", "max_output_tokens"),
        }),
        ("Contexto conversacional", {
            "fields": ("history_window",),
            "description": "Cuántos mensajes anteriores enviar como contexto. Más mensajes = más coherencia pero más costo.",
        }),
        ("Auditoría", {
            "fields": ("notes", "created_at", "updated_at"),
        }),
    )
