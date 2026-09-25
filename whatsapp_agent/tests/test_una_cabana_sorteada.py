"""Luna ofrece UNA cabaña, sorteada por fecha, con la Torre al final (Jorge, 25-09-2026).

«Luna siempre ofrece las mismas cabañas… siempre ofrece cabaña Acantilado como
primera opción. Debería ofrecer solo una opción, no dos, y de las disponibles
aleatoriamente.» En prod, 60 días: de 580 borradores con cabañas, el 52%
ofrecía primero Acantilado y el 30% Arrayán; la mitad ofrecía dos. Decisiones
de Jorge: sorteo por fecha (la misma fecha, la misma cabaña: no la cambia entre
un mensaje y el siguiente) y Torre fuera del sorteo.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_una_cabana_sorteada
"""
from __future__ import annotations

import datetime
from collections import Counter
from unittest import mock

from django.test import SimpleTestCase, TestCase

from destino_puerto_varas.services.llm.openrouter_provider import LLMResult
from whatsapp_agent import agent
from whatsapp_agent.agent import (_una_cabana_multinoche, _una_cabana_opciones,
                                  _una_cabana_servicios)
from whatsapp_agent.availability import (clave_sorteo_cabana, disponibilidad,
                                         disponibilidad_alojamiento_multinoche,
                                         ordenar_cabanas)

PROVIDER = ('destino_puerto_varas.services.llm.openrouter_provider.'
            'OpenRouterProvider.generate_with_tools')

CABANAS = ['Cabaña Acantilado', 'Cabaña Arrayan', 'Cabaña Laurel', 'Cabaña Tepa', 'Cabaña Torre']
DIA = datetime.date(2026, 9, 26)


def _cab(nombre, precio=110000):
    return {'nombre': nombre, 'tipo': 'cabana', 'precio_total': precio, 'servicio_id': hash(nombre) % 1000}


def _fechas(n=60):
    return [DIA + datetime.timedelta(days=i) for i in range(n)]


class ElSorteo(SimpleTestCase):
    def _orden(self, fecha, nombres=CABANAS):
        return [c['nombre'] for c in ordenar_cabanas([_cab(n) for n in nombres], fecha)]

    def test_la_misma_fecha_da_siempre_el_mismo_orden(self):
        self.assertEqual(self._orden(DIA), self._orden(DIA))
        self.assertEqual(self._orden(DIA), self._orden(DIA, list(reversed(CABANAS))))

    def test_la_torre_va_siempre_al_final(self):
        for fecha in _fechas():
            self.assertEqual(self._orden(fecha)[-1], 'Cabaña Torre', fecha)

    def test_fechas_distintas_reparten_la_primera(self):
        primeras = Counter(self._orden(f)[0] for f in _fechas())
        for nombre in CABANAS[:4]:
            self.assertGreaterEqual(primeras[nombre], 5, primeras)   # ~15 cada una en 60 días
        self.assertNotIn('Cabaña Torre', primeras)

    def test_si_se_ocupa_una_las_demas_no_cambian_de_lugar(self):
        for fecha in _fechas(20):
            completo = self._orden(fecha)
            sin_una = self._orden(fecha, [n for n in CABANAS if n != completo[0]])
            self.assertEqual(sin_una, completo[1:], fecha)

    def test_los_demas_servicios_no_se_mueven(self):
        servicios = [{'nombre': 'Tina Tronador', 'tipo': 'tina'}, _cab('Cabaña Tepa'),
                     {'nombre': 'Masaje', 'tipo': 'masaje'}, _cab('Cabaña Acantilado')]
        ordenados = ordenar_cabanas(servicios, DIA)
        self.assertEqual(ordenados[0]['nombre'], 'Tina Tronador')
        self.assertEqual(ordenados[2]['nombre'], 'Masaje')
        self.assertEqual({ordenados[1]['nombre'], ordenados[3]['nombre']},
                         {'Cabaña Tepa', 'Cabaña Acantilado'})

    def test_la_clave_pone_torre_al_final_aunque_el_hash_diga_otra_cosa(self):
        self.assertTrue(clave_sorteo_cabana('Cabaña Torre', DIA)[0])
        self.assertFalse(clave_sorteo_cabana('Cabaña Laurel', DIA)[0])


