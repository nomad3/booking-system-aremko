"""El PDF de la gift card sale solo por WhatsApp al registrarse el pago (2b).

Jorge (24-09-2026): «ok» a que, como la boleta, la gift card le llegue al
comprador por WhatsApp apenas se registra el pago, si está conversando. Es el
momento en que más sirve: Claudia (22-09) escribió «Me llegó la confirmación
pero no gift» minutos después de pagar; estaba en spam.

Reglas: solo con la venta pagada ENTERA (la regla del código en la tarjeta),
solo si el comprador escribió en las últimas 24 horas, una sola vez, y nada de
esto puede voltear el cobro.

Ejecutar:
    python manage.py test ventas.tests_giftcard_envio_al_pagar
"""
from __future__ import annotations

import datetime
import inspect
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from ventas.models import Cliente, GiftCard, Pago, VentaReserva

PDF = b'%PDF-1.4 gift card'
VENTANA = 'facturacion.services.envio_whatsapp.ventana_abierta'
GENERAR_PDF = 'ventas.services.giftcard_pdf_service.GiftCardPDFService.generar_pdf_giftcard'
EMAIL = 'ventas.signals.giftcard_signals.enviar_email_giftcards'


# Se reemplaza SOLO el envío de WhatsApp: al registrar un pago corren otras
# señales (avisos, Meta) que también usan requests, y no son el sujeto acá.
ENVIAR = 'facturacion.services.envio_whatsapp.enviar_documento'
OK = (True, 'enviado')
FALLA = (False, 'el backend respondió 500')


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.claudia = Cliente.objects.create(nombre='Claudia Carrasco', telefono='+56993422409',
                                             email='claudia@test.cl')

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def _venta(self, monto=110000):
        venta = VentaReserva.objects.create(cliente=self.claudia)
        gc = GiftCard.objects.create(
            monto_inicial=monto, monto_disponible=monto,
            fecha_vencimiento=timezone.localdate() + datetime.timedelta(days=365),
            servicio_asociado='pausa_junto_al_rio', destinatario_nombre='Natalia',
            cliente_comprador=self.claudia, venta_reserva=venta)
        venta.calcular_total()
        venta.refresh_from_db()
        return venta, gc

    def _pagar(self, venta, monto=None, ventana=True, respuesta=OK, pdf=PDF):
        """Registra el pago como lo hacen la tarjeta y el admin, y corre lo que
        queda agendado para después de confirmarlo."""
        generar = (mock.patch(GENERAR_PDF, side_effect=pdf) if callable(pdf)
                   else mock.patch(GENERAR_PDF, return_value=pdf))
        with mock.patch(EMAIL), mock.patch(VENTANA, return_value=ventana), generar, \
             mock.patch(ENVIAR, return_value=respuesta) as enviar, \
             self.captureOnCommitCallbacks(execute=True):
            Pago.objects.create(venta_reserva=venta, monto=monto or venta.total,
                                metodo_pago='transferencia')
        return enviar


class AlPagarseSaleSola(_Base):
    def test_pago_completo_y_conversando_el_pdf_sale_solo(self):
        venta, gc = self._venta()
        enviar = self._pagar(venta)
        enviar.assert_called_once()
        telefono, contenido, archivo, texto = enviar.call_args.args
        self.assertEqual(telefono, '+56993422409')
        self.assertEqual(contenido, PDF)
        self.assertEqual(archivo, f'giftcard-{gc.codigo}.pdf')
        self.assertIn('Hola Claudia', texto)
        gc.refresh_from_db()
        self.assertTrue(gc.enviado_whatsapp)

    def test_si_no_conversa_hace_24_horas_queda_el_email(self):
        venta, gc = self._venta()
        enviar = self._pagar(venta, ventana=False)
        enviar.assert_not_called()
        gc.refresh_from_db()
        self.assertFalse(gc.enviado_whatsapp)

    def test_con_un_pago_parcial_no_sale(self):
        venta, gc = self._venta()
        enviar = self._pagar(venta, monto=10000)
        enviar.assert_not_called()

    def test_la_que_ya_se_envio_no_se_repite(self):
        venta, gc = self._venta()
        GiftCard.objects.filter(pk=gc.pk).update(enviado_whatsapp=True)
        enviar = self._pagar(venta)
        enviar.assert_not_called()

    def test_una_reserva_sin_gift_cards_no_manda_nada(self):
        venta = VentaReserva.objects.create(cliente=self.claudia)
        with mock.patch(ENVIAR) as enviar, self.captureOnCommitCallbacks(execute=True):
            Pago.objects.create(venta_reserva=venta, monto=10000, metodo_pago='efectivo')
        enviar.assert_not_called()


class NuncaTumbaElCobro(_Base):
    def test_si_whatsapp_falla_el_pago_queda_y_no_se_marca(self):
        venta, gc = self._venta()
        self._pagar(venta, respuesta=FALLA)
        self.assertTrue(Pago.objects.filter(venta_reserva=venta).exists())
        gc.refresh_from_db()
        self.assertFalse(gc.enviado_whatsapp)

    def test_si_el_pdf_revienta_el_pago_queda(self):
        venta, gc = self._venta()

        def revienta(*a, **k):
            raise RuntimeError('WeasyPrint no disponible')
        self._pagar(venta, pdf=revienta)
        self.assertTrue(Pago.objects.filter(venta_reserva=venta).exists())
        venta.refresh_from_db()
        self.assertEqual(int(venta.saldo_pendiente), 0)


class ElEmailEsperaElPagoCompleto(_Base):
    """Jorge (25-09-2026): «haz ese cambio». Con un abono parcial, el email ya
    mandaba la gift card con su código sin estar cobrada entera."""

    def _registrar(self, venta, monto):
        with mock.patch(EMAIL) as email, mock.patch(ENVIAR, return_value=OK):
            Pago.objects.create(venta_reserva=venta, monto=monto, metodo_pago='transferencia')
        return email

    def test_con_un_abono_parcial_no_sale_y_sigue_por_cobrar(self):
        venta, gc = self._venta()
        email = self._registrar(venta, 10000)
        email.assert_not_called()
        gc.refresh_from_db()
        self.assertEqual(gc.estado, 'por_cobrar')

    def test_al_completar_el_pago_sale_una_vez(self):
        venta, gc = self._venta()
        self._registrar(venta, 10000)
        email = self._registrar(venta, 100000)
        email.assert_called_once()
        gc.refresh_from_db()
        self.assertEqual(gc.estado, 'cobrado')

    def test_pagada_de_una_sale(self):
        venta, gc = self._venta()
        email = self._registrar(venta, 110000)
        email.assert_called_once()


class LaVentaWebTambien(SimpleTestCase):
    """El pago por Flow materializa la venta y manda el email por su cuenta: el
    envío por WhatsApp va justo después (se revisa en la fuente, como en
    test_dia: el webhook no se puede invocar suelto)."""

    def test_flow_lo_llama_despues_del_email(self):
        from ventas.views import flow_views
        fuente = inspect.getsource(flow_views)
        self.assertIn('enviar_al_pagarse(', fuente)
        self.assertLess(fuente.index('GiftCardPDFService.enviar_giftcard_por_email('),
                        fuente.index('enviar_al_pagarse('))
