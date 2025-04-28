from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static
# Remove direct import of ventas.views
# from ventas import views
from django.contrib.auth import views as auth_views # Import auth views
# Import the specific view function needed for the root URL
from ventas.views.public_views import homepage_view

urlpatterns = [
    path('admin/', admin.site.urls),
    # Root URL pointing to the homepage view in its new location
    path('', homepage_view, name='homepage'), # Use the directly imported view
    # Include all URLs from the ventas app under the /ventas/ prefix with namespace
    path('ventas/', include('ventas.urls', namespace='ventas')),
    # Include Django auth urls
    path('accounts/', include('django.contrib.auth.urls')), # Provides login, logout, etc.
    # Removed redundant URL patterns previously defined here,
    # as they are now handled within ventas.urls
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
