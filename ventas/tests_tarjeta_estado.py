"""Llegada y salida desde la tarjeta, sin pasar por el admin.

Jorge (05-09-2026): «en la card de una reserva agreguemos un botón para
cambiar el estado de pendiente a check in y de check in a check out.
Actualmente para hacer ese cambio de estado debemos ir al admin de django y
editar la reserva».

La lógica ya existía (ventas/llegadas.py, usada por el QR del Pase y por la
agenda operativa). Acá NO se reimplementa: la tarjeta pega contra los mismos
endpoints, para que los tres caminos dejen el mismo rastro en el historial
del cliente y no puedan contradecirse.

Ejecutar:
    python manage.py test ventas.tests_tarjeta_estado
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ventas.models import Cliente, MovimientoCliente, VentaReserva


class ElBotonQueSeMuestra(TestCase):
    """El botón cambia según dónde está la reserva: uno solo, el que toca."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='recepcion', email='r@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Jimena Herrera',
                                             telefono='+56911112222')

    def setUp(self):
        self.client.force_login(self.staff)
        self.venta = VentaReserva.objects.create(cliente=self.cliente)

    def _html(self):
        return self.client.get(
            reverse('ventas:tarjeta_reserva', args=[self.venta.pk])
        ).content.decode()

    def test_pendiente_ofrece_registrar_la_llegada(self):
        html = self._html()
        self.assertIn('Registrar llegada', html)
        self.assertNotIn('Registrar salida', html)

    def test_en_checkin_ofrece_registrar_la_salida(self):
        self.venta.estado_reserva = 'checkin'
        self.venta.save(update_fields=['estado_reserva'])
        html = self._html()
        self.assertIn('Registrar salida', html)
        self.assertNotIn('Registrar llegada', html)

    def test_en_checkout_ya_no_ofrece_nada(self):
        self.venta.estado_reserva = 'checkout'
        self.venta.save(update_fields=['estado_reserva'])
        html = self._html()
        self.assertNotIn('Registrar llegada', html)
        self.assertNotIn('Registrar salida', html)
        self.assertIn('estadía ya está cerrada', html)

    def test_muestra_el_estado_arriba(self):
        # Para verlo de un vistazo sin bajar hasta los botones.
        self.assertIn('Pendiente', self._html())
        self.venta.estado_reserva = 'checkin'
        self.venta.save(update_fields=['estado_reserva'])
        self.assertIn('Check-in', self._html())


class LaLlegadaYLaSalidaSeRegistran(TestCase):
    """Contra los endpoints reales que usa el botón."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='recepcion2', email='r2@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Iván Soto',
                                             telefono='+56933334444')

    def setUp(self):
        self.client.force_login(self.staff)
        self.venta = VentaReserva.objects.create(cliente=self.cliente)

    def _llegada(self):
        return self.client.post(
            reverse('ventas:marcar_llegada_api'),
            data=f'{{"reserva_id": {self.venta.pk}}}',
            content_type='application/json')

    def _salida(self):
        return self.client.post(
            reverse('ventas:marcar_checkout_api'),
            data=f'{{"reserva_id": {self.venta.pk}}}',
            content_type='application/json')

    def test_la_llegada_deja_la_reserva_en_checkin(self):
        self.assertTrue(self._llegada().json()['success'])
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado_reserva, 'checkin')

    def test_la_salida_deja_la_reserva_en_checkout(self):
        self._llegada()
        self.assertTrue(self._salida().json()['success'])
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado_reserva, 'checkout')

    def test_queda_el_rastro_en_el_historial_del_cliente(self):
        # Esto es lo que se pierde si alguien reimplementa el cambio de estado
        # a mano: el estado cambia pero nadie sabe quién ni cuándo.
        self._llegada()
        mov = MovimientoCliente.objects.filter(
            venta_reserva=self.venta, tipo_movimiento='llegada').first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.usuario, self.staff)

    def test_se_puede_cerrar_sin_haber_marcado_la_llegada(self):
        # Nadie marcó la llegada y el cliente ya se va: obligar dos toques
        # cuando alguien se olvidó del primero solo deja la reserva colgada.
        self.assertTrue(self._salida().json()['success'])
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado_reserva, 'checkout')

    def test_apretar_dos_veces_no_duplica_el_movimiento(self):
        # Doble clic en el celular, o dos personas a la vez en el mesón.
        self._llegada()
        self._llegada()
        self.assertEqual(MovimientoCliente.objects.filter(
            venta_reserva=self.venta, tipo_movimiento='llegada').count(), 1)


class SoloElPersonal(TestCase):
    def test_un_desconocido_no_puede_marcar_llegadas(self):
        cliente = Cliente.objects.create(nombre='X', telefono='+56900000000')
        venta = VentaReserva.objects.create(cliente=cliente)
        r = self.client.post(reverse('ventas:marcar_llegada_api'),
                             data=f'{{"reserva_id": {venta.pk}}}',
                             content_type='application/json')
        self.assertNotEqual(r.status_code, 200)
        venta.refresh_from_db()
        self.assertEqual(venta.estado_reserva, 'pendiente')
