# -*- coding: utf-8 -*-
"""Agregados dentro del regalo (Jorge, 2026-08-12).

«Nos ha pasado varias veces que una persona regala una estadía para sus padres
o una pausa junto al río y agrega una tabla o jugos. En tal caso eso debería
estar en la descripción de la experiencia que se regala.»

Las dos reglas que fijó:
  1. Con UNA sola gift card, los agregados van DENTRO de la carta y la carta
     lo dice. Se facturan al comprar y se entregan al canjear.
  2. Con VARIAS gift cards no se agregan productos: esas ventas van simples.

Y de paso lo que apareció al mirar el código: una venta SOLO de gift cards con
productos reventaba con IndexError al aprobarla (la comanda buscaba la fecha
del primer servicio, y no había servicios).
"""
from django.test import TestCase, override_settings
from django.utils import timezone

from ventas.models import (Cliente, Comanda, GiftCard, GiftCardExperiencia,
                           Producto, ReservaProducto, VentaReserva)
from whatsapp_agent.giftcards import (cartas_en_payload, materializar_giftcards,
                                      preparar_giftcard, texto_incluye)
from whatsapp_agent.models import PropuestaReserva
from whatsapp_agent.reserva_service import agregar_producto_a_propuesta

from .test_giftcards_luna import CLIENTE, _SinSenalesDeVenta, _experiencia


def _producto(nombre='Jugo Natural de Frambuesa', precio=4000):
    return Producto.objects.create(
        nombre=nombre, precio_base=precio, cantidad_disponible=50,
        publicado_web=True)


class TextoIncluyeTest(TestCase):
    """La línea que lee quien recibe el regalo."""

    def test_arma_la_linea_con_cantidad_y_nombre(self):
        jugo = _producto()
        self.assertEqual(
            texto_incluye([{'producto_id': jugo.id, 'cantidad': 2}]),
            'Incluye: 2 Jugo Natural de Frambuesa')

    def test_varios_productos_van_separados(self):
        jugo = _producto()
        tabla = _producto('Tabla de Quesos', 20000)
        self.assertEqual(
            texto_incluye([{'producto_id': jugo.id, 'cantidad': 2},
                           {'producto_id': tabla.id, 'cantidad': 1}]),
            'Incluye: 2 Jugo Natural de Frambuesa · 1 Tabla de Quesos')

    def test_sin_productos_no_hay_linea(self):
        self.assertEqual(texto_incluye([]), '')
        self.assertEqual(texto_incluye(None), '')

    def test_un_producto_borrado_no_tumba_la_venta(self):
        jugo = _producto()
        self.assertEqual(
            texto_incluye([{'producto_id': jugo.id, 'cantidad': 1},
                           {'producto_id': 999999, 'cantidad': 1}]),
            'Incluye: 1 Jugo Natural de Frambuesa')

    def test_cuenta_cartas_por_unidad_no_por_linea(self):
        """Una línea con cantidad 2 son DOS cartas."""
        self.assertEqual(cartas_en_payload({'giftcards': [{'cantidad': 2}]}), 2)
        self.assertEqual(
            cartas_en_payload({'giftcards': [{'cantidad': 1}, {}]}), 2)
        self.assertEqual(cartas_en_payload({}), 0)


