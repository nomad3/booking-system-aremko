# -*- coding: utf-8 -*-
"""Las comandas siguen a la reserva cuando se mueve de fecha (caso 6586).

Lo que clava esta suite:

· Mover la fecha de un servicio mueve las comandas pendientes ancladas a ESE
  horario — y solo esas: la anclada a otro momento (pedido desde la tina el
  segundo día) y la ya entregada no se tocan.
· La etiqueta de destino distingue hoy / ya empezó / futuro: antes un servicio
  del 29/08 se mostraba "(en curso)" el 22/08.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from django.contrib.auth.models import User

from ventas.comandas_objetivo import objetivo_de, reanclar_comandas
from ventas.models import (CategoriaServicio, Cliente, Comanda, Producto,
                           ReservaProducto, ReservaServicio, Servicio,
                           VentaReserva)
from ventas.views.agenda_operativa_view import calcular_destino_comanda
from whatsapp_agent.tests.test_giftcards_luna import _SinSenalesDeVenta

HOY = date(2026, 8, 22)
EL_29 = date(2026, 8, 29)


class _Base(_SinSenalesDeVenta, TestCase):

    @classmethod
    def setUpTestData(cls):
        cat = CategoriaServicio.objects.create(id=9201, nombre='Tinas')
        cat_cab = CategoriaServicio.objects.create(id=9202, nombre='Cabañas')
        cls.tina = Servicio.objects.create(
            id=9211, nombre='Tina Hidromasaje Villarrica', categoria=cat,
            tipo_servicio='tina', precio_base=Decimal('30000'), duracion=120,
            activo=True)
        cls.cabana = Servicio.objects.create(
            id=9212, nombre='Cabaña Arrayan', categoria=cat_cab,
            tipo_servicio='cabana', precio_base=Decimal('55000'), duracion=60,
            activo=True)

    def _reserva(self, telefono='+56949138196'):
        cliente = Cliente.objects.create(nombre='Alexis', telefono=telefono)
        return VentaReserva.objects.create(cliente=cliente, total=0,
                                           estado_reserva='pendiente',
                                           fecha_reserva=timezone.now())

    def _servicio(self, venta, servicio, fecha, hora):
        return ReservaServicio.objects.create(
            venta_reserva=venta, servicio=servicio, fecha_agendamiento=fecha,
            hora_inicio=hora, cantidad_personas=2,
            precio_unitario_venta=servicio.precio_base)

    def _comanda(self, venta, objetivo, estado='pendiente'):
        return Comanda.objects.create(venta_reserva=venta, estado=estado,
                                      fecha_entrega_objetivo=objetivo)


class ObjetivoDeTest(TestCase):

    def test_compone_fecha_y_hora(self):
        o = objetivo_de(EL_29, '21:30')
        self.assertEqual(timezone.localtime(o).strftime('%Y-%m-%d %H:%M'),
                         '2026-08-29 21:30')

    def test_hora_vacia_o_rara_cae_a_mediodia(self):
        self.assertEqual(timezone.localtime(objetivo_de(EL_29, '')).hour, 12)
        self.assertEqual(timezone.localtime(objetivo_de(EL_29, 'xx')).hour, 12)

    def test_sin_fecha_es_none(self):
        self.assertIsNone(objetivo_de(None, '21:30'))


class ComandasSiguenAlServicioTest(_Base):

    def test_mover_la_fecha_del_servicio_mueve_la_comanda_anclada(self):
        # El caso 6586 tal cual: tina el 22 a las 21:30 con comanda anclada ahí,
        # el cliente se cambia al 29.
        v = self._reserva()
        rs = self._servicio(v, self.tina, HOY, '21:30')
        c = self._comanda(v, objetivo_de(HOY, '21:30'))
        rs.fecha_agendamiento = EL_29
        rs.save()
        c.refresh_from_db()
        self.assertEqual(c.fecha_entrega_objetivo, objetivo_de(EL_29, '21:30'))

    def test_mover_solo_la_hora_tambien_la_mueve(self):
        v = self._reserva()
        rs = self._servicio(v, self.tina, HOY, '21:30')
        c = self._comanda(v, objetivo_de(HOY, '21:30'))
        rs.hora_inicio = '19:00'
        rs.save()
        c.refresh_from_db()
        self.assertEqual(c.fecha_entrega_objetivo, objetivo_de(HOY, '19:00'))

    def test_la_comanda_anclada_a_otro_momento_no_se_toca(self):
        # Pedido hecho desde la tina "ahora": no está anclado al servicio.
        v = self._reserva()
        rs = self._servicio(v, self.tina, HOY, '21:30')
        otro_momento = objetivo_de(HOY, '18:05')
        c = self._comanda(v, otro_momento)
        rs.fecha_agendamiento = EL_29
        rs.save()
        c.refresh_from_db()
        self.assertEqual(c.fecha_entrega_objetivo, otro_momento)

    def test_la_comanda_entregada_no_se_toca(self):
        v = self._reserva()
        rs = self._servicio(v, self.tina, HOY, '21:30')
        c = self._comanda(v, objetivo_de(HOY, '21:30'), estado='entregada')
        rs.fecha_agendamiento = EL_29
        rs.save()
        c.refresh_from_db()
        self.assertEqual(c.fecha_entrega_objetivo, objetivo_de(HOY, '21:30'))

    def test_guardar_sin_cambiar_fecha_ni_hora_no_hace_nada(self):
        v = self._reserva()
        rs = self._servicio(v, self.tina, HOY, '21:30')
        c = self._comanda(v, objetivo_de(HOY, '21:30'))
        rs.cantidad_personas = 3
        rs.save()
        c.refresh_from_db()
        self.assertEqual(c.fecha_entrega_objetivo, objetivo_de(HOY, '21:30'))

    def test_cada_comanda_sigue_a_su_propio_servicio(self):
        # 6586 real: #792 anclada a la cabaña 16:00 y #791 a la tina 21:30.
        v = self._reserva()
        rs_cab = self._servicio(v, self.cabana, HOY, '16:00')
        rs_tina = self._servicio(v, self.tina, HOY, '21:30')
        c_cab = self._comanda(v, objetivo_de(HOY, '16:00'))
        c_tina = self._comanda(v, objetivo_de(HOY, '21:30'))
        for rs in (rs_cab, rs_tina):
            rs.fecha_agendamiento = EL_29
            rs.save()
        c_cab.refresh_from_db()
        c_tina.refresh_from_db()
        self.assertEqual(c_cab.fecha_entrega_objetivo, objetivo_de(EL_29, '16:00'))
        self.assertEqual(c_tina.fecha_entrega_objetivo, objetivo_de(EL_29, '21:30'))

    def test_reanclar_devuelve_cuantas_movio(self):
        v = self._reserva()
        self._comanda(v, objetivo_de(HOY, '21:30'))
        self._comanda(v, objetivo_de(HOY, '21:30'))
        n = reanclar_comandas(v.id, HOY, '21:30', EL_29, '21:30')
        self.assertEqual(n, 2)
        self.assertEqual(reanclar_comandas(v.id, HOY, '21:30', HOY, '21:30'), 0)


class EtiquetaDestinoTest(_Base):

    def test_servicio_de_hoy_muestra_la_hora(self):
        v = self._reserva()
        self._servicio(v, self.tina, HOY, '21:30')
        d = calcular_destino_comanda(v, hoy=HOY)
        self.assertEqual(d['label'], 'Tina Hidromasaje Villarrica · 21:30')

    def test_servicio_futuro_muestra_fecha_y_hora_no_en_curso(self):
        v = self._reserva()
        self._servicio(v, self.tina, EL_29, '21:30')
        d = calcular_destino_comanda(v, hoy=HOY)
        self.assertEqual(d['label'], 'Tina Hidromasaje Villarrica · 29/08 21:30')
        self.assertNotIn('en curso', d['label'])

    def test_servicio_que_ya_empezo_sigue_en_curso(self):
        v = self._reserva()
        self._servicio(v, self.cabana, HOY - timedelta(days=1), '16:00')
        d = calcular_destino_comanda(v, hoy=HOY)
        self.assertEqual(d['label'], 'Cabaña Arrayan · (en curso)')


class FechaEntregaSoloLecturaEnElAdminTest(_Base):
    """Pieza 2 del caso 6586: la «Fecha de entrega» del producto ya no se edita
    en la reserva. Para el sistema significa «YA se entregó» (descuenta stock),
    pero el tooltip decía «fue/será entregado» y se usaba como fecha planificada."""

    def test_el_inline_muestra_entregado_el_y_no_deja_editar_fecha_entrega(self):
        admin_user = User.objects.create_superuser('jefe', 'j@aremko.cl', 'x')
        self.client.force_login(admin_user)
        v = self._reserva()
        prod = Producto.objects.create(nombre='Tabla Mixta', precio_base=36000,
                                       cantidad_disponible=24)
        ReservaProducto.objects.create(venta_reserva=v, producto=prod, cantidad=1)
        resp = self.client.get(f'/admin/ventas/ventareserva/{v.id}/change/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Entregado el')
        self.assertContains(resp, '— (pendiente)')
        # Ningún input editable de fecha_entrega en el inline de productos.
        self.assertNotContains(resp, 'reservaproductos-0-fecha_entrega')
