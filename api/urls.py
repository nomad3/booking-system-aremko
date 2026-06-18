"""
API URL Configuration
"""

from django.urls import path
from . import views
from ventas.views import luna_api_views

app_name = 'api'

urlpatterns = [
    # Availability endpoints
    path('v1/availability/tinajas/', views.tinajas_availability, name='tinajas-availability'),
    path('v1/availability/masajes/', views.masajes_availability, name='masajes-availability'),
    path('v1/availability/cabanas/', views.cabanas_availability, name='cabanas-availability'),
    path('v1/availability/summary/', views.availability_summary, name='availability-summary'),

    # Leads Refugio — conteo REAL desde la BD (no el fb_pixel_lead de Meta).
    path('refugio-leads/summary/', views.refugio_leads_summary, name='refugio-leads-summary'),
    # H-002: listado de leads (formulario + WhatsApp [Refugio]) para CPL real y Etapa 4b.
    path('refugio-leads/', views.refugio_leads_list, name='refugio-leads-list'),

    # H-028: Resumen de reserva para agente Luna
    path('v1/resumen-reserva/<int:reserva_id>/', views.resumen_reserva_json, name='resumen-reserva-json'),

    # Luna AI API (agente de WhatsApp)
    path('luna/test/', luna_api_views.test_connection, name='luna-test'),
    path('luna/health/', luna_api_views.health_check, name='luna-health'),
    path('luna/regiones/', luna_api_views.listar_regiones, name='luna-regiones'),
    path('luna/cliente/', luna_api_views.lookup_cliente, name='luna-lookup-cliente'),
    path('luna/reservas/validar/', luna_api_views.validar_disponibilidad, name='luna-validar-disponibilidad'),
    path('luna/reservas/create/', luna_api_views.crear_reserva, name='luna-crear-reserva'),
    path('luna/reservas/<int:reserva_id>/servicios/', luna_api_views.agregar_servicios_reserva, name='luna-agregar-servicios'),
]