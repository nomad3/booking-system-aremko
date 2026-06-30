"""Tests del endpoint de conciliación (AP-001 · PASO 2 escritura).

Correr en el entorno real (no hay Django local):
    python manage.py test conciliacion
"""

import json

from django.test import TestCase, override_settings
from django.utils import timezone

from ventas.models import Cliente, Servicio, VentaReserva, ReservaServicio, Pago
from conciliacion.models import ReconciliacionLog

URL = '/ventas/api/aremko-cli/recon/aplicar-pago/'
KEY = 'test-automation-key'


@override_settings(AUTOMATION_API_KEY=KEY)
class AplicarPagoTests(TestCase):

    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Test Conciliación', telefono='+56900000777')
        self.servicio = Servicio.objects.create(nombre='Tina test', precio_base=50000, duracion=60)
        self.reserva = VentaReserva.objects.create(cliente=self.cliente)
        ReservaServicio.objects.create(
            venta_reserva=self.reserva,
            servicio=self.servicio,
            fecha_agendamiento=timezone.now().date(),
            hora_inicio='16:00',
            cantidad_personas=1,
            precio_unitario_venta=50000,
        )
        self.reserva.calcular_total()  # total = 50000, saldo = 50000, estado = pendiente
        self.reserva.refresh_from_db()

    def _post(self, body, key=KEY):
        headers = {'HTTP_X_API_KEY': key} if key else {}
        return self.client.post(URL, data=json.dumps(body),
                                content_type='application/json', **headers)

    def test_baseline(self):
        self.assertEqual(int(self.reserva.total), 50000)
        self.assertEqual(self.reserva.estado_pago, 'pendiente')

    def test_aplicar_pago_total_marca_pagado(self):
        r = self._post({'reserva_id': self.reserva.id, 'monto': 50000,
                        'referencia': 'mov-1', 'metodo_pago': 'transferencia'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertFalse(data['ya_aplicado'])
        self.assertEqual(data['estado_pago'], 'pagado')
        self.assertEqual(data['saldo_pendiente'], 0)
        self.assertEqual(Pago.objects.filter(venta_reserva=self.reserva).count(), 1)
        self.assertEqual(ReconciliacionLog.objects.filter(referencia='mov-1').count(), 1)

    def test_idempotencia_no_duplica_pago(self):
        b = {'reserva_id': self.reserva.id, 'monto': 50000, 'referencia': 'mov-1'}
        r1 = self._post(b)
        r2 = self._post(b)  # mismo movimiento otra vez
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r1.json()['ya_aplicado'])
        self.assertTrue(r2.json()['ya_aplicado'])
        # NO se crea un segundo pago ni un segundo log
        self.assertEqual(Pago.objects.filter(venta_reserva=self.reserva).count(), 1)
        self.assertEqual(ReconciliacionLog.objects.filter(referencia='mov-1').count(), 1)

    def test_pago_parcial(self):
        r = self._post({'reserva_id': self.reserva.id, 'monto': 20000, 'referencia': 'mov-2'})
        data = r.json()
        self.assertEqual(data['estado_pago'], 'parcial')
        self.assertEqual(data['saldo_pendiente'], 30000)

    def test_sin_key_devuelve_401(self):
        r = self._post({'reserva_id': self.reserva.id, 'monto': 50000, 'referencia': 'x'}, key=None)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(Pago.objects.filter(venta_reserva=self.reserva).count(), 0)

    def test_metodo_invalido_400(self):
        r = self._post({'reserva_id': self.reserva.id, 'monto': 50000,
                        'referencia': 'x', 'metodo_pago': 'bitcoin'})
        self.assertEqual(r.status_code, 400)

    def test_monto_cero_400(self):
        r = self._post({'reserva_id': self.reserva.id, 'monto': 0, 'referencia': 'x'})
        self.assertEqual(r.status_code, 400)

    def test_reserva_inexistente_404(self):
        r = self._post({'reserva_id': 999999, 'monto': 1000, 'referencia': 'x'})
        self.assertEqual(r.status_code, 404)

    def test_falta_referencia_400(self):
        r = self._post({'reserva_id': self.reserva.id, 'monto': 50000})
        self.assertEqual(r.status_code, 400)
