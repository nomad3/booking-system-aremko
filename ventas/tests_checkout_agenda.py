"""Checkout de la agenda operativa: quién se va HOY y cuánto debe.

Pedido de Jorge (2026-08-02): "en la agenda de control operativo debería aparecer
un botón checkout... mostrar las cabañas que se arrendaron el día anterior y que
tienen fecha de salida hoy... su saldo y si tienen saldo pendiente, el monto".

El detalle que define todo el diseño: **una estadía NO tiene fecha de salida en la
BD**. Se guarda una `ReservaServicio` POR NOCHE, misma cabaña en fechas
consecutivas; la salida es una derivación (última noche + 1 día).

Por eso la consulta obvia ("cabañas con fecha_agendamiento = ayer") está MAL:
también agarra a quien llegó ayer y se queda 2 noches — ese sale mañana y todavía
está alojado. El test `test_estadia_en_curso_NO_aparece` es el que fija eso.

Ejecutar:
    python manage.py test ventas.tests_checkout_agenda
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models.signals import post_save
from django.test import TestCase
from django.utils import timezone

from control_gestion.signals import react_to_reserva_change

from .models import (
    Cliente, CategoriaServicio, Servicio, VentaReserva, ReservaServicio, Pago,
)
from .signals.main_signals import actualizar_tramo_y_premios_on_pago
from .views.agenda_operativa_view import salidas_para_checkout

_SENSORES = (actualizar_tramo_y_premios_on_pago, react_to_reserva_change)


class _BaseCheckout(TestCase):
    """Catálogo mínimo: dos cabañas y una tina (para probar que la tina no cuenta)."""

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
        cls.hoy = date(2026, 8, 2)
        cls.cat_cab = CategoriaServicio.objects.create(nombre='Cabañas')
        cls.cat_tinas = CategoriaServicio.objects.create(nombre='Tinas')
        cls.cabana = Servicio.objects.create(
            nombre='Cabaña Torre', categoria=cls.cat_cab, tipo_servicio='cabana',
            precio_base=Decimal('80000'), duracion=60, activo=True)
        cls.cabana2 = Servicio.objects.create(
            nombre='Cabaña Río', categoria=cls.cat_cab, tipo_servicio='cabana',
            precio_base=Decimal('90000'), duracion=60, activo=True)
        cls.tina = Servicio.objects.create(
            nombre='Tina Hornopirén', categoria=cls.cat_tinas, tipo_servicio='tina',
            precio_base=Decimal('25000'), duracion=60, activo=True)

    # -- helpers ------------------------------------------------------------
    def _reserva(self, nombre, noches_fechas, precio_noche=100000, pagado=None,
                 servicio=None, estado='confirmada'):
        """Reserva con una ReservaServicio por cada fecha, como en producción.

        El pago se registra como `Pago` REAL y el total lo calcula el modelo: no
        sirve fijar `pagado`/`saldo_pendiente` a mano, porque `calcular_total()`
        (que dispara al guardar cada servicio) los recalcula desde los pagos.
        Default: todo pagado.
        """
        cliente = Cliente.objects.create(
            nombre=nombre, telefono=f'+5691{abs(hash(nombre)) % 10000000:07d}')
        venta = VentaReserva.objects.create(
            cliente=cliente, total=0, estado_reserva=estado,
            fecha_reserva=timezone.now())
        for f in noches_fechas:
            ReservaServicio.objects.create(
                venta_reserva=venta, servicio=servicio or self.cabana,
                fecha_agendamiento=f, hora_inicio='16:00',
                cantidad_personas=1, precio_unitario_venta=Decimal(precio_noche))
        total = precio_noche * len(noches_fechas)
        monto_pagado = total if pagado is None else pagado
        if monto_pagado:
            Pago.objects.create(venta_reserva=venta, monto=Decimal(monto_pagado),
                                metodo_pago='transferencia')
        venta.calcular_total()  # deja total/pagado/saldo consistentes
        venta.refresh_from_db()
        return venta

    def _nombres(self, salidas):
        return [s['cliente'] for s in salidas]


class SalidasDelDiaTest(_BaseCheckout):

    def test_una_noche_que_termino_ayer_sale_hoy(self):
        ayer = self.hoy - timedelta(days=1)
        self._reserva('Ana', [ayer])
        salidas = salidas_para_checkout(self.hoy)
        self.assertEqual(self._nombres(salidas), ['Ana'])
        self.assertEqual(salidas[0]['salida'], self.hoy)
        self.assertEqual(salidas[0]['noches'], 1)
        self.assertEqual(salidas[0]['dias_atras'], 0)

    def test_dos_noches_que_terminan_ayer_salen_hoy(self):
        self._reserva('Beto', [self.hoy - timedelta(days=2), self.hoy - timedelta(days=1)])
        salidas = salidas_para_checkout(self.hoy)
        self.assertEqual(self._nombres(salidas), ['Beto'])
        self.assertEqual(salidas[0]['noches'], 2)
        self.assertEqual(salidas[0]['llegada'], self.hoy - timedelta(days=2))
        self.assertEqual(salidas[0]['salida'], self.hoy)

    def test_estadia_en_curso_NO_aparece(self):
        """EL caso que rompe la consulta ingenua.

        Llegó AYER y se queda 2 noches → tiene una noche con fecha de ayer (que
        un filtro `fecha_agendamiento = ayer` capturaría), pero también una de
        HOY: sale mañana y sigue alojado. No es un checkout de hoy.
        """
        self._reserva('Carla', [self.hoy - timedelta(days=1), self.hoy])
        self.assertEqual(salidas_para_checkout(self.hoy), [])

    def test_estadia_larga_en_curso_tampoco(self):
        # Llegó hace 3 días, se va en 2 más: tiene noches viejas Y futuras.
        fechas = [self.hoy - timedelta(days=d) for d in (3, 2, 1)] + [self.hoy]
        self._reserva('Diego', fechas)
        self.assertEqual(salidas_para_checkout(self.hoy), [])

    def test_llega_hoy_no_es_checkout(self):
        self._reserva('Elena', [self.hoy])
        self.assertEqual(salidas_para_checkout(self.hoy), [])

    def test_una_tina_de_ayer_no_es_un_checkout(self):
        # Solo las cabañas hacen checkout; una tina de ayer ya terminó y se fue.
        self._reserva('Fran', [self.hoy - timedelta(days=1)], servicio=self.tina)
        self.assertEqual(salidas_para_checkout(self.hoy), [])

    def test_reserva_cancelada_no_aparece(self):
        self._reserva('Gonzalo', [self.hoy - timedelta(days=1)], estado='cancelada')
        self.assertEqual(salidas_para_checkout(self.hoy), [])


class RezagadosTest(_BaseCheckout):
    """Salidas viejas: solo interesan si quedaron DEBIENDO."""

    def test_rezagado_con_deuda_se_arrastra(self):
        # Salió anteayer y quedó debiendo: no se puede perder ese cobro.
        self._reserva('Hugo', [self.hoy - timedelta(days=3)], precio_noche=100000, pagado=50000)
        salidas = salidas_para_checkout(self.hoy)
        self.assertEqual(self._nombres(salidas), ['Hugo'])
        self.assertEqual(salidas[0]['saldo'], 50000)
        self.assertEqual(salidas[0]['dias_atras'], 2)
        self.assertTrue(salidas[0]['debe'])

    def test_rezagado_ya_pagado_NO_ensucia_la_lista(self):
        self._reserva('Ines', [self.hoy - timedelta(days=3)], precio_noche=100000)
        self.assertEqual(salidas_para_checkout(self.hoy), [])

    def test_fuera_de_la_ventana_no_se_arrastra_aunque_deba(self):
        # Más viejo que la ventana: eso ya es cobranza, no checkout del día.
        self._reserva('Julio', [self.hoy - timedelta(days=30)], precio_noche=100000, pagado=0)
        self.assertEqual(salidas_para_checkout(self.hoy), [])

    def test_la_ventana_es_configurable(self):
        self._reserva('Karla', [self.hoy - timedelta(days=6)], precio_noche=100000, pagado=0)
        self.assertEqual(salidas_para_checkout(self.hoy), [])
        self.assertEqual(
            self._nombres(salidas_para_checkout(self.hoy, dias_rezagados=10)), ['Karla'])


class OrdenYMontosTest(_BaseCheckout):

    def test_deudores_primero_y_por_mayor_saldo(self):
        ayer = self.hoy - timedelta(days=1)
        self._reserva('Pagada', [ayer], precio_noche=100000)
        self._reserva('DebePoco', [ayer], precio_noche=100000, pagado=90000)   # debe 10.000
        self._reserva('DebeMucho', [ayer], precio_noche=200000, pagado=50000)  # debe 150.000
        self.assertEqual(self._nombres(salidas_para_checkout(self.hoy)),
                         ['DebeMucho', 'DebePoco', 'Pagada'])

    def test_trae_total_pagado_y_saldo_por_separado(self):
        """Los tres juntos a propósito: `saldo_pendiente` es un campo ALMACENADO
        y ya hubo un bug en `actualizar_saldo` (H-060). Si algún día no cuadra,
        tiene que verse en pantalla, no esconderse en un solo número."""
        self._reserva('Luis', [self.hoy - timedelta(days=1)], precio_noche=120000, pagado=70000)
        s = salidas_para_checkout(self.hoy)[0]
        self.assertEqual((s['total'], s['pagado'], s['saldo']), (120000, 70000, 50000))

    def test_junta_las_cabanas_de_una_misma_reserva(self):
        # Dos cabañas la misma noche (grupo grande) = UNA sola línea de checkout.
        ayer = self.hoy - timedelta(days=1)
        venta = self._reserva('Marta', [ayer])
        ReservaServicio.objects.create(
            venta_reserva=venta, servicio=self.cabana2, fecha_agendamiento=ayer,
            hora_inicio='16:00', cantidad_personas=2,
            precio_unitario_venta=Decimal('90000'))
        salidas = salidas_para_checkout(self.hoy)
        self.assertEqual(len(salidas), 1)
        self.assertEqual(salidas[0]['cabanas'], 'Cabaña Río, Cabaña Torre')

    def test_sin_salidas_devuelve_lista_vacia(self):
        self.assertEqual(salidas_para_checkout(self.hoy), [])
