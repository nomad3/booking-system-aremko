"""Descontar en pesos desde la tarjeta, sin buscar el item de -1.

Jorge (05-09-2026): "cuando queremos agregar un descuento en un servicio o en
un producto, tenemos como servicio el descuento valorizado en -1 pesos y al
poner la cantidad por ejemplo 10.000 descuenta 10.000 pesos". El truco
funciona y la contabilidad lo entiende, así que NO se cambia — pero obliga a
pensar en "cantidad de personas" para rebajar plata, y en la tarjeta se leía
"Descuento_Servicios · 30000 pers.".

Acá el descuento tiene su propia puerta: se escribe el monto y listo. Y
"monto libre no más" (Jorge): no hay descuentos con nombre.

Ejecutar:
    python manage.py test ventas.tests_tarjeta_descuento
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import (Cliente, CategoriaProducto, CategoriaServicio,
                           Producto, ReservaProducto, ReservaServicio,
                           Servicio, VentaReserva)


class BaseDescuento(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='cajera_desc', email='d@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Edigmar', telefono='+56955556666')
        cat_s = CategoriaServicio.objects.create(nombre='Descuento_Servicio')
        cls.desc_serv = Servicio.objects.create(
            nombre='Descuento_Servicios', precio_base=-1, categoria=cat_s,
            duracion=0, tipo_servicio='otro', activo=True)
        cat_p = CategoriaProducto.objects.create(nombre='Descuento')
        cls.desc_prod = Producto.objects.create(
            nombre='Descuento -1', precio_base=-1, categoria=cat_p,
            cantidad_disponible=999999, venta_meson=True)
        # Un servicio normal, para que el catálogo no sea solo descuentos.
        cls.tina = Servicio.objects.create(
            nombre='Tina Hidromasaje', precio_base=40000,
            categoria=CategoriaServicio.objects.create(nombre='Tinas'),
            duracion=60, tipo_servicio='tina', activo=True)

    def setUp(self):
        self.client.force_login(self.staff)
        self.venta = VentaReserva.objects.create(cliente=self.cliente)
        self.url = reverse('ventas:tarjeta_aplicar_descuento', args=[self.venta.pk])

    def _descontar(self, monto='10000', destino='servicios'):
        return self.client.post(self.url, {'monto': monto, 'destino': destino})


class DescontarEnPesos(BaseDescuento):
    def test_descuenta_de_los_servicios(self):
        self.assertTrue(self._descontar('10000').json()['ok'])
        linea = ReservaServicio.objects.get(venta_reserva=self.venta)
        self.assertEqual(linea.servicio, self.desc_serv)
        # La CANTIDAD es el monto: así lo entiende la contabilidad hace años.
        self.assertEqual(linea.cantidad_personas, 10000)

    def test_descuenta_de_los_productos(self):
        self.assertTrue(self._descontar('5000', 'productos').json()['ok'])
        linea = ReservaProducto.objects.get(venta_reserva=self.venta)
        self.assertEqual(linea.producto, self.desc_prod)
        self.assertEqual(linea.cantidad, 5000)

    def test_el_total_baja_de_verdad(self):
        ReservaServicio.objects.create(
            venta_reserva=self.venta, servicio=self.tina,
            fecha_agendamiento=timezone.localdate(), hora_inicio='14:00',
            cantidad_personas=2, precio_unitario_venta=40000)
        self.venta.calcular_total()
        antes = int(self.venta.total)
        self._descontar('10000')
        self.venta.refresh_from_db()
        self.assertEqual(int(self.venta.total), antes - 10000)

    def test_acepta_el_monto_con_puntos(self):
        # Deborah escribe "10.000" tan naturalmente como "10000".
        self.assertTrue(self._descontar('10.000').json()['ok'])
        self.assertEqual(
            ReservaServicio.objects.get(venta_reserva=self.venta).cantidad_personas,
            10000)

    def test_devuelve_los_totales_frescos(self):
        d = self._descontar('7000').json()
        self.assertEqual(d['descuento'], 7000)
        self.assertIn('total', d)
        self.assertIn('saldo', d)


class ElMontoSaleDelPrecioPorLaCantidad(BaseDescuento):
    """Con el item de -1 el monto coincide con la cantidad y un error de
    cálculo no se nota. Los descuentos reales de Aremko son de -1000 y -500
    (reserva 6747: "59× Descuento -1000" = $59.000)."""

    def test_un_item_de_menos_1000_muestra_el_monto_correcto(self):
        mil = Producto.objects.create(
            nombre='Descuento -1000', precio_base=-1000,
            categoria=CategoriaProducto.objects.get(nombre='Descuento'),
            cantidad_disponible=99999, venta_meson=True)
        ReservaProducto.objects.create(
            venta_reserva=self.venta, producto=mil, cantidad=59,
            precio_unitario_venta=-1000)
        html = self.client.get(
            reverse('ventas:tarjeta_reserva', args=[self.venta.pk])).content.decode()
        self.assertIn('−$59.000', html)     # 59 × 1000, no "59"
        self.assertNotIn('−$59<', html)


class LoQueNoDeberiaPasar(BaseDescuento):
    def test_no_acepta_un_monto_vacio(self):
        r = self._descontar('')
        self.assertFalse(r.json()['ok'])
        self.assertEqual(ReservaServicio.objects.count(), 0)

    def test_no_acepta_texto(self):
        self.assertFalse(self._descontar('mucho').json()['ok'])
        self.assertEqual(ReservaServicio.objects.count(), 0)

    def test_no_acepta_cero_ni_negativo(self):
        self.assertFalse(self._descontar('0').json()['ok'])
        self.assertFalse(self._descontar('-5000').json()['ok'])
        self.assertEqual(ReservaServicio.objects.count(), 0)

    def test_frena_un_monto_absurdo(self):
        # El cero de más: 100.000 escrito como 10.000.000.
        r = self._descontar('10000000')
        self.assertFalse(r.json()['ok'])
        self.assertIn('demasiado', r.json()['mensaje'])
        self.assertEqual(ReservaServicio.objects.count(), 0)

    def test_avisa_claro_si_no_existe_el_item(self):
        # Si alguien borra el item de -1 en el admin, el mensaje tiene que
        # decir qué hacer, no reventar.
        self.desc_serv.delete()
        r = self._descontar('10000')
        self.assertFalse(r.json()['ok'])
        self.assertIn('admin', r.json()['mensaje'])

    def test_solo_el_personal(self):
        self.client.logout()
        r = self._descontar('10000')
        self.assertNotEqual(r.status_code, 200)
        self.assertEqual(ReservaServicio.objects.count(), 0)


class SeLeeComoPlata(BaseDescuento):
    """Jorge: "lo que nos importa es que los descuentos se lean como
    corresponde y se apliquen a la familia de servicio o de productos... ¿eso
    se ve claramente así en la ficha?".

    No se veía. En productos decía "59× Descuento -1000" —caso real de la
    reserva 6747— y en servicios el descuento arrastraba una hora sin
    sentido. La familia queda clara porque cada descuento vive en la lista de
    los suyos: el de la tina de 6 que se cobra como 5 va en SERVICIOS, el de
    los dos cafés que se cobran como uno va en PRODUCTOS.
    """

    def _tarjeta(self):
        return self.client.get(
            reverse('ventas:tarjeta_reserva', args=[self.venta.pk])
        ).content.decode()

    def test_el_descuento_de_servicios_se_lee_como_plata(self):
        self._descontar('30000')
        html = self._tarjeta()
        self.assertIn('−$30.000', html)
        self.assertNotIn('30000 pers.', html)

    def test_el_descuento_de_productos_NO_dice_10000x(self):
        # El caso real: "59× Descuento -1000" en vez de "− $59.000".
        self._descontar('59000', 'productos')
        html = self._tarjeta()
        self.assertIn('−$59.000', html)
        self.assertNotIn('59000×', html)

    def test_el_descuento_de_servicios_va_en_la_lista_de_SERVICIOS(self):
        # La familia se lee por dónde aparece: es lo que hace obvio a qué se
        # le descontó sin tener que explicarlo.
        self._descontar('30000', 'servicios')
        html = self._tarjeta()
        servicios = html.split('id="servicios"')[1].split('id="productos"')[0]
        self.assertIn('−$30.000', servicios)

    def test_el_descuento_de_productos_va_en_la_lista_de_PRODUCTOS(self):
        self._descontar('5000', 'productos')
        html = self._tarjeta()
        productos = html.split('id="listaProductos"')[1].split('id="pagos"')[0]
        self.assertIn('−$5.000', productos)

    def test_no_repite_la_palabra_servicios_dentro_de_SERVICIOS(self):
        # El item se llama "Descuento_Servicios" y el bloque ya se llama
        # SERVICIOS: decirlo dos veces solo estorba.
        self._descontar('10000')
        html = self._tarjeta()
        self.assertNotIn('Descuento_Servicios', html)
        self.assertNotIn('Descuento Servicios', html)   # ni con espacio

    def test_el_descuento_no_arrastra_una_hora_sin_sentido(self):
        # Antes mostraba "06/09 · 00:00", que no significa nada.
        self._descontar('10000')
        html = self._tarjeta()
        servicios = html.split('id="servicios"')[1].split('id="productos"')[0]
        self.assertNotIn('00:00', servicios)
        # La fila del descuento es la editable (tipo 'otro'): que no arrastre
        # ni la fecha ni la hora, que para un descuento no significan nada.
        fila = servicios.split('fila-tap')[1].split('</button>')[0]
        self.assertNotIn('class="cuando"', fila)

    def test_un_servicio_normal_sigue_diciendo_personas_y_hora(self):
        ReservaServicio.objects.create(
            venta_reserva=self.venta, servicio=self.tina,
            fecha_agendamiento=timezone.localdate(), hora_inicio='14:00',
            cantidad_personas=2, precio_unitario_venta=40000)
        html = self._tarjeta()
        self.assertIn('2 pers.', html)
        self.assertIn('14:00', html)

    def test_un_producto_normal_sigue_diciendo_2x(self):
        cafe = Producto.objects.create(
            nombre='Café Americano', precio_base=2500,
            categoria=CategoriaProducto.objects.create(nombre='Cafetería'),
            cantidad_disponible=50, venta_meson=True)
        ReservaProducto.objects.create(
            venta_reserva=self.venta, producto=cafe, cantidad=2,
            precio_unitario_venta=2500)
        self.assertIn('2× Café Americano', self._tarjeta())

    def test_la_tarjeta_ofrece_el_boton(self):
        self.assertIn('Aplicar descuento', self._tarjeta())
