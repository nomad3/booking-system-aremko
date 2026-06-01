"""
API URL Configuration
"""

from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Availability endpoints
    path('v1/availability/tinajas/', views.tinajas_availability, name='tinajas-availability'),
    path('v1/availability/masajes/', views.masajes_availability, name='masajes-availability'),
    path('v1/availability/cabanas/', views.cabanas_availability, name='cabanas-availability'),
    path('v1/availability/summary/', views.availability_summary, name='availability-summary'),

    # Leads Refugio — conteo REAL desde la BD (no el fb_pixel_lead de Meta).
    path('refugio-leads/summary/', views.refugio_leads_summary, name='refugio-leads-summary'),
]