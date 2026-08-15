"""La hora que ve cocina es la hora en que el cliente pidió.

Caso real (2026-08-15): una clienta entró a la tina a las 12:00 y pidió un jugo
desde ahí. La agenda mostró **7165 min de espera** — casi cinco días. El pedido
había heredado la fecha de su comanda BORRADOR, que nace vacía al abrir el link
(o al confirmar el pedido anterior) y puede tener días encima.

Un minutero que exagera no es un detalle cosmético: el badge rojo de urgencia
salía siempre, y una alarma que suena siempre deja de ser una alarma.
"""
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import Cliente, Comanda, DetalleComanda, Producto, VentaReserva


class HoraDelPedidoDelClienteTests(TestCase):
    def setUp(self):
        self.client_web = Client()
        cliente = Cliente.objects.create(nombre='Huésped Tina', telefono='+56999999999')
        self.venta = VentaReserva.objects.create(cliente=cliente)
        self.producto = Producto.objects.create(
            nombre='Jugo Natural Arándanos', precio_base=5000,
            cantidad_disponible=10, comanda_cliente=True)

        self.token = 'tok-prueba-hora-pedido'
        self.borrador = Comanda.objects.create(
            venta_reserva=self.venta, estado='borrador', creada_por_cliente=True,
            token_acceso=self.token,
            fecha_vencimiento_link=timezone.now() + timedelta(days=2))
        DetalleComanda.objects.create(comanda=self.borrador, producto=self.producto,
                                      cantidad=1, precio_unitario=5000)

        # El borrador nació hace 5 días: el cliente abrió el link al recibir su
        # confirmación y recién hoy, dentro de la tina, pidió algo.
        self.hace_cinco_dias = timezone.now() - timedelta(days=5)
        Comanda.objects.filter(pk=self.borrador.pk).update(
            fecha_solicitud=self.hace_cinco_dias)

    def confirmar(self):
        return self.client_web.post(
            reverse('ventas:comanda_cliente_finalizar', kwargs={'token': self.token}))

    def test_confirmar_estampa_la_hora_real_del_pedido(self):
        self.confirmar()

        self.borrador.refresh_from_db()
        self.assertGreater(self.borrador.fecha_solicitud, self.hace_cinco_dias)
        self.assertLess((timezone.now() - self.borrador.fecha_solicitud).total_seconds(), 60)

    def test_cocina_ve_una_espera_de_minutos_no_de_dias(self):
        self.confirmar()

        self.borrador.refresh_from_db()
        self.assertEqual(self.borrador.tiempo_espera(), 0)  # recién pedido

    def test_la_hora_de_solicitud_acompana_a_la_fecha(self):
        """Las dos se muestran en pantallas distintas; si se separan, una de las
        dos miente y no hay forma de saber cuál."""
        self.confirmar()

        self.borrador.refresh_from_db()
        esperada = timezone.localtime(self.borrador.fecha_solicitud).time()
        self.assertEqual(self.borrador.hora_solicitud.hour, esperada.hour)
        self.assertEqual(self.borrador.hora_solicitud.minute, esperada.minute)

    def test_el_borrador_del_proximo_pedido_arranca_limpio(self):
        """Confirmar deja otro borrador para el siguiente pedido. Ese borrador
        es el que le pasará la fecha al pedido que venga, así que su hora tiene
        que ser la de ahora y no la del anterior."""
        self.confirmar()

        siguiente = Comanda.objects.get(venta_reserva=self.venta, estado='borrador')
        self.assertNotEqual(siguiente.pk, self.borrador.pk)
        self.assertLess((timezone.now() - siguiente.fecha_solicitud).total_seconds(), 60)
