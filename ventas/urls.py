from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import servicios_vendidos_view, inicio_sistema_view, caja_diaria_view, auditoria_movimientos_view, venta_reserva_list, venta_reserva_detail
from . import api

# Registrar las vistas en el router de DRF
router = DefaultRouter()
router.register(r'proveedores', views.ProveedorViewSet)
router.register(r'categorias', views.CategoriaProductoViewSet)
router.register(r'productos', views.ProductoViewSet)
router.register(r'ventasreservas', views.VentaReservaViewSet)
router.register(r'pagos', views.PagoViewSet)
router.register(r'clientes', views.ClienteViewSet)

# Añadir las nuevas vistas a las URLs
urlpatterns = [
    path('', inicio_sistema_view, name='inicio_sistema'),  # Nueva vista de inicio
    path('servicios-vendidos/', servicios_vendidos_view, name='servicios_vendidos'),
    path('caja-diaria/', caja_diaria_view, name='caja_diaria'),  # Nueva vista de caja diaria
    path('auditoria-movimientos/', auditoria_movimientos_view, name='auditoria_movimientos'),  # Nueva vista de auditoría
    path('', include(router.urls)),  # Mantener las rutas del router
    path('venta_reservas/', views.venta_reserva_list, name='venta_reserva_list'),
    path('venta_reservas/<int:pk>/', views.venta_reserva_detail, name='venta_reserva_detail'),
    path('compras/', views.compra_list, name='compra_list'),
    path('compras/<int:pk>/', views.compra_detail, name='compra_detail'),
    path('detalles-compras/', views.detalle_compra_list, name='detalle_compra_list'),  # Nueva ruta
    path('detalles-compras/<int:pk>/', views.detalle_compra_detail, name='detalle_compra_detail'),  # Opcional: detalle específico
    path('productos-vendidos/', views.productos_vendidos, name='productos_vendidos'),
    path('ventas/prebooking/', api.create_prebooking, name='create_prebooking'),
    path('exportar-clientes/', views.exportar_clientes_excel, name='exportar_clientes_excel'),
    path('clientes/', views.lista_clientes, name='lista_clientes'),
]
