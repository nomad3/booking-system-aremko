from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static
from ventas import views
from django.contrib.auth import views as auth_views # Import auth views
from ventas.views import (
    servicios_vendidos_view, inicio_sistema_view, caja_diaria_view,
    auditoria_movimientos_view, venta_reserva_list, venta_reserva_detail,
    homepage_view, cart_view, checkout_view, add_to_cart, remove_from_cart, get_available_hours,
    complete_checkout  # Changed 'checkout' to 'checkout_view' and added 'complete_checkout'
)

urlpatterns = [
    path('admin/', admin.site.urls),  # Esta línea es clave para registrar el namespace 'admin'
    path('', homepage_view, name='homepage'),  # Nueva vista de inicio pública
    path('admin-dashboard/', inicio_sistema_view, name='inicio_sistema'),  # Vista de inicio del sistema admin
    path('cart/', cart_view, name='cart'),  # Vista del carrito de compras
    path('checkout/', checkout_view, name='checkout'),  # Vista de la página de checkout
    path('cart/add/', add_to_cart, name='add_to_cart'),
    path('cart/remove/', remove_from_cart, name='remove_from_cart'),
    path('cart/checkout/', complete_checkout, name='checkout_api'),  # API endpoint para procesar el checkout
    path('get-available-hours/', get_available_hours, name='get_available_hours'),
    path('ventas/', include('ventas.urls')),  # Incluye las urls de la app 'ventas'
    path('servicios-vendidos/', servicios_vendidos_view, name='servicios_vendidos'),
    path('caja-diaria/', caja_diaria_view, name='caja_diaria'),  # Nueva vista de caja diaria
    path('auditoria-movimientos/', auditoria_movimientos_view, name='auditoria_movimientos'),  # Nueva vista de auditoría
    path('venta_reservas/', views.venta_reserva_list, name='venta_reserva_list'),
    path('venta_reservas/<int:pk>/', views.venta_reserva_detail, name='venta_reserva_detail'),
    path('caja_diaria_recepcionistas/', views.caja_diaria_recepcionistas_view, name='caja_diaria_recepcionistas'),
    # Add Django auth urls
    path('accounts/', include('django.contrib.auth.urls')), # Provides login, logout, etc.
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
