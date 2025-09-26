from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static
# Remove direct import of ventas.views
# from ventas import views
from django.contrib.auth import views as auth_views # Import auth views
# Import the specific view function needed for the root URL
from ventas.views.public_views import homepage_view
# Removed direct import of ventas.urls

from django.contrib.sitemaps.views import sitemap
from ventas.sitemaps import StaticSitemap, CategoriaSitemap
from django.views.generic import TemplateView

sitemaps = {
    'static': StaticSitemap,
    'categorias': CategoriaSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    # Root URL pointing to the homepage view in its new location
    path('', homepage_view, name='homepage'), # Use the directly imported view
    # Include all URLs from the ventas app under the /ventas/ prefix
    path('ventas/', include('ventas.urls')), # Rely on app_name in ventas.urls
    # Include Django auth urls
    path('accounts/', include('django.contrib.auth.urls')), # Provides login, logout, etc.

    # SEO endpoints
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='seo/robots.txt', content_type='text/plain'), name='robots_txt'),
    path('ai.txt', TemplateView.as_view(template_name='seo/ai.txt', content_type='text/plain'), name='ai_txt'),
    path('llm.txt', TemplateView.as_view(template_name='seo/llm.txt', content_type='text/plain'), name='llm_txt'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
