"""
Tests de la lógica de emisión (corren con `python manage.py test facturacion`).

Cubren: cálculo neto/IVA, filtro por medio de pago, idempotencia del candado
OneToOne y el modo simulado end-to-end.
"""
from django.test import TestCase

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion, MedioPago
from facturacion.services.emisor import (calcular_montos, emitir_boleta_para_pago,
                                         medio_genera_boleta)
from ventas.models import Cliente, Pago, VentaReserva


class CalculoMontosTest(TestCase):
    def test_neto_iva_cuadran_con_el_total(self):
        # $110.000 bruto (cabaña 2 personas): neto 92.437 + IVA 17.563
        neto, iva = calcular_montos(110000)
        self.assertEqual(neto, 92437)
        self.assertEqual(iva, 17563)
        self.assertEqual(neto + iva, 110000)

    def test_montos_chicos(self):
        neto, iva = calcular_montos(1190)
        self.assertEqual(neto, 1000)
        self.assertEqual(iva, 190)


class EmisionTest(TestCase):
    def setUp(self):
        MedioPago.objects.create(codigo='transferencia', nombre='Transferencia', genera_boleta=True)
        MedioPago.objects.create(codigo='mercadopago_link', nombre='Link MP', genera_boleta=False)
        config = ConfiguracionFacturacion.get()
        config.ambiente = 'simulado'
        config.save()
        self.cliente = Cliente.objects.create(nombre='Test Boleta', telefono='+56999999901')
        self.reserva = VentaReserva.objects.create(cliente=self.cliente)

    def _pago(self, metodo='transferencia', monto=50000):
        return Pago.objects.create(venta_reserva=self.reserva, monto=monto, metodo_pago=metodo)

    def test_medio_no_boleteable_no_emite(self):
        pago = self._pago(metodo='mercadopago_link')
        boleta, mensaje = emitir_boleta_para_pago(pago)
        self.assertIsNone(boleta)
        self.assertIn('no genera boleta', mensaje)
        self.assertFalse(medio_genera_boleta('mercadopago_link'))

    def test_emision_simulada(self):
        pago = self._pago()
        boleta, mensaje = emitir_boleta_para_pago(pago)
        self.assertIsNotNone(boleta)
        self.assertEqual(boleta.estado, 'simulada')
        self.assertEqual(int(boleta.monto_total), 50000)
        self.assertEqual(int(boleta.monto_neto) + int(boleta.monto_iva), 50000)
        self.assertIsNotNone(boleta.emitida_at)

    def test_idempotencia_no_duplica(self):
        pago = self._pago()
        b1, _ = emitir_boleta_para_pago(pago)
        b2, mensaje = emitir_boleta_para_pago(pago)
        self.assertEqual(b1.pk, b2.pk)
        self.assertIn('ya existía', mensaje)
        self.assertEqual(BoletaElectronica.objects.filter(pago=pago).count(), 1)

    def test_monto_cero_no_emite(self):
        pago = self._pago(monto=0)
        boleta, mensaje = emitir_boleta_para_pago(pago)
        self.assertIsNone(boleta)
        self.assertIn('monto', mensaje)

    def test_medio_desconocido_no_emite(self):
        pago = self._pago(metodo='flow')  # sin fila MedioPago
        boleta, _ = emitir_boleta_para_pago(pago)
        self.assertIsNone(boleta)
