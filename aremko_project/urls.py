from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static
# Remove direct import of ventas.views
# from ventas import views
from django.contrib.auth import views as auth_views # Import auth views
# Import the specific view functions needed for root URLs
from ventas.views.public_views import homepage_view, empresas_view, empresas_presentacion_view, solicitar_cotizacion_empresa, tinas_view, masajes_view, alojamientos_view, productos_view, garantia_view, tarjetas_qr_reviews_view, encuesta_satisfaccion_view, encuesta_gracias_view
# Removed direct import of ventas.urls

from django.contrib.sitemaps.views import sitemap
from ventas.sitemaps import (
    HomepageSitemap,
    MainPagesSitemap,
    CorporatePagesSitemap,
    CategoriaSitemap
)
from aremko_blog.sitemaps import AremkoBlogIndexSitemap, AremkoBlogPostSitemap
from django.views.generic import TemplateView

sitemaps = {
    'homepage': HomepageSitemap,
    'main-pages': MainPagesSitemap,
    'corporate': CorporatePagesSitemap,
    'categorias': CategoriaSitemap,
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
    # Tarjetas QR imprimibles para Google Reviews (asset operativo interno)
    path('tarjetas-qr-reviews/', tarjetas_qr_reviews_view, name='tarjetas_qr_reviews'),
    # Encuesta de satisfacción D+1 (Tarea 1.4 plan maestro - sistema VoC nativo)
    path('encuesta-satisfaccion/', encuesta_satisfaccion_view, name='encuesta_satisfaccion'),
    path('encuesta-gracias/', encuesta_gracias_view, name='encuesta_gracias'),
    # Corporate landing pages (direct URLs without /ventas/ prefix)
    path('empresas/', empresas_view, name='empresas'),
    path('empresas/presentacion/', empresas_presentacion_view, name='empresas_presentacion'),
    path('empresas/solicitar-cotizacion/', solicitar_cotizacion_empresa, name='solicitar_cotizacion_empresa'),
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
