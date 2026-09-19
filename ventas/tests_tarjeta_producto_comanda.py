"""Un producto agregado desde la tarjeta móvil llega a cocina, igual que desde el admin.

Reserva de prueba 6859 (Jorge, 19-09-2026): Deborah guardó la reserva en el admin
con la tina —el sistema revisó si había productos para cocina, no había— y después
agregaron un café desde la tarjeta. El café quedó vendido y sumado al total, pero
sin comanda: la regla que la crea vivía solo en el guardado del admin.

Ahora la regla vive en ventas/services/comanda_productos.py y la llaman los dos.

Ejecutar:
    python manage.py test ventas.tests_tarjeta_producto_comanda
"""
from __future__ import annotations

import datetime
import inspect
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import (CategoriaProducto, CategoriaServicio, Cliente, Comanda, Producto,
                           ReservaProducto, Servicio, VentaReserva)
from ventas.services.comanda_productos import (asegurar_comanda_de_productos,
                                               se_prepara_en_cocina)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='deborah_tarjeta', email='d@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Deborah Prueba', telefono='+56911111119')
        cls.tina = Servicio.objects.create(
            nombre='Tina Hidromasaje Puyehue', precio_base=30000, duracion=120,
            categoria=CategoriaServicio.objects.create(nombre='Tinas'),
            tipo_servicio='tina', activo=True, slots_disponibles={})
        cls.cafe = Producto.objects.create(
            nombre='Cafe Marley Capuchino Mediano', precio_base=2500, cantidad_disponible=14,
            categoria=CategoriaProducto.objects.create(nombre='Bebestibles'),
            venta_meson=True)
        cls.giftcard = Producto.objects.create(
            nombre='Gift Card 50.000', precio_base=50000, cantidad_disponible=100,
            categoria=CategoriaProducto.objects.create(nombre='Gift Cards'),
            venta_meson=True)

    def setUp(self):
        self.client.force_login(self.staff)

    def tearDown(self):
        # ThreadLocalMiddleware guarda el usuario de la última petición y nadie lo
        # limpia: tras el rollback queda apuntando a un usuario borrado, y la suite
        # que corre después revienta con «usuario_id no existe en auth_user».
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def _venta(self, dia=None, hora='21:30'):
        v = VentaReserva.objects.create(cliente=self.cliente)
        v.reservaservicios.create(servicio=self.tina,
                                  fecha_agendamiento=dia or timezone.localdate(),
                                  hora_inicio=hora, cantidad_personas=2,
                                  precio_unitario_venta=Decimal('30000'))
        return v

    def _agregar(self, venta, producto, cantidad=1):
        return self.client.post(reverse('ventas:tarjeta_agregar_producto', args=[venta.pk]),
                                {'producto_id': producto.pk, 'cantidad': cantidad})


class DesdeLaTarjeta(_Base):
    def test_agregar_un_cafe_crea_su_comanda_para_cocina(self):
        v = self._venta()
        r = self._agregar(v, self.cafe)
        self.assertEqual(r.status_code, 200, r.content)
        comanda = Comanda.objects.get(venta_reserva=v)
        self.assertEqual(comanda.estado, 'pendiente')
        self.assertEqual(comanda.usuario_solicita, self.staff)
        self.assertIn('[Tarjeta]', comanda.notas_generales)
        detalle = comanda.detalles.get()
        self.assertEqual((detalle.producto, detalle.cantidad, int(detalle.precio_unitario)),
                         (self.cafe, 1, 2500))
        # La comanda apunta al horario del primer servicio, como la del admin.
        objetivo = timezone.localtime(comanda.fecha_entrega_objetivo)
        self.assertEqual((objetivo.date(), objetivo.strftime('%H:%M')),
                         (timezone.localdate(), '21:30'))

    def test_la_respuesta_le_dice_a_quien_vende_que_ya_va_a_cocina(self):
        v = self._venta()
        datos = self._agregar(v, self.cafe).json()
        self.assertTrue(datos['ok'])
        self.assertEqual(datos['comanda'], {'id': Comanda.objects.get(venta_reserva=v).id})

    def test_lo_que_no_se_prepara_no_genera_comanda(self):
        v = self._venta()
        datos = self._agregar(v, self.giftcard).json()
        self.assertTrue(datos['ok'])
        self.assertIsNone(datos['comanda'])
        self.assertFalse(Comanda.objects.filter(venta_reserva=v).exists())

    def test_una_reserva_que_ya_paso_no_genera_comanda(self):
        v = self._venta(dia=timezone.localdate() - datetime.timedelta(days=3))
        self._agregar(v, self.cafe)
        self.assertFalse(Comanda.objects.filter(venta_reserva=v).exists())

    def test_si_la_comanda_falla_la_venta_del_producto_no_se_pierde(self):
        v = self._venta()
        with patch('ventas.services.comanda_productos.asegurar_comanda_de_productos',
                   side_effect=RuntimeError('cocina caída')):
            datos = self._agregar(v, self.cafe).json()
        self.assertTrue(datos['ok'])
        self.assertIsNone(datos['comanda'])
        self.assertTrue(ReservaProducto.objects.filter(venta_reserva=v, producto=self.cafe).exists())
        v.refresh_from_db()
        self.assertEqual(int(v.total), 62500)


class ElAdminYLaTarjetaHacenLoMismo(_Base):
    def test_la_regla_del_admin_es_la_misma_funcion(self):
        v = self._venta()
        ReservaProducto.objects.create(venta_reserva=v, producto=self.cafe, cantidad=2,
                                       precio_unitario_venta=Decimal('2500'))
        comanda = asegurar_comanda_de_productos(v, usuario=self.staff, origen='Admin')
        self.assertIn('[Admin]', comanda.notas_generales)
        self.assertEqual(comanda.detalles.get().cantidad, 2)
        # Con la comanda ya creada, una segunda pasada no duplica.
        self.assertIsNone(asegurar_comanda_de_productos(v, usuario=self.staff))
        self.assertEqual(Comanda.objects.filter(venta_reserva=v).count(), 1)

    def test_el_admin_no_tiene_una_copia_propia_de_la_regla(self):
        # Método duplicado pisa al original (08-09-2026): una sola definición de cada cosa.
        import ventas.admin as admin_mod
        fuente = inspect.getsource(admin_mod)
        self.assertNotIn('def _se_prepara_en_cocina(', fuente)
        self.assertEqual(fuente.count('def _asegurar_comanda_de_productos('), 1)
        self.assertIs(admin_mod._se_prepara_en_cocina, se_prepara_en_cocina)   # Luna lo importa de acá
        self.assertNotIn('Comanda.objects.create(', inspect.getsource(
            admin_mod.VentaReservaAdmin._asegurar_comanda_de_productos))

    def test_guardar_la_reserva_en_el_admin_sigue_creando_la_comanda(self):
        from django.contrib import admin as dj_admin
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        from ventas.admin import VentaReservaAdmin
        v = self._venta()
        ReservaProducto.objects.create(venta_reserva=v, producto=self.cafe, cantidad=1,
                                       precio_unitario_venta=Decimal('2500'))
        req = RequestFactory().post('/')
        req.user = self.staff
        req.session = {}
        req._messages = FallbackStorage(req)
        VentaReservaAdmin(VentaReserva, dj_admin.site)._asegurar_comanda_de_productos(req, v)
        self.assertEqual(Comanda.objects.filter(venta_reserva=v).count(), 1)
        self.assertTrue(any('creada automáticamente' in str(m) for m in req._messages))
