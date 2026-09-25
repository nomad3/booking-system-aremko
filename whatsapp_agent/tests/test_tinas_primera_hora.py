"""Tinas: primera hora sin alojamiento, la más tarde con alojamiento (Jorge, 25-09-2026).

«Para solo tinas debe mostrar desde el primer horario en adelante hasta el
último, mostrando de uno en uno. Para las tinas con alojamiento, experiencia
Noche de Aguas Calientes, lo lógico es que se le ofrezca al cliente la tina
más tarde disponible.» Y: Pausa también desde la primera hora; la primera hora
sea cual sea la tina; a igual hora, sorteo por fecha (no el alfabeto: en 60
días Hornopiren salía primera el 43% contra 16% de Tronador); las olitas, todas
las opciones (la Pausa solo armaba combinaciones con Hornopiren y Llaima).

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_tinas_primera_hora
"""
from __future__ import annotations

import datetime
from unittest import mock

from django.test import SimpleTestCase, TestCase

from destino_puerto_varas.services.llm.openrouter_provider import LLMResult
from whatsapp_agent import agent, alternativas, packs
from whatsapp_agent.agent import _pausa_de_a_una, _tool_alternativas_experiencia
from whatsapp_agent.availability import clave_sorteo

DIA = datetime.date(2026, 10, 1)
PROVIDER = ('destino_puerto_varas.services.llm.openrouter_provider.'
            'OpenRouterProvider.generate_with_tools')
TINAS = ['Tina Tronador', 'Tina Hornopiren', 'Tina Hidromasaje Llaima', 'Tina Hidromasaje Puyehue']


def _tina(nombre, horas, precio=None):
    precio = precio or (60000 if 'Hidromasaje' in nombre else 50000)
    return {'nombre': nombre, 'precio_total': precio, 'precio_por_persona': precio // 2,
            'slots_libres': list(horas), 'servicio_id': abs(hash(nombre)) % 1000}


def _alt(nombre, hora, precio=50000, masaje=None):
    itin = [{'servicio': nombre, 'hora': hora}]
    if masaje:
        itin.append({'servicio': 'Masaje Relajación o Descontracturante', 'hora': masaje})
    return {'titulo': f'{nombre} · {hora}', 'precio_total': precio,
            'precio_con_descuento': precio, 'hay_descuento': False,
            'texto_sugerido': f'{nombre} {hora}', 'itinerario': itin}


def _luna(tipo, alts):
    with mock.patch('whatsapp_agent.availability.resolver_fecha',
                    return_value={'fecha_iso': DIA.isoformat(), 'dia_semana': 'jueves',
                                  'ambiguo': False, 'error': None}), \
            mock.patch('whatsapp_agent.alternativas.construir_alternativas',
                       return_value={'tipo': tipo, 'fecha': DIA.isoformat(), 'personas': 2,
                                     'nombre_experiencia': 'x', 'alternativas': alts}):
        return _tool_alternativas_experiencia({'tipo': tipo, 'fecha': 'el jueves', 'personas': 2})


class ElMotorDeSoloTina(SimpleTestCase):
    def _orden(self, fecha):
        tinas = [_tina(n, ['14:00']) for n in TINAS]
        with mock.patch('whatsapp_agent.alternativas.disponibilidad',
                        return_value={'fecha': fecha.isoformat(), 'servicios': tinas}):
            alts = alternativas.construir_alternativas('tina_sola', fecha.isoformat(), 2)['alternativas']
        return [a['itinerario'][0]['servicio'] for a in alts]

    def test_a_igual_hora_manda_el_sorteo_del_dia(self):
        esperado = sorted(TINAS, key=lambda n: clave_sorteo(n, DIA))
        self.assertEqual(self._orden(DIA), esperado)
        self.assertEqual(self._orden(DIA), self._orden(DIA))

    def test_otra_fecha_otro_orden(self):
        primeras = {self._orden(DIA + datetime.timedelta(days=i))[0] for i in range(20)}
        self.assertGreater(len(primeras), 1, primeras)       # ya no gana siempre la misma


