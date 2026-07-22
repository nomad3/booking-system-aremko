"""Aviso de "2 horas para pagar" en la ficha de reserva del cliente (solo lectura).

Se muestra SOLO cuando la reserva está en estado_pago='pendiente' (cero abonos) y
desaparece apenas hay cualquier pago (parcial o pagado) — pedido de Jorge 2026-07-22.
"""
from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from control_gestion.signals import react_to_reserva_change

from .models import Cliente, VentaReserva
from .signals.main_signals import actualizar_tramo_y_premios_on_pago
from .views.ficha_reserva_view import token_para_reserva

AVISO_TEXTO = '2 horas'

# Dos receivers post_save(VentaReserva) independientes (ventas + control_gestion) llaman
# TramoService.calcular_gasto_cliente → CRMService.get_customer_360 → crm_service_history,
# tabla ausente en la BD local de test (drift AR-034, ver [[project_aremko_ar033_ar034_drift]]).
# Se desconectan acá, igual que ventas/tests.py, porque no son relevantes para lo que
# probamos (el aviso de la ficha).
_SENSORES_TRAMO = (actualizar_tramo_y_premios_on_pago, react_to_reserva_change)


class AvisoPagoFichaReservaTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for receptor in _SENSORES_TRAMO:
            post_save.disconnect(receptor, sender=VentaReserva)

    @classmethod
    def tearDownClass(cls):
        for receptor in _SENSORES_TRAMO:
            post_save.connect(receptor, sender=VentaReserva)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            nombre='Ana Soto', telefono='+56911112222', email='ana@test.com')

    def _url(self, venta):
        return reverse('ventas:ficha_reserva_cliente',
                        kwargs={'token': token_para_reserva(venta.id)})

    def test_aviso_visible_si_pendiente(self):
        venta = VentaReserva.objects.create(
            cliente=self.cliente, total=60000, saldo_pendiente=60000,
            estado_pago='pendiente', fecha_reserva=timezone.now())
        resp = self.client.get(self._url(venta))
        self.assertContains(resp, AVISO_TEXTO)

    def test_aviso_oculto_si_parcial(self):
        venta = VentaReserva.objects.create(
            cliente=self.cliente, total=60000, pagado=30000, saldo_pendiente=30000,
            estado_pago='parcial', fecha_reserva=timezone.now())
        resp = self.client.get(self._url(venta))
        self.assertNotContains(resp, AVISO_TEXTO)

    def test_aviso_oculto_si_pagado(self):
        venta = VentaReserva.objects.create(
            cliente=self.cliente, total=60000, pagado=60000, saldo_pendiente=0,
            estado_pago='pagado', fecha_reserva=timezone.now())
        resp = self.client.get(self._url(venta))
        self.assertNotContains(resp, AVISO_TEXTO)

    def test_aviso_oculto_si_cancelado(self):
        venta = VentaReserva.objects.create(
            cliente=self.cliente, total=60000, saldo_pendiente=60000,
            estado_pago='cancelado', fecha_reserva=timezone.now())
        resp = self.client.get(self._url(venta))
        self.assertNotContains(resp, AVISO_TEXTO)
