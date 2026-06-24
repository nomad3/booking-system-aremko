from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static
# Remove direct import of ventas.views
# from ventas import views
from django.contrib.auth import views as auth_views # Import auth views
# Import the specific view functions needed for root URLs
from ventas.views.public_views import unsubscribe_view, homepage_view, empresas_view, empresas_presentacion_view, solicitar_cotizacion_empresa, tinas_view, masajes_view, alojamientos_view, productos_view, garantia_view, tarjetas_qr_reviews_view, encuesta_satisfaccion_view, encuesta_gracias_view, refugio_landing_view, refugio_submit_view, privacy_policy_view, ritual_rio_landing_view
from ventas.views import flow_views
from ventas.views import masaje_views
from ventas.views import masaje_outbox_api_views
from ventas.views import whatsapp_api_views
from ventas.views import metrics_api_views
from inbox_omnicanal import views as inbox_views
from personal_operativo import api_views as personal_operativo_api
# Removed direct import of ventas.urls

from django.contrib.sitemaps.views import sitemap
from ventas.sitemaps import (
    HomepageSitemap,
    MainPagesSitemap,
    CorporatePagesSitemap,
    CategoriaSitemap,
    RefugioLandingSitemap,
    RitualRioLandingSitemap,
)
from aremko_blog.sitemaps import AremkoBlogIndexSitemap, AremkoBlogPostSitemap
from django.views.generic import TemplateView

