"""DRF serializers para Destino Puerto Varas (catálogo + conversación)."""

from __future__ import annotations

from rest_framework import serializers

from ..enums import ChannelType
from ..models import (
    AremkoRecommendation,
    Circuit,
    CircuitDay,
    CircuitPlace,
    ConversationMessage,
    DurationCase,
    LeadConversation,
    Place,
    TravelTip,
)


# ─────────────────────── Serializadores de catálogo ───────────────────────


class DurationCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = DurationCase
        fields = [
            "id",
            "code",
            "name",
            "duration_type",
            "days",
            "nights",
            "sort_order",
            "is_active",
            "description",
        ]


class PlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Place
        fields = [
            "id",
            "name",
            "slug",
            "place_type",
            "short_description",
            "long_description",
            "location_label",
            "latitude",
            "longitude",
            "is_rain_friendly",
            "is_romantic",
            "is_family_friendly",
            "is_adventure_related",
            "practical_tips",
            "safety_notes",
            "did_you_know",
            "nobody_tells_you",
            "published",
        ]


class CircuitPlaceSerializer(serializers.ModelSerializer):
    place = PlaceSerializer(read_only=True)

    class Meta:
        model = CircuitPlace
        fields = ["id", "place", "visit_order", "is_main_stop"]


class CircuitDaySerializer(serializers.ModelSerializer):
    place_stops = CircuitPlaceSerializer(many=True, read_only=True)

    class Meta:
        model = CircuitDay
        fields = [
            "id",
            "day_number",
            "title",
            "block_type",
            "summary",
            "sort_order",
            "place_stops",
        ]


class CircuitListSerializer(serializers.ModelSerializer):
    """Serializer compacto para listados."""
    duration_case_code = serializers.CharField(source="duration_case.code", read_only=True)
    duration_case_name = serializers.CharField(source="duration_case.name", read_only=True)

    class Meta:
        model = Circuit
        fields = [
            "id",
            "number",
            "name",
            "slug",
            "short_description",
            "duration_case_code",
            "duration_case_name",
            "primary_interest",
            "recommended_profile",
            "is_romantic",
            "is_family_friendly",
            "is_adventure",
            "is_rain_friendly",
            "is_premium",
            "featured",
            "sort_order",
            "updated_at",
        ]


class CircuitDetailSerializer(serializers.ModelSerializer):
    """Serializer expandido (con días y paradas)."""
    duration_case = DurationCaseSerializer(read_only=True)
    days = CircuitDaySerializer(many=True, read_only=True)

    class Meta:
        model = Circuit
        fields = [
            "id",
            "number",
            "name",
            "slug",
            "short_description",
            "long_description",
            "duration_case",
            "primary_interest",
            "recommended_profile",
            "is_romantic",
            "is_family_friendly",
            "is_adventure",
            "is_rain_friendly",
            "is_premium",
            "published",
            "featured",
            "sort_order",
            "created_at",
            "updated_at",
            "days",
        ]


class AremkoRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AremkoRecommendation
        fields = [
            "id",
            "name",
            "context_key",
            "title",
            "message_text",
            "recommended_service_type",
            "priority",
            "is_active",
        ]


class TravelTipSerializer(serializers.ModelSerializer):
    duration_case_code = serializers.CharField(
        source="duration_case.code", read_only=True, allow_null=True
    )

    class Meta:
        model = TravelTip
        fields = [
            "id",
            "title",
            "tip_text",
            "interest",
            "profile",
            "duration_case_code",
            "applies_when_raining",
            "applies_when_sunny",
            "sort_order",
            "is_active",
        ]


# ─────────────────────── Serializadores de conversación ───────────────────────


class ConversationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationMessage
        fields = ["id", "sender_type", "text", "metadata", "created_at"]


class LeadConversationSerializer(serializers.ModelSerializer):
    detected_duration_case_code = serializers.CharField(
        source="detected_duration_case.code", read_only=True, allow_null=True
    )
    messages = ConversationMessageSerializer(many=True, read_only=True)

    class Meta:
        model = LeadConversation
        fields = [
            "id",
            "channel",
            "external_id",
            "contact_name",
            "contact_phone",
            "contact_email",
            "status",
            "detected_interest",
            "detected_profile",
            "detected_duration_case_code",
            "recommended_circuit",
            "referred_to_aremko",
            "showed_interest_in_aremko",
            "last_user_message_at",
            "last_assistant_message_at",
            "created_at",
            "updated_at",
            "messages",
        ]


# ─────────────────────── Serializadores de requests ───────────────────────


class StartConversationRequestSerializer(serializers.Serializer):
    """Payload para iniciar una conversación conversacional."""
    channel = serializers.ChoiceField(choices=ChannelType.choices)
    external_id = serializers.CharField(max_length=120, required=False, allow_blank=True)
    contact_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    initial_message = serializers.CharField(required=False, allow_blank=True)


class ContinueConversationRequestSerializer(serializers.Serializer):
    """Payload para continuar una conversación existente."""
    conversation_id = serializers.IntegerField()
    message_text = serializers.CharField()
    is_rainy = serializers.BooleanField(required=False, default=False)
