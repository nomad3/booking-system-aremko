"""Tests de CarritoService — foco en obtener_productos_pendientes/limpiar_productos
(H-044: fusión de productos sueltos del carrito en propuestas de Ritual/Refugio, que
arman su cotización AFUERA del carrito). Caso real que motivó el fix: 2026-07-21,
cliente agregó una tabla de quesos vía chat, la tabla quedó huérfana en el carrito
porque el Ritual del Río nunca llegó a crear la propuesta con esos productos.
"""
from django.test import TestCase

from ventas.models import Producto
from .models import CarritoReserva
from .services import CarritoService


class ObtenerProductosPendientesTests(TestCase):

    def test_carrito_inexistente_devuelve_lista_vacia(self):
        """Si aún no hay carrito para esa conversación, se crea vacío y no hay productos."""
        productos = CarritoService.obtener_productos_pendientes('whatsapp', '+56900000001')
        self.assertEqual(productos, [])

    def test_solo_extrae_items_tipo_producto(self):
        carrito = CarritoReserva.objects.create(
            canal='whatsapp', external_id='+56900000002',
            items=[
                {'tipo': 'servicio', 'servicio_id': 10, 'nombre': 'Tina X',
                 'fecha': '2026-09-06', 'hora': '17:00', 'cantidad_personas': 2,
                 'precio_unitario': 30000, 'subtotal': 60000},
                {'tipo': 'producto', 'producto_id': 5, 'nombre': 'Tabla Mixta',
                 'cantidad': 1, 'precio_unitario': 36000, 'subtotal': 36000},
            ],
        )
        productos = CarritoService.obtener_productos_pendientes('whatsapp', carrito.external_id)
        self.assertEqual(productos, [{'producto_id': 5, 'cantidad': 1}])

    def test_varios_productos_mantiene_orden_y_cantidad(self):
        carrito = CarritoReserva.objects.create(
            canal='whatsapp', external_id='+56900000003',
            items=[
                {'tipo': 'producto', 'producto_id': 5, 'nombre': 'Tabla Mixta',
                 'cantidad': 1, 'precio_unitario': 36000, 'subtotal': 36000},
                {'tipo': 'producto', 'producto_id': 7, 'nombre': 'Jugo Natural',
                 'cantidad': 3, 'precio_unitario': 4000, 'subtotal': 12000},
            ],
        )
        productos = CarritoService.obtener_productos_pendientes('whatsapp', carrito.external_id)
        self.assertEqual(productos, [
            {'producto_id': 5, 'cantidad': 1},
            {'producto_id': 7, 'cantidad': 3},
        ])

    def test_no_muta_el_carrito(self):
        """Es un peek de solo lectura — llamar esto NO debe vaciar el carrito.
        (La limpieza es responsabilidad explícita de limpiar_productos, y solo debe
        pasar DESPUÉS de confirmar que la propuesta se creó bien.)"""
        carrito = CarritoReserva.objects.create(
            canal='whatsapp', external_id='+56900000004',
            items=[{'tipo': 'producto', 'producto_id': 5, 'nombre': 'Tabla Mixta',
                    'cantidad': 1, 'precio_unitario': 36000, 'subtotal': 36000}],
        )
        CarritoService.obtener_productos_pendientes('whatsapp', carrito.external_id)
        carrito.refresh_from_db()
        self.assertEqual(len(carrito.items), 1)


