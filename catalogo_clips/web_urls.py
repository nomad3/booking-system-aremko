"""Rutas WEB del catálogo (H-071 B1) — separadas de urls.py (la API X-API-KEY)
para poder montarlas en /marketing/catalogo/ sin chocar de namespace."""
from django.urls import path

from . import web_views

app_name = 'catalogo_web'

urlpatterns = [
    path('', web_views.explorador, name='explorador'),
    path('<int:clip_id>/', web_views.detalle, name='detalle'),
]
