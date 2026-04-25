import json
import logging

from django.contrib import admin, messages
from django import forms
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.text import slugify

from .enums import InterestType, PartnershipLevel, PlaceType, ProfileType
from .models import (
    AgentPromptTemplate,
    AremkoRecommendation,
    Circuit,
    CircuitCompositionDraft,
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


def render_draft_mobile_preview(draft):
    """Renderiza el preview móvil (chat bubble + datos) del borrador IA.

    Reutilizable por PlaceAdmin (panel inline) y PlaceEnrichmentDraftAdmin.
    Retorna SafeString.
    """
    if not draft or not draft.proposed_data:
        return format_html(
            "<div style='color:#999;font-style:italic;'>Sin datos para previsualizar.</div>"
        )

    place = draft.place
    data = draft.proposed_data or {}
    fields = data.get("fields") or {}
    long_desc = (data.get("long_description") or "").strip()
    extra = data.get("extra_data") or {}
    photos = data.get("photos") or []

    type_icons = {
        "ATTRACTION": "📍", "RESTAURANT": "🍴", "ACTIVITY": "🚣",
        "VIEWPOINT": "🔭", "CAFE": "☕", "SHOP": "🛍",
        "PARK": "🌲", "MUSEUM": "🏛", "LODGING": "🛏",
        "SPA": "🧖", "TOUR_OPERATOR": "🚐", "BUSINESS": "🏢",
        "THEATER": "🎭", "CHURCH": "⛪", "CULTURAL_CENTER": "🏛",
        "OTHER": "📍",
    }
    icon = type_icons.get(place.place_type, "📍")

    header_html = format_html(
        '<div style="font-size:15px;font-weight:600;color:#1a1a1a;margin-bottom:2px;">{} {}</div>',
        icon, place.name,
    )
    loc_label = place.location_label or place.get_place_type_display()
    sub_html = format_html(
        '<div style="font-size:12px;color:#777;margin-bottom:10px;">{}</div>',
        loc_label,
    )

    photo_html = ""
    if photos and isinstance(photos, list):
        url = (photos[0].get("url") or "").strip() if isinstance(photos[0], dict) else ""
        if url:
            photo_html = format_html(
                '<div style="margin:8px 0 10px 0;border-radius:10px;overflow:hidden;">'
                '<img src="{}" alt="" style="width:100%;display:block;max-height:220px;object-fit:cover;"/></div>',
                url,
            )

    desc_html = ""
    if long_desc:
        preview = long_desc if len(long_desc) <= 280 else long_desc[:280].rsplit(" ", 1)[0] + "…"
        desc_html = format_html(
            '<div style="font-size:14px;line-height:1.5;color:#2a2a2a;margin-bottom:10px;">{}</div>',
            preview,
        )

    rows = []
    if fields.get("elevation_m"):
        rows.append(("⛰", f"{fields['elevation_m']:,} m de altura".replace(",", ".")))
    if fields.get("distance_from_pv_km"):
        km = fields["distance_from_pv_km"]
        extra_dist = f" · {fields['drive_time_from_pv_min']} min en auto" if fields.get("drive_time_from_pv_min") else ""
        rows.append(("📍", f"{km} km de Puerto Varas{extra_dist}"))
    if fields.get("year_established"):
        rows.append(("📅", f"Establecido en {fields['year_established']}"))
    if fields.get("entry_fee_clp") is not None:
        fee = "Entrada gratuita" if fields["entry_fee_clp"] == 0 else f"Entrada: ${fields['entry_fee_clp']:,} CLP".replace(",", ".")
        rows.append(("🎟", fee))
    if fields.get("best_season"):
        rows.append(("🌤", str(fields["best_season"])))
    if fields.get("phone"):
        rows.append(("📞", str(fields["phone"])))
    if fields.get("website"):
        rows.append(("🌐", str(fields["website"])[:80]))
    if fields.get("price_range"):
        rows.append(("💰", str(fields["price_range"])))

    infra = []
    if fields.get("has_parking"): infra.append("🅿 Estacionamiento")
    if fields.get("has_restrooms"): infra.append("🚻 Baños")
    if fields.get("has_conaf_office"): infra.append("🏠 CONAF")
    if fields.get("has_food_service"): infra.append("🍴 Comida")
    if infra:
        rows.append(("✓", " · ".join(infra)))

    if fields.get("accessibility_notes"):
        rows.append(("♿", str(fields["accessibility_notes"])[:120]))

    rows_html = format_html_join(
        "",
        '<div style="font-size:13px;line-height:1.5;color:#3a3a3a;margin:3px 0;">'
        '<span style="display:inline-block;width:22px;">{}</span>{}</div>',
        rows,
    )

    curioso_html = ""
    for k in ("datos_curiosos", "historia", "dato_curioso"):
        v = extra.get(k)
        if v:
            txt = v if isinstance(v, str) else (v[0] if isinstance(v, list) and v else "")
            if txt:
                txt_short = txt[:200] + ("…" if len(txt) > 200 else "")
                curioso_html = format_html(
                    '<div style="margin-top:10px;padding:8px 10px;background:#fff8e1;border-left:3px solid #f5b800;border-radius:6px;font-size:12px;color:#5a4500;">'
                    '<strong>💡 ¿Sabías que…?</strong><br>{}</div>',
                    txt_short,
                )
                break

    return format_html(
        '<div style="display:flex;align-items:flex-start;gap:20px;flex-wrap:wrap;">'
        '<div style="width:360px;background:#e5ded8;border:1px solid #c8c0b8;border-radius:24px;padding:14px 10px;'
        'box-shadow:0 6px 20px rgba(0,0,0,.12);font-family:-apple-system,BlinkMacSystemFont,\\"Segoe UI\\",sans-serif;">'
        '<div style="display:flex;justify-content:space-between;font-size:11px;color:#555;padding:0 12px 8px 12px;">'
        '<span>9:41</span><span>📶 ⚡ 87%</span></div>'
        '<div style="display:flex;align-items:center;gap:8px;padding:6px 8px;background:#075e54;color:#fff;border-radius:8px 8px 0 0;">'
        '<div style="width:32px;height:32px;border-radius:50%;background:#0e8e7e;display:flex;align-items:center;justify-content:center;font-size:16px;">🌋</div>'
        '<div><div style="font-size:13px;font-weight:600;">Destino Puerto Varas</div>'
        '<div style="font-size:10px;opacity:.85;">en línea</div></div></div>'
        '<div style="background:#fff;padding:12px 14px;border-radius:0 0 8px 8px 12px 12px 12px 4px;'
        'max-width:100%;box-shadow:0 1px 1px rgba(0,0,0,.05);">'
        '{}{}{}{}{}{}'
        '<div style="font-size:10px;color:#999;text-align:right;margin-top:6px;">9:42 ✓✓</div>'
        '</div></div>'
        '<div style="flex:1;min-width:280px;font-size:12px;color:#666;line-height:1.6;">'
        '<strong>Nota:</strong> esto es una simulación. El bot real puede reformular el texto '
        'según la pregunta del turista.'
        '<br><br><strong>Fotos:</strong> {} foto(s) propuesta(s).'
        '<br><strong>Extra data:</strong> {} clave(s) temática(s).'
        '<br><strong>Long description:</strong> {} caracteres.'
        '</div></div>',
        header_html, sub_html, photo_html, desc_html, rows_html, curioso_html,
        len(photos) if isinstance(photos, list) else 0,
        len(extra) if isinstance(extra, dict) else 0,
        len(long_desc),
    )


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


class CircuitManualCreateForm(forms.Form):
    """Form de creación manual de Circuit.

    El usuario elige las paradas en orden (sortable JS). La IA NO selecciona
    paradas — solo propone 3 nombres alternativos + narrativa + flags.
    El usuario elige el nombre en un segundo paso.
    """

    duration_case = forms.ModelChoiceField(
        label="Duración",
        queryset=DurationCase.objects.filter(is_active=True).order_by("sort_order", "days"),
        required=True,
        help_text="Define cuántos días tendrá el circuito.",
    )
    primary_interest = forms.ChoiceField(
        label="Interés primario",
        choices=InterestType.choices,
        required=True,
        help_text="El tema principal del circuito.",
    )
    recommended_profile = forms.ChoiceField(
        label="Perfil recomendado",
        choices=[("", "(no aplica)")] + list(ProfileType.choices),
        required=False,
    )
    places_ordered = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        help_text="IDs de Places en orden separados por coma (controlado por JS sortable).",
    )

    def clean_places_ordered(self):
        raw = (self.cleaned_data.get("places_ordered") or "").strip()
        if not raw:
            raise forms.ValidationError("Debes agregar al menos 1 parada.")
        try:
            ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            raise forms.ValidationError("Formato de paradas inválido.")
        if not ids:
            raise forms.ValidationError("Debes agregar al menos 1 parada.")

        # Validar que TODOS estén publicados
        valid = set(
            Place.objects.filter(id__in=ids, published=True).values_list("id", flat=True)
        )
        invalid = [pid for pid in ids if pid not in valid]
        if invalid:
            raise forms.ValidationError(
                f"Estos Places no existen o no están publicados: {invalid}. "
                "Las paradas de un circuito deben ser Places publicados."
            )
        return ids