sitemaps = {
    'homepage': HomepageSitemap,
    'main-pages': MainPagesSitemap,
    'corporate': CorporatePagesSitemap,
    'categorias': CategoriaSitemap,
    'refugio': RefugioLandingSitemap,
    'ritual': RitualRioLandingSitemap,
    'blog_index': AremkoBlogIndexSitemap,
    'blog_posts': AremkoBlogPostSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    # Root URL pointing to the homepage view in its new location
    path('', homepage_view, name='homepage'), # Use the directly imported view
    # Direct category access (without /ventas/ prefix)
    path('tinas/', tinas_view, name='tinas'),
    path('masajes/', masajes_view, name='masajes'),
    path('alojamientos/', alojamientos_view, name='alojamientos'),
    path('productos/', productos_view, name='productos'),
    # Garantía Aremko (diferenciador único — del reporte 7 Maletas)
    path('garantia/', garantia_view, name='garantia'),

    # Política de Privacidad (ruta pública /privacidad/ — la que carga Meta).
    # Solo en el urlconf de aremko.cl; destinopuertovaras.cl usa dpv_root_urls.py.
    path('privacidad/', privacy_policy_view, name='privacidad'),

    # Conexión-Masajes: formularios públicos con token (ficha de bienestar + acompañante)
    path('masaje/ficha/<str:token>/', masaje_views.masaje_ficha, name='masaje_ficha'),
    path('masaje/acompanante/<str:token>/', masaje_views.masaje_registrar_acompanante, name='masaje_registrar_acompanante'),
    path('masaje/baja/<str:token>/', masaje_views.masaje_baja_comunicaciones, name='masaje_baja'),

    # Conexión-Masajes: bandeja de salida (consumida por aremko-cli, X-API-Key)
    path('api/masaje/outbox/', masaje_outbox_api_views.outbox_list, name='masaje_outbox_list'),
    path('api/masaje/outbox/<int:seg_id>/preview/', masaje_outbox_api_views.outbox_preview, name='masaje_outbox_preview'),
    path('api/masaje/outbox/<int:seg_id>/send/', masaje_outbox_api_views.outbox_send, name='masaje_outbox_send'),
    path('api/masaje/outbox/<int:seg_id>/cancel/', masaje_outbox_api_views.outbox_cancel, name='masaje_outbox_cancel'),
    path('api/masaje/outbox/<int:seg_id>/', masaje_outbox_api_views.outbox_edit, name='masaje_outbox_edit'),

    # WhatsApp Cloud API: persistencia de conversaciones (consumido por aremko-cli/Go).
    # Auth X-API-Key. Solo en aremko.cl.
    path('api/whatsapp/inbound', whatsapp_api_views.inbound, name='whatsapp_inbound'),
    path('api/whatsapp/inbound-media', whatsapp_api_views.inbound_media, name='whatsapp_inbound_media'),
    path('api/whatsapp/outbound', whatsapp_api_views.outbound, name='whatsapp_outbound'),
    path('api/whatsapp/outbound-media', whatsapp_api_views.outbound_media, name='whatsapp_outbound_media'),
    path('api/whatsapp/conversation/', whatsapp_api_views.conversation, name='whatsapp_conversation'),
    path('api/whatsapp/conversations/', whatsapp_api_views.conversations, name='whatsapp_conversations'),
    # Luna Interna · Fase 2: cola de notificaciones a staff (aremko-cli drena y envía)
    path('api/staff/notificaciones', personal_operativo_api.notificaciones_pendientes, name='staff_notif_pendientes'),
    path('api/staff/notificaciones/marcar', personal_operativo_api.marcar_notificaciones, name='staff_notif_marcar'),
    path('api/whatsapp/conversations/<str:phone>/marcar-atendido/', whatsapp_api_views.marcar_atendido, name='whatsapp_marcar_atendido'),
    path('api/whatsapp/conversations/<str:phone>/editar-nombre/', whatsapp_api_views.editar_nombre, name='whatsapp_editar_nombre'),
    # Agente IA WhatsApp (H-007): config singleton editable desde aremko-cli.
    path('api/whatsapp/agente/config', whatsapp_api_views.agente_config, name='whatsapp_agente_config'),
    path('api/whatsapp/agente/feedback', whatsapp_api_views.agente_feedback, name='whatsapp_agente_feedback'),
    path('api/whatsapp/agente/procesar-aprendizaje', whatsapp_api_views.agente_procesar_aprendizaje, name='whatsapp_agente_procesar_aprendizaje'),
    path('api/whatsapp/agente/sugerencias-aprendizaje', whatsapp_api_views.agente_sugerencias_aprendizaje, name='whatsapp_agente_sugerencias'),
    path('api/whatsapp/agente/sugerencias-aprendizaje/<int:sug_id>/aprobar', whatsapp_api_views.agente_sugerencia_aprobar, name='whatsapp_agente_sugerencia_aprobar'),
    path('api/whatsapp/agente/sugerencias-aprendizaje/<int:sug_id>/descartar', whatsapp_api_views.agente_sugerencia_descartar, name='whatsapp_agente_sugerencia_descartar'),
    # Verificación del Ritual del Río (página HTML, login de staff; revisar desde el celular).
    path('whatsapp/verificar-ritual/', whatsapp_api_views.verificar_ritual_view, name='whatsapp_verificar_ritual'),
    path('whatsapp/verificar-refugio/', whatsapp_api_views.verificar_refugio_view, name='whatsapp_verificar_refugio'),
    # Campaña de plantillas Meta (Vuelta a Casa): Django decide, Go envía.
    # H-012: bandeja de envíos por plantilla — aprobación antes de enviar.
    path('api/whatsapp/bandeja-envios', whatsapp_api_views.bandeja_envios_por_aprobar, name='whatsapp_bandeja_envios'),
    path('api/whatsapp/bandeja-envios/aprobar-lote', whatsapp_api_views.bandeja_envios_aprobar_lote, name='whatsapp_bandeja_envios_aprobar_lote'),
    path('api/whatsapp/bandeja-envios/<int:contacto_id>/aprobar', whatsapp_api_views.bandeja_envio_aprobar, name='whatsapp_bandeja_envio_aprobar'),
    path('api/whatsapp/bandeja-envios/<int:contacto_id>/descartar', whatsapp_api_views.bandeja_envio_descartar, name='whatsapp_bandeja_envio_descartar'),
    path('api/whatsapp/pending-template-sends', whatsapp_api_views.pending_template_sends, name='whatsapp_pending_template_sends'),
    path('api/whatsapp/mark-template-sent', whatsapp_api_views.mark_template_sent, name='whatsapp_mark_template_sent'),
    path('api/whatsapp/mark-template-failed', whatsapp_api_views.mark_template_failed, name='whatsapp_mark_template_failed'),

    # Métricas / Tablero de Evolución (H-021+H-022): agregación read-only, series semanales. X-API-Key.
    path('api/metrics/campanas', metrics_api_views.metrics_campanas, name='metrics_campanas'),
    path('api/metrics/campanas/reservas', metrics_api_views.metrics_campanas_reservas, name='metrics_campanas_reservas'),
    path('api/metrics/agente', metrics_api_views.metrics_agente, name='metrics_agente'),
    path('api/metrics/canales', metrics_api_views.metrics_canales, name='metrics_canales'),
    path('api/metrics/masajes', metrics_api_views.metrics_masajes, name='metrics_masajes'),

    # Bandeja omnicanal (H-016+H-023+H-024): Instagram DM + Messenger + reads channel-aware (WhatsApp + Instagram + Messenger).
    # Auth X-API-Key (LUNA_API_KEY). Conviven con /api/whatsapp/* legacy.
    path('api/instagram/inbound', inbox_views.instagram_inbound, name='instagram_inbound'),
    path('api/instagram/inbound-media', inbox_views.instagram_inbound_media, name='instagram_inbound_media'),
    path('api/messenger/inbound', inbox_views.messenger_inbound, name='messenger_inbound'),
    path('api/messenger/inbound-media', inbox_views.messenger_inbound_media, name='messenger_inbound_media'),
    path('api/instagram/inbound-media', inbox_views.instagram_inbound_media, name='instagram_inbound_media'),
    path('api/inbox/conversations/', inbox_views.conversations, name='inbox_conversations'),
    path('api/inbox/conversation/', inbox_views.conversation, name='inbox_conversation'),
    path('api/inbox/conversations/<str:canal>/<str:external_id>/marcar-atendido/',
         inbox_views.marcar_atendido, name='inbox_marcar_atendido'),
    path('api/inbox/media-library', inbox_views.media_library, name='inbox_media_library'),

    # Landing campaña "Refugio Aremko" (lanzamiento 15-jun-2026)
    # Alias raíz de la baja: TODOS los emails históricos llevan este link
    # (el real vive bajo /ventas/); sin esto, 'Darse de baja' daba 404.
    path('unsubscribe/<str:email>/', unsubscribe_view, name='unsubscribe_root'),
    path('refugio/', refugio_landing_view, name='refugio_landing'),
    path('refugio/submit/', refugio_submit_view, name='refugio_submit'),
    # Landing OCULTA (noindex, no enlazada, fuera del sitemap) — producto insignia ritual del río
    path('ritual-del-rio/', ritual_rio_landing_view, name='ritual_rio_landing'),
    # Tarjetas QR imprimibles para Google Reviews (asset operativo interno)
    path('tarjetas-qr-reviews/', tarjetas_qr_reviews_view, name='tarjetas_qr_reviews'),
    # Encuesta de satisfacción D+1 (Tarea 1.4 plan maestro - sistema VoC nativo)
    path('encuesta-satisfaccion/', encuesta_satisfaccion_view, name='encuesta_satisfaccion'),
    path('encuesta-gracias/', encuesta_gracias_view, name='encuesta_gracias'),
    # Corporate landing pages (direct URLs without /ventas/ prefix)
    path('empresas/', empresas_view, name='empresas'),
    path('empresas/presentacion/', empresas_presentacion_view, name='empresas_presentacion'),
    path('empresas/solicitar-cotizacion/', solicitar_cotizacion_empresa, name='solicitar_cotizacion_empresa'),
    # Flow.cl payment callbacks at root (sin prefix /ventas/)
    # Las settings FLOW_CONFIRMATION_URL y FLOW_RETURN_URL apuntan a estas
    # rutas root, asi que Flow llama a aremko.cl/payment/* directamente.
    path('payment/confirmation/', flow_views.flow_confirmation, name='flow_confirmation_root'),
    path('payment/return/', flow_views.flow_return, name='flow_return_root'),
    # Include all URLs from the ventas app under the /ventas/ prefix
    path('ventas/', include('ventas.urls')), # Rely on app_name in ventas.urls
    # Include Control de Gestión URLs
    path('control_gestion/', include('control_gestion.urls')),
    # Include Django auth urls
    path('accounts/', include('django.contrib.auth.urls')), # Provides login, logout, etc.

    # API endpoints
    path('api/', include('api.urls')),

    # DPV — Destino Puerto Varas (catálogo + conversación + webhooks)
    path('api/destino-puerto-varas/', include('destino_puerto_varas.api.urls')),

    # DPV — Sitio público (preview en infra Aremko; futuro destinopuertovaras.cl)
    path('dpv/', include('destino_puerto_varas.urls')),

    # Aremko · Blog editorial (app aislada — portable si DPV se separa después)
    path('blog/', include('aremko_blog.urls', namespace='aremko_blog')),

    # SEO endpoints
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='seo/robots.txt', content_type='text/plain'), name='robots_txt'),
    path('ai.txt', TemplateView.as_view(template_name='seo/ai.txt', content_type='text/plain'), name='ai_txt'),
    path('llm.txt', TemplateView.as_view(template_name='seo/llm.txt', content_type='text/plain'), name='llm_txt'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
