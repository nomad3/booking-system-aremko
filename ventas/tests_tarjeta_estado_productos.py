"""En la tarjeta móvil cada producto muestra su estado: Pendiente, En proceso, Entregado.

Jorge, 19-09-2026, mirando la tarjeta de la 6859 con dos cafés y un agua sin nada
que dijera cuál estaba entregado: «sería conveniente que en la ficha se vea el
estado de cada producto». Es el mismo reparto por cantidad de la agenda: la
tarjeta no puede decir una cosa y la agenda otra.

Ejecutar:
    python manage.py test ventas.tests_tarjeta_estado_productos
"""
from __future__ import annotations

import re
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import (CategoriaProducto, CategoriaServicio, Cliente, Comanda, Producto,
                           ReservaProducto, Servicio, VentaReserva)
from ventas.views.agenda_operativa_view import _estados_de_lineas


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='deborah_estado', email='d4@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Deborah Prueba', telefono='+56911111122')
        cls.tina = Servicio.objects.create(
            nombre='Tina Hidromasaje Puyehue', precio_base=30000, duracion=120,
            categoria=CategoriaServicio.objects.create(nombre='Tinas'),
            tipo_servicio='tina', activo=True, slots_disponibles={})
        bebestibles = CategoriaProducto.objects.create(nombre='Bebestibles')
        cls.cafe = Producto.objects.create(nombre='Cafe Marley Capuchino Mediano', precio_base=2500,
                                           cantidad_disponible=14, categoria=bebestibles,
                                           venta_meson=True)
        cls.agua = Producto.objects.create(nombre='Agua Mineral Individual con gas',
                                           precio_base=2000, cantidad_disponible=16,
                                           categoria=bebestibles, venta_meson=True)
        cls.giftcard = Producto.objects.create(
            nombre='Gift Card 50.000', precio_base=50000, cantidad_disponible=100,
            categoria=CategoriaProducto.objects.create(nombre='Gift Cards'), venta_meson=True)

    def setUp(self):
        self.client.force_login(self.staff)
        self.venta = VentaReserva.objects.create(cliente=self.cliente)
        self.venta.reservaservicios.create(
            servicio=self.tina, fecha_agendamiento=timezone.localdate(), hora_inicio='21:30',
            cantidad_personas=2, precio_unitario_venta=Decimal('30000'))

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def _agregar(self, producto):
        r = self.client.post(reverse('ventas:tarjeta_agregar_producto', args=[self.venta.pk]),
                             {'producto_id': producto.pk, 'cantidad': 1})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def _tarjeta(self):
        return self.client.get(reverse('ventas:tarjeta_reserva', args=[self.venta.pk]))

    def _la_6859(self):
        ReservaProducto.objects.create(venta_reserva=self.venta, producto=self.cafe, cantidad=1,
                                       precio_unitario_venta=Decimal('2500'))
        self._agregar(self.agua)
        c1 = Comanda.objects.get(venta_reserva=self.venta)
        c1.estado = 'entregada'
        c1.save()
        self._agregar(self.cafe)
        return c1


class CadaProductoConSuEstado(_Base):
    def test_la_6859_primer_cafe_y_agua_entregados_segundo_cafe_pendiente(self):
        self._la_6859()
        r = self._tarjeta()
        estados = [(p.producto.nombre[:4], p.estado_cocina) for p in r.context['productos']]
        self.assertEqual(estados, [('Cafe', 'entregada'), ('Agua', 'entregada'),
                                   ('Cafe', 'pendiente')])
        html = r.content.decode()
        filas = re.findall(r'<span>1× ([^<\n]+?)\s*<span class="est est-(\w+)">([^<]+)</span>', html)
        self.assertEqual([(n[:4], clase, texto) for n, clase, texto in filas],
                         [('Cafe', 'entregada', 'Entregado'), ('Agua', 'entregada', 'Entregado'),
                          ('Cafe', 'pendiente', 'Pendiente')])

    def test_una_comanda_en_proceso_se_lee_en_proceso(self):
        self._agregar(self.cafe)
        Comanda.objects.filter(venta_reserva=self.venta).update(estado='procesando')
        html = self._tarjeta().content.decode()
        self.assertIn('<span class="est est-procesando">En proceso</span>', html)

    def test_la_tarjeta_y_la_agenda_dicen_lo_mismo(self):
        self._la_6859()
        en_tarjeta = {p.pk: p.estado_cocina for p in self._tarjeta().context['productos']}
        self.assertEqual(en_tarjeta, _estados_de_lineas(self.venta))

    def test_lo_que_no_se_prepara_va_sin_etiqueta(self):
        ReservaProducto.objects.create(venta_reserva=self.venta, producto=self.giftcard,
                                       cantidad=1, precio_unitario_venta=Decimal('50000'))
        r = self._tarjeta()
        self.assertIsNone(r.context['productos'][0].estado_cocina)
        self.assertNotIn('class="est ', r.content.decode())


class AlAgregarUnProducto(_Base):
    def test_el_recien_agregado_aparece_pendiente_sin_recargar(self):
        self.assertEqual(self._agregar(self.cafe)['producto']['estado'], 'pendiente')

    def test_una_gift_card_no_trae_estado(self):
        self.assertIsNone(self._agregar(self.giftcard)['producto']['estado'])

    def test_el_js_pinta_la_etiqueta_del_recien_agregado(self):
        html = self._tarjeta().content.decode()
        self.assertIn("d.producto.estado === 'pendiente'", html)
        self.assertIn("est.className = 'est est-pendiente'", html)


class UnaEtiquetaNoTumbaLaTarjeta(_Base):
    def test_si_el_calculo_falla_la_tarjeta_abre_igual(self):
        self._agregar(self.cafe)
        with patch('ventas.services.comanda_productos.estados_para_mostrar',
                   side_effect=RuntimeError('reparto caído')):
            r = self._tarjeta()
        self.assertEqual(r.status_code, 200)
        self.assertIn('Cafe Marley Capuchino Mediano', r.content.decode())
        self.assertNotIn('class="est ', r.content.decode())
