"""Botón de check-out de la agenda operativa (salidas del día).

Recepción cierra la estadía desde la agenda en vez de abrir el admin. Lo que se
protege acá es que el gesto sea seguro de repetir: el mostrador es un lugar de
interrupciones, y el mismo botón se aprieta dos veces con toda naturalidad.
"""
import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from ventas.llegadas import TIPO_SALIDA
from ventas.models import Cliente, MovimientoCliente, VentaReserva


class CheckoutDesdeAgendaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser('recepcion', 'r@aremko.cl', 'x')
        cls.cliente = Cliente.objects.create(nombre='Huésped Prueba',
                                             telefono='+56999999999')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.staff)
        self.url = reverse('ventas:marcar_checkout_api')

    def cerrar(self, reserva_id):
        return self.client.post(self.url,
                                data=json.dumps({'reserva_id': reserva_id}),
                                content_type='application/json')

    def test_cierra_una_reserva_en_checkin(self):
        venta = VentaReserva.objects.create(cliente=self.cliente, estado_reserva='checkin')

        resp = self.cerrar(venta.pk)

        self.assertEqual(resp.status_code, 200)
        datos = resp.json()
        self.assertTrue(datos['success'])
        self.assertTrue(datos['recien'])
        self.assertEqual(datos['estado_reserva'], 'checkout')
        venta.refresh_from_db()
        self.assertEqual(venta.estado_reserva, 'checkout')

    def test_cierra_aunque_nadie_haya_marcado_la_llegada(self):
        """Que no se registrara el check-in no significa que el huésped no
        estuviera; obligar a marcar una llegada falsa sería peor dato."""
        venta = VentaReserva.objects.create(cliente=self.cliente, estado_reserva='pendiente')

        self.cerrar(venta.pk)

        venta.refresh_from_db()
        self.assertEqual(venta.estado_reserva, 'checkout')

    def test_apretar_dos_veces_no_duplica_ni_pisa_la_hora(self):
        venta = VentaReserva.objects.create(cliente=self.cliente, estado_reserva='checkin')

        primera = self.cerrar(venta.pk).json()
        segunda = self.cerrar(venta.pk).json()

        self.assertTrue(segunda['success'])       # repetir NO es un error
        self.assertFalse(segunda['recien'])
        self.assertEqual(segunda['hora'], primera['hora'])
        self.assertEqual(
            MovimientoCliente.objects.filter(venta_reserva=venta,
                                             tipo_movimiento=TIPO_SALIDA).count(),
            1)

    def test_deja_rastro_de_quien_cerro_y_del_saldo(self):
        venta = VentaReserva.objects.create(cliente=self.cliente, estado_reserva='checkin')
        # saldo_pendiente es un campo almacenado: se fija con update() para no
        # gatillar el recálculo del save().
        VentaReserva.objects.filter(pk=venta.pk).update(saldo_pendiente=50000)
        venta.refresh_from_db()

        self.cerrar(venta.pk)

        mov = MovimientoCliente.objects.get(venta_reserva=venta, tipo_movimiento=TIPO_SALIDA)
        self.assertEqual(mov.usuario, self.staff)
        self.assertIn('50.000', mov.comentarios)  # el saldo queda escrito

    def test_reserva_inexistente_responde_404(self):
        self.assertEqual(self.cerrar(999999).status_code, 404)

    def test_sin_sesion_de_staff_no_se_puede_cerrar(self):
        venta = VentaReserva.objects.create(cliente=self.cliente, estado_reserva='checkin')
        anonimo = Client()

        resp = anonimo.post(self.url, data=json.dumps({'reserva_id': venta.pk}),
                            content_type='application/json')

        self.assertNotEqual(resp.status_code, 200)
        venta.refresh_from_db()
        self.assertEqual(venta.estado_reserva, 'checkin')
