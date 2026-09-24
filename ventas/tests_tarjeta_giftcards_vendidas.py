"""Gift cards vendidas en la tarjeta móvil (Jorge, 24-09-2026, «paso 2»).

«En la tarjeta móvil debe aparecer un botón que diga ver giftcards y que al
verla permita copiar su código y también enviar la giftcard en formato pdf al
cliente comprador por whatsapp.» Decisiones del mismo día: el código queda
oculto hasta que la compra esté pagada; el envío automático al pagarse va
después, en otro deploy.

El caso que lo resume (22-09-2026): Claudia compró una Pausa junto al río para
Natalia, pagó, y escribió «Me llegó la confirmación pero no gift». Estaba en
spam. En 60 días fueron unos 6 así, y 10 PDF mandados a mano desde la bandeja.

Ejecutar:
    python manage.py test ventas.tests_tarjeta_giftcards_vendidas
"""
from __future__ import annotations

import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import Cliente, GiftCard, Pago, VentaReserva

PDF = b'%PDF-1.4 gift card de prueba'
VENTANA = 'facturacion.services.envio_whatsapp.ventana_abierta'
GENERAR_PDF = 'ventas.services.giftcard_pdf_service.GiftCardPDFService.generar_pdf_giftcard'
EMAIL = 'ventas.services.giftcard_pdf_service.GiftCardPDFService.enviar_giftcard_por_email'


def _respuesta(codigo=200):
    r = mock.Mock()
    r.status_code = codigo
    r.text = '' if codigo == 200 else 'error del backend'
    return r


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='deborah_t2', email='d2@test.cl', password='x')
        cls.claudia = Cliente.objects.create(nombre='Claudia Carrasco Baeza',
                                             telefono='+56993422409',
                                             email='claudia@test.cl')

    def setUp(self):
        self.client.force_login(self.staff)

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def _venta_de_giftcard(self, pagada=True, n=1):
        """Como las arman Luna y la web: la gift card es lo que se vende."""
        venta = VentaReserva.objects.create(cliente=self.claudia)
        cartas = [GiftCard.objects.create(
            monto_inicial=110000, monto_disponible=110000,
            fecha_vencimiento=timezone.localdate() + datetime.timedelta(days=365),
            servicio_asociado='pausa_junto_al_rio', destinatario_nombre=f'Natalia {i}',
            cliente_comprador=self.claudia, venta_reserva=venta) for i in range(n)]
        venta.calcular_total()
        venta.refresh_from_db()
        if pagada:
            # Al pagarse sale el email automático: no es el sujeto de estas pruebas.
            with mock.patch('ventas.signals.giftcard_signals.enviar_email_giftcards'):
                Pago.objects.create(venta_reserva=venta, monto=venta.total, metodo_pago='efectivo')
        for gc in cartas:
            gc.refresh_from_db()
        return venta, cartas

    def _tarjeta(self, venta):
        return self.client.get(reverse('ventas:tarjeta_reserva', args=[venta.pk])).content.decode()

    def _whatsapp(self, venta, gc, **extra):
        datos = {'giftcard_id': gc.pk}
        datos.update(extra)
        return self.client.post(reverse('ventas:tarjeta_enviar_giftcard_whatsapp',
                                        args=[venta.pk]), datos)

    def _email(self, venta, gc):
        return self.client.post(reverse('ventas:tarjeta_reenviar_giftcard_email',
                                        args=[venta.pk]), {'giftcard_id': gc.pk})


class LaTarjetaMuestraLasGiftCards(_Base):
    def test_una_venta_de_gift_card_ya_no_se_ve_vacia(self):
        venta, [gc] = self._venta_de_giftcard()
        html = self._tarjeta(venta)
        self.assertIn('Gift cards vendidas (1)', html)
        self.assertIn('Ver gift cards', html)
        self.assertIn('Natalia 0', html)
        self.assertIn(gc.codigo, html)
        self.assertIn('Copiar código', html)
        self.assertIn('Enviar PDF por WhatsApp', html)
        self.assertIn('Reenviar por email', html)

    def test_una_reserva_sin_gift_cards_no_muestra_la_seccion(self):
        venta = VentaReserva.objects.create(cliente=self.claudia)
        self.assertNotIn('id="btnVerGc"', self._tarjeta(venta))

    def test_con_la_compra_sin_pagar_el_codigo_no_aparece(self):
        venta, [gc] = self._venta_de_giftcard(pagada=False)
        html = self._tarjeta(venta)
        self.assertNotIn(gc.codigo, html)
        self.assertIn('se muestra cuando se registre el pago', html)
        self.assertNotIn('Enviar PDF por WhatsApp', html)

    def test_si_el_email_con_el_codigo_ya_salio_se_ve_aunque_la_venta_deba(self):
        venta, [gc] = self._venta_de_giftcard(pagada=False)
        GiftCard.objects.filter(pk=gc.pk).update(enviado_email=True)
        self.assertIn(gc.codigo, self._tarjeta(venta))

    def test_varias_ofrecen_enviarlas_todas(self):
        venta, _ = self._venta_de_giftcard(n=2)
        self.assertIn('Enviar todas por WhatsApp', self._tarjeta(venta))


