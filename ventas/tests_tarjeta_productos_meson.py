"""En la tarjeta, «Agregar producto» ofrece SOLO los de venta en mesón.

Pedido de Jorge (01-09-2026). La tarjeta es la herramienta del mesón; el campo
`comanda_cliente` es otra cosa: el menú público que el cliente ve en su link.
Mezclarlos alargaba la lista con productos que ahí no se venden.

La lista y la guarda del servidor tienen que decir lo MISMO: si el selector
ofrece una cosa y el guardado acepta otra, el error aparece recién al guardar.

Ejecutar:
    python manage.py test ventas.tests_tarjeta_productos_meson
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ventas.models import Cliente, Producto, ReservaProducto, VentaReserva


class SoloProductosDeMeson(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='tarjeta_prod', email='s@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Betty', telefono='+56911111111')
        cls.venta = VentaReserva.objects.create(cliente=cliente)

        cls.espumante = Producto.objects.create(
            nombre='Espumante', precio_base=18000, cantidad_disponible=10,
            venta_meson=True, comanda_cliente=False)
        cls.jugo = Producto.objects.create(
            nombre='Jugo natural', precio_base=3500, cantidad_disponible=10,
            venta_meson=False, comanda_cliente=True)
        cls.insumo = Producto.objects.create(
            nombre='Cloro piscina', precio_base=9000, cantidad_disponible=10,
            venta_meson=False, comanda_cliente=False)
        cls.agotado = Producto.objects.create(
            nombre='Vino agotado', precio_base=12000, cantidad_disponible=0,
            venta_meson=True, comanda_cliente=False)

    def setUp(self):
        self.client.force_login(self.staff)

    def _catalogo(self):
        r = self.client.get(reverse('ventas:tarjeta_reserva', args=[self.venta.pk]))
        return [p.nombre for p in r.context['catalogo']]

    def test_ofrece_los_de_meson(self):
        self.assertIn('Espumante', self._catalogo())

    def test_no_ofrece_los_del_menu_del_cliente(self):
        # El jugo se vende, pero por el link del cliente: en el mesón no va.
        self.assertNotIn('Jugo natural', self._catalogo())

    def test_no_ofrece_insumos_internos(self):
        self.assertNotIn('Cloro piscina', self._catalogo())

    def test_no_ofrece_lo_agotado(self):
        self.assertNotIn('Vino agotado', self._catalogo())

    def test_lo_ya_guardado_en_la_reserva_sigue_apareciendo(self):
        # Si no, abrir una reserva antigua con un producto descatalogado
        # reventaría al guardar con «Escoja una opción válida».
        ReservaProducto.objects.create(venta_reserva=self.venta,
                                       producto=self.jugo, cantidad=1)
        self.assertIn('Jugo natural', self._catalogo())

    def test_el_servidor_rechaza_lo_que_no_es_de_meson(self):
        # La lista y la guarda tienen que decir lo mismo, incluso si alguien
        # dejó la pestaña abierta desde antes del cambio.
        r = self.client.post(
            reverse('ventas:tarjeta_agregar_producto', args=[self.venta.pk]),
            {'producto_id': self.jugo.pk, 'cantidad': '1'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('venta en mesón', r.json()['mensaje'])

    def test_el_servidor_acepta_uno_de_meson(self):
        r = self.client.post(
            reverse('ventas:tarjeta_agregar_producto', args=[self.venta.pk]),
            {'producto_id': self.espumante.pk, 'cantidad': '2'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        self.assertTrue(ReservaProducto.objects.filter(
            venta_reserva=self.venta, producto=self.espumante).exists())
