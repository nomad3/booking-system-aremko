"""Agregar un servicio de una lista, sin pasar por el calendario.

Jorge (05-09-2026): "para los servicios muestra en la vista los calendarios y
eso es correcto, pero también debe dar la posibilidad de elegir servicios de
una lista, la lista visible del admin de django".

El calendario está hecho para lo que OCUPA una hora. Para chocolates, el
desayuno de una cabaña o una comisión de Booking es un trámite: elegir fecha,
esperar la grilla, elegir una hora que da lo mismo cuál sea.

Se da la lista completa, como el admin — pero el admin NO valida
disponibilidad, y por acá sí: agregar una tina a una hora ocupada es
sobreventa, y eso no se arregla después.

Ejecutar:
    python manage.py test ventas.tests_tarjeta_servicio_lista
"""
from __future__ import annotations

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import (Cliente, CategoriaServicio, ReservaServicio,
                           Servicio, VentaReserva)


class BaseLista(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='cajera_lista', email='l@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Ana', telefono='+56977778888')
        otros = CategoriaServicio.objects.create(nombre='Otros')
        # Lo que motivó el botón: no ocupa hora.
        cls.chocolates = Servicio.objects.create(
            nombre='Caja de chocolates', precio_base=16000, categoria=otros,
            duracion=0, tipo_servicio='otro', activo=True)
        # Lo que sí ocupa hora, con un horario declarado.
        cls.tina = Servicio.objects.create(
            nombre='Tina Hidromasaje', precio_base=40000,
            categoria=CategoriaServicio.objects.create(nombre='Tinas'),
            duracion=60, tipo_servicio='tina', activo=True,
            slots_disponibles={'monday': ['14:00'], 'tuesday': ['14:00'],
                               'wednesday': ['14:00'], 'thursday': ['14:00'],
                               'friday': ['14:00'], 'saturday': ['14:00'],
                               'sunday': ['14:00']})
        cls.descuento = Servicio.objects.create(
            nombre='Descuento_Servicios', precio_base=-1,
            categoria=CategoriaServicio.objects.create(nombre='Descuento_Servicio'),
            duracion=0, tipo_servicio='otro', activo=True)
        cls.retirado = Servicio.objects.create(
            nombre='San Valentin', precio_base=40000, categoria=otros,
            duracion=0, tipo_servicio='otro', activo=False)

    def setUp(self):
        self.client.force_login(self.staff)
        self.venta = VentaReserva.objects.create(cliente=self.cliente)
        self.url = reverse('ventas:tarjeta_agregar_servicio_lista',
                           args=[self.venta.pk])

    def _agregar(self, servicio=None, **extra):
        datos = {'servicio_id': (servicio or self.chocolates).pk, 'cantidad': '1'}
        datos.update(extra)
        return self.client.post(self.url, datos)


class LoQueNoOcupaHora(BaseLista):
    def test_se_agrega_sin_calendario(self):
        self.assertTrue(self._agregar().json()['ok'])
        linea = ReservaServicio.objects.get(venta_reserva=self.venta)
        self.assertEqual(linea.servicio, self.chocolates)

    def test_no_pregunta_por_la_hora(self):
        # Para chocolates la hora es una pregunta sin respuesta.
        self._agregar()
        self.assertEqual(
            ReservaServicio.objects.get(venta_reserva=self.venta).hora_inicio, '00:00')

    def test_respeta_la_cantidad(self):
        self._agregar(cantidad='3')
        self.assertEqual(
            ReservaServicio.objects.get(venta_reserva=self.venta).cantidad_personas, 3)

    def test_congela_el_precio(self):
        # Si mañana sube el catálogo, lo ya vendido no cambia.
        self._agregar()
        self.assertEqual(
            int(ReservaServicio.objects.get(venta_reserva=self.venta)
                .precio_unitario_venta), 16000)

    def test_el_total_sube(self):
        self._agregar()
        self.venta.refresh_from_db()
        self.assertEqual(int(self.venta.total), 16000)

    def test_cae_en_la_fecha_de_los_servicios_de_la_reserva(self):
        visita = timezone.localdate() + datetime.timedelta(days=10)
        ReservaServicio.objects.create(
            venta_reserva=self.venta, servicio=self.tina,
            fecha_agendamiento=visita, hora_inicio='14:00',
            cantidad_personas=2, precio_unitario_venta=40000)
        self._agregar()
        nuevo = ReservaServicio.objects.get(servicio=self.chocolates)
        self.assertEqual(nuevo.fecha_agendamiento, visita)

    def test_se_puede_dar_otra_fecha(self):
        otro = timezone.localdate() + datetime.timedelta(days=3)
        self._agregar(fecha=otro.strftime('%Y-%m-%d'))
        self.assertEqual(
            ReservaServicio.objects.get(servicio=self.chocolates).fecha_agendamiento,
            otro)


