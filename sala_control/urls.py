from django.urls import path

from . import panel

app_name = 'sala_control'

urlpatterns = [
    path('', panel.sala, name='sala'),
    path('marcar-publicacion/', panel.marcar_publicacion, name='marcar_publicacion'),
    path('agregar-nota/', panel.agregar_nota, name='agregar_nota'),
    path('alternar-nota/', panel.alternar_nota, name='alternar_nota'),
    path('alternar-prioridad/', panel.alternar_prioridad, name='alternar_prioridad'),
    path('refrescar-ads/', panel.refrescar_ads, name='refrescar_ads'),
]