class LunaRecibeUnaSola(SimpleTestCase):
    def test_consulta_de_cabana(self):
        r = _una_cabana_servicios({'fecha': '2026-09-26', 'servicios': [_cab(n) for n in CABANAS]})
        self.assertEqual([s['nombre'] for s in r['servicios']], ['Cabaña Acantilado'])
        self.assertEqual([c['nombre'] for c in r['otras_cabanas_libres']], CABANAS[1:])
        self.assertIn('Ofrece SOLO esta cabaña', r['instruccion_cabana'])

    def test_con_una_sola_libre_no_hay_respaldo(self):
        r = _una_cabana_servicios({'servicios': [_cab('Cabaña Tepa')]})
        self.assertNotIn('otras_cabanas_libres', r)

    def test_los_otros_servicios_se_conservan(self):
        r = _una_cabana_servicios({'servicios': [{'nombre': 'Tina Tronador', 'tipo': 'tina'},
                                                 _cab('Cabaña Tepa'), _cab('Cabaña Laurel')]})
        self.assertEqual([s['nombre'] for s in r['servicios']], ['Tina Tronador', 'Cabaña Tepa'])

    def test_noche_de_aguas_calientes(self):
        opciones = [{'cabana': {'nombre': 'Cabaña Tepa'}, 'tina': {'nombre': 'Tina Tronador'}},
                    {'cabana': {'nombre': 'Cabaña Laurel'}, 'tina': {'nombre': 'Tina Tronador'}}]
        libres = {'servicios': [_cab('Cabaña Tepa'), _cab('Cabaña Laurel'), _cab('Cabaña Torre', 120000)]}
        with mock.patch('whatsapp_agent.availability.disponibilidad', return_value=libres) as disp:
            r = _una_cabana_opciones({'fecha': '2026-09-26', 'opciones': opciones}, 'el sábado')
        disp.assert_called_once_with('2026-09-26', 2, 'cabana', limite=None)
        self.assertEqual([o['cabana']['nombre'] for o in r['opciones']], ['Cabaña Tepa'])
        self.assertEqual([c['nombre'] for c in r['otras_cabanas_libres']],
                         ['Cabaña Laurel', 'Cabaña Torre'])

    def test_varias_noches(self):
        cabanas = [{'nombre': n, 'total_estadia': 220000} for n in ('Cabaña Tepa', 'Cabaña Laurel')]
        r = _una_cabana_multinoche({'cabanas': cabanas, 'total_disponibles': 2})
        self.assertEqual([c['nombre'] for c in r['cabanas']], ['Cabaña Tepa'])
        self.assertEqual(r['otras_cabanas_libres'], [{'nombre': 'Cabaña Laurel', 'total_estadia': 220000}])


class ConCabanasReales(TestCase):
    @classmethod
    def setUpTestData(cls):
        from ventas.models import Servicio
        for nombre in CABANAS:
            Servicio.objects.create(
                nombre=nombre, precio_base=60000 if 'Torre' in nombre else 55000, duracion=1140,
                tipo_servicio='cabana', activo=True, publicado_web=True,
                capacidad_minima=1, capacidad_maxima=2,
                # verificar_disponibilidad lee los horarios por día de la semana.
                slots_disponibles={d: ['16:00'] for d in ('monday', 'tuesday', 'wednesday',
                                                          'thursday', 'friday', 'saturday',
                                                          'sunday')})

    def test_la_consulta_de_cabanas_sale_en_el_orden_del_sorteo(self):
        fecha = datetime.date.today() + datetime.timedelta(days=30)
        todas = [s['nombre'] for s in disponibilidad(fecha.isoformat(), 2, 'cabana', limite=None)['servicios']]
        esperado = [c['nombre'] for c in ordenar_cabanas([_cab(n) for n in CABANAS], fecha)]
        self.assertEqual(todas, esperado)
        self.assertEqual(todas[-1], 'Cabaña Torre')
        dos = [s['nombre'] for s in disponibilidad(fecha.isoformat(), 2, 'cabana')['servicios']]
        self.assertEqual(dos, esperado[:2])                  # antes: Acantilado y Arrayan

    def test_en_60_fechas_la_primera_no_es_siempre_acantilado(self):
        hoy = datetime.date.today() + datetime.timedelta(days=1)
        primeras = Counter(
            disponibilidad((hoy + datetime.timedelta(days=i)).isoformat(), 2, 'cabana')['servicios'][0]['nombre']
            for i in range(60))
        self.assertLess(primeras['Cabaña Acantilado'], 30, primeras)
        self.assertNotIn('Cabaña Torre', primeras)

    def test_trae_todas_las_libres_en_el_orden_del_sorteo(self):
        llegada = datetime.date.today() + datetime.timedelta(days=30)
        r = disponibilidad_alojamiento_multinoche(llegada.isoformat(), 2, noches=2)
        nombres = [c['nombre'] for c in r['cabanas']]
        self.assertEqual(len(nombres), 5)                    # antes: las 2 primeras
        self.assertEqual(r['total_disponibles'], 5)
        self.assertEqual(nombres[-1], 'Cabaña Torre')
        esperado = [c['nombre'] for c in ordenar_cabanas([_cab(n) for n in CABANAS], llegada)]
        self.assertEqual(nombres, esperado)


