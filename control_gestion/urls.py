"""
URLs para Control de Gestión
"""

from django.urls import path
from . import views, views_templates
from .views import comandas_view

app_name = "control_gestion"

urlpatterns = [
    # Vistas web
    path("mi-dia/", views.mi_dia, name="mi_dia"),
    path("equipo/", views.equipo_snapshot, name="equipo_snapshot"),
    path("indicadores/", views.indicadores, name="indicadores"),

    # Acciones rápidas (AJAX)
    path("tarea/<int:task_id>/cambiar-estado/", views.cambiar_estado_tarea, name="cambiar_estado"),

    # Tareas de emergencia
    path("emergencia/crear/", views.crear_tarea_emergencia, name="crear_tarea_emergencia"),
    
    # Gestión de plantillas (interfaz amigable)
    path("plantillas/", views_templates.plantillas_dashboard, name="plantillas_dashboard"),
    path("plantillas/crear/", views_templates.plantillas_crear, name="plantillas_crear"),
    path("plantillas/<int:plantilla_id>/editar/", views_templates.plantillas_editar, name="plantillas_editar"),
    path("plantillas/<int:plantilla_id>/toggle/", views_templates.plantillas_toggle, name="plantillas_toggle"),
    path("plantillas/<int:plantilla_id>/eliminar/", views_templates.plantillas_eliminar, name="plantillas_eliminar"),
    
    # Reportes diarios
    path("reportes/", views.reportes_diarios, name="reportes_diarios"),

    # Documentación
    path("como-usarlo/", views.como_usarlo, name="como_usarlo"),
    
    # Webhooks
    path("webhooks/cliente_en_sitio/", views.webhook_cliente_en_sitio, name="webhook_cliente_en_sitio"),
    path("ai/ingest_message/", views.ai_ingest_message, name="ai_ingest_message"),
    path("ai/generate_checklist/", views.ai_generate_checklist, name="ai_generate_checklist"),
    
    # Endpoints para cron externo
    path("cron/preparacion-servicios/", views.cron_preparacion_servicios, name="cron_preparacion"),
    path("cron/vaciado-tinas/", views.cron_vaciado_tinas, name="cron_vaciado"),
    path("cron/daily-opening/", views.cron_daily_opening, name="cron_opening"),
    path("cron/daily-reports/", views.cron_daily_reports, name="cron_reports"),

    # Gestión de Comandas para Cafetería
    path("comandas/", comandas_view.lista_comandas, name="lista_comandas"),
    path("comandas/<int:comanda_id>/", comandas_view.detalle_comanda, name="detalle_comanda"),
    path("comandas/<int:comanda_id>/estado/", comandas_view.cambiar_estado_comanda, name="cambiar_estado_comanda"),
    path("comandas/cocina/", comandas_view.comandas_cocina, name="comandas_cocina"),
    path("comandas/<int:comanda_id>/imprimir/", comandas_view.imprimir_comanda, name="imprimir_comanda"),
]