class EnviarPorWhatsApp(_Base):
    def test_manda_el_pdf_al_comprador_y_queda_marcada(self):
        venta, [gc] = self._venta_de_giftcard()
        with mock.patch(VENTANA, return_value=True), \
             mock.patch(GENERAR_PDF, return_value=PDF), \
             mock.patch('requests.post', return_value=_respuesta()) as post:
            r = self._whatsapp(venta, gc)
        self.assertTrue(r.json()['ok'], r.json())
        post.assert_called_once()
        datos, archivos = post.call_args.kwargs['data'], post.call_args.kwargs['files']
        self.assertEqual(datos['to'], '+56993422409')
        self.assertIn('Hola Claudia', datos['caption'])
        self.assertIn('para Natalia 0', datos['caption'])
        # Nombre sin puntos de más: WhatsApp los lee como extensión (#546).
        self.assertEqual(archivos['file'], (f'giftcard-{gc.codigo}.pdf', PDF, 'application/pdf'))
        gc.refresh_from_db()
        self.assertTrue(gc.enviado_whatsapp)

    def test_fuera_de_la_ventana_no_intenta_y_lo_explica(self):
        venta, [gc] = self._venta_de_giftcard()
        with mock.patch(VENTANA, return_value=False), mock.patch('requests.post') as post:
            r = self._whatsapp(venta, gc)
        self.assertTrue(r.json()['fuera_de_ventana'])
        self.assertIn('24 horas', r.json()['mensaje'])
        post.assert_not_called()

    def test_si_ya_se_envio_pregunta_y_confirmando_la_manda(self):
        venta, [gc] = self._venta_de_giftcard()
        GiftCard.objects.filter(pk=gc.pk).update(enviado_whatsapp=True)
        with mock.patch(VENTANA, return_value=True), \
             mock.patch(GENERAR_PDF, return_value=PDF), \
             mock.patch('requests.post', return_value=_respuesta()) as post:
            r = self._whatsapp(venta, gc)
            self.assertEqual(r.status_code, 409)
            self.assertTrue(r.json()['ya_enviada'])
            post.assert_not_called()
            r = self._whatsapp(venta, gc, reenviar='1')
        self.assertTrue(r.json()['ok'])
        post.assert_called_once()

    def test_sin_pagar_no_se_manda(self):
        venta, [gc] = self._venta_de_giftcard(pagada=False)
        with mock.patch(VENTANA, return_value=True), mock.patch('requests.post') as post:
            r = self._whatsapp(venta, gc)
        self.assertEqual(r.status_code, 400)
        self.assertIn('no está pagada', r.json()['mensaje'])
        post.assert_not_called()

    def test_una_gift_card_de_otra_reserva_no_se_manda_desde_esta(self):
        _, [ajena] = self._venta_de_giftcard()
        otra, _ = self._venta_de_giftcard()
        with mock.patch(VENTANA, return_value=True), mock.patch('requests.post') as post:
            r = self._whatsapp(otra, ajena)
        self.assertEqual(r.status_code, 404)
        post.assert_not_called()

    def test_si_el_backend_falla_no_queda_como_enviada(self):
        venta, [gc] = self._venta_de_giftcard()
        with mock.patch(VENTANA, return_value=True), \
             mock.patch(GENERAR_PDF, return_value=PDF), \
             mock.patch('requests.post', return_value=_respuesta(500)):
            r = self._whatsapp(venta, gc)
        self.assertFalse(r.json()['ok'])
        gc.refresh_from_db()
        self.assertFalse(gc.enviado_whatsapp)

    def test_solo_el_equipo(self):
        venta, [gc] = self._venta_de_giftcard()
        self.client.force_login(get_user_model().objects.create_user(username='visita2', password='x'))
        with mock.patch(VENTANA, return_value=True), mock.patch('requests.post') as post:
            r = self._whatsapp(venta, gc)
        self.assertNotEqual(r.status_code, 200)
        post.assert_not_called()


class ReenviarPorEmail(_Base):
    def test_reenvia_al_correo_del_comprador(self):
        venta, [gc] = self._venta_de_giftcard()
        with mock.patch(EMAIL, return_value=True) as enviar:
            r = self._email(venta, gc)
        self.assertTrue(r.json()['ok'], r.json())
        self.assertEqual(enviar.call_args.kwargs['comprador_email'], 'claudia@test.cl')
        gc.refresh_from_db()
        self.assertTrue(gc.enviado_email)

    def test_si_el_correo_falla_lo_dice(self):
        venta, [gc] = self._venta_de_giftcard()
        with mock.patch(EMAIL, return_value=False):
            r = self._email(venta, gc)
        self.assertFalse(r.json()['ok'])

    def test_sin_pagar_tampoco(self):
        venta, [gc] = self._venta_de_giftcard(pagada=False)
        with mock.patch(EMAIL, return_value=True) as enviar:
            r = self._email(venta, gc)
        self.assertEqual(r.status_code, 400)
        enviar.assert_not_called()
