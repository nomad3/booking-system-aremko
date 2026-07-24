"""F2-C — "Personaliza tu velada": el comprador cambia su bebida incluida (secreta,
excluyente, $0) desde la ficha. Reemplaza el contenido de la comanda de bebida sin
tocar el cobro, respetando la fecha de la visita, y no se puede cambiar una vez servida.
"""
from decimal import Decimal
from datetime import timedelta

from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse
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
    personalizar_bebida, bebida_editable, bebida_actual,
    asegurar_comanda_bebida_default, MARCA_BEBIDA,
    JUGOS, AGUAS, VINO_ID, ESPUMANTE_ID,
)
from .views.ficha_reserva_view import token_para_reserva

_SENSORES_TRAMO = (actualizar_tramo_y_premios_on_pago, react_to_reserva_change)


class _BaseBebida(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for r in _SENSORES_TRAMO:
            post_save.disconnect(r, sender=VentaReserva)
        # Aislar: sembramos la bebida a mano, sin el signal de ambientación.
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
            nombre='Pareja Test', telefono='+56911112222', email='p@test.com')
        cls.cat_amb = CategoriaServicio.objects.create(nombre='Ambientaciones')
        cls.cat_tinas = CategoriaServicio.objects.create(nombre='Tinas')
        cls.serv_tina = Servicio.objects.create(
            nombre='Tina Pareja', categoria=cls.cat_tinas, tipo_servicio='tina',
            precio_base=Decimal('60000'), duracion=60, activo=True)
        cls.serv_amb = Servicio.objects.create(
            nombre='Ambientación romántica R1', categoria=cls.cat_amb,
            tipo_servicio='otro', precio_base=Decimal('32000'), duracion=60, activo=True)
        # Productos reales de bebida (ids que esperan las constantes).
        for pid, nom in [(108, 'Jugo Frambuesa'), (107, 'Jugo Arándano'), (109, 'Jugo Melón'),
                         (125, 'Agua con gas'), (126, 'Agua sin gas'),
                         (VINO_ID, 'Botella Vino'), (ESPUMANTE_ID, 'Espumante')]:
            Producto.objects.create(id=pid, nombre=nom, precio_base=Decimal('3500'),
                                    cantidad_disponible=50)
        cls.fecha_visita = timezone.now().date() + timedelta(days=10)

    def _venta(self, con_ambientacion=True):
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
            asegurar_comanda_bebida_default(venta)  # siembra default [108, 107]
        return venta

    def _comanda(self, venta):
        return Comanda.objects.get(
            venta_reserva=venta, notas_generales__icontains=MARCA_BEBIDA)

    def _detalle_ids(self, venta):
        return sorted(self._comanda(venta).detalles.values_list('producto_id', flat=True))

    def _rp_ids(self, venta):
        return sorted(ReservaProducto.objects.filter(venta_reserva=venta)
                      .values_list('producto_id', flat=True))


