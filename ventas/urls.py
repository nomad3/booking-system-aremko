from django.urls import path, include
from rest_framework.routers import DefaultRouter
# Import view modules including the new admin_views
from .views import (
    api_views, availability_views, checkout_views, crud_views,
    flow_views, import_export_views, misc_views, public_views, reporting_views,
    admin_views # Import the new admin views module
)
from . import api # Keep api module import as is
# from .admin import ServicioAdmin # This import seems unused here, commenting out

# Registrar las vistas en el router de DRF
router = DefaultRouter()
router.register(r'api/proveedores', api_views.ProveedorViewSet)
router.register(r'api/categorias', api_views.CategoriaProductoViewSet)
router.register(r'api/productos', api_views.ProductoViewSet)
router.register(r'api/ventasreservas', api_views.VentaReservaViewSet)
router.register(r'api/pagos', api_views.PagoViewSet)
router.register(r'api/clientes', api_views.ClienteViewSet)
# Note: ReservaProductoViewSet and ReservaServicioViewSet were in the old views.py but not registered here.
# If they need API endpoints, they should be registered using api_views.

# Añadir las nuevas vistas a las URLs
urlpatterns = [
    path('admin-dashboard/', misc_views.inicio_sistema_view, name='inicio_sistema'),  # Vista de inicio del sistema admin
    path('', public_views.homepage_view, name='homepage'),  # Nueva vista de inicio pública
    path('categoria/<int:categoria_id>/', public_views.categoria_detail_view, name='categoria_detail'), # New category detail URL
    path('servicios-vendidos/', reporting_views.servicios_vendidos_view, name='servicios_vendidos'),
    path('caja-diaria/', reporting_views.caja_diaria_view, name='caja_diaria'),  # Nueva vista de caja diaria
    path('caja-diaria-recepcionistas/', reporting_views.caja_diaria_recepcionistas_view, name='caja_diaria_recepcionistas'), # Added path if needed
    path('auditoria-movimientos/', reporting_views.auditoria_movimientos_view, name='auditoria_movimientos'),  # Nueva vista de auditoría
    path('venta_reservas/', crud_views.venta_reserva_list, name='venta_reserva_list'),
    path('venta_reservas/<int:pk>/', crud_views.venta_reserva_detail, name='venta_reserva_detail'),
    path('compras/', crud_views.compra_list, name='compra_list'),
    path('compras/<int:pk>/', crud_views.compra_detail, name='compra_detail'),
    path('detalles-compras/', crud_views.detalle_compra_list, name='detalle_compra_list'),  # Nueva ruta
    path('detalles-compras/<int:pk>/', crud_views.detalle_compra_detail, name='detalle_compra_detail'),  # Opcional: detalle específico
    path('productos-vendidos/', reporting_views.productos_vendidos, name='productos_vendidos'),
    path('ventas/prebooking/', api.create_prebooking, name='create_prebooking'), # Keep using api module
    path('exportar-clientes/', import_export_views.exportar_clientes_excel, name='exportar_clientes_excel'),
    path('clientes/', crud_views.lista_clientes, name='lista_clientes'),
    path('importar-clientes/', import_export_views.importar_clientes_excel, name='importar_clientes_excel'),
    # Custom Views for CRM/Reporting
    path('reportes/segmentacion-clientes/', reporting_views.cliente_segmentation_view, name='cliente_segmentation'),
    path('reportes/segmentacion-clientes/<str:segment_name>/', reporting_views.client_list_by_segment_view, name='client_list_by_segment'),
    path('admin/campaign/setup/', admin_views.campaign_setup_view, name='campaign_setup_add'), # For adding new
    path('admin/campaign/setup/<int:campaign_id>/', admin_views.campaign_setup_view, name='campaign_setup_change'), # For editing existing
    path('admin/campaign/select-for-clients/', admin_views.select_campaign_for_clients_view, name='select_campaign_for_clients'),
    # Admin Section URLs
    path('admin/section/crm/', admin_views.admin_section_crm_view, name='admin_section_crm'),
    path('admin/section/ventas/', admin_views.admin_section_ventas_view, name='admin_section_ventas'),
    path('admin/section/servicios/', admin_views.admin_section_servicios_view, name='admin_section_servicios'),
    path('admin/section/productos/', admin_views.admin_section_productos_view, name='admin_section_productos'),
    path('admin/section/config/', admin_views.admin_section_config_view, name='admin_section_config'),
    # Keep existing api paths using the api module
    path('api/cliente/create/', api.create_cliente, name='create_cliente'),
    path('api/cliente/update/<str:telefono>/', api.update_cliente, name='update_cliente'),
    path('api/cliente/', api.get_cliente, name='get_clientes'),
    path('api/cliente/<str:telefono>/', api.get_cliente, name='get_cliente'),
    path('api/get-client-by-phone/', api.get_client_by_phone, name='get_client_by_phone'), # New URL for phone lookup
    # Booking process URLs
    path('get-available-hours/', availability_views.get_available_hours, name='get_available_hours'),
    path('check-availability/', availability_views.check_slot_availability, name='check_slot_availability'), # Added URL
    path('add-to-cart/', checkout_views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/', checkout_views.remove_from_cart, name='remove_from_cart'),
    path('cart/', checkout_views.cart_view, name='cart'), # Added cart view URL
    path('checkout/', checkout_views.checkout_view, name='checkout'),
    path('complete-checkout/', checkout_views.complete_checkout, name='complete_checkout'),
    # Flow Payment URLs
    path('api/flow/create/', flow_views.create_flow_payment, name='create_flow_payment'),
    path('payment/confirmation/', flow_views.flow_confirmation, name='flow_confirmation'), # Adjust path as needed
    path('payment/return/', flow_views.flow_return, name='flow_return'), # Adjust path as needed
    # New API endpoint for client lookup by phone
    path('api/get-client-details/', api_views.get_client_details_by_phone, name='get_client_details_by_phone'),
    # Removed URL for get_service_providers as it's no longer needed
    # path('api/get-service-providers/<int:servicio_id>/', api_views.get_service_providers, name='get_service_providers'),

    # --- Remarketing/Automation API URLs ---
    path('api/campaigns/<int:campaign_id>/details/', api_views.get_campaign_details, name='get_campaign_details'), # Added campaign details endpoint
    path('api/campaigns/<int:campaign_id>/targets/', api_views.get_campaign_targets, name='get_campaign_targets'),
    path('api/activities/log/', api_views.log_external_activity, name='log_external_activity'), # Logs outgoing activities
    path('api/interactions/log/', api_views.log_campaign_interaction, name='log_campaign_interaction'), # Logs incoming interactions
    # --- End Remarketing URLs ---

    # API Router (Keep this last if possible, or ensure specific paths come first)
    path('', include(router.urls)),
]
