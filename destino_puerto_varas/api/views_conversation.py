"""Endpoints conversacionales DPV: start, continue y webhooks placeholder."""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..enums import MessageSenderType
from ..models import ConversationMessage, LeadConversation
from ..selectors import get_or_create_conversation
from ..services.channel_router import build_channel_action
from ..services.conversation_flow_service import process_incoming_message
from ..services.weather_adaptation_service import adapt_recommendation_for_weather
from ..services.whatsapp_inbound_service import handle_incoming_message
from .serializers import (
    ContinueConversationRequestSerializer,
    StartConversationRequestSerializer,
)


def _append_user_message(conversation: LeadConversation, text: str) -> ConversationMessage:
    """Registra un mensaje del usuario y actualiza el timestamp."""
    msg = ConversationMessage.objects.create(
        conversation=conversation,
        sender_type=MessageSenderType.USER,
        text=text,
    )
    conversation.last_user_message_at = timezone.now()
    conversation.save(update_fields=["last_user_message_at", "updated_at"])
    return msg


class StartConversationView(APIView):
    """POST /api/destino-puerto-varas/conversations/start/

    Crea (o recupera) una conversación por (channel, external_id) y procesa
    un mensaje inicial opcional. Devuelve la respuesta del bot."""

    def post(self, request, *args, **kwargs):
        serializer = StartConversationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        channel = data["channel"]
        external_id = data.get("external_id") or ""
        conversation, created = get_or_create_conversation(channel, external_id)

        # Sincroniza datos de contacto si vinieron en el payload
        updates = []
        for field in ("contact_name", "contact_phone", "contact_email"):
            value = data.get(field)
            if value and getattr(conversation, field) != value:
                setattr(conversation, field, value)
                updates.append(field)
        if updates:
            updates.append("updated_at")
            conversation.save(update_fields=updates)

        initial_message = data.get("initial_message") or ""
        if initial_message.strip():
            _append_user_message(conversation, initial_message)
            payload = process_incoming_message(conversation, initial_message)
        else:
            # Sin mensaje inicial: despacha el handler de start
            from ..services.conversation_flow_service import handle_start
            payload = handle_start(conversation)

        payload["channel_action"] = build_channel_action(conversation, initial_message)
        payload["conversation_created"] = created
        return Response(payload, status=status.HTTP_200_OK)


class ContinueConversationView(APIView):
    """POST /api/destino-puerto-varas/conversations/continue/

    Procesa un mensaje entrante sobre una conversación existente."""

    def post(self, request, *args, **kwargs):
        serializer = ContinueConversationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            conversation = LeadConversation.objects.get(pk=data["conversation_id"])
        except LeadConversation.DoesNotExist:
            return Response(
                {"detail": "Conversación no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        message_text = data["message_text"]
        is_rainy = data.get("is_rainy", False)

        _append_user_message(conversation, message_text)
        payload = process_incoming_message(conversation, message_text)

        # Ajuste por clima si hay circuito recomendado
        if conversation.recommended_circuit_id:
            weather = adapt_recommendation_for_weather(
                conversation.recommended_circuit, is_rainy=is_rainy
            )
            if weather.get("adjusted"):
                payload["weather_adjustment"] = weather

        payload["channel_action"] = build_channel_action(conversation, message_text)
        return Response(payload, status=status.HTTP_200_OK)


# ─────────────────────── Webhook placeholders ───────────────────────


class WhatsAppWebhookView(APIView):
    """Placeholder para integración con WhatsApp Cloud API.
    GET → handshake hub.challenge. POST → recibe eventos (no procesa aún)."""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, *args, **kwargs):
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        expected_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "")
        if mode == "subscribe" and token == expected_token and challenge:
            return Response(int(challenge), status=status.HTTP_200_OK)
        return Response({"detail": "verification failed"}, status=status.HTTP_403_FORBIDDEN)

    def post(self, request, *args, **kwargs):
        # DPV-006: recibe eventos del servicio neonize. Auth por token simétrico.
        expected_token = getattr(settings, "NEONIZE_SERVICE_TOKEN", "")
        provided_token = request.headers.get("X-Auth-Token", "")
        if not expected_token or provided_token != expected_token:
            return Response(
                {"detail": "invalid or missing X-Auth-Token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        result = handle_incoming_message(request.data or {})
        return Response(result, status=status.HTTP_200_OK)


class InstagramWebhookView(APIView):
    """Placeholder para integración con Instagram Graph API.
    GET → handshake hub.challenge. POST → recibe eventos (no procesa aún)."""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, *args, **kwargs):
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        expected_token = getattr(settings, "INSTAGRAM_VERIFY_TOKEN", "")
        if mode == "subscribe" and token == expected_token and challenge:
            return Response(int(challenge), status=status.HTTP_200_OK)
        return Response({"detail": "verification failed"}, status=status.HTTP_403_FORBIDDEN)

    def post(self, request, *args, **kwargs):
        return Response({"received": True}, status=status.HTTP_200_OK)
