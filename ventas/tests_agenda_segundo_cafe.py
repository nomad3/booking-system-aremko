"""La agenda muestra el estado de CADA línea, y su botón «Entregar» entrega la
comanda de ESA línea.

Jorge, reserva 6859, 19-09-2026, después del arreglo del segundo café: entregó la
primera comanda (café + agua), agregó un segundo café, y la agenda mostró LOS DOS
cafés en «Pendiente» y solo el agua en «Entregado». La base de datos estaba bien
—primer café entregado y descontado, segundo con su comanda pendiente—; la que
mentía era la agenda, que tenía su propia regla «la comanda más reciente con ese
producto pisa». Su botón de un click tenía la misma: apretar «Entregar» en el
primer café habría entregado la comanda del segundo.

Ejecutar:
    python manage.py test ventas.tests_agenda_segundo_cafe
"""
from __future__ import annotations

import json
from decimal import Decimal

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
            username='deborah_agenda', email='d3@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Deborah Prueba', telefono='+56911111121')
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

    def setUp(self):
        self.client.force_login(self.staff)
        self.venta = VentaReserva.objects.create(cliente=self.cliente)
        self.venta.reservaservicios.create(
            servicio=self.tina, fecha_agendamiento=timezone.localdate(), hora_inicio='21:30',
            cantidad_personas=2, precio_unitario_venta=Decimal('30000'))

    def tearDown(self):
        # ThreadLocalMiddleware guarda el usuario de la última petición y nadie lo
        # limpia: tras el rollback queda apuntando a un usuario borrado, y la suite
        # que corre después revienta con «usuario_id no existe en auth_user».
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def _agregar(self, producto):
        r = self.client.post(reverse('ventas:tarjeta_agregar_producto', args=[self.venta.pk]),
                             {'producto_id': producto.pk, 'cantidad': 1})
        self.assertEqual(r.status_code, 200, r.content)

    def _la_6859(self):
        """Café + agua en la comanda 1, entregada; después un segundo café (comanda 2)."""
        ReservaProducto.objects.create(venta_reserva=self.venta, producto=self.cafe, cantidad=1,
                                       precio_unitario_venta=Decimal('2500'))
        self._agregar(self.agua)                       # comanda 1: café huérfano + agua
        c1 = Comanda.objects.get(venta_reserva=self.venta)
        c1.estado = 'entregada'
        c1.save()
        self._agregar(self.cafe)                       # comanda 2: el segundo café
        c2 = Comanda.objects.filter(venta_reserva=self.venta).exclude(pk=c1.pk).get()
        cafe1, agua, cafe2 = self.venta.reservaproductos.order_by('id')
        return c1, c2, cafe1, agua, cafe2

    def _click_entregar(self, linea):
        return self.client.post(reverse('ventas:producto_marcar_entregado_api'),
                                json.dumps({'reserva_producto_id': linea.pk}),
                                content_type='application/json')

    def _stock(self, producto):
        producto.refresh_from_db()
        return producto.cantidad_disponible


class LoQueMuestraLaAgenda(_Base):
    def test_el_primer_cafe_entregado_y_el_segundo_pendiente(self):
        _, _, cafe1, agua, cafe2 = self._la_6859()
        estados = _estados_de_lineas(self.venta)
        self.assertEqual(estados[cafe1.pk], 'entregada', 'la agenda lo mostraba Pendiente')
        self.assertEqual(estados[agua.pk], 'entregada')
        self.assertEqual(estados[cafe2.pk], 'pendiente')

    def test_la_pagina_de_la_agenda_pinta_eso_mismo(self):
        _, _, cafe1, agua, cafe2 = self._la_6859()
        r = self.client.get(reverse('ventas:agenda_operativa'))
        self.assertEqual(r.status_code, 200)
        pintados = {}
        for bloque in r.context['agenda']:
            for item in bloque['items']:
                for p in item.get('productos') or []:
                    pintados[p.pk] = p.estado_comanda
        self.assertEqual(pintados.get(cafe1.pk), 'entregada')
        self.assertEqual(pintados.get(agua.pk), 'entregada')
        self.assertEqual(pintados.get(cafe2.pk), 'pendiente')

    def test_un_producto_sin_comanda_se_muestra_pendiente(self):
        rp = ReservaProducto.objects.create(venta_reserva=self.venta, producto=self.cafe,
                                            cantidad=1, precio_unitario_venta=Decimal('2500'))
        self.assertEqual(_estados_de_lineas(self.venta)[rp.pk], 'pendiente')


class ElBotonEntregarDeLaAgenda(_Base):
    def test_entregar_el_segundo_cafe_entrega_SU_comanda(self):
        c1, c2, cafe1, _, cafe2 = self._la_6859()
        self.assertEqual(self._stock(self.cafe), 13)          # ya bajó por el primero
        r = self._click_entregar(cafe2)
        self.assertTrue(r.json()['success'])
        self.assertEqual(r.json()['comanda_id'], c2.pk)
        cafe2.refresh_from_db()
        self.assertIsNotNone(cafe2.fecha_entrega)
        self.assertEqual(self._stock(self.cafe), 12)

    def test_apretar_entregar_en_el_primero_NO_entrega_el_segundo(self):
        # Con la regla vieja esto entregaba la comanda 2: «la más reciente con café».
        c1, c2, cafe1, _, cafe2 = self._la_6859()
        r = self._click_entregar(cafe1)
        self.assertTrue(r.json()['success'])
        self.assertEqual(r.json()['comanda_id'], c1.pk)
        c2.refresh_from_db(); cafe2.refresh_from_db()
        self.assertEqual(c2.estado, 'pendiente')
        self.assertIsNone(cafe2.fecha_entrega)
        self.assertEqual(self._stock(self.cafe), 13, 'no puede descontar el segundo café')

    def test_un_producto_sin_comanda_se_entrega_y_AHORA_si_descuenta_stock(self):
        rp = ReservaProducto.objects.create(venta_reserva=self.venta, producto=self.agua,
                                            cantidad=2, precio_unitario_venta=Decimal('2000'))
        r = self._click_entregar(rp)
        self.assertTrue(r.json()['success'])
        comanda = Comanda.objects.get(pk=r.json()['comanda_id'])
        self.assertEqual((comanda.estado, comanda.detalles.get().cantidad), ('entregada', 2))
        rp.refresh_from_db()
        self.assertIsNotNone(rp.fecha_entrega)
        self.assertEqual(self._stock(self.agua), 14, 'una comanda que nace entregada no descontaba')

    def test_apretar_dos_veces_no_descuenta_dos_veces(self):
        _, _, _, _, cafe2 = self._la_6859()
        self._click_entregar(cafe2)
        self._click_entregar(cafe2)
        self.assertEqual(self._stock(self.cafe), 12)
        self.assertEqual(Comanda.objects.filter(venta_reserva=self.venta).count(), 2)
