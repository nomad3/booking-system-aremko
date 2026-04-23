"""URLs del módulo Destino Puerto Varas (catálogo + conversación + webhooks)."""

from __future__ import annotations

from django.urls import path

from .views_conversation import (
    ContinueConversationView,
    InstagramWebhookView,
    StartConversationView,
    WhatsAppWebhookView,
)
from .views_public import (
    CircuitDetailView,
    CircuitListView,
    DurationCaseListView,
    PlaceListView,
)

app_name = "destino_puerto_varas"

urlpatterns = [
    # Catálogo público
    path("circuits/", CircuitListView.as_view(), name="circuit-list"),
    path("circuits/<slug:slug>/", CircuitDetailView.as_view(), name="circuit-detail"),
    path("places/", PlaceListView.as_view(), name="place-list"),
    path("duration-cases/", DurationCaseListView.as_view(), name="duration-case-list"),

    # Conversacional
    path("conversations/start/", StartConversationView.as_view(), name="conversation-start"),
    path("conversations/continue/", ContinueConversationView.as_view(), name="conversation-continue"),

    # Webhooks placeholder
    path("webhooks/whatsapp/", WhatsAppWebhookView.as_view(), name="webhook-whatsapp"),
    path("webhooks/instagram/", InstagramWebhookView.as_view(), name="webhook-instagram"),
]
