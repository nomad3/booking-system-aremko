"""
URLs para Control de Gestión
"""

from django.urls import path
from . import views

app_name = "control_gestion"

urlpatterns = [
    # Vistas (se implementarán en Etapa 4)
    # path("mi-dia/", views.mi_dia, name="mi_dia"),
    # path("equipo/", views.equipo_snapshot, name="equipo"),
    
    # Webhooks (se implementarán en Etapa 4)
    # path("webhooks/cliente_en_sitio/", views.webhook_cliente_en_sitio, name="webhook_cliente_en_sitio"),
    # path("ai/ingest_message/", views.ai_ingest_message, name="ai_ingest_message"),
    # path("ai/generate_checklist/", views.ai_generate_checklist, name="ai_generate_checklist"),
]

