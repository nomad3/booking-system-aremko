"""El segundo café de una reserva: llega a cocina, no nace «entregado» y no se
entrega solo cuando se entrega el primero.

Jorge, 19-09-2026, reserva de prueba 6859: «si se agrega un segundo café a esa
reserva, inmediatamente aparece como entregado, aun cuando nadie lo haya
entregado». Todo calzaba por tipo de producto y no por cantidad, en tres lugares:
qué falta mandar a cocina, qué estado se muestra y qué se marca al entregar.

En 60 días de producción había 6 casos así (reservas 6524, 6558, 6561, 6573,
6761…): dos jugos vendidos y uno solo en la comanda.

Ejecutar:
    python manage.py test ventas.tests_segundo_cafe
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib import admin as dj_admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.admin import ReservaProductoInline
from ventas.models import (CategoriaProducto, CategoriaServicio, Cliente, Comanda, DetalleComanda,
                           Producto, ReservaProducto, Servicio, VentaReserva)
from ventas.services.comanda_productos import (asegurar_comanda_de_productos, estado_de_linea,
                                               repartir_comandas)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='deborah_cafe', email='d2@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Deborah Prueba', telefono='+56911111120')
        cls.tina = Servicio.objects.create(
            nombre='Tina Hidromasaje Puyehue', precio_base=30000, duracion=120,
            categoria=CategoriaServicio.objects.create(nombre='Tinas'),
            tipo_servicio='tina', activo=True, slots_disponibles={})
        bebestibles = CategoriaProducto.objects.create(nombre='Bebestibles')
        cls.cafe = Producto.objects.create(nombre='Cafe Marley Capuchino Mediano', precio_base=2500,
                                           cantidad_disponible=14, categoria=bebestibles,
                                           venta_meson=True)
        cls.jugo = Producto.objects.create(nombre='Jugo Natural de Frambuesa', precio_base=3500,
                                           cantidad_disponible=10, categoria=bebestibles,
                                           venta_meson=True)

    def setUp(self):
        self.client.force_login(self.staff)
        self.venta = VentaReserva.objects.create(cliente=self.cliente)
        self.venta.reservaservicios.create(
            servicio=self.tina, fecha_agendamiento=timezone.localdate(), hora_inicio='21:30',
            cantidad_personas=2, precio_unitario_venta=Decimal('30000'))

    def _agregar(self, producto, cantidad=1):
        r = self.client.post(reverse('ventas:tarjeta_agregar_producto', args=[self.venta.pk]),
                             {'producto_id': producto.pk, 'cantidad': cantidad})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _entregar(self, comanda):
        comanda.estado = 'entregada'
        comanda.save()

    def _stock(self, producto):
        producto.refresh_from_db()
        return producto.cantidad_disponible

    def _estado_en_el_admin(self, linea):
        return ReservaProductoInline(VentaReserva, dj_admin.site).estado_comanda(linea)


class ElSegundoCafe(_Base):
    def test_el_segundo_cafe_tambien_llega_a_cocina(self):
        primera = self._agregar(self.cafe)['comanda']['id']
        segunda = self._agregar(self.cafe)['comanda']
        self.assertIsNotNone(segunda, 'el segundo café se daba por cubierto y no generaba comanda')
        self.assertNotEqual(segunda['id'], primera)
        self.assertEqual(Comanda.objects.get(pk=segunda['id']).detalles.get().cantidad, 1)

    def test_no_nace_entregado_aunque_el_primero_ya_lo_este(self):
        self._agregar(self.cafe)
        self._entregar(Comanda.objects.get(venta_reserva=self.venta))
        self._agregar(self.cafe)
        a, b = self.venta.reservaproductos.order_by('id')
        self.assertEqual(self._estado_en_el_admin(a), '🟢 Entregado')
        self.assertEqual(self._estado_en_el_admin(b), '🟠 Pendiente')
        self.assertIsNotNone(a.fecha_entrega)
        self.assertIsNone(b.fecha_entrega)

    def test_entregar_la_comanda_del_primero_no_entrega_el_segundo(self):
        self._agregar(self.cafe)
        self._agregar(self.cafe)
        c1, c2 = Comanda.objects.filter(venta_reserva=self.venta).order_by('id')
        self._entregar(c1)
        a, b = self.venta.reservaproductos.order_by('id')
        self.assertIsNotNone(a.fecha_entrega)
        self.assertIsNone(b.fecha_entrega, 'se marcaban TODAS las líneas de ese producto')
        self.assertEqual(self._stock(self.cafe), 13, 'el stock baja UNA unidad, no dos')
        self._entregar(c2)
        b.refresh_from_db()
        self.assertIsNotNone(b.fecha_entrega)
        self.assertEqual(self._stock(self.cafe), 12)

    def test_el_cron_de_vencidas_tampoco_arrastra_a_la_otra_linea(self):
        self._agregar(self.cafe)
        self._agregar(self.cafe)
        _, c2 = Comanda.objects.filter(venta_reserva=self.venta).order_by('id')
        self.assertEqual(c2.entregar_inventario(), 1)        # lo que llama el cron
        a, b = self.venta.reservaproductos.order_by('id')
        self.assertIsNone(a.fecha_entrega)
        self.assertIsNotNone(b.fecha_entrega)


class PorCantidadYNoPorTipo(_Base):
    def test_una_linea_de_dos_con_comanda_de_uno_manda_el_que_falta(self):
        # Caso real 6558: dos jugos vendidos, uno solo en la comanda.
        ReservaProducto.objects.create(venta_reserva=self.venta, producto=self.jugo, cantidad=2,
                                       precio_unitario_venta=Decimal('3500'))
        vieja = Comanda.objects.create(venta_reserva=self.venta, estado='pendiente')
        DetalleComanda.objects.create(comanda=vieja, producto=self.jugo, cantidad=1,
                                      precio_unitario=Decimal('3500'))
        nueva = asegurar_comanda_de_productos(self.venta, usuario=self.staff, origen='Tarjeta')
        self.assertIsNotNone(nueva)
        self.assertEqual(nueva.detalles.get().cantidad, 1)

    def test_dos_lineas_sin_cubrir_del_mismo_producto_van_en_un_solo_renglon(self):
        for _ in range(2):
            ReservaProducto.objects.create(venta_reserva=self.venta, producto=self.cafe, cantidad=1,
                                           precio_unitario_venta=Decimal('2500'))
        comanda = asegurar_comanda_de_productos(self.venta, usuario=self.staff)
        self.assertEqual(comanda.detalles.get().cantidad, 2)

    def test_una_segunda_pasada_no_duplica(self):
        self._agregar(self.cafe)
        self._agregar(self.jugo, 2)
        self.assertIsNone(asegurar_comanda_de_productos(self.venta, usuario=self.staff))
        self.assertEqual(Comanda.objects.filter(venta_reserva=self.venta).count(), 2)

    def test_una_comanda_cancelada_no_cubre_nada(self):
        self._agregar(self.cafe)
        Comanda.objects.filter(venta_reserva=self.venta).update(estado='cancelada')
        self.assertIsNotNone(asegurar_comanda_de_productos(self.venta, usuario=self.staff))

    def test_el_reparto_sigue_el_orden_de_venta(self):
        self._agregar(self.cafe)
        self._agregar(self.cafe)
        c1, c2 = Comanda.objects.filter(venta_reserva=self.venta).order_by('id')
        reparto = repartir_comandas(self.venta)
        self.assertEqual([[c.pk for c, _ in it['cubren']] for it in reparto], [[c1.pk], [c2.pk]])
        self.assertEqual([it['sin_cubrir'] for it in reparto], [0, 0])

    def test_una_linea_a_medio_cubrir_se_muestra_sin_comanda(self):
        rp = ReservaProducto.objects.create(venta_reserva=self.venta, producto=self.jugo, cantidad=2,
                                            precio_unitario_venta=Decimal('3500'))
        c = Comanda.objects.create(venta_reserva=self.venta, estado='entregada')
        DetalleComanda.objects.create(comanda=c, producto=self.jugo, cantidad=1,
                                      precio_unitario=Decimal('3500'))
        item = next(it for it in repartir_comandas(self.venta) if it['linea'].pk == rp.pk)
        self.assertEqual(estado_de_linea(item), 'sin_comanda')
        self.assertEqual(self._estado_en_el_admin(rp), '🟠 Pendiente (sin comanda)')