def _luna_llama(nombre, args):
    """Corre un turno de Luna en que el modelo (simulado) llama a `nombre` con `args`;
    devuelve lo que la herramienta le entregó."""
    visto = {}

    def generate_with_tools(self, messages, tools, tool_executor, **kwargs):
        visto['resultado'] = tool_executor(nombre, args)
        return LLMResult('Listo', 'google/gemini-2.5-flash', 10, 5, 100)

    with mock.patch(PROVIDER, generate_with_tools):
        agent._producir_borrador_inner(agent.get_config(), 'hola, ¿tienen cabaña?',
                                       phone='+56911112222')
    return visto['resultado']


class LasHerramientasDeLunaEntreganUna(TestCase):
    def test_consultar_disponibilidad_de_cabana(self):
        todas = {'servicios': [_cab(n) for n in CABANAS]}
        with mock.patch('whatsapp_agent.availability.disponibilidad', return_value=todas) as disp:
            r = _luna_llama('consultar_disponibilidad',
                            {'personas': 2, 'fecha': 'el sábado', 'tipo': 'cabana'})
        disp.assert_called_once_with('el sábado', 2, 'cabana', limite=None)
        self.assertEqual(len(r['servicios']), 1)
        self.assertEqual(len(r['otras_cabanas_libres']), 4)

    def test_pack_cabana_tina(self):
        pack = {'fecha': '2026-09-26', 'opciones': [{'cabana': {'nombre': 'Cabaña Tepa'}},
                                                    {'cabana': {'nombre': 'Cabaña Laurel'}}]}
        with mock.patch('whatsapp_agent.packs.disponibilidad_pack_cabana_tina', return_value=pack), \
                mock.patch('whatsapp_agent.availability.disponibilidad',
                           return_value={'servicios': [_cab('Cabaña Tepa'), _cab('Cabaña Laurel')]}):
            r = _luna_llama('consultar_disponibilidad_pack_cabana', {'fecha': 'el sábado'})
        self.assertEqual(len(r['opciones']), 1)
        self.assertEqual([c['nombre'] for c in r['otras_cabanas_libres']], ['Cabaña Laurel'])

    def test_varias_noches(self):
        multi = {'cabanas': [{'nombre': 'Cabaña Tepa', 'total_estadia': 220000},
                             {'nombre': 'Cabaña Laurel', 'total_estadia': 220000}]}
        with mock.patch('whatsapp_agent.availability.disponibilidad_alojamiento_multinoche',
                        return_value=multi):
            r = _luna_llama('consultar_disponibilidad_alojamiento_multinoche',
                            {'fecha_llegada': 'el viernes', 'noches': 2, 'personas': 2})
        self.assertEqual(len(r['cabanas']), 1)

    def test_el_enrutador_con_alojamiento(self):
        solo = dict({'servicios': [_cab(n) for n in CABANAS[:3]]}, rama='alojamiento')
        with mock.patch('whatsapp_agent.packs.router_disponibilidad', return_value=solo):
            r = _luna_llama('consultar_disponibilidad_combo',
                            {'servicios': ['cabaña'], 'fecha': 'el sábado', 'personas': 2})
        self.assertEqual(len(r['servicios']), 1)
        self.assertEqual(len(r['otras_cabanas_libres']), 2)


class LaNocheDesempataPorSorteo(SimpleTestCase):
    """Las alternativas de la Noche (olitas y recomendación de Luna) desempataban por
    nombre de cabaña: a igual tina y precio, ganaba Acantilado."""

    def test_a_igual_tina_y_precio_manda_el_sorteo(self):
        from whatsapp_agent import packs
        cabanas = [dict(_cab(n), precio_total=110000, precio_por_persona=55000,
                        slots_libres=['16:00']) for n in CABANAS[:4]]
        tinas = [{'nombre': 'Tina Tronador', 'servicio_id': 9, 'precio_total': 50000,
                  'slots_libres': ['22:00']}]

        def disponibilidad(fecha, personas=1, tipo=None, limite=2, **kw):
            return {'servicios': cabanas if tipo == 'cabana' else tinas}

        with mock.patch('whatsapp_agent.availability.disponibilidad', side_effect=disponibilidad), \
                mock.patch('whatsapp_agent.packs._descuento_pack_cabana', return_value=0), \
                mock.patch('whatsapp_agent.packs._desayuno_de_cabana', return_value=None):
            r = packs.disponibilidad_pack_cabana_tina(DIA.isoformat(), todas=True)
        primeras = [a['cabana']['nombre'] for a in r['alternativas']]
        esperado = [c['nombre'] for c in ordenar_cabanas([_cab(n) for n in CABANAS[:4]], DIA)]
        self.assertEqual(primeras, esperado)
