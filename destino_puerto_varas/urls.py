"""URLs HTML públicas de Destino Puerto Varas.

Rutas para el sitio público (futuro destinopuertovaras.cl). Por ahora
montadas en la instancia Aremko bajo /dpv/ para iterar diseño y datos.
"""
from __future__ import annotations

from django.urls import path

from .views import CircuitDetailPublicView, CircuitListPublicView

app_name = "destino_puerto_varas_public"

urlpatterns = [
    path("", CircuitListPublicView.as_view(), name="circuit-list"),
    path("circuitos/<slug:slug>/", CircuitDetailPublicView.as_view(), name="circuit-detail"),
]