class CircuitQuickCreateForm(forms.Form):
    """Form de quick-create de Circuit con IA.

    El usuario describe la idea libre + parámetros básicos, y el composer arma
    un borrador con paradas seleccionadas del catálogo de Places publicados.
    """

    user_idea = forms.CharField(
        label="Idea del circuito",
        widget=forms.Textarea(attrs={
            "rows": 4,
            "cols": 70,
            "placeholder": (
                "Ejemplo: Circuito romántico de un día con tinas calientes, "
                "vistas al lago y un buen restaurante para almorzar."
            ),
        }),
        help_text=(
            "Describe en lenguaje natural qué tipo de circuito quieres. "
            "Mientras más específico, mejor (incluye intereses, ánimo, restricciones)."
        ),
    )
    duration_case = forms.ModelChoiceField(
        label="Duración",
        queryset=DurationCase.objects.filter(is_active=True).order_by("sort_order", "days"),
        required=True,
        help_text="La IA respetará exactamente esta duración.",
    )
    primary_interest = forms.ChoiceField(
        label="Interés primario",
        choices=[("", "(la IA decide)")] + list(InterestType.choices),
        required=False,
        help_text="Si lo dejas vacío, la IA inferirá del texto de la idea.",
    )
    recommended_profile = forms.ChoiceField(
        label="Perfil recomendado",
        choices=[("", "(la IA decide)")] + list(ProfileType.choices),
        required=False,
    )
    anchor_places = forms.ModelMultipleChoiceField(
        label="Lugares ancla (opcional)",
        queryset=Place.objects.filter(published=True).order_by("name"),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple(verbose_name="Places", is_stacked=False),
        help_text=(
            "Lugares que DEBEN aparecer en el circuito. Solo se muestran Places "
            "publicados (las paradas de un circuito tienen que existir y estar publicadas)."
        ),
    )


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
        "paradas_panel",
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

    def paradas_panel(self, obj):
        """Muestra TODAS las paradas en orden real (día → visit_order) + botón editar."""
        if not obj.pk:
            return format_html(
                '<em style="color:#888;">Guarda el circuito primero para ver y editar paradas.</em>'
            )

        rows = []
        global_idx = 0
        for day in obj.days.order_by("day_number", "sort_order").prefetch_related(
            "place_stops__place"
        ):
            for stop in day.place_stops.order_by("visit_order"):
                global_idx += 1
                main_badge = (
                    ' <span style="background:#fff3cd;color:#856404;padding:1px 6px;'
                    'border-radius:3px;font-size:11px;">⭐ main</span>'
                    if stop.is_main_stop
                    else ""
                )
                rows.append(
                    format_html(
                        '<tr>'
                        '<td style="padding:6px 10px;color:#0c4b78;font-weight:600;width:34px;">{}.</td>'
                        '<td style="padding:6px 10px;">{}{}</td>'
                        '<td style="padding:6px 10px;color:#666;font-size:12px;white-space:nowrap;">'
                        'Día {} · #{}</td>'
                        '</tr>',
                        global_idx,
                        stop.place.name,
                        format_html(main_badge) if main_badge else "",
                        day.day_number,
                        stop.visit_order,
                    )
                )

        if not rows:
            table_html = format_html(
                '<div style="padding:14px;background:#fff8e1;border:1px dashed #f5b800;'
                'border-radius:4px;color:#856404;">'
                'Este circuito no tiene paradas. Click en "✏️ Editar paradas" para agregar.'
                '</div>'
            )
        else:
            table_html = format_html(
                '<table style="border-collapse:collapse;background:#fff;border:1px solid #ddd;'
                'border-radius:4px;width:100%;max-width:680px;">{}</table>',
                format_html("".join(rows)),
            )

        edit_url = reverse("admin:dpv_circuit_edit_places", args=[obj.pk])
        button_html = format_html(
            '<div style="margin-top:10px;">'
            '<a href="{}" class="button" '
            'style="background:#0c4b78;color:#fff;padding:8px 14px;border-radius:4px;'
            'text-decoration:none;display:inline-block;">'
            '✏️ Editar paradas (drag &amp; drop)</a>'
            '<span style="margin-left:10px;color:#666;font-size:12px;">'
            '— al editar, la narrativa quedará marcada como stale (regenerar con IA).'
            '</span></div>',
            edit_url,
        )
        return format_html('{}{}', table_html, button_html)

    paradas_panel.short_description = "Paradas (en orden real)"

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

    # ─── Form 2 (Fase A): Quick-Create de Circuit con IA ───
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "crear-con-ia/",
                self.admin_site.admin_view(self.quick_create_circuit_with_ai),
                name="dpv_circuit_quick_create",
            ),
            path(
                "crear-manual/",
                self.admin_site.admin_view(self.manual_create_circuit),
                name="dpv_circuit_manual_create",
            ),
            path(
                "crear-manual/revisar/<int:draft_id>/",
                self.admin_site.admin_view(self.manual_review_branding),
                name="dpv_circuit_manual_review",
            ),
            path(
                "<int:circuit_id>/editar-paradas/",
                self.admin_site.admin_view(self.edit_circuit_places),
                name="dpv_circuit_edit_places",
            ),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["quick_create_url"] = reverse("admin:dpv_circuit_quick_create")
        extra_context["manual_create_url"] = reverse("admin:dpv_circuit_manual_create")
        return super().changelist_view(request, extra_context=extra_context)

    def quick_create_circuit_with_ai(self, request):
        from .services.circuit_composer_service import (
            apply_composition,
            compose_circuit_from_idea,
            is_composer_available,
        )

        if request.method == "POST":
            form = CircuitQuickCreateForm(request.POST)
            if form.is_valid():
                if not is_composer_available():
                    messages.error(
                        request,
                        "OPENROUTER_API_KEY no está configurada en Render. "
                        "El composer no puede llamar al LLM.",
                    )
                    return redirect("admin:dpv_circuit_quick_create")

                anchor_ids = list(
                    form.cleaned_data.get("anchor_places", []).values_list("id", flat=True)
                )

                try:
                    draft = compose_circuit_from_idea(
                        user_idea=form.cleaned_data["user_idea"],
                        duration_case=form.cleaned_data["duration_case"],
                        primary_interest=form.cleaned_data.get("primary_interest") or "",
                        recommended_profile=form.cleaned_data.get("recommended_profile") or "",
                        anchor_place_ids=anchor_ids,
                    )
                except Exception as exc:
                    logger.exception("quick_create_circuit_with_ai: composer lanzó excepción")
                    messages.error(
                        request,
                        f"La IA falló componiendo: {exc}. Intenta de nuevo.",
                    )
                    return redirect("admin:dpv_circuit_quick_create")

                if not draft:
                    messages.error(
                        request,
                        "El composer retornó None. Revisa la configuración del LLM.",
                    )
                    return redirect("admin:dpv_circuit_quick_create")

                if draft.status == CircuitCompositionDraft.STATUS_REJECTED:
                    messages.warning(
                        request,
                        f"La IA no logró componer un circuito válido: {draft.review_notes}. "
                        "Revisa el borrador o intenta con otra idea.",
                    )
                    return redirect(
                        "admin:destino_puerto_varas_circuitcompositiondraft_change",
                        draft.id,
                    )

                # Aplicar inmediatamente: crear Circuit + Days + Stops (sin publicar)
                try:
                    circuit = apply_composition(draft, reviewer=request.user.username)
                except Exception as exc:
                    logger.exception("quick_create_circuit_with_ai: apply_composition falló")
                    messages.error(
                        request,
                        f"Error aplicando la composición: {exc}. "
                        "El borrador quedó guardado para revisión manual.",
                    )
                    return redirect(
                        "admin:destino_puerto_varas_circuitcompositiondraft_change",
                        draft.id,
                    )

                if not circuit:
                    messages.warning(
                        request,
                        "apply_composition retornó None. Revisa el borrador manualmente.",
                    )
                    return redirect(
                        "admin:destino_puerto_varas_circuitcompositiondraft_change",
                        draft.id,
                    )

                gaps = (draft.proposed_data or {}).get("gaps_detected") or []
                warnings = (draft.proposed_data or {}).get("validation_warnings") or []
                msg = (
                    f"✓ Circuito '#{circuit.number} {circuit.name}' creado con "
                    f"{circuit.days.count()} día(s). Revísalo abajo y publícalo cuando esté listo."
                )
                if gaps:
                    msg += f" La IA detectó gaps: {gaps[0]}"
                if warnings:
                    msg += f" Advertencias: {warnings[0]}"
                messages.success(request, msg)
                return redirect("admin:destino_puerto_varas_circuit_change", circuit.id)
        else:
            form = CircuitQuickCreateForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Crear circuito con IA",
            "form": form,
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request),
        }
        return TemplateResponse(
            request,
            "admin/destino_puerto_varas/circuit/quick_create.html",
            context,
        )

    # ─── Form 2 modo Manual: 2 pasos (paradas → revisar nombre → crear) ───
    def manual_create_circuit(self, request):
        """Step 1 manual: usuario elige paradas en orden + parámetros básicos."""
        from .services.circuit_narrative_service import propose_circuit_branding

        if request.method == "POST":
            form = CircuitManualCreateForm(request.POST)
            if form.is_valid():
                from django.conf import settings as dj_settings

                if not getattr(dj_settings, "OPENROUTER_API_KEY", ""):
                    messages.error(
                        request,
                        "OPENROUTER_API_KEY no está configurada en Render.",
                    )
                    return redirect("admin:dpv_circuit_manual_create")

                place_ids = form.cleaned_data["places_ordered"]
                # Preservar orden — Place.objects.filter no garantiza orden por IDs
                places_by_id = {
                    p.id: p
                    for p in Place.objects.filter(id__in=place_ids, published=True)
                }
                places_in_order = [places_by_id[pid] for pid in place_ids if pid in places_by_id]

                try:
                    draft = propose_circuit_branding(
                        places_in_order=places_in_order,
                        duration_case=form.cleaned_data["duration_case"],
                        primary_interest=form.cleaned_data["primary_interest"],
                        recommended_profile=form.cleaned_data.get("recommended_profile") or "",
                    )
                except Exception as exc:
                    logger.exception("manual_create_circuit: propose_circuit_branding falló")
                    messages.error(request, f"La IA falló: {exc}.")
                    return redirect("admin:dpv_circuit_manual_create")

                if not draft:
                    messages.error(request, "El servicio retornó None. Revisa configuración del LLM.")
                    return redirect("admin:dpv_circuit_manual_create")

                if draft.status == CircuitCompositionDraft.STATUS_REJECTED:
                    messages.warning(
                        request,
                        f"La IA falló componiendo el branding: {draft.review_notes}.",
                    )
                    return redirect(
                        "admin:destino_puerto_varas_circuitcompositiondraft_change",
                        draft.id,
                    )

                return redirect("admin:dpv_circuit_manual_review", draft.id)
        else:
            form = CircuitManualCreateForm()

        # Catálogo para el autocomplete del sortable
        published_places = list(
            Place.objects.filter(published=True).order_by("name").values(
                "id", "name", "place_type", "location_label"
            )
        )

        context = {
            **self.admin_site.each_context(request),
            "title": "Crear circuito manual",
            "form": form,
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request),
            "published_places_json": json.dumps(published_places, ensure_ascii=False),
        }
        return TemplateResponse(
            request,
            "admin/destino_puerto_varas/circuit/manual_create.html",
            context,
        )

    def manual_review_branding(self, request, draft_id):
        """Step 2 manual: usuario revisa las 3 propuestas de nombre y elige una."""
        from .services.circuit_composer_service import apply_manual_composition

        draft = get_object_or_404(CircuitCompositionDraft, pk=draft_id)

        if draft.status not in (
            CircuitCompositionDraft.STATUS_DRAFT,
            CircuitCompositionDraft.STATUS_APPROVED,
        ):
            messages.warning(
                request,
                f"Este borrador ya está en estado {draft.get_status_display()}, no se puede revisar.",
            )
            if draft.created_circuit_id:
                return redirect(
                    "admin:destino_puerto_varas_circuit_change", draft.created_circuit_id
                )
            return redirect("admin:destino_puerto_varas_circuit_changelist")

        proposed = draft.proposed_data or {}
        options = proposed.get("name_options") or []

        if request.method == "POST":
            try:
                chosen_index = int(request.POST.get("chosen_name_index", "0"))
            except ValueError:
                chosen_index = 0
            if chosen_index < 0 or chosen_index >= len(options):
                messages.error(request, "Índice de nombre inválido.")
                return redirect("admin:dpv_circuit_manual_review", draft.id)

            try:
                circuit = apply_manual_composition(
                    draft,
                    chosen_name_index=chosen_index,
                    reviewer=request.user.username,
                )
            except Exception as exc:
                logger.exception("manual_review_branding: apply_manual_composition falló")
                messages.error(request, f"Error creando el circuito: {exc}.")
                return redirect("admin:dpv_circuit_manual_review", draft.id)

            if not circuit:
                messages.warning(request, "apply_manual_composition retornó None. Revisa logs.")
                return redirect("admin:dpv_circuit_manual_review", draft.id)

            messages.success(
                request,
                f"✓ Circuito '#{circuit.number} {circuit.name}' creado con "
                f"{circuit.days.count()} día(s) y {sum(d.place_stops.count() for d in circuit.days.all())} parada(s). "
                "Revísalo abajo y publícalo cuando esté listo.",
            )
            return redirect("admin:destino_puerto_varas_circuit_change", circuit.id)

        # GET: render con paradas + 3 cards
        place_ids_in_order = draft.anchor_place_ids or []
        places_by_id = {p.id: p for p in Place.objects.filter(id__in=place_ids_in_order)}
        ordered_places = [places_by_id[pid] for pid in place_ids_in_order if pid in places_by_id]

        context = {
            **self.admin_site.each_context(request),
            "title": "Revisa y elige el nombre del circuito",
            "draft": draft,
            "ordered_places": ordered_places,
            "name_options": options,
            "long_description": proposed.get("long_description", ""),
            "day_summaries": proposed.get("day_summaries", {}),
            "flags": {
                "is_romantic": proposed.get("is_romantic", False),
                "is_family_friendly": proposed.get("is_family_friendly", False),
                "is_adventure": proposed.get("is_adventure", False),
                "is_rain_friendly": proposed.get("is_rain_friendly", False),
                "is_premium": proposed.get("is_premium", False),
            },
            "rationale": proposed.get("rationale", ""),
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request),
        }
        return TemplateResponse(
            request,
            "admin/destino_puerto_varas/circuit/manual_create_review.html",
            context,
        )

    # ─── Editor de paradas (drag & drop) sobre un Circuit existente ───
    def edit_circuit_places(self, request, circuit_id):
        """Editor unificado: agregar/quitar/reordenar paradas en un Circuit existente.

        En POST: wipe + rebuild de CircuitPlace en transacción atómica.
        Las paradas se redistribuyen entre los días existentes preservando el orden
        global. La narrativa queda automáticamente stale (places_signature cambia).
        """
        from django.db import transaction
        from .services.circuit_composer_service import _distribute_stops_across_days

        circuit = get_object_or_404(Circuit, pk=circuit_id)

        if request.method == "POST":
            raw = (request.POST.get("places_ordered") or "").strip()
            try:
                new_ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
            except ValueError:
                messages.error(request, "Formato de paradas inválido.")
                return redirect("admin:dpv_circuit_edit_places", circuit.id)

            if not new_ids:
                messages.error(request, "Debes dejar al menos 1 parada.")
                return redirect("admin:dpv_circuit_edit_places", circuit.id)

            valid_ids = set(
                Place.objects.filter(id__in=new_ids, published=True).values_list(
                    "id", flat=True
                )
            )
            invalid = [pid for pid in new_ids if pid not in valid_ids]
            if invalid:
                messages.error(
                    request,
                    f"Estos Places no existen o no están publicados: {invalid}.",
                )
                return redirect("admin:dpv_circuit_edit_places", circuit.id)

            places_by_id = {p.id: p for p in Place.objects.filter(id__in=new_ids)}
            ordered_places = [places_by_id[pid] for pid in new_ids]

            existing_days = list(circuit.days.order_by("day_number", "sort_order"))
            if not existing_days:
                # Defensivo: si no hay días, crear el Día 1
                from .enums import BlockType
                day1 = CircuitDay.objects.create(
                    circuit=circuit,
                    day_number=1,
                    title="Día 1",
                    block_type=BlockType.FULL_DAY,
                    summary="",
                    sort_order=1,
                )
                existing_days = [day1]

            n_days = len(existing_days)
            distribution = _distribute_stops_across_days(ordered_places, n_days)

            with transaction.atomic():
                # Wipe paradas actuales
                CircuitPlace.objects.filter(circuit_day__circuit=circuit).delete()
                # Rebuild distribuyendo entre los días existentes
                for day, day_places in zip(existing_days, distribution):
                    for idx, place in enumerate(day_places, start=1):
                        CircuitPlace.objects.create(
                            circuit_day=day,
                            place=place,
                            visit_order=idx,
                            is_main_stop=False,
                        )

            messages.success(
                request,
                f"✓ Paradas actualizadas: {len(new_ids)} parada(s) distribuida(s) "
                f"en {n_days} día(s). La narrativa quedó stale — regenérala con la "
                "acción 'Generar narrativa con IA' en el changelist.",
            )
            return redirect("admin:destino_puerto_varas_circuit_change", circuit.id)

        # GET: cargar paradas actuales en el sortable
        current_stops = []
        for day in circuit.days.order_by("day_number", "sort_order").prefetch_related(
            "place_stops__place"
        ):
            for stop in day.place_stops.order_by("visit_order"):
                current_stops.append({
                    "id": stop.place.id,
                    "name": stop.place.name,
                    "place_type": stop.place.place_type,
                    "location_label": stop.place.location_label,
                })

        published_places = list(
            Place.objects.filter(published=True).order_by("name").values(
                "id", "name", "place_type", "location_label"
            )
        )

        context = {
            **self.admin_site.each_context(request),
            "title": f"Editar paradas — #{circuit.number} {circuit.name}",
            "circuit": circuit,
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request),
            "published_places_json": json.dumps(published_places, ensure_ascii=False),
            "current_stops_json": json.dumps(current_stops, ensure_ascii=False),
            "n_days": circuit.days.count(),
        }
        return TemplateResponse(
            request,
            "admin/destino_puerto_varas/circuit/edit_places.html",
            context,
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


class PlaceQuickCreateForm(forms.Form):
    """Formulario para crear un Place nuevo y dispararle enrichment IA."""
    name = forms.CharField(
        label="Nombre del lugar",
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Ej: Volcán Osorno", "size": 60}),
        help_text="Nombre completo y reconocible. Mientras más específico, mejor búsqueda.",
    )
    place_type = forms.ChoiceField(
        label="Tipo de lugar",
        choices=PlaceType.choices,
        initial=PlaceType.ATTRACTION,
    )
    partnership_level = forms.ChoiceField(
        label="Nivel de relación comercial",
        choices=PartnershipLevel.choices,
        initial=PartnershipLevel.LISTED,
        help_text=(
            "PROPIO=Aremko · PARTNER=acuerdo activo (Teatro del Lago, "
            "restaurantes aliados) · LISTED=mencionable sin acuerdo · "
            "DIRECTORY=referencial (volcanes, iglesias, museos públicos)."
        ),
    )
    location_label = forms.CharField(
        label="Ubicación / contexto",
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ej: Ensenada, Petrohué, Frutillar", "size": 60}),
        help_text="Comuna/sector de referencia. Ayuda a la IA a desambiguar lugares con nombres parecidos.",
    )
    short_description = forms.CharField(
        label="Descripción breve (opcional)",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "cols": 60}),
        help_text="Si la dejas vacía, la IA generará la descripción larga (long_description).",
    )
    publish_after = forms.BooleanField(
        label="Publicar inmediatamente",
        required=False,
        initial=False,
        help_text="Si lo dejas desmarcado, el lugar queda como borrador (no aparece al público).",
    )


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "place_type",
        "partnership_level",
        "location_label",
        "elevation_m",
        "entry_fee_clp",
        "last_enriched_at",
        "published",
    )
    list_filter = (
        "place_type",
        "partnership_level",
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
    actions = ["accion_enriquecer_con_ia", "accion_autoderivar_short_desc"]
    fieldsets = (
        ("Identidad", {
            "fields": ("name", "slug", "place_type", "partnership_level", "location_label", "published"),
            "description": (
                "<strong>partnership_level</strong>: PROPIO=Aremko; PARTNER=acuerdo activo "
                "(Teatro del Lago, restaurantes aliados); LISTED=mencionable sin acuerdo; "
                "DIRECTORY=referencial (atracciones naturales, iglesias, museos públicos)."
            ),
        }),
        ("Ubicación", {
            "fields": ("latitude", "longitude", "distance_from_pv_km", "drive_time_from_pv_min"),
        }),
        ("Descripción editorial", {
            "fields": ("short_description", "long_description"),
        }),
        ("Datos comerciales (negocios / restaurantes / teatros / museos)", {
            "fields": (
                ("phone", "website"),
                ("instagram", "reservations_url"),
                ("price_range",),
                "opening_hours",
            ),
            "description": (
                "Llenar solo si aplica al tipo de lugar (un volcán no tiene horarios). "
                "<strong>opening_hours</strong>: JSON con claves mon/tue/wed/thu/fri/sat/sun "
                "+ opcional 'notes'. Ej: <code>{\"mon\":\"09:00-18:00\",\"sun\":\"cerrado\"}</code>."
            ),
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

    @admin.action(description="✏ Auto-derivar 'short_description' desde long_description (si está vacío)")
    def accion_autoderivar_short_desc(self, request, queryset):
        ok, skipped = 0, 0
        for place in queryset:
            if place.short_description:
                skipped += 1
                continue
            if not place.long_description:
                skipped += 1
                continue
            first_sentence = place.long_description.strip().split(". ")[0].strip()
            if len(first_sentence) > 240:
                short = first_sentence[:240].rsplit(" ", 1)[0] + "…"
            else:
                short = first_sentence
            place.short_description = short[:255]
            place.save(update_fields=["short_description", "updated_at"])
            ok += 1
        self.message_user(
            request,
            f"✓ {ok} lugar(es) actualizado(s). {skipped} saltado(s) (ya tenían short_desc o no hay long_desc).",
            level=messages.SUCCESS if ok else messages.WARNING,
        )

    # ──────────────────────────────────────────────────────────────────
    # "+ Crear lugar con IA" — formulario custom de creación con enrichment
    # ──────────────────────────────────────────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "crear-con-ia/",
                self.admin_site.admin_view(self.quick_create_with_ai),
                name="dpv_place_quick_create",
            ),
            path(
                "<int:place_id>/aplicar-y-publicar/",
                self.admin_site.admin_view(self.aplicar_y_publicar_view),
                name="dpv_place_apply_publish",
            ),
            path(
                "<int:place_id>/re-enriquecer/",
                self.admin_site.admin_view(self.re_enriquecer_view),
                name="dpv_place_re_enrich",
            ),
            path(
                "<int:place_id>/descartar-draft/",
                self.admin_site.admin_view(self.descartar_draft_view),
                name="dpv_place_discard_draft",
            ),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["quick_create_url"] = reverse("admin:dpv_place_quick_create")
        return super().changelist_view(request, extra_context=extra_context)

    # ─── Override para inyectar el panel del draft pendiente ───
    change_form_template = "admin/destino_puerto_varas/place/change_form.html"

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        try:
            place = Place.objects.get(pk=object_id)
        except (Place.DoesNotExist, ValueError):
            return super().change_view(request, object_id, form_url, extra_context)

        pending = (
            place.enrichment_drafts
            .filter(status__in=[
                PlaceEnrichmentDraft.STATUS_DRAFT,
                PlaceEnrichmentDraft.STATUS_APPROVED,
            ])
            .order_by("-created_at")
            .first()
        )
        if pending:
            extra_context["pending_draft"] = pending
            extra_context["pending_draft_preview"] = render_draft_mobile_preview(pending)
            extra_context["pending_draft_change_url"] = reverse(
                "admin:destino_puerto_varas_placeenrichmentdraft_change", args=[pending.id]
            )
            extra_context["pending_draft_apply_url"] = reverse(
                "admin:dpv_place_apply_publish", args=[place.id]
            )
            extra_context["pending_draft_re_enrich_url"] = reverse(
                "admin:dpv_place_re_enrich", args=[place.id]
            )
            extra_context["pending_draft_discard_url"] = reverse(
                "admin:dpv_place_discard_draft", args=[place.id]
            )
        return super().change_view(request, object_id, form_url, extra_context)

    # ─── Acciones del panel inline (botones) ───
    def aplicar_y_publicar_view(self, request, place_id):
        from .services.place_enrichment_service import apply_draft

        if request.method != "POST":
            return redirect("admin:destino_puerto_varas_place_change", place_id)

        place = get_object_or_404(Place, pk=place_id)
        pending = (
            place.enrichment_drafts
            .filter(status__in=[
                PlaceEnrichmentDraft.STATUS_DRAFT,
                PlaceEnrichmentDraft.STATUS_APPROVED,
            ])
            .order_by("-created_at")
            .first()
        )
        if not pending:
            messages.warning(request, "No hay borrador pendiente para este lugar.")
            return redirect("admin:destino_puerto_varas_place_change", place_id)

        proposed = pending.proposed_data or {}
        has_content = bool(
            (proposed.get("fields") or {})
            or (proposed.get("long_description") or "").strip()
            or (proposed.get("extra_data") or {})
            or (proposed.get("photos") or [])
        )
        if not has_content:
            messages.error(
                request,
                "El borrador está vacío. Re-enriquece o descarta antes de aplicar.",
            )
            return redirect("admin:destino_puerto_varas_place_change", place_id)

        # Aprobar si está en draft
        if pending.status == PlaceEnrichmentDraft.STATUS_DRAFT:
            pending.status = PlaceEnrichmentDraft.STATUS_APPROVED
            pending.reviewed_by = request.user.username
            pending.reviewed_at = timezone.now()
            pending.save()

        # Aplicar
        try:
            ok = apply_draft(pending, reviewer=request.user.username)
        except Exception as exc:
            logger.exception("aplicar_y_publicar_view: error en apply_draft")
            messages.error(request, f"Error aplicando: {exc}")
            return redirect("admin:destino_puerto_varas_place_change", place_id)

        if not ok:
            messages.warning(
                request,
                f"apply_draft retornó False (status={pending.status}). Revisa logs.",
            )
            return redirect("admin:destino_puerto_varas_place_change", place_id)

        # Publicar
        place.refresh_from_db()
        if not place.published:
            place.published = True
            place.save(update_fields=["published", "updated_at"])

        messages.success(
            request,
            f"✓ Borrador aplicado y '{place.name}' publicado. "
            "Los datos están abajo en el formulario.",
        )
        return redirect("admin:destino_puerto_varas_place_change", place_id)

    def re_enriquecer_view(self, request, place_id):
        from .services.place_enrichment_service import (
            enrich_place,
            is_enrichment_available,
        )

        if request.method != "POST":
            return redirect("admin:destino_puerto_varas_place_change", place_id)

        place = get_object_or_404(Place, pk=place_id)

        if not is_enrichment_available():
            messages.error(
                request,
                "Faltan credenciales: PERPLEXITY_API_KEY u OPENROUTER_API_KEY.",
            )
            return redirect("admin:destino_puerto_varas_place_change", place_id)

        # Marcar drafts pendientes como rechazados
        place.enrichment_drafts.filter(
            status__in=[
                PlaceEnrichmentDraft.STATUS_DRAFT,
                PlaceEnrichmentDraft.STATUS_APPROVED,
            ]
        ).update(
            status=PlaceEnrichmentDraft.STATUS_REJECTED,
            reviewed_by=request.user.username,
            reviewed_at=timezone.now(),
            review_notes="Reemplazado al re-enriquecer.",
        )

        try:
            draft = enrich_place(place)
        except Exception as exc:
            logger.exception("re_enriquecer_view: error en enrich_place")
            messages.error(request, f"Error re-enriqueciendo: {exc}")
            return redirect("admin:destino_puerto_varas_place_change", place_id)

        if draft and draft.status == PlaceEnrichmentDraft.STATUS_DRAFT:
            messages.success(request, "✓ Nuevo borrador IA generado. Revísalo arriba.")
        else:
            status = draft.status if draft else "None"
            messages.warning(request, f"La IA no generó borrador válido (status={status}).")
        return redirect("admin:destino_puerto_varas_place_change", place_id)

    def descartar_draft_view(self, request, place_id):
        if request.method != "POST":
            return redirect("admin:destino_puerto_varas_place_change", place_id)

        place = get_object_or_404(Place, pk=place_id)
        n = place.enrichment_drafts.filter(
            status__in=[
                PlaceEnrichmentDraft.STATUS_DRAFT,
                PlaceEnrichmentDraft.STATUS_APPROVED,
            ]
        ).update(
            status=PlaceEnrichmentDraft.STATUS_REJECTED,
            reviewed_by=request.user.username,
            reviewed_at=timezone.now(),
            review_notes="Descartado desde la página del Place.",
        )
        if n:
            messages.info(request, f"✓ {n} borrador(es) descartado(s).")
        else:
            messages.warning(request, "No había borradores pendientes.")
        return redirect("admin:destino_puerto_varas_place_change", place_id)

    def quick_create_with_ai(self, request):
        from .services.place_enrichment_service import (
            enrich_place,
            is_enrichment_available,
        )

        if request.method == "POST":
            form = PlaceQuickCreateForm(request.POST)
            if form.is_valid():
                if not is_enrichment_available():
                    messages.error(
                        request,
                        "Faltan credenciales: necesito PERPLEXITY_API_KEY (search) "
                        "y OPENROUTER_API_KEY (synthesis) en las env vars.",
                    )
                    return redirect("admin:dpv_place_quick_create")

                name = form.cleaned_data["name"].strip()
                base_slug = slugify(name) or "lugar"
                slug = base_slug
                n = 2
                while Place.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{n}"
                    n += 1

                place = Place.objects.create(
                    name=name,
                    slug=slug,
                    place_type=form.cleaned_data["place_type"],
                    partnership_level=form.cleaned_data["partnership_level"],
                    location_label=form.cleaned_data["location_label"] or "",
                    short_description=form.cleaned_data["short_description"] or "",
                    published=form.cleaned_data.get("publish_after", False),
                )
                messages.info(request, f"Lugar '{name}' creado (slug: {slug}).")

                try:
                    draft = enrich_place(place, save=True)
                except Exception as exc:
                    logger.exception("quick_create_with_ai: enrich_place lanzó excepción")
                    messages.error(
                        request,
                        f"La IA falló: {exc}. El lugar quedó creado, "
                        "puedes enriquecerlo después con la acción 'Enriquecer con IA'.",
                    )
                    return redirect("admin:destino_puerto_varas_place_change", place.id)

                if not draft:
                    messages.warning(
                        request,
                        "enrich_place retornó None (revisa logs). "
                        "El lugar quedó creado pero sin borrador.",
                    )
                    return redirect("admin:destino_puerto_varas_place_change", place.id)

                if draft.status == PlaceEnrichmentDraft.STATUS_REJECTED:
                    messages.warning(
                        request,
                        f"Borrador generado pero la IA falló: {draft.review_notes}. "
                        "Lugar creado; reintenta con 'Re-enriquecer' o llena los campos a mano.",
                    )
                else:
                    messages.success(
                        request,
                        "✓ Borrador IA generado. Revísalo arriba en la vista previa, "
                        "y haz click en 'Aplicar y publicar'.",
                    )
                return redirect("admin:destino_puerto_varas_place_change", place.id)
        else:
            form = PlaceQuickCreateForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Crear lugar con IA",
            "form": form,
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request),
        }
        return TemplateResponse(
            request,
            "admin/destino_puerto_varas/place/quick_create.html",
            context,
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
        "mobile_preview",
    )
    ordering = ("-created_at",)
    actions = ["accion_aprobar", "accion_rechazar", "accion_aplicar_aprobados"]
    fieldsets = (
        ("Lugar", {"fields": ("place", "status")}),
        (
            "📱 Vista previa móvil (cómo lo verá el turista)",
            {
                "fields": ("mobile_preview",),
                "description": (
                    "Simulación de cómo se vería este lugar como mensaje de chat (Telegram/"
                    "WhatsApp). Refleja los datos actuales del JSON de abajo — si los editas, "
                    "guarda y refresca para actualizar la previa."
                ),
            },
        ),
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

    def mobile_preview(self, obj):
        """Simula cómo se vería este lugar al turista en Telegram/WhatsApp."""
        return render_draft_mobile_preview(obj)
    mobile_preview.short_description = "📱 Vista móvil"


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

        total = queryset.count()
        approved_qs = queryset.filter(status=PlaceEnrichmentDraft.STATUS_APPROVED)
        approved_count = approved_qs.count()
        skipped_not_approved = total - approved_count

        ok, fail_empty, fail_exc, fail_other = 0, 0, 0, 0
        details: list[str] = []

        for draft in approved_qs:
            label = f"#{draft.id} ({draft.place.name})"
            proposed = draft.proposed_data or {}
            has_fields = bool((proposed.get("fields") or {}))
            has_long = bool((proposed.get("long_description") or "").strip())
            has_extra = bool((proposed.get("extra_data") or {}))
            has_photos = bool((proposed.get("photos") or []))

            if not (has_fields or has_long or has_extra or has_photos):
                fail_empty += 1
                details.append(
                    f"⚠ {label}: proposed_data vacío — saltado. "
                    "Borra este draft y vuelve a enriquecer el Place."
                )
                continue

            try:
                applied = apply_draft(draft, reviewer=request.user.username)
            except Exception as exc:
                logger.exception("Error aplicando draft %s", label)
                fail_exc += 1
                details.append(f"✗ {label}: excepción — {exc}")
                continue

            if applied:
                # Releer Place desde DB para confirmar que se escribió
                draft.refresh_from_db()
                place = draft.place
                place.refresh_from_db()
                summary_bits = []
                if place.long_description:
                    summary_bits.append(f"long_desc={len(place.long_description)} chars")
                if place.elevation_m:
                    summary_bits.append(f"alt={place.elevation_m}m")
                if place.distance_from_pv_km:
                    summary_bits.append(f"dist={place.distance_from_pv_km}km")
                if place.extra_data:
                    summary_bits.append(f"extra={len(place.extra_data)} keys")
                summary = ", ".join(summary_bits) or "sin campos no-null"
                details.append(f"✓ {label}: aplicado ({summary})")
                ok += 1
            else:
                fail_other += 1
                details.append(
                    f"✗ {label}: apply_draft retornó False (status={draft.status})"
                )

        # Mensaje resumen
        self.message_user(
            request,
            f"Resumen: {total} draft(s) seleccionados, {approved_count} aprobados, "
            f"{skipped_not_approved} saltados (no aprobados). "
            f"Aplicados: {ok}. Vacíos: {fail_empty}. Excepciones: {fail_exc}. Otros: {fail_other}.",
            level=messages.SUCCESS if ok else messages.WARNING,
        )
        # Detalle por draft
        for line in details:
            level = messages.SUCCESS if line.startswith("✓") else messages.WARNING
            self.message_user(request, line, level=level)


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


@admin.register(CircuitCompositionDraft)
class CircuitCompositionDraftAdmin(admin.ModelAdmin):
    """Admin para inspeccionar/depurar borradores de composición de Circuit con IA.

    El flujo normal aplica el draft inmediatamente y crea el Circuit, pero si
    la IA falla (status=REJECTED) o el apply lanza excepción, el draft queda
    aquí para revisión manual.
    """
    list_display = (
        "id",
        "short_idea",
        "status",
        "duration_case",
        "primary_interest",
        "created_circuit",
        "llm_model",
        "created_at",
    )
    list_filter = ("status", "primary_interest", "duration_case", "llm_model")
    search_fields = ("user_idea", "review_notes", "created_circuit__name")
    readonly_fields = (
        "user_idea",
        "duration_case",
        "primary_interest",
        "recommended_profile",
        "anchor_place_ids",
        "proposed_data_pretty",
        "created_circuit",
        "llm_model",
        "llm_input_tokens",
        "llm_output_tokens",
        "llm_latency_ms",
        "reviewed_by",
        "reviewed_at",
        "applied_at",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        ("Input del usuario", {
            "fields": (
                "user_idea",
                ("duration_case", "primary_interest", "recommended_profile"),
                "anchor_place_ids",
            ),
        }),
        ("Estado", {
            "fields": ("status", "review_notes", "created_circuit"),
        }),
        ("Propuesta IA", {
            "fields": ("proposed_data_pretty",),
        }),
        ("Métricas LLM", {
            "fields": (
                "llm_model",
                ("llm_input_tokens", "llm_output_tokens", "llm_latency_ms"),
            ),
            "classes": ("collapse",),
        }),
        ("Auditoría", {
            "fields": (
                ("reviewed_by", "reviewed_at"),
                "applied_at",
                ("created_at", "updated_at"),
            ),
            "classes": ("collapse",),
        }),
    )

    def short_idea(self, obj):
        idea = (obj.user_idea or "").strip()
        return (idea[:80] + "…") if len(idea) > 80 else idea
    short_idea.short_description = "Idea"

    def proposed_data_pretty(self, obj):
        if not obj.proposed_data:
            return "—"
        try:
            pretty = json.dumps(obj.proposed_data, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            pretty = str(obj.proposed_data)
        return format_html(
            '<pre style="background:#f5f5f5;padding:10px;border-radius:4px;'
            'max-height:600px;overflow:auto;font-size:12px;">{}</pre>',
            pretty,
        )
    proposed_data_pretty.short_description = "Estructura propuesta"


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
