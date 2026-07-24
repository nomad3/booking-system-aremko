"""F-01 (plan Ficha) — medir aperturas de la ficha del cliente.

Se registra la PRIMERA apertura real por reserva como un MovimientoCliente
(`tipo_movimiento='ficha_abierta'`), filtrando bots / preview de link, sin duplicar.
"""
from decimal import Decimal

from django.db.models.signals import post_save
from django.test import TestCase, RequestFactory
from django.utils import timezone

from control_gestion.signals import react_to_reserva_change

from .models import Cliente, VentaReserva, MovimientoCliente
from .signals.main_signals import actualizar_tramo_y_premios_on_pago
from .views.ficha_reserva_view import _registrar_apertura_ficha

_SENSORES = (actualizar_tramo_y_premios_on_pago, react_to_reserva_change)
UA_HUMANO = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1'


class RegistrarAperturaFichaTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for r in _SENSORES:
            post_save.disconnect(r, sender=VentaReserva)

    @classmethod
    def tearDownClass(cls):
        for r in _SENSORES:
            post_save.connect(r, sender=VentaReserva)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            nombre='Ana Soto', telefono='+56911112222', email='ana@test.com')

    def _venta(self):
        return VentaReserva.objects.create(
            cliente=self.cliente, total=Decimal('60000'), estado_pago='pendiente',
            fecha_reserva=timezone.now())

    def _aperturas(self, venta):
        return MovimientoCliente.objects.filter(
            venta_reserva=venta, tipo_movimiento='ficha_abierta').count()

    def test_registra_primera_apertura(self):
        venta = self._venta()
        _registrar_apertura_ficha(RequestFactory().get('/', HTTP_USER_AGENT=UA_HUMANO), venta)
        self.assertEqual(self._aperturas(venta), 1)

    def test_no_duplica_en_segunda_apertura(self):
        venta = self._venta()
        req = RequestFactory().get('/', HTTP_USER_AGENT=UA_HUMANO)
        _registrar_apertura_ficha(req, venta)
        _registrar_apertura_ficha(req, venta)
        self.assertEqual(self._aperturas(venta), 1)  # dedup por reserva

    def test_ignora_bots_y_preview(self):
        venta = self._venta()
        for ua in ('WhatsApp/2.23', 'facebookexternalhit/1.1', 'Googlebot/2.1', ''):
            _registrar_apertura_ficha(RequestFactory().get('/', HTTP_USER_AGENT=ua), venta)
        self.assertEqual(self._aperturas(venta), 0)  # ninguna cuenta como apertura del cliente
