from django.urls import path

from . import api_views

app_name = 'marketing_briefs'

urlpatterns = [
    path('api/aremko-cli/publicaciones-semana/', api_views.publicaciones_semana, name='publicaciones_semana'),
    path('api/aremko-cli/publicaciones/<int:pub_id>/', api_views.publicacion_detalle, name='publicacion_detalle'),
    path('api/aremko-cli/publicaciones/<int:pub_id>/actualizar/', api_views.publicacion_actualizar, name='publicacion_actualizar'),
    path('api/aremko-cli/publicaciones/<int:pub_id>/material/', api_views.publicacion_material, name='publicacion_material'),
]
