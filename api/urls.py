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
]