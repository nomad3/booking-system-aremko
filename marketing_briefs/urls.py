from django.urls import path

from . import api_views

app_name = 'marketing_briefs'

urlpatterns = [
    path('api/aremko-cli/publicaciones-semana/', api_views.publicaciones_semana, name='publicaciones_semana'),
    path('api/aremko-cli/publicaciones/<int:pub_id>/actualizar/', api_views.publicacion_actualizar, name='publicacion_actualizar'),
]