class NoSobrevender(BaseLista):
    """El admin deja agregar una tina a cualquier hora y por eso existe el
    calendario. Esta puerta NO puede ser un atajo para saltarse eso."""

    def _manana_14(self):
        return (timezone.localdate() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    def test_una_tina_en_un_horario_libre_entra(self):
        r = self._agregar(self.tina, fecha=self._manana_14(), hora='14:00')
        self.assertTrue(r.json()['ok'], r.json())

    def test_una_tina_YA_TOMADA_se_rechaza(self):
        dia = timezone.localdate() + datetime.timedelta(days=1)
        ReservaServicio.objects.create(
            venta_reserva=VentaReserva.objects.create(cliente=self.cliente),
            servicio=self.tina, fecha_agendamiento=dia, hora_inicio='14:00',
            cantidad_personas=2, precio_unitario_venta=40000)
        r = self._agregar(self.tina, fecha=self._manana_14(), hora='14:00')
        self.assertFalse(r.json()['ok'])
        self.assertIn('calendario', r.json()['mensaje'])
        self.assertEqual(ReservaServicio.objects.filter(venta_reserva=self.venta).count(), 0)

    def test_una_tina_a_una_hora_que_no_existe_se_rechaza(self):
        # 03:00 no está en los horarios declarados del servicio.
        r = self._agregar(self.tina, fecha=self._manana_14(), hora='03:00')
        self.assertFalse(r.json()['ok'])

    def test_si_la_verificacion_falla_NO_se_agrega(self):
        # Ante la duda, no vender: un error técnico no puede convertirse en
        # una tina sobrevendida.
        with patch('ventas.calendar_utils.verificar_disponibilidad',
                   side_effect=RuntimeError('BD caída')):
            r = self._agregar(self.tina, fecha=self._manana_14(), hora='14:00')
        self.assertFalse(r.json()['ok'])
        self.assertEqual(ReservaServicio.objects.filter(venta_reserva=self.venta).count(), 0)

    def test_lo_que_no_ocupa_hora_NO_pasa_por_esa_validacion(self):
        # Dos cajas de chocolates el mismo día no son un conflicto.
        self._agregar()
        self.assertTrue(self._agregar().json()['ok'])
        self.assertEqual(ReservaServicio.objects.filter(venta_reserva=self.venta).count(), 2)


class LaListaQueSeOfrece(BaseLista):
    def _tarjeta(self):
        return self.client.get(
            reverse('ventas:tarjeta_reserva', args=[self.venta.pk])
        ).content.decode()

    def test_ofrece_el_boton(self):
        self.assertIn('Agregar de la lista', self._tarjeta())

    def test_incluye_los_servicios_activos(self):
        self.assertIn('Caja de chocolates', self._tarjeta())

    def test_NO_incluye_los_descuentos(self):
        # Tienen su propio botón, donde se escribe el monto en pesos. Dejarlos
        # acá sería reofrecer el camino confuso que se acaba de sacar.
        html = self._tarjeta()
        bloque = html.split('id="listaSelect"')[1].split('</select>')[0]
        self.assertNotIn('Descuento', bloque)

    def test_NO_incluye_los_servicios_dados_de_baja(self):
        html = self._tarjeta()
        bloque = html.split('id="listaSelect"')[1].split('</select>')[0]
        self.assertNotIn('San Valentin', bloque)

    def test_el_servidor_tampoco_acepta_un_descuento(self):
        # Ni desde una pestaña vieja que todavía lo muestre.
        r = self._agregar(self.descuento)
        self.assertFalse(r.json()['ok'])
        self.assertIn('Aplicar descuento', r.json()['mensaje'])

    def test_el_servidor_tampoco_acepta_uno_dado_de_baja(self):
        self.assertFalse(self._agregar(self.retirado).json()['ok'])


class SoloElPersonal(BaseLista):
    def test_un_desconocido_no_puede_agregar(self):
        self.client.logout()
        r = self._agregar()
        self.assertNotEqual(r.status_code, 200)
        self.assertEqual(ReservaServicio.objects.count(), 0)
