"""Repunte de chocolates (jul-2026) — la ambientación con chocolates mueve el
INVENTARIO del Producto real (Caja Chocolate, id 42) EN LA FECHA de la visita,
vía una comanda a $0, sin duplicar el cobro (que va por la línea de servicio).

Camino seguro: cero cambios al checkout compartido. Ver
ventas/services/ambientacion_bebidas.py::asegurar_comanda_chocolates.
"""
from decimal import Decimal
from datetime import timedelta

from django.db.models.signals import post_save
from django.test import TestCase
from django.utils import timezone

from control_gestion.signals import react_to_reserva_change

from .models import (
    Cliente, VentaReserva, Servicio, CategoriaServicio, Producto,
    ReservaServicio, ReservaProducto, Comanda,
)
from .signals.main_signals import (
    actualizar_tramo_y_premios_on_pago, asegurar_bebida_ambientacion,
)
from .services.ambientacion_bebidas import (
    asegurar_comanda_chocolates, CHOCOLATES_ID, MARCA_CHOCOLATES,
    NOMBRE_SERVICIO_CHOCOLATES,
)

# Sensores post_save(VentaReserva) que tocan crm_service_history (tabla ausente en
# la BD de test por el drift AR-034). Se desconectan como en los demás tests DB.
_SENSORES_TRAMO = (actualizar_tramo_y_premios_on_pago, react_to_reserva_change)


