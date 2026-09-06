"""La señal de disponibilidad ya no grita por servicios sin horario.

Jorge (06-09-2026), al ver el registro del botón nuevo: "dale con el arreglo
de la alarma falsa".

`verificar_disponibilidad` responde "no disponible" para cualquier servicio
sin slots declarados —una caja de chocolates, un desayuno, una comisión— y la
señal anotaba un ERROR por cada uno. Nunca bloqueó nada; solo ensuciaba el
registro y tapaba los avisos que sí importan.

ADEMÁS quedó documentado acá algo más grave que se descubrió de paso: la
señal NUNCA bloquea, ni siquiera una sobreventa real. El `raise
ValidationError` está dentro del `try` y el `except Exception` de abajo lo
atrapa y solo lo anota. Se deja tal cual a propósito —encenderlo cambiaría
cómo se comporta todo el sistema y eso lo decide Jorge—, pero con una prueba
que lo fija para que nadie lo "arregle" sin querer.

Ejecutar:
    python manage.py test ventas.tests_senal_disponibilidad
"""
from __future__ import annotations

import logging

from django.test import TestCase
from django.utils import timezone

from ventas.models import (CategoriaServicio, Cliente, ReservaServicio,
                           Servicio, VentaReserva)

HORARIO = {d: ['14:00'] for d in ('monday', 'tuesday', 'wednesday', 'thursday',
                                  'friday', 'saturday', 'sunday')}


class BaseSenal(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nombre='Ana', telefono='+56900001111')
        otros = CategoriaServicio.objects.create(nombre='Otros')
        cls.chocolates = Servicio.objects.create(
            nombre='Caja de chocolates', precio_base=16000, categoria=otros,
            duracion=0, tipo_servicio='otro', activo=True)
        cls.tina = Servicio.objects.create(
            nombre='Tina Hornopiren', precio_base=40000,
            categoria=CategoriaServicio.objects.create(nombre='Tinas'),
            duracion=60, tipo_servicio='tina', activo=True,
            slots_disponibles=HORARIO)

    def setUp(self):
        self.venta = VentaReserva.objects.create(cliente=self.cliente)

    def _crear(self, servicio, hora='00:00'):
        return ReservaServicio.objects.create(
            venta_reserva=self.venta, servicio=servicio,
            fecha_agendamiento=timezone.localdate(), hora_inicio=hora,
            cantidad_personas=1, precio_unitario_venta=servicio.precio_base)


class NoGritaPorLoQueNoTieneHorario(BaseSenal):
    def test_los_chocolates_no_anotan_ningun_error(self):
        with self.assertLogs('ventas.signals.main_signals', level='ERROR') as cm:
            logging.getLogger('ventas.signals.main_signals').error('centinela')
            self._crear(self.chocolates)
        # Solo el centinela: la señal no agregó nada.
        self.assertEqual(len(cm.output), 1)
        self.assertIn('centinela', cm.output[0])

    def test_los_chocolates_igual_se_guardan(self):
        self._crear(self.chocolates)
        self.assertEqual(ReservaServicio.objects.filter(
            servicio=self.chocolates).count(), 1)

    def test_dos_cajas_el_mismo_dia_no_son_un_conflicto(self):
        self._crear(self.chocolates)
        self._crear(self.chocolates)
        self.assertEqual(ReservaServicio.objects.filter(
            servicio=self.chocolates).count(), 2)


class LaTinaSIGUESIENDOREVISADA(BaseSenal):
    """El arreglo silencia lo que no tiene horario. Lo que sí lo tiene se
    sigue revisando exactamente igual que antes."""

    def test_una_tina_en_horario_malo_SIGUE_anotando_el_aviso(self):
        with self.assertLogs('ventas.signals.main_signals', level='ERROR') as cm:
            self._crear(self.tina, hora='03:00')
        self.assertTrue(any('no disponible' in x for x in cm.output), cm.output)


class LaSenalNuncaBLOQUEA(BaseSenal):
    """Hallazgo del 06-09-2026, dejado COMO ESTÁ a propósito.

    El `raise ValidationError` vive dentro del `try` y el `except Exception`
    de abajo lo atrapa: la señal anota y deja pasar. O sea que la protección
    contra sobreventa lleva quién sabe cuánto tiempo apagada.

    NO se enciende acá: hacerlo cambiaría cómo se comporta el admin, Luna, el
    calendario y las importaciones de golpe, y eso lo decide Jorge. Esta
    prueba fija el comportamiento REAL para que el día que se encienda sea
    una decisión y no un accidente — cuando pase, esta prueba falla y avisa.
    """

    def test_hoy_una_sobreventa_NO_se_bloquea(self):
        self._crear(self.tina, hora='14:00')
        otra = VentaReserva.objects.create(cliente=self.cliente)
        ReservaServicio.objects.create(
            venta_reserva=otra, servicio=self.tina,
            fecha_agendamiento=timezone.localdate(), hora_inicio='14:00',
            cantidad_personas=2, precio_unitario_venta=40000)
        self.assertEqual(
            ReservaServicio.objects.filter(servicio=self.tina, hora_inicio='14:00').count(),
            2, 'Si esto falla, la señal EMPEZÓ a bloquear: revisar que sea a propósito.')
