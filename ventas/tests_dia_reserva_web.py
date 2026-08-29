"""Reserva por la web del programa «Cabaña y spa por el día» (2026-08-29).

Nació de una venta perdida: una clienta entró a reservar y la página solo le
ofrecía WhatsApp. Este camino cobra con tarjeta, así que lo que se prueba acá
no es que "funcione": es que NO le cobre mal a nadie.

Ejecutar:
    python manage.py test ventas.tests_dia_reserva_web
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from ventas.models import Servicio
from ventas.services.pack_descuento_service import PackDescuentoService
from whatsapp_agent.packs import DIA_PRECIO_PLANO


class ArmarElPaqueteEnLaWeb(TestCase):
    def setUp(self):
        self.cab = Servicio.objects.create(nombre='Cabaña Torre', precio_base=60000,
                                           duracion=60, tipo_servicio='cabana')
        self.tina = Servicio.objects.create(nombre='Tina Calbuco', precio_base=25000,
                                            duracion=120, tipo_servicio='tina')
        self.mas = Servicio.objects.create(nombre='Masaje Relajación', precio_base=15000,
                                           duracion=50, tipo_servicio='masaje')
        self.url = reverse('dia_reservar')

    def _armado(self, servicios=None, total=DIA_PRECIO_PLANO):
        """Lo que devuelve el armador del paquete, con el total ya cuadrado.

        60.000×2 + 25.000×2 + 15.000×2 = 200.000 exactos, así que este paquete
        de prueba no necesita ítem de descuento.
        """
        return {
            'disponible': True,
            'fecha': '2026-08-31',
            'personas': 2,
            'servicios': servicios if servicios is not None else [
                {'servicio_id': self.cab.id, 'fecha': '2026-08-31',
                 'hora': '10:00', 'cantidad_personas': 2},
                {'servicio_id': self.tina.id, 'fecha': '2026-08-31',
                 'hora': '16:30', 'cantidad_personas': 2},
                {'servicio_id': self.mas.id, 'fecha': '2026-08-31',
                 'hora': '14:15', 'cantidad_personas': 2},
            ],
            'total': total,
            'cabana_id': self.cab.id,
        }

    def test_arma_el_carrito_y_cobra_exactamente_lo_prometido(self):
        with patch('whatsapp_agent.packs.construir_servicios_dia',
                   return_value=self._armado()):
            r = self.client.post(self.url, {'fecha': '31-08-2026'})

        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('ventas:checkout'))
        cart = self.client.session['cart']
        self.assertEqual(round(cart['total']), DIA_PRECIO_PLANO)
        self.assertEqual(len(cart['servicios']), 3)

    def test_la_cabaña_NO_se_cobra_por_capacidad_maxima(self):
        """El motivo por el que este camino existe: `add_to_cart` le reescribe
        a toda cabaña la cantidad de personas a su capacidad máxima (AR-014).
        Pasando por ahí, el paquete de dos personas se cobraría por cuatro o
        seis y la clienta pagaría más de lo que la página le prometió."""
        with patch('whatsapp_agent.packs.construir_servicios_dia',
                   return_value=self._armado()):
            self.client.post(self.url, {'fecha': '31-08-2026'})

        cabana = [s for s in self.client.session['cart']['servicios']
                  if s['tipo_servicio'] == 'cabana'][0]
        self.assertEqual(cabana['cantidad_personas'], 2)
        self.assertEqual(cabana['subtotal'], 120000.0)

    def test_si_el_total_no_calza_NO_la_manda_a_pagar(self):
        """Falla cerrado. Si alguien editó un precio en el admin y el paquete
        deja de sumar $200.000, mandarla al checkout sería cobrarle un monto
        que nadie le prometió. Es preferible perder la venta."""
        caro = self._armado(servicios=[
            {'servicio_id': self.cab.id, 'fecha': '2026-08-31',
             'hora': '10:00', 'cantidad_personas': 2},
            {'servicio_id': self.tina.id, 'fecha': '2026-08-31',
             'hora': '16:30', 'cantidad_personas': 2},
        ])  # suma 170.000, no 200.000
        with patch('whatsapp_agent.packs.construir_servicios_dia', return_value=caro):
            r = self.client.post(self.url, {'fecha': '31-08-2026'})

        self.assertIn('motivo=precio', r.url)
        self.assertNotIn('cart', self.client.session)

    def test_el_carrito_recuerda_que_hay_una_noche_que_bloquear(self):
        """Sin esta marca el webhook de Flow no sabría que tiene que proteger
        la víspera, y la cabaña quedaría vendible la noche anterior."""
        with patch('whatsapp_agent.packs.construir_servicios_dia',
                   return_value=self._armado()):
            self.client.post(self.url, {'fecha': '31-08-2026'})

        marca = self.client.session['cart']['dia_bloqueo']
        self.assertEqual(marca['cabana_id'], self.cab.id)
        self.assertEqual(marca['fecha'], '2026-08-31')

    def test_un_dia_que_no_se_vende_vuelve_explicando(self):
        """La base pública no dibuja los mensajes de Django: si esto redirige
        sin motivo, la clienta vuelve a la misma página sin entender nada."""
        with patch('whatsapp_agent.packs.construir_servicios_dia',
                   return_value={'disponible': False, 'fecha': '2026-09-05',
                                 'nota': 'sólo lunes, miércoles y jueves'}):
            r = self.client.post(self.url, {'fecha': '05-09-2026'})

        self.assertIn('motivo=no_disponible', r.url)
        self.assertIn('fecha=2026-09-05', r.url)

    def test_sin_fecha_no_inventa_una(self):
        r = self.client.post(self.url, {})
        self.assertIn('motivo=sin_fecha', r.url)

    def test_entrar_por_la_direccion_no_arma_nada(self):
        r = self.client.get(self.url)
        self.assertEqual(r.url, reverse('dia_landing'))
        self.assertNotIn('cart', self.client.session)


class UnPaqueteCerradoNoRecibeOtroDescuento(TestCase):
    """El precio del programa ya viene con su descuento adentro. Si además se
    le aplicara un descuento de pack, la clienta pagaría menos de lo que el
    producto vale y nadie se enteraría hasta cuadrar la caja."""

    def _cart(self, cerrado):
        cart = {'servicios': [{'id': 1, 'nombre': 'Cabaña', 'precio': 100000.0,
                               'fecha': '2026-08-31', 'hora': '10:00',
                               'cantidad_personas': 2, 'tipo_servicio': 'cabana',
                               'subtotal': 200000.0}],
                'giftcards': []}
        if cerrado:
            cart['paquete_cerrado'] = 'dia'
        return cart

    def _con_un_pack_falso(self, cart):
        from decimal import Decimal

        class _Pack:
            nombre = 'Pack inventado'

        falso = [{'pack': _Pack(), 'descuento': Decimal('30000'),
                  'items_incluidos': [0], 'descripcion_aplicacion': 'x'}]
        with patch.object(PackDescuentoService, 'detectar_packs_aplicables',
                          return_value=falso):
            return PackDescuentoService.calcular_total_con_descuentos(cart)

    def test_el_paquete_cerrado_ignora_el_pack(self):
        r = self._con_un_pack_falso(self._cart(cerrado=True))
        self.assertEqual(r['total_descuentos'], 0)
        self.assertEqual(r['total'], 200000.0)

    def test_un_carrito_normal_SI_recibe_el_pack(self):
        """La contraparte: el blindaje no puede haber apagado los descuentos
        del resto del sitio."""
        r = self._con_un_pack_falso(self._cart(cerrado=False))
        self.assertEqual(r['total_descuentos'], 30000.0)
        self.assertEqual(r['total'], 170000.0)


class LasFechasQueSeOfrecenSonVendibles(TestCase):
    """La lista del formulario y la validación del POST son dos criterios que
    tienen que decir lo mismo. Si discrepan, la forma en que se nota es la peor:
    la clienta elige un día que la página le ofreció, y la página se lo rechaza.
    """

    def test_todas_las_fechas_ofrecidas_son_lunes_miercoles_o_jueves(self):
        from datetime import date

        from whatsapp_agent.packs import DIA_DIAS_VALIDOS, _dia_semana_pack

        r = self.client.get(reverse('dia_landing'))
        fechas = r.context['fechas_vendibles']
        self.assertTrue(fechas, 'la landing no ofreció ninguna fecha')
        for f in fechas:
            d = date.fromisoformat(f['valor'])
            self.assertIn(_dia_semana_pack(d), DIA_DIAS_VALIDOS,
                          f"se ofreció {f['texto']}, que no se vende")

    def test_ninguna_fecha_ofrecida_es_hoy_ni_pasado(self):
        """Reservar para hoy a las 10:00 cuando ya son las 15:00 no es una
        venta: es un reclamo."""
        from datetime import date

        from django.utils import timezone

        hoy = timezone.localdate()
        for f in self.client.get(reverse('dia_landing')).context['fechas_vendibles']:
            self.assertGreater(date.fromisoformat(f['valor']), hoy)

    def test_la_landing_muestra_el_formulario_de_pago(self):
        html = self.client.get(reverse('dia_landing')).content.decode()
        self.assertIn(reverse('dia_reservar'), html)
        self.assertIn('csrfmiddlewaretoken', html)
        self.assertIn('Reservar y pagar', html)

    def test_sigue_ofreciendo_whatsapp(self):
        """El camino nuevo se suma, no reemplaza: hay gente que prefiere
        conversar antes de pagar."""
        html = self.client.get(reverse('dia_landing')).content.decode()
        self.assertIn('wa.me/56957902525', html)

    def test_al_volver_con_un_motivo_lo_explica(self):
        html = self.client.get(
            reverse('dia_landing') + '?motivo=no_disponible&fecha=2026-08-31'
        ).content.decode()
        self.assertIn('ya no está disponible', html)


class UnDescuentoNoOcupaUnCupo(TestCase):
    """El paquete clava el precio con una línea de descuento (un Servicio de
    precio negativo) agendada a las 10:00. La revalidación previa al cobro
    marcaba «no disponible» cualquier servicio que ya tuviera una reserva a esa
    fecha y hora — incluida esa línea.

    El daño aparecía en la SEGUNDA venta: la clienta pagaba con tarjeta y la
    reserva fallaba después, obligando a un reembolso a mano. Un descuento no
    tiene capacidad, ni pieza, ni masajista; dos ventas pueden llevar descuento
    el mismo día a la misma hora sin estorbarse.
    """

    def setUp(self):
        from ventas.models import Cliente, ReservaServicio, VentaReserva

        self.desc = Servicio.objects.create(nombre='Descuento de servicios',
                                            precio_base=-1000, duracion=0,
                                            tipo_servicio='otro')
        self.masaje = Servicio.objects.create(nombre='Masaje', precio_base=15000,
                                              duracion=50, tipo_servicio='masaje')
        cliente = Cliente.objects.create(nombre='Primera venta', telefono='+56900000001')
        venta = VentaReserva.objects.create(cliente=cliente)
        # La primera venta del día ya dejó su descuento agendado a las 10:00.
        ReservaServicio.objects.create(venta_reserva=venta, servicio=self.desc,
                                       fecha_agendamiento='2026-08-31', hora_inicio='10:00')
        self.venta, self.ReservaServicio = venta, ReservaServicio

    def _validar(self, servicio):
        from ventas.services.reservation_service import validar_disponibilidad_carrito

        return validar_disponibilidad_carrito({'servicios': [{
            'id': servicio.id, 'fecha': '2026-08-31', 'hora': '10:00',
            'cantidad_personas': 2,
        }]})

    def test_la_segunda_venta_del_dia_no_choca_con_el_descuento_de_la_primera(self):
        self.assertEqual(self._validar(self.desc), [])

    def test_un_servicio_de_verdad_SI_sigue_chocando(self):
        """La contraparte: soltar la validación de los descuentos no puede
        haber soltado la de los cupos reales, o se vendería dos veces el mismo
        masaje a la misma hora."""
        self.ReservaServicio.objects.create(
            venta_reserva=self.venta, servicio=self.masaje,
            fecha_agendamiento='2026-08-31', hora_inicio='10:00')
        self.assertEqual(len(self._validar(self.masaje)), 1)