class LunaSinAlojamientoDesdeLaPrimeraHora(SimpleTestCase):
    def test_solo_tina_la_primera_hora_aunque_sea_hidromasaje(self):
        alts = [_alt('Tina Hidromasaje Llaima', '11:30', 60000), _alt('Tina Tronador', '12:00'),
                _alt('Tina Hornopiren', '19:30')]
        out = _luna('tina_sola', alts)
        self.assertEqual(out['recomendada']['titulo'], 'Tina Hidromasaje Llaima · 11:30')
        self.assertIn('PRIMER horario libre', out['instruccion'])

    def test_el_respaldo_va_de_a_una_hasta_el_ultimo_horario(self):
        horas = ['11:30', '12:00', '14:00', '14:30', '16:30', '17:00', '19:00', '21:30']
        alts = [_alt(n, h, 60000 if 'Hidro' in n else 50000) for h in horas
                for n in ('Tina Tronador', 'Tina Hidromasaje Llaima')]
        out = _luna('tina_sola', alts)
        horas_respaldo = [a['itinerario'][0]['hora'] for a in out['otras_alternativas']]
        self.assertEqual(horas_respaldo[:8], horas)           # una por horario, en orden
        nombres = {a['itinerario'][0]['servicio'] for a in out['otras_alternativas']}
        self.assertEqual(nombres, {'Tina Tronador', 'Tina Hidromasaje Llaima'})

    def test_la_pausa_tambien_desde_la_primera_hora(self):
        alts = [_alt('Tina Hidromasaje Llaima', '11:30', 140000, masaje='13:15'),
                _alt('Tina Tronador', '14:00', 110000, masaje='16:00')]
        out = _luna('pausa', alts)
        self.assertEqual(out['recomendada']['titulo'], 'Tina Hidromasaje Llaima · 11:30')


class LunaConAlojamientoLaMasTarde(SimpleTestCase):
    def test_la_noche_ofrece_la_tina_mas_tarde_del_motor(self):
        # El motor de la Noche ya ordena de la tina más tarde a la más temprana.
        tarde = {'titulo': 'Cabaña Tepa · tina 22:00', 'precio_total': 170000,
                 'precio_con_descuento': 170000, 'hay_descuento': False, 'texto_sugerido': '…',
                 'itinerario': [{'servicio': 'Cabaña Tepa', 'hora': '16:00'},
                                {'servicio': 'Tina Hidromasaje Llaima', 'hora': '22:00'}]}
        temprano = dict(tarde, titulo='Cabaña Tepa · tina 19:30', precio_total=160000,
                        precio_con_descuento=160000,
                        itinerario=[{'servicio': 'Cabaña Tepa', 'hora': '16:00'},
                                    {'servicio': 'Tina Tronador', 'hora': '19:30'}])
        out = _luna('noche_aguas_calientes', [tarde, temprano])
        self.assertEqual(out['recomendada']['titulo'], 'Cabaña Tepa · tina 22:00')
        self.assertIn('MÁS TARDE', out['instruccion'])

    def test_la_tina_mas_tarde_empata_por_precio_y_despues_por_sorteo(self):
        # Una fecha en que el sorteo da Tronador: con el alfabeto ganaría Hornopiren.
        fecha = next(DIA + datetime.timedelta(days=i) for i in range(60)
                     if clave_sorteo('Tina Tronador', DIA + datetime.timedelta(days=i))
                     < clave_sorteo('Tina Hornopiren', DIA + datetime.timedelta(days=i)))
        tinas = [_tina(n, ['22:00'], 50000) for n in ('Tina Tronador', 'Tina Hornopiren')]
        tinas.append(_tina('Tina Hidromasaje Llaima', ['22:00'], 60000))
        tina, hora = packs.elegir_tina_mas_tarde(tinas, fecha=fecha)
        self.assertEqual((tina['nombre'], hora), ('Tina Tronador', '22:00'))

    def test_sin_fecha_sigue_el_nombre(self):
        tinas = [_tina(n, ['22:00'], 50000) for n in ('Tina Tronador', 'Tina Hornopiren')]
        self.assertEqual(packs.elegir_tina_mas_tarde(tinas)[0]['nombre'], 'Tina Hornopiren')


class MasajeSoloNoCambia(SimpleTestCase):
    def test_sigue_la_mas_barata_y_mas_tarde(self):
        alts = [_alt('Masaje Relajación', '13:00', 40000), _alt('Masaje Relajación', '19:15', 40000)]
        self.assertEqual(_luna('masaje_solo', alts)['recomendada']['itinerario'][0]['hora'], '19:15')


