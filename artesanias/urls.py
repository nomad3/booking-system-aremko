from django.urls import path

from . import views

app_name = 'artesanias'

urlpatterns = [
    path('', views.catalogo, name='catalogo'),
]
