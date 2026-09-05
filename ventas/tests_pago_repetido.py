"""No dejar que el mismo cobro se registre dos veces sin avisar.

Caso real (04-09-2026, reserva 6742): Deborah registró el mismo pago con **6
segundos de diferencia** — probablemente no vio la confirmación del primero.
La reserva quedó marcando $120.000 sobre un total de $60.000 y, peor, se
emitieron DOS boletas electrónicas por la misma venta, las dos enviadas al
cliente. El sistema no dijo nada.

Jorge: «evitemos que ocurra nuevamente, que no permita o avise».

Se eligió **avisar y no bloquear**: dos personas pagando $20.000 cada una en
efectivo es un caso real y legítimo. Un bloqueo duro dejaría a Deborah sin
poder cobrar; el aviso caza el error y deja pasar al que sabe lo que hace.

Ejecutar:
    python manage.py test ventas.tests_pago_repetido
"""
from __future__ import annotations

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import Cliente, Pago, VentaReserva


class AvisaAntesDeRepetirUnPago(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='cajera_rep', email='r@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Valerie', telefono='+56957840164')

    def setUp(self):
        self.client.force_login(self.staff)
        self.venta = VentaReserva.objects.create(cliente=self.cliente)
        self.url = reverse('ventas:tarjeta_agregar_pago', args=[self.venta.pk])

    def _cobrar(self, monto='60000', metodo='efectivo', **extra):
        datos = {'monto': monto, 'metodo_pago': metodo}
        datos.update(extra)
        return self.client.post(self.url, datos)

    def test_el_primer_pago_pasa_sin_preguntar(self):
        r = self._cobrar()
        self.assertTrue(r.json()['ok'])
        self.assertEqual(Pago.objects.count(), 1)

    def test_el_segundo_igual_avisa_y_NO_lo_guarda(self):
        # Esto es exactamente lo que pasó en la reserva 6742.
        self._cobrar()
        r = self._cobrar()
        self.assertFalse(r.json()['ok'])
        self.assertTrue(r.json()['repetido'])
        self.assertEqual(Pago.objects.count(), 1, 'no debe guardarse el repetido')

    def test_el_aviso_dice_a_que_hora_fue_el_anterior(self):
        self._cobrar()
        mensaje = self._cobrar().json()['mensaje']
        self.assertIn('60.000', mensaje)
        self.assertIn(timezone.localtime(Pago.objects.first().fecha_pago)
                      .strftime('%H:%M'), mensaje)

    def test_confirmando_SI_lo_guarda(self):
        # Dos personas pagando lo mismo en efectivo: caso legítimo.
        self._cobrar()
        r = self._cobrar(confirmar_repetido='1')
        self.assertTrue(r.json()['ok'])
        self.assertEqual(Pago.objects.count(), 2)

    def test_no_avisa_si_cambia_el_monto(self):
        self._cobrar(monto='60000')
        r = self._cobrar(monto='30000')
        self.assertTrue(r.json()['ok'])

    def test_no_avisa_si_cambia_el_medio(self):
        self._cobrar(metodo='efectivo')
        r = self._cobrar(metodo='cuentarut')
        self.assertTrue(r.json()['ok'])

    def test_no_avisa_por_un_pago_de_otra_reserva(self):
        self._cobrar()
        otra = VentaReserva.objects.create(
            cliente=Cliente.objects.create(nombre='Otro', telefono='+56911110000'))
        r = self.client.post(
            reverse('ventas:tarjeta_agregar_pago', args=[otra.pk]),
            {'monto': '60000', 'metodo_pago': 'efectivo'})
        self.assertTrue(r.json()['ok'])

    def test_no_avisa_si_el_anterior_es_viejo(self):
        # Un cobro de ayer por el mismo monto no es un error de hoy.
        self._cobrar()
        Pago.objects.all().update(
            fecha_pago=timezone.now() - datetime.timedelta(hours=3))
        r = self._cobrar()
        self.assertTrue(r.json()['ok'])

    def test_avisar_nunca_impide_cobrar(self):
        # Si el detector falla, el cobro tiene que pasar igual: quien está al
        # otro lado es Deborah con un cliente al frente.
        from unittest.mock import patch
        with patch('ventas.views.tarjeta_reserva_view._pago_igual_reciente',
                   side_effect=RuntimeError('BD caída')):
            r = self._cobrar()
        self.assertTrue(r.json()['ok'])