@override_settings(LUNA_API_KEY='clave-test')
class RegalaConAgregadosTest(_SinSenalesDeVenta, TestCase):
    """El caso de Jorge, de punta a punta."""

    def setUp(self):
        super().setUp()
        _experiencia(id_exp='masaje_pareja', nombre='Masaje para Dos',
                     monto_fijo=80000)
        self.jugo = _producto()

    def _propuesta_con_jugo(self, cantidad_cartas=1, jugos=2):
        prep = preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=dict(CLIENTE),
            historial=('[Cliente]: para Alda\n'
                       '[Cliente]: que la quiero mucho\n'),
            giftcards_data=[{'experiencia_id': 'masaje_pareja',
                             'cantidad': cantidad_cartas,
                             'destinatario_nombre': 'Alda',
                             'mensaje': 'Que la quiero mucho'}])
        self.assertTrue(prep['success'], prep)
        sumado = agregar_producto_a_propuesta(
            canal='whatsapp', external_id='+56911111111',
            producto_id=self.jugo.id, cantidad=jugos)
        return prep, sumado

    def _aprobar(self, propuesta_id):
        return self.client.post(
            '/api/luna/reservas/create/', {'propuesta_id': propuesta_id},
            content_type='application/json', HTTP_X_API_KEY='clave-test')

    def test_una_carta_con_jugos_los_lleva_adentro(self):
        prep, sumado = self._propuesta_con_jugo()
        self.assertTrue(sumado['success'], sumado)
        # El total de la cotización ya trae los jugos.
        self.assertEqual(sumado['total'], 80000 + 4000 * 2)

        r = self._aprobar(prep['propuesta_id'])
        self.assertEqual(r.status_code, 201, r.content)
        venta = VentaReserva.objects.get(id=r.json()['reserva']['id'])

        carta = venta.giftcards.get()
        self.assertEqual(carta.detalle_especial,
                         'Incluye: 2 Jugo Natural de Frambuesa')
        # Se cobran: la línea de facturación existe...
        self.assertEqual(venta.reservaproductos.count(), 1)
        self.assertEqual(int(venta.total), 88000)
        # ...pero NO se manda nada a cocina: se preparan el día del canje, que
        # puede ser en 11 meses.
        self.assertFalse(Comanda.objects.filter(venta_reserva=venta).exists())

    def test_aprobar_una_venta_solo_giftcards_con_productos_no_revienta(self):
        """Antes del 2026-08-12 esto era un IndexError: el bloque de comanda
        ordenaba `servicios_data` y tomaba el [0] de una lista vacía. La venta
        entera moría al aprobarla."""
        prep, _ = self._propuesta_con_jugo()
        r = self._aprobar(prep['propuesta_id'])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()['success'])

    def test_con_varias_cartas_no_se_agregan_productos(self):
        prep, sumado = self._propuesta_con_jugo(cantidad_cartas=2)
        self.assertFalse(sumado['success'], sumado)
        self.assertEqual(sumado['error'], 'giftcards_no_admiten_agregados')
        # Y la cotización quedó intacta: dos cartas, sin jugos ni total inflado.
        prop = PropuestaReserva.objects.get(propuesta_id=prep['propuesta_id'])
        self.assertEqual(int(prop.total), 160000)
        self.assertFalse(prop.payload.get('productos'))

    def test_sin_agregados_la_carta_no_dice_nada(self):
        """Ninguna carta debe salir con un «Incluye:» vacío o inventado."""
        venta = VentaReserva.objects.create(
            cliente=Cliente.objects.create(nombre='María', telefono='+56911111111'),
            total=0, fecha_reserva=timezone.now())
        materializar_giftcards(
            venta, {'cliente': dict(CLIENTE),
                    'giftcards': [{'experiencia_id': 'masaje_pareja',
                                   'precio': 80000, 'cantidad': 1}]},
            venta.cliente)
        self.assertEqual(venta.giftcards.get().detalle_especial, '')

    def test_dos_cartas_nunca_reciben_el_texto(self):
        """Defensa en profundidad: aunque llegara un payload con productos y
        dos cartas (regla 2 saltada), no se reparte nada."""
        venta = VentaReserva.objects.create(
            cliente=Cliente.objects.create(nombre='María', telefono='+56911111112'),
            total=0, fecha_reserva=timezone.now())
        materializar_giftcards(
            venta, {'cliente': dict(CLIENTE),
                    'giftcards': [{'experiencia_id': 'masaje_pareja',
                                   'precio': 80000, 'cantidad': 2}],
                    'productos': [{'producto_id': self.jugo.id, 'cantidad': 2}]},
            venta.cliente)
        self.assertEqual(venta.giftcards.count(), 2)
        for carta in venta.giftcards.all():
            self.assertEqual(carta.detalle_especial, '')


class SeVeEnElPaseYEnLaCartaTest(_SinSenalesDeVenta, TestCase):

    def _venta_con_carta(self, incluye):
        _experiencia(id_exp='masaje_pareja', nombre='Masaje para Dos',
                     monto_fijo=80000)
        cliente = Cliente.objects.create(nombre='María', telefono='+56911111111')
        venta = VentaReserva.objects.create(cliente=cliente, total=0,
                                            fecha_reserva=timezone.now())
        carta = GiftCard.objects.create(
            monto_inicial=80000, monto_disponible=80000,
            fecha_vencimiento=timezone.now().date().replace(year=2027),
            estado='por_cobrar', cliente_comprador=cliente, venta_reserva=venta,
            destinatario_nombre='Alda', servicio_asociado='masaje_pareja',
            detalle_especial=incluye)
        venta.calcular_total()
        return venta, carta

    def test_el_pase_muestra_lo_que_incluye(self):
        from ventas.views.ficha_reserva_view import token_para_reserva
        venta, _ = self._venta_con_carta('Incluye: 2 Jugo Natural de Frambuesa')
        r = self.client.get(f'/ventas/reserva/{token_para_reserva(venta.id)}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Incluye: 2 Jugo Natural de Frambuesa')

    def test_la_carta_que_recibe_la_persona_lo_muestra(self):
        _venta, carta = self._venta_con_carta('Incluye: 2 Jugo Natural de Frambuesa')
        r = self.client.get(f'/ventas/giftcard/{carta.codigo}/view/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Incluye: 2 Jugo Natural de Frambuesa')

    def test_sin_agregados_la_carta_no_muestra_la_seccion(self):
        _venta, carta = self._venta_con_carta('')
        r = self.client.get(f'/ventas/giftcard/{carta.codigo}/view/')
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Además')


class ReglaEnElPromptTest(TestCase):
    """Luna tiene que poder explicar las dos reglas sin inventarlas."""

    def _fuente(self):
        import whatsapp_agent.prompt as prompt_mod
        return open(prompt_mod.__file__, encoding='utf-8').read()

    def test_el_prompt_dice_que_mis_papas_es_una_sola_carta(self):
        fuente = self._fuente()
        self.assertIn('mis papás', fuente)
        self.assertIn('NO son dos cartas', fuente)

    def test_el_prompt_dice_que_con_varias_cartas_no_hay_agregados(self):
        fuente = self._fuente()
        self.assertIn('Agregados a un regalo', fuente)
        self.assertIn('VARIAS gift cards, no se', fuente)
