"""Rutas WEB del catálogo (H-071 B1) — separadas de urls.py (la API X-API-KEY)
para poder montarlas en /marketing/catalogo/ sin chocar de namespace."""
from django.urls import path

from . import web_views

app_name = 'catalogo_web'

urlpatterns = [
    path('', web_views.explorador, name='explorador'),
    path('ingesta/', web_views.ingesta_web, name='ingesta'),
    path('ingesta/guardar/', web_views.ingesta_guardar, name='ingesta_guardar'),
    path('componer/<int:clip_id>/', web_views.componer, name='componer'),
    path('componer/<int:clip_id>/enganchar/', web_views.enganchar_publicacion, name='enganchar'),
    path('auto-generar/', web_views.auto_generar, name='auto_generar'),
    path('<int:clip_id>/', web_views.detalle, name='detalle'),
]
