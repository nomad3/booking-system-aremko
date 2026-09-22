"""Una reserva cancelada no ocupa su horario (P-41, 22-09-2026).

Los caminos que deciden disponibilidad —`verificar_disponibilidad` (tarjeta,
checkout, señal, Luna), la vitrina web (`is_slot_available`,
`get_available_hours`), el carrito (`validar_disponibilidad_carrito`) y la
señal de masajistas en sitio de Luna— contaban TODAS las líneas de servicio
del slot, sin mirar si la venta estaba cancelada. El código marca una
cancelación de dos formas (`estado_reserva='cancelada'` o
`estado_pago='cancelado'`); el filtro único vive en
`ventas/services/ocupacion.py` y estas pruebas cubren las dos marcas.

Cada prueba tiene su control: la MISMA reserva sin cancelar sí bloquea. Así
un filtro roto en cualquiera de los dos sentidos se nota.

Ejecutar:
    python manage.py test ventas.tests_reserva_cancelada_no_bloquea
"""
from __future__ import annotations

import json

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.calendar_utils import verificar_disponibilidad
from ventas.models import (CategoriaServicio, Cliente, ReservaServicio,
                           Servicio, VentaReserva)
from ventas.services.ocupacion import lineas_vigentes
from ventas.services.reservation_service import validar_disponibilidad_carrito
from ventas.views.availability_views import is_slot_available
from whatsapp_agent.availability import _hay_masaje_agendado_hoy

HORA = '14:00'
DIAS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',
        'sunday')
HORARIO = {d: [HORA] for d in DIAS}


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nombre='Ana', telefono='+56900001111')
        cls.tina = Servicio.objects.create(
            nombre='Tina Hornopiren', precio_base=40000,
            categoria=CategoriaServicio.objects.create(nombre='Tinas'),
            duracion=60, tipo_servicio='tina', activo=True,
            capacidad_maxima=2, max_servicios_simultaneos=1,
            slots_disponibles=HORARIO)
        cls.masaje = Servicio.objects.create(
            nombre='Masaje relajación', precio_base=45000,
            categoria=CategoriaServicio.objects.create(nombre='Masajes'),
            duracion=50, tipo_servicio='masaje', activo=True,
            capacidad_maxima=1, max_servicios_simultaneos=1,
            slots_disponibles=HORARIO)
        cls.hoy = timezone.localdate()

    def _reservar(self, servicio, estado_reserva='pendiente', estado_pago='pagado'):
        """Primero se reserva, después se cancela: el mismo orden que en la vida.

        Al revés no sirve: crear la línea dispara señales que vuelven a guardar
        la venta con lo que tenía en memoria y pisan la marca. Y `cancelada`
        no está en las choices del desplegable —es la marca que usan la agenda,
        iCal y los bloqueos—, así que va con `update()`.
        """
        venta = VentaReserva.objects.create(cliente=self.cliente)
        ReservaServicio.objects.create(
            venta_reserva=venta, servicio=servicio, fecha_agendamiento=self.hoy,
            hora_inicio=HORA, cantidad_personas=2,
            precio_unitario_venta=servicio.precio_base)
        VentaReserva.objects.filter(pk=venta.pk).update(
            estado_reserva=estado_reserva, estado_pago=estado_pago)
        return venta


class ElFiltro(Base):
    def test_excluye_las_dos_marcas_y_conserva_las_vigentes(self):
        viva = self._reservar(self.tina)
        por_reserva = self._reservar(self.tina, estado_reserva='cancelada')
        por_pago = self._reservar(self.tina, estado_pago='cancelado')
        ids = set(lineas_vigentes().values_list('venta_reserva_id', flat=True))
        self.assertIn(viva.pk, ids)
        self.assertNotIn(por_reserva.pk, ids)
        self.assertNotIn(por_pago.pk, ids)

    def test_acepta_un_queryset_ya_filtrado(self):
        self._reservar(self.tina, estado_reserva='cancelada')
        self._reservar(self.masaje)
        base = ReservaServicio.objects.filter(servicio=self.tina)
        self.assertEqual(lineas_vigentes(base).count(), 0)


class VerificarDisponibilidad(Base):
    """El camino de la tarjeta, el checkout, la señal y Luna."""

    def test_control_la_reserva_viva_bloquea(self):
        self._reservar(self.tina)
        self.assertFalse(verificar_disponibilidad(self.tina, self.hoy, HORA, 2))

    def test_cancelada_por_estado_de_reserva_libera_la_hora(self):
        self._reservar(self.tina, estado_reserva='cancelada')
        self.assertTrue(verificar_disponibilidad(self.tina, self.hoy, HORA, 2))

    def test_cancelada_por_estado_de_pago_libera_la_hora(self):
        self._reservar(self.tina, estado_pago='cancelado')
        self.assertTrue(verificar_disponibilidad(self.tina, self.hoy, HORA, 2))

    def test_masaje_cancelado_libera_la_hora(self):
        self._reservar(self.masaje, estado_reserva='cancelada')
        self.assertTrue(verificar_disponibilidad(self.masaje, self.hoy, HORA, 1))
        self._reservar(self.masaje)
        self.assertFalse(verificar_disponibilidad(self.masaje, self.hoy, HORA, 1))


class VitrinaWeb(Base):
    def test_is_slot_available_ignora_la_cancelada(self):
        self._reservar(self.tina, estado_reserva='cancelada')
        self.assertTrue(is_slot_available(self.tina, self.hoy, HORA))
        self._reservar(self.tina)
        self.assertFalse(is_slot_available(self.tina, self.hoy, HORA))

    def _horas(self):
        r = self.client.get(reverse('ventas:get_available_hours'),
                            {'servicio_id': self.tina.pk, 'fecha': self.hoy.isoformat()})
        self.assertEqual(r.status_code, 200)
        return json.loads(r.content)['horas_disponibles']

    def test_get_available_hours_muestra_la_hora_de_una_cancelada(self):
        self._reservar(self.tina, estado_pago='cancelado')
        self.assertIn(HORA, self._horas())

    def test_control_get_available_hours_esconde_la_hora_ocupada(self):
        self._reservar(self.tina)
        self.assertNotIn(HORA, self._horas())


class Carrito(Base):
    def _carrito(self):
        return {'servicios': [{'id': self.tina.pk, 'fecha': self.hoy.isoformat(),
                               'hora': HORA}]}

    def test_la_cancelada_no_frena_el_carrito(self):
        self._reservar(self.tina, estado_reserva='cancelada')
        self.assertEqual(validar_disponibilidad_carrito(self._carrito()), [])

    def test_control_la_viva_si_frena_el_carrito(self):
        self._reservar(self.tina)
        self.assertEqual(len(validar_disponibilidad_carrito(self._carrito())), 1)


class MasajistasEnSitio(Base):
    def test_un_masaje_cancelado_no_cuenta_como_masajista_en_sitio(self):
        self._reservar(self.masaje, estado_reserva='cancelada')
        self.assertFalse(_hay_masaje_agendado_hoy(self.hoy))
        self._reservar(self.masaje)
        self.assertTrue(_hay_masaje_agendado_hoy(self.hoy))