class LaPausaConTodasLasTinas(SimpleTestCase):
    def test_arma_combinaciones_con_todas_las_tinas(self):
        llamadas = []

        def disponibilidad(fecha, personas=1, tipo=None, limite=2, **kw):
            llamadas.append((tipo, limite))
            return {'servicios': []}

        with mock.patch('whatsapp_agent.availability.disponibilidad', side_effect=disponibilidad):
            packs.disponibilidad_pack_tina_masaje(DIA.isoformat(), 2, todas=True)
        self.assertIn(('tina', None), llamadas)               # antes: el tope de 2

    def test_de_a_una_desde_la_primera_hora(self):
        def combo(hora):
            return {'tina': {'nombre': 'Tina Tronador', 'hora': hora},
                    'masaje': {'nombre': 'Masaje', 'hora': '18:00'}}
        pack = {'fecha': DIA.isoformat(), 'opciones': [combo('14:00'), combo('11:30')],
                'alternativas': [combo('11:30'), combo('14:00'), combo('16:30')], 'nota': ''}
        self.assertEqual(_pausa_de_a_una(pack)['opciones'], [combo('11:30')])
        self.assertNotIn('alternativas', _pausa_de_a_una(pack))
        self.assertEqual(_pausa_de_a_una(pack, despues_de='11:30')['opciones'], [combo('14:00')])
        self.assertEqual(_pausa_de_a_una(pack, mas_tarde=True)['opciones'], [combo('14:00')])
        ultima = _pausa_de_a_una(pack, despues_de='16:30')
        self.assertEqual(ultima['opciones'], [])
        self.assertIn('la última', ultima['nota'])


def _luna_llama(nombre, args):
    visto = {}

    def generate_with_tools(self, messages, tools, tool_executor, **kwargs):
        visto['resultado'] = tool_executor(nombre, args)
        return LLMResult('Listo', 'google/gemini-2.5-flash', 10, 5, 100)

    with mock.patch(PROVIDER, generate_with_tools):
        agent._producir_borrador_inner(agent.get_config(), 'hola, ¿tienen tina?',
                                       phone='+56911112222')
    return visto['resultado']


class LasHerramientasDeLuna(TestCase):
    PACK = {'fecha': DIA.isoformat(), 'nombre_experiencia': 'Pausa junto al río', 'nota': '',
            'opciones': [{'tina': {'nombre': 'Tina Tronador', 'hora': '14:00'}}],
            'alternativas': [{'tina': {'nombre': 'Tina Tronador', 'hora': h}} for h in ('11:30', '14:00')]}

    def test_la_herramienta_de_la_pausa_entrega_una(self):
        with mock.patch('whatsapp_agent.packs.disponibilidad_pack_tina_masaje',
                        return_value=self.PACK) as pack:
            r = _luna_llama('consultar_disponibilidad_pack', {'fecha': 'el jueves', 'personas': 2})
        self.assertTrue(pack.call_args.kwargs.get('todas'))
        self.assertEqual([o['tina']['hora'] for o in r['opciones']], ['11:30'])

    def test_la_pausa_mas_tarde_trae_la_siguiente(self):
        with mock.patch('whatsapp_agent.packs.disponibilidad_pack_tina_masaje', return_value=self.PACK):
            r = _luna_llama('consultar_disponibilidad_pack',
                            {'fecha': 'el jueves', 'personas': 2, 'despues_de': '11:30'})
        self.assertEqual([o['tina']['hora'] for o in r['opciones']], ['14:00'])

    def test_el_enrutador_con_solo_tina_da_una_recomendacion(self):
        with mock.patch('whatsapp_agent.packs.router_disponibilidad',
                        return_value={'rama': 'tina', 'servicios': []}), \
                mock.patch('whatsapp_agent.agent._tool_alternativas_experiencia',
                           return_value={'success': True, 'recomendada': {'titulo': 'x'}}) as una:
            r = _luna_llama('consultar_disponibilidad_combo',
                            {'servicios': ['tina'], 'fecha': 'el jueves', 'personas': 2})
        una.assert_called_once_with({'tipo': 'tina_sola', 'fecha': 'el jueves', 'personas': 2})
        self.assertEqual(r['rama'], 'tina')

    def test_el_enrutador_con_tina_y_masaje_da_una_pausa(self):
        with mock.patch('whatsapp_agent.packs.router_disponibilidad',
                        return_value={'rama': 'tina_masaje', 'opciones': []}), \
                mock.patch('whatsapp_agent.packs.disponibilidad_pack_tina_masaje',
                           return_value=self.PACK):
            r = _luna_llama('consultar_disponibilidad_combo',
                            {'servicios': ['tina', 'masaje'], 'fecha': 'el jueves', 'personas': 2})
        self.assertEqual([o['tina']['hora'] for o in r['opciones']], ['11:30'])
        self.assertEqual(r['rama'], 'tina_masaje')
