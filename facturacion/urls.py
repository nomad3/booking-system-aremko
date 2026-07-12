from django.urls import path

from . import views

app_name = 'facturacion'

urlpatterns = [
    path('consulta/', views.consulta_boleta, name='consulta_boleta'),
    path('b/<str:token>/', views.boleta_por_token, name='boleta_por_token'),
]
