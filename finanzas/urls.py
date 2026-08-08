from django.urls import path

from . import views

app_name = 'finanzas'

urlpatterns = [
    path('tablero/', views.tablero, name='tablero'),
    path('cargar-cartola/', views.cargar_cartola, name='cargar_cartola'),
    path('flujo-caja/', views.flujo_caja, name='flujo_caja'),
]
