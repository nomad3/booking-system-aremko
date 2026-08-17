# -*- coding: utf-8 -*-
"""Expiración de propuestas vencidas (P-29).

Medido en producción el 2026-08-17: 55 de 56 «pendientes» estaban vencidas —la
más vieja del 19 de junio— porque el estado solo se corrige cuando alguien
vuelve a abrir esa propuesta. Los informes leen el estado guardado, así que
mientras mienta, el embudo miente.
"""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from whatsapp_agent.models import PropuestaReserva


def _propuesta(pid, estado='pendiente', vence_en_horas=24):
    return PropuestaReserva.objects.create(
        propuesta_id=pid, idempotency_key=pid, canal='whatsapp',
        external_id='+56911111111', payload={}, cliente_data={}, servicios=[],
        total=50000, estado=estado,
        expires_at=timezone.now() + timedelta(hours=vence_en_horas))


class ExpirarPropuestasTest(TestCase):

    def _correr(self, *args):
        salida = StringIO()
        call_command('expirar_propuestas_vencidas', *args, stdout=salida)
        return salida.getvalue()

    def test_marca_la_vencida_y_deja_viva_la_vigente(self):
        _propuesta('vieja', vence_en_horas=-48)
        _propuesta('fresca', vence_en_horas=24)
        self._correr()
        self.assertEqual(
            PropuestaReserva.objects.get(propuesta_id='vieja').estado, 'expirada')
        self.assertEqual(
            PropuestaReserva.objects.get(propuesta_id='fresca').estado, 'pendiente')

    def test_no_toca_creadas_ni_descartadas(self):
        # Una creada vencida sigue siendo una VENTA: pisarla borraría la
        # conversión del embudo, que es justo lo que queremos medir.
        _propuesta('vendida', estado='creada', vence_en_horas=-48)
        _propuesta('rechazada', estado='descartada', vence_en_horas=-48)
        self._correr()
        self.assertEqual(
            PropuestaReserva.objects.get(propuesta_id='vendida').estado, 'creada')
        self.assertEqual(
            PropuestaReserva.objects.get(propuesta_id='rechazada').estado, 'descartada')

    def test_dry_run_no_escribe(self):
        _propuesta('vieja', vence_en_horas=-48)
        salida = self._correr('--dry-run')
        self.assertIn('dry-run', salida)
        self.assertEqual(
            PropuestaReserva.objects.get(propuesta_id='vieja').estado, 'pendiente')

    def test_es_idempotente(self):
        _propuesta('vieja', vence_en_horas=-48)
        self._correr()
        salida = self._correr()
        self.assertIn('No hay propuestas pendientes vencidas', salida)
