from django.contrib import admin

from .models import (
    AremkoRecommendation,
    Circuit,
    CircuitDay,
    CircuitPlace,
    ConversationMessage,
    DurationCase,
    LeadConversation,
    Place,
    RecommendationRule,
    TravelTip,
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


@admin.register(Circuit)
class CircuitAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "name",
        "duration_case",
        "primary_interest",
        "recommended_profile",
        "published",
        "featured",
        "sort_order",
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


@admin.register(CircuitDay)
class CircuitDayAdmin(admin.ModelAdmin):
    list_display = ("circuit", "day_number", "title", "block_type", "sort_order")
    list_filter = ("block_type", "circuit")
    search_fields = ("title", "circuit__name")
    inlines = [CircuitPlaceInline]
    ordering = ("circuit", "day_number", "sort_order")


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "place_type",
        "location_label",
        "is_rain_friendly",
        "is_romantic",
        "is_family_friendly",
        "is_adventure_related",
        "published",
    )
    list_filter = (
        "place_type",
        "published",
        "is_rain_friendly",
        "is_romantic",
        "is_family_friendly",
        "is_adventure_related",
    )
    search_fields = ("name", "slug", "location_label", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


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
