"""Tests H-078: rollback del estado de venta en turnos escalados + tool cotizadora.

NOTA: la suite local no puede correr mientras exista el drift AR-033/AR-034 (crear el
test DB revienta al re-aplicar migraciones). Estos tests documentan el contrato y
quedan listos para cuando eso se resuelva / para CI.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from carrito_reservas.models import CarritoReserva
from whatsapp_agent import rollback
from whatsapp_agent.agent import _tool_alternativas_experiencia
from whatsapp_agent.models import PropuestaReserva


CANAL = 'whatsapp'
PHONE = '+56900000078'


class RollbackCarritoTests(TestCase):
    def test_turno_crea_carrito_que_no_existia_se_elimina(self):
        snap = rollback.snapshot_estado_venta(CANAL, PHONE)  # no existe nada aún
        CarritoReserva.objects.create(canal=CANAL, external_id=PHONE, items=[
            {'tipo': 'servicio', 'id': 9, 'nombre': 'Tina Hornopiren',
             'fecha': '2026-08-05', 'hora': '14:30', 'cantidad_personas': 2,
             'precio_unitario': 25000.0, 'subtotal': 50000.0},
        ])
        self.assertTrue(rollback.restaurar_estado_venta(CANAL, PHONE, snap))
        self.assertFalse(
            CarritoReserva.objects.filter(canal=CANAL, external_id=PHONE).exists())

    def test_items_agregados_en_el_turno_se_revierten(self):
        carrito = CarritoReserva.objects.create(
            canal=CANAL, external_id=PHONE,
            items=[{'tipo': 'producto', 'id': 3, 'nombre': 'Tabla Quesos',
                    'cantidad': 1, 'precio_unitario': 20000.0, 'subtotal': 20000.0}],
            subtotal_productos=Decimal('20000'), total=Decimal('20000'))
        snap = rollback.snapshot_estado_venta(CANAL, PHONE)

        carrito.items = carrito.items + [
            {'tipo': 'servicio', 'id': 9, 'nombre': 'Tina Hornopiren',
             'fecha': '2026-08-05', 'hora': '14:30', 'cantidad_personas': 2,
             'precio_unitario': 25000.0, 'subtotal': 50000.0}]
        carrito.subtotal_servicios = Decimal('50000')
        carrito.total = Decimal('70000')
        carrito.save()

        self.assertTrue(rollback.restaurar_estado_venta(CANAL, PHONE, snap))
        carrito.refresh_from_db()
        self.assertEqual(len(carrito.items), 1)
        self.assertEqual(carrito.items[0]['nombre'], 'Tabla Quesos')
        self.assertEqual(carrito.total, Decimal('20000'))

    def test_sin_cambios_no_toca_nada(self):
        CarritoReserva.objects.create(canal=CANAL, external_id=PHONE, items=[])
        snap = rollback.snapshot_estado_venta(CANAL, PHONE)
        self.assertFalse(rollback.restaurar_estado_venta(CANAL, PHONE, snap))


class RollbackPropuestaTests(TestCase):
    def _propuesta(self, **kwargs):
        base = dict(
            propuesta_id=f'test-{PropuestaReserva.objects.count() + 1}',
            canal=CANAL, external_id=PHONE, estado='pendiente',
            payload={'servicios': [], 'productos': []}, servicios=[],
            # cliente_data y expires_at son NOT NULL sin default: el create
            # revienta sin ellos (la app siempre los llena en reserva_service).
            cliente_data={}, expires_at=timezone.now() + timedelta(hours=2),
            total=Decimal('0'), resumen_texto='')
        base.update(kwargs)
        return PropuestaReserva.objects.create(**base)

    def test_propuesta_creada_en_el_turno_se_descarta(self):
        snap = rollback.snapshot_estado_venta(CANAL, PHONE)  # sin propuesta previa
        p = self._propuesta()
        self.assertTrue(rollback.restaurar_estado_venta(CANAL, PHONE, snap))
        p.refresh_from_db()
        self.assertEqual(p.estado, 'descartada')

    def test_edicion_de_propuesta_en_el_turno_se_revierte(self):
        p = self._propuesta(
            payload={'servicios': [{'servicio_id': 1}], 'productos': []},
            servicios=[{'servicio_id': 1}], total=Decimal('50000'), resumen_texto='1x Tina')
        snap = rollback.snapshot_estado_venta(CANAL, PHONE)

        p.servicios = [{'servicio_id': 1}, {'servicio_id': 2}]
        p.total = Decimal('130000')
        p.resumen_texto = '1x Tina + 1x Masaje'
        p.save()

        self.assertTrue(rollback.restaurar_estado_venta(CANAL, PHONE, snap))
        p.refresh_from_db()
        self.assertEqual(p.servicios, [{'servicio_id': 1}])
        self.assertEqual(p.total, Decimal('50000'))
        self.assertEqual(p.resumen_texto, '1x Tina')
        self.assertEqual(p.estado, 'pendiente')


class ToolAlternativasExperienciaTests(TestCase):
    """La tool cotizadora: validaciones deterministas + passthrough del motor H-061."""

    def test_exige_personas(self):
        out = _tool_alternativas_experiencia({'tipo': 'pausa', 'fecha': '2026-08-05'})
        self.assertFalse(out['success'])
        self.assertEqual(out['error'], 'falta_personas')

    @mock.patch('whatsapp_agent.availability.resolver_fecha')
    def test_fecha_ambigua_no_cotiza(self, m_fecha):
        m_fecha.return_value = {'fecha_iso': '2026-08-05', 'dia_semana': 'miércoles',
                                'ambiguo': True, 'error': None}
        out = _tool_alternativas_experiencia(
            {'tipo': 'pausa', 'fecha': 'domingo 5', 'personas': 2})
        self.assertFalse(out['success'])
        self.assertEqual(out['error'], 'fecha_ambigua')

    @mock.patch('whatsapp_agent.alternativas.construir_alternativas')
    @mock.patch('whatsapp_agent.availability.resolver_fecha')
    def test_passthrough_del_motor_con_tope(self, m_fecha, m_alts):
        m_fecha.return_value = {'fecha_iso': '2026-08-05', 'dia_semana': 'miércoles',
                                'ambiguo': False, 'error': None}
        alternativa = {
            'titulo': 'Tina Hornopiren · 14:30', 'precio_total': 130000,
            'precio_con_descuento': 110000, 'hay_descuento': True,
            'texto_sugerido': 'Tina Hornopiren 14:30 + masaje 16:00 → $110.000',
            'itinerario': [{'servicio': 'Tina Hornopiren', 'hora': '14:30'},
                           {'servicio': 'Masaje', 'hora': '16:00'}],
        }
        m_alts.return_value = {'tipo': 'pausa', 'fecha': '2026-08-05', 'personas': 2,
                               'nombre_experiencia': 'Pausa junto al río',
                               'alternativas': [alternativa] * 12}
        out = _tool_alternativas_experiencia(
            {'tipo': 'pausa', 'fecha': 'el próximo miércoles', 'personas': 2})
        self.assertTrue(out['success'])
        m_alts.assert_called_once_with('pausa', '2026-08-05', 2)
        self.assertEqual(out['dia_semana'], 'miércoles')
        self.assertEqual(out['total_alternativas'], 12)
        # H-081: UNA recomendada + respaldo topeado (contexto acotado).
        self.assertIn('texto_sugerido', out['recomendada'])
        self.assertEqual(len(out['otras_alternativas']), 8)

    @mock.patch('whatsapp_agent.alternativas.construir_alternativas')
    @mock.patch('whatsapp_agent.availability.resolver_fecha')
    def test_recomendada_mas_barata_y_a_igual_precio_mas_tarde(self, m_fecha, m_alts):
        """H-081 (decisión Jorge 2026-07-30): la recomendada es la MÁS BARATA (precio
        final, luego normal); a igual precio, el horario MÁS TARDE."""
        m_fecha.return_value = {'fecha_iso': '2026-08-05', 'dia_semana': 'miércoles',
                                'ambiguo': False, 'error': None}

        def alt(nombre, hora, total, desc):
            return {'titulo': f'{nombre} · {hora}', 'precio_total': total,
                    'precio_con_descuento': desc, 'hay_descuento': total != desc,
                    'texto_sugerido': f'{nombre} {hora}',
                    'itinerario': [{'servicio': nombre, 'hora': hora}]}

        cara_temprano = alt('Tina Hidromasaje Llaima', '14:00', 140000, 110000)
        barata_temprano = alt('Tina Hornopiren', '14:30', 130000, 110000)
        barata_tarde = alt('Tina Hornopiren', '17:00', 130000, 110000)
        m_alts.return_value = {'tipo': 'pausa', 'fecha': '2026-08-05', 'personas': 2,
                               'nombre_experiencia': 'Pausa junto al río',
                               'alternativas': [cara_temprano, barata_temprano, barata_tarde]}
        out = _tool_alternativas_experiencia(
            {'tipo': 'pausa', 'fecha': '2026-08-05', 'personas': 2})
        # Más barata (precio normal 130k) y, entre las dos baratas, la MÁS TARDE (17:00).
        self.assertEqual(out['recomendada']['titulo'], 'Tina Hornopiren · 17:00')
        self.assertEqual([a['titulo'] for a in out['otras_alternativas']],
                         ['Tina Hornopiren · 14:30', 'Tina Hidromasaje Llaima · 14:00'])

    @mock.patch('whatsapp_agent.alternativas.construir_alternativas')
    @mock.patch('whatsapp_agent.availability.resolver_fecha')
    def test_sin_disponibilidad_recomendada_none(self, m_fecha, m_alts):
        m_fecha.return_value = {'fecha_iso': '2026-08-05', 'dia_semana': 'miércoles',
                                'ambiguo': False, 'error': None}
        m_alts.return_value = {'tipo': 'pausa', 'fecha': '2026-08-05', 'personas': 2,
                               'nombre_experiencia': 'Pausa junto al río', 'alternativas': []}
        out = _tool_alternativas_experiencia(
            {'tipo': 'pausa', 'fecha': '2026-08-05', 'personas': 2})
        self.assertTrue(out['success'])
        self.assertIsNone(out['recomendada'])
        self.assertEqual(out['total_alternativas'], 0)

    @mock.patch('whatsapp_agent.alternativas.construir_alternativas')
    @mock.patch('whatsapp_agent.availability.resolver_fecha')
    def test_tipo_invalido_propaga_error(self, m_fecha, m_alts):
        m_fecha.return_value = {'fecha_iso': '2026-08-05', 'dia_semana': 'miércoles',
                                'ambiguo': False, 'error': None}
        m_alts.return_value = {'error': "tipo inválido: 'spa_day'"}
        out = _tool_alternativas_experiencia(
            {'tipo': 'spa_day', 'fecha': '2026-08-05', 'personas': 2})
        self.assertFalse(out['success'])
        self.assertEqual(out['error'], 'alternativas_invalidas')
