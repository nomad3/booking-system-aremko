# -*- coding: utf-8 -*-
"""Guardar una reserva no puede terminar en 500.

El 2026-08-11 editar la reserva 6552 en el admin devolvía Error 500: una fila
del inline de servicios llegaba a `clean()` sin servicio elegido, y en una FK
obligatoria `self.servicio` NO devuelve None — lanza RelatedObjectDoesNotExist.
"""
from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from ventas.models import (CategoriaServicio, Proveedor, ReservaServicio,
                           Servicio)


class ReservaServicioCleanTest(TestCase):

    def setUp(self):
        self.cat = CategoriaServicio.objects.create(nombre='Masajes')
        self.masaje = Servicio.objects.create(
            nombre='Masaje relajación', precio_base=50000, duracion=50,
            categoria=self.cat, tipo_servicio='masaje')

    def test_una_fila_sin_servicio_no_revienta(self):
        """El caso exacto del 500: fila a medio llenar, con hora pero sin
        servicio. Tiene que dejar validar para que el formulario muestre
        «este campo es obligatorio»."""
        fila = ReservaServicio(fecha_agendamiento=date(2026, 8, 12),
                               hora_inicio='15:00', cantidad_personas=1)
        fila.clean()          # antes: RelatedObjectDoesNotExist → 500

    def test_una_fila_sin_proveedor_tampoco_revienta(self):
        fila = ReservaServicio(servicio=self.masaje,
                               fecha_agendamiento=date(2026, 8, 12),
                               hora_inicio='15:00', cantidad_personas=1)
        fila.clean()

    def test_sigue_rechazando_un_masajista_no_habilitado(self):
        """La validación que existía no se perdió en el arreglo."""
        otra = Proveedor.objects.create(nombre='Alguien que no da masajes')
        fila = ReservaServicio(servicio=self.masaje, proveedor_asignado=otra,
                               fecha_agendamiento=date(2026, 8, 12),
                               hora_inicio='15:00', cantidad_personas=1)
        with self.assertRaises(ValidationError):
            fila.clean()

    def test_acepta_al_masajista_habilitado(self):
        carolina = Proveedor.objects.create(nombre='Carolina Vidal')
        self.masaje.proveedores.add(carolina)
        fila = ReservaServicio(servicio=self.masaje,
                               proveedor_asignado=carolina,
                               fecha_agendamiento=date(2026, 8, 12),
                               hora_inicio='15:00', cantidad_personas=1)
        fila.clean()
