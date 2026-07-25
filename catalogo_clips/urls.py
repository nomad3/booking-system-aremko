from django.urls import path

from . import api_views

app_name = 'catalogo_clips'

urlpatterns = [
    path('ingesta/', api_views.catalogo_ingesta, name='catalogo_ingesta'),
    path('', api_views.catalogo_lista, name='catalogo_lista'),
    path('<int:clip_id>/', api_views.catalogo_detalle, name='catalogo_detalle'),
]