class LimpiarProductosTests(TestCase):

    def test_quita_solo_los_productos_deja_servicios(self):
        carrito = CarritoReserva.objects.create(
            canal='whatsapp', external_id='+56900000005',
            items=[
                {'tipo': 'servicio', 'servicio_id': 10, 'nombre': 'Tina X',
                 'fecha': '2026-09-06', 'hora': '17:00', 'cantidad_personas': 2,
                 'precio_unitario': 30000, 'subtotal': 60000},
                {'tipo': 'producto', 'producto_id': 5, 'nombre': 'Tabla Mixta',
                 'cantidad': 1, 'precio_unitario': 36000, 'subtotal': 36000},
            ],
        )
        CarritoService.limpiar_productos('whatsapp', carrito.external_id)
        carrito.refresh_from_db()
        self.assertEqual(len(carrito.items), 1)
        self.assertEqual(carrito.items[0]['tipo'], 'servicio')

    def test_recalcula_totales_tras_limpiar(self):
        carrito = CarritoReserva.objects.create(
            canal='whatsapp', external_id='+56900000006',
            items=[
                {'tipo': 'servicio', 'servicio_id': 10, 'nombre': 'Tina X',
                 'fecha': '2026-09-06', 'hora': '17:00', 'cantidad_personas': 2,
                 'precio_unitario': 30000, 'subtotal': 60000},
                {'tipo': 'producto', 'producto_id': 5, 'nombre': 'Tabla Mixta',
                 'cantidad': 1, 'precio_unitario': 36000, 'subtotal': 36000},
            ],
        )
        CarritoService._recalcular_totales(carrito)  # estado inicial, como haría agregar_*
        self.assertEqual(int(carrito.total), 96000)

        CarritoService.limpiar_productos('whatsapp', carrito.external_id)
        carrito.refresh_from_db()
        self.assertEqual(int(carrito.subtotal_productos), 0)
        self.assertEqual(int(carrito.total), 60000)

    def test_carrito_sin_productos_no_falla_y_no_toca_items(self):
        carrito = CarritoReserva.objects.create(
            canal='whatsapp', external_id='+56900000007',
            items=[{'tipo': 'servicio', 'servicio_id': 10, 'nombre': 'Tina X',
                    'fecha': '2026-09-06', 'hora': '17:00', 'cantidad_personas': 2,
                    'precio_unitario': 30000, 'subtotal': 60000}],
        )
        CarritoService.limpiar_productos('whatsapp', carrito.external_id)  # no debe lanzar
        carrito.refresh_from_db()
        self.assertEqual(len(carrito.items), 1)

    def test_carrito_vacio_no_falla(self):
        CarritoService.limpiar_productos('whatsapp', '+56900000008')  # carrito recién creado, sin items


class FlujoRealAgregarYFusionarTests(TestCase):
    """End-to-end con el mismo camino que usa Luna de verdad: CarritoService.agregar_producto
    (el que llama la tool agregar_producto_carrito) → obtener_productos_pendientes →
    limpiar_productos. Reproduce el caso real de Paulina (2026-07-21)."""

    def setUp(self):
        self.producto = Producto.objects.create(
            nombre='Tabla Mixta de Quesos y Jamones',
            precio_base=36000,
            cantidad_disponible=10,
            publicado_web=True,
        )

    def test_producto_agregado_antes_de_la_propuesta_se_puede_fusionar_y_limpiar(self):
        canal, external_id = 'whatsapp', '+56999621500'

        resultado = CarritoService.agregar_producto(canal, external_id, self.producto.id, 1)
        self.assertTrue(resultado['success'])

        # Esto es lo que haría confirmar_ritual/confirmar_refugio antes de armar el payload.
        productos = CarritoService.obtener_productos_pendientes(canal, external_id)
        self.assertEqual(productos, [{'producto_id': self.producto.id, 'cantidad': 1}])

        # Y esto, después de un preparar_reserva exitoso.
        CarritoService.limpiar_productos(canal, external_id)
        carrito = CarritoReserva.obtener_o_crear(canal, external_id)
        self.assertEqual(carrito.items, [])
        self.assertEqual(int(carrito.total), 0)

        # Si el cliente agrega otro producto después, el carrito vuelve a funcionar normal
        # (no quedó en un estado raro tras la limpieza).
        resultado2 = CarritoService.agregar_producto(canal, external_id, self.producto.id, 2)
        self.assertTrue(resultado2['success'])
        carrito.refresh_from_db()
        self.assertEqual(len(carrito.items), 1)
        self.assertEqual(carrito.items[0]['cantidad'], 2)
