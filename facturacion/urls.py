from django.urls import path

from . import views

app_name = 'facturacion'

urlpatterns = [
    path('consulta/', views.consulta_boleta, name='consulta_boleta'),
    path('b/<str:token>/', views.boleta_por_token, name='boleta_por_token'),
    # Staff: bajar el sobre del set para subirlo a mano al SII si hiciera falta.
    path('sobre-set/', views.descargar_sobre_set, name='descargar_sobre_set'),
    # El consumo de folios del día, para subirlo a mano junto al sobre.
    path('cof-set/', views.descargar_cof_set, name='descargar_cof_set'),
]
