"""
URLs para Control de Gestión
"""

from django.urls import path
from . import views

app_name = "control_gestion"

urlpatterns = [
    # Vistas web
    path("mi-dia/", views.mi_dia, name="mi_dia"),
    path("equipo/", views.equipo_snapshot, name="equipo"),
    
    # Webhooks
    path("webhooks/cliente_en_sitio/", views.webhook_cliente_en_sitio, name="webhook_cliente_en_sitio"),
    path("ai/ingest_message/", views.ai_ingest_message, name="ai_ingest_message"),
    path("ai/generate_checklist/", views.ai_generate_checklist, name="ai_generate_checklist"),
    
    # Endpoints para cron externo
    path("cron/preparacion-servicios/", views.cron_preparacion_servicios, name="cron_preparacion"),
    path("cron/daily-opening/", views.cron_daily_opening, name="cron_opening"),
    path("cron/daily-reports/", views.cron_daily_reports, name="cron_reports"),
]