class _BaseChoco(TestCase):
    """Setup común: catálogo mínimo + reserva con tina + ambientación + chocolates.

    Por defecto DESCONECTA el signal de ambientación para probar la función a
    solas; el test de wiring lo reconecta a propósito.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for r in _SENSORES_TRAMO:
            post_save.disconnect(r, sender=VentaReserva)
        post_save.disconnect(asegurar_bebida_ambientacion, sender=ReservaServicio)

    @classmethod
    def tearDownClass(cls):
        post_save.connect(asegurar_bebida_ambientacion, sender=ReservaServicio)
        for r in _SENSORES_TRAMO:
            post_save.connect(r, sender=VentaReserva)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(
            nombre='Pareja Test', telefono='+56911112222', email='pareja@test.com')
        cls.cat_amb = CategoriaServicio.objects.create(nombre='Ambientaciones')
        cls.cat_tinas = CategoriaServicio.objects.create(nombre='Tinas')
        cls.serv_tina = Servicio.objects.create(
            nombre='Tina Pareja', categoria=cls.cat_tinas, tipo_servicio='tina',
            precio_base=Decimal('60000'), duracion=60)
        cls.serv_amb = Servicio.objects.create(
            nombre='Ambientación romántica R1', categoria=cls.cat_amb,
            tipo_servicio='otro', precio_base=Decimal('32000'), duracion=60)
        cls.serv_choco = Servicio.objects.create(
            nombre=NOMBRE_SERVICIO_CHOCOLATES, categoria=cls.cat_amb,
            tipo_servicio='otro', precio_base=Decimal('16000'), duracion=60)
        # El Producto REAL de inventario, con el id que espera el servicio.
        cls.prod_choco = Producto.objects.create(
            id=CHOCOLATES_ID, nombre='Caja Chocolate',
            precio_base=Decimal('16000'), cantidad_disponible=10)
        cls.fecha_visita = (timezone.now().date() + timedelta(days=10))

    # -- helpers ------------------------------------------------------------
    def _venta_con(self, con_chocolates=True, con_ambientacion=True):
        venta = VentaReserva.objects.create(
            cliente=self.cliente, total=0, estado_pago='pendiente',
            fecha_reserva=timezone.now())
        ReservaServicio.objects.create(
            venta_reserva=venta, servicio=self.serv_tina,
            fecha_agendamiento=self.fecha_visita, hora_inicio='16:00',
            cantidad_personas=2, precio_unitario_venta=Decimal('60000'))
        if con_ambientacion:
            ReservaServicio.objects.create(
                venta_reserva=venta, servicio=self.serv_amb,
                fecha_agendamiento=self.fecha_visita, hora_inicio='16:00',
                cantidad_personas=1, precio_unitario_venta=Decimal('32000'))
        if con_chocolates:
            ReservaServicio.objects.create(
                venta_reserva=venta, servicio=self.serv_choco,
                fecha_agendamiento=self.fecha_visita, hora_inicio='16:00',
                cantidad_personas=1, precio_unitario_venta=Decimal('16000'))
        return venta


class AsegurarComandaChocolatesTest(_BaseChoco):

    def test_crea_comanda_con_producto_a_cero(self):
        venta = self._venta_con()
        comanda = asegurar_comanda_chocolates(venta)

        self.assertIsNotNone(comanda)
        self.assertIn(MARCA_CHOCOLATES, comanda.notas_generales)
        # Detalle de comanda con el Producto real, a $0 (solo mueve inventario).
        detalle = comanda.detalles.get(producto_id=CHOCOLATES_ID)
        self.assertEqual(detalle.cantidad, 1)
        self.assertEqual(int(detalle.precio_unitario), 0)
        # ReservaProducto sin fecha_entrega (no descuenta hasta la visita) y a $0.
        rp = ReservaProducto.objects.get(venta_reserva=venta, producto_id=CHOCOLATES_ID)
        self.assertIsNone(rp.fecha_entrega)
        self.assertEqual(int(rp.precio_unitario_venta), 0)

    def test_fecha_objetivo_es_la_fecha_de_la_visita(self):
        venta = self._venta_con()
        comanda = asegurar_comanda_chocolates(venta)
        self.assertEqual(comanda.fecha_entrega_objetivo.date(), self.fecha_visita)

    def test_idempotente_no_duplica(self):
        venta = self._venta_con()
        c1 = asegurar_comanda_chocolates(venta)
        c2 = asegurar_comanda_chocolates(venta)
        self.assertEqual(c1.id, c2.id)
        self.assertEqual(
            Comanda.objects.filter(
                venta_reserva=venta,
                notas_generales__icontains=MARCA_CHOCOLATES).count(), 1)
        self.assertEqual(
            ReservaProducto.objects.filter(
                venta_reserva=venta, producto_id=CHOCOLATES_ID).count(), 1)

    def test_sin_linea_de_chocolates_devuelve_none(self):
        venta = self._venta_con(con_chocolates=False)  # ambientación pero sin chocolates
        self.assertIsNone(asegurar_comanda_chocolates(venta))
        self.assertFalse(
            Comanda.objects.filter(
                venta_reserva=venta,
                notas_generales__icontains=MARCA_CHOCOLATES).exists())

    def test_no_infla_el_total(self):
        venta = self._venta_con()
        venta.calcular_total()
        total_antes = venta.total  # tina 60k×2 + amb 32k + choco-servicio 16k = 168k
        asegurar_comanda_chocolates(venta)
        venta.refresh_from_db()
        venta.calcular_total()
        self.assertEqual(venta.total, total_antes)  # la línea de producto a $0 no suma
        self.assertEqual(int(venta.total), 168000)

    def test_entrega_descuenta_stock_en_la_fecha(self):
        venta = self._venta_con()
        asegurar_comanda_chocolates(venta)
        # Al reservar, el stock NO baja (fecha_entrega = NULL).
        self.prod_choco.refresh_from_db()
        self.assertEqual(self.prod_choco.cantidad_disponible, 10)
        # El "día de la visita" el cron entrega la comanda → recién ahí baja el stock.
        comanda = Comanda.objects.get(
            venta_reserva=venta, notas_generales__icontains=MARCA_CHOCOLATES)
        comanda.entregar_inventario(fecha=self.fecha_visita)
        self.prod_choco.refresh_from_db()
        self.assertEqual(self.prod_choco.cantidad_disponible, 9)


class WiringSignalChocolatesTest(_BaseChoco):
    """El signal de ambientación debe disparar la comanda de chocolates solo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Reconectar el signal para probar el cableado real (create → comanda).
        post_save.connect(asegurar_bebida_ambientacion, sender=ReservaServicio)

    @classmethod
    def tearDownClass(cls):
        post_save.disconnect(asegurar_bebida_ambientacion, sender=ReservaServicio)
        super().tearDownClass()

    def test_crear_linea_chocolates_auto_crea_la_comanda(self):
        venta = self._venta_con()  # crear la línea de choco dispara el signal
        self.assertTrue(
            Comanda.objects.filter(
                venta_reserva=venta,
                notas_generales__icontains=MARCA_CHOCOLATES).exists())
        rp = ReservaProducto.objects.get(venta_reserva=venta, producto_id=CHOCOLATES_ID)
        self.assertIsNone(rp.fecha_entrega)