class PersonalizarBebidaTest(_BaseBebida):

    def test_default_sembrado(self):
        venta = self._venta()
        self.assertEqual(self._detalle_ids(venta), [107, 108])

    def test_cambia_a_vino(self):
        venta = self._venta()
        self.assertEqual(personalizar_bebida(venta, [VINO_ID]), 'ok')
        self.assertEqual(self._detalle_ids(venta), [VINO_ID])
        # Los jugos viejos se fueron; queda solo el vino.
        self.assertEqual(self._rp_ids(venta), [VINO_ID])

    def test_cambia_jugos_incluye_melon(self):
        venta = self._venta()
        self.assertEqual(personalizar_bebida(venta, [JUGOS['frambuesa'], JUGOS['melon']]), 'ok')
        self.assertEqual(self._detalle_ids(venta), sorted([108, 109]))

    def test_aguas_agrega_cantidad(self):
        venta = self._venta()
        self.assertEqual(personalizar_bebida(venta, [AGUAS['con_gas'], AGUAS['con_gas']]), 'ok')
        det = self._comanda(venta).detalles.get(producto_id=AGUAS['con_gas'])
        self.assertEqual(det.cantidad, 2)  # 2 aguas con gas = una línea cantidad 2
        rp = ReservaProducto.objects.get(venta_reserva=venta, producto_id=AGUAS['con_gas'])
        self.assertEqual(rp.cantidad, 2)

    def test_descarta_ids_fuera_de_lista_blanca(self):
        venta = self._venta()
        self.assertEqual(personalizar_bebida(venta, [999999, VINO_ID]), 'ok')
        self.assertEqual(self._detalle_ids(venta), [VINO_ID])

    def test_sin_seleccion_valida_no_cambia(self):
        venta = self._venta()
        self.assertEqual(personalizar_bebida(venta, [999999]), 'sin_seleccion')
        self.assertEqual(self._detalle_ids(venta), [107, 108])  # intacto

    def test_sin_ambientacion(self):
        venta = self._venta(con_ambientacion=False)
        self.assertEqual(personalizar_bebida(venta, [VINO_ID]), 'sin_ambientacion')

    def test_no_cambia_si_ya_entregada(self):
        venta = self._venta()
        # Simular entrega: marcar fecha_entrega en los reservaproductos de bebida.
        ReservaProducto.objects.filter(
            venta_reserva=venta, producto_id__in=[107, 108]).update(fecha_entrega=self.fecha_visita)
        self.assertEqual(personalizar_bebida(venta, [VINO_ID]), 'ya_entregada')
        self.assertEqual(self._detalle_ids(venta), [107, 108])  # intacto

    def test_no_infla_total(self):
        venta = self._venta()
        venta.calcular_total()
        antes = venta.total
        personalizar_bebida(venta, [VINO_ID])
        venta.refresh_from_db(); venta.calcular_total()
        self.assertEqual(venta.total, antes)  # la bebida sigue a $0


class BebidaEditableYActualTest(_BaseBebida):

    def test_editable_true_normal(self):
        self.assertTrue(bebida_editable(self._venta()))

    def test_editable_false_sin_ambientacion(self):
        self.assertFalse(bebida_editable(self._venta(con_ambientacion=False)))

    def test_editable_false_si_entregada(self):
        venta = self._venta()
        ReservaProducto.objects.filter(
            venta_reserva=venta, producto_id__in=[107, 108]).update(fecha_entrega=self.fecha_visita)
        self.assertFalse(bebida_editable(venta))

    def test_actual_default_es_jugos(self):
        venta = self._venta()
        self.assertEqual(bebida_actual(venta), {'tipo': 'jugos', 'jugos': ['frambuesa', 'arandano']})

    def test_actual_refleja_vino(self):
        venta = self._venta()
        personalizar_bebida(venta, [VINO_ID])
        self.assertEqual(bebida_actual(venta), {'tipo': 'vino'})

    def test_actual_refleja_aguas(self):
        venta = self._venta()
        personalizar_bebida(venta, [AGUAS['sin_gas'], AGUAS['sin_gas']])
        self.assertEqual(bebida_actual(venta), {'tipo': 'aguas', 'agua': 'sin_gas'})


class EndpointFichaBebidaTest(_BaseBebida):

    def _url(self, venta):
        return reverse('ventas:ficha_personalizar_bebida',
                       kwargs={'token': token_para_reserva(venta.id)})

    def test_post_cambia_bebida_y_redirige(self):
        venta = self._venta()
        resp = self.client.post(self._url(venta), {'bebida': 'vino'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('bebida=ok', resp.url)
        self.assertEqual(self._detalle_ids(venta), [VINO_ID])

    def test_get_no_hace_nada(self):
        venta = self._venta()
        resp = self.client.get(self._url(venta))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._detalle_ids(venta), [107, 108])  # sin cambios
