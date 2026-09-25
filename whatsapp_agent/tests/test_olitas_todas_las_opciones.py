"""Las olitas muestran TODAS las opciones, desde el primer horario (Jorge, 25-09-2026).

«Debería mostrar desde el primer horario en adelante todas las opciones al ir
presionando el botón de las olitas. Hoy solo muestra algunas.» Había un tope de
12 que se aplicaba DESPUÉS de ordenar por hora: el 26-09, «Solo tina» para 2
tenía 20 opciones libres y llegaban 12 (11:30 a 16:30). Y como Luna elige «la
más tarde» (H-081) entre las que le llegan, nunca veía la tarde.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_olitas_todas_las_opciones
"""
from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase

from whatsapp_agent import alternativas
from whatsapp_agent.agent import _otras_variadas, _tool_alternativas_experiencia

HORAS = ['11:30', '12:00', '14:00', '14:30', '16:30', '17:00', '19:00', '21:30']


def _tina(nombre, precio, horas, sid):
    return {'nombre': nombre, 'precio_total': precio, 'precio_por_persona': precio // 2,
            'slots_libres': list(horas), 'servicio_id': sid}


class LasOlitasTraenTodo(SimpleTestCase):
    def test_solo_tina_trae_todas_desde_la_primera_hora(self):
        tinas = [_tina('Tina Tronador', 50000, HORAS, 1),
                 _tina('Tina Hidromasaje Llaima', 60000, HORAS, 2),
                 _tina('Tina Hidromasaje Puyehue', 60000, HORAS, 3)]
        with mock.patch('whatsapp_agent.alternativas.disponibilidad',
                        return_value={'fecha': '2026-09-26', 'servicios': tinas}):
            r = alternativas.construir_alternativas('tina_sola', '2026-09-26', 2)
        alts = r['alternativas']
        self.assertEqual(len(alts), 24)                       # antes llegaban 12
        horas = [a['itinerario'][0]['hora'] for a in alts]
        self.assertEqual(horas[0], '11:30')
        self.assertEqual(horas[-1], '21:30')
        self.assertIn('Tina Tronador a las 21:30', ' '.join(a['texto_sugerido'] for a in alts))

    def test_las_horas_se_ordenan_por_reloj_no_por_texto(self):
        tinas = [_tina('Tina Tronador', 50000, ['11:00', '9:30', '21:30'], 1)]
        with mock.patch('whatsapp_agent.alternativas.disponibilidad',
                        return_value={'fecha': '2026-09-26', 'servicios': tinas}):
            alts = alternativas.construir_alternativas('tina_sola', '2026-09-26', 2)['alternativas']
        self.assertEqual([a['itinerario'][0]['hora'] for a in alts], ['9:30', '11:00', '21:30'])

    def test_masaje_solo_tambien_trae_todo(self):
        masajes = [_tina('Masaje Relajación o Descontracturante', 80000, HORAS, 7),
                   _tina('Masaje Piedras Calientes', 90000, HORAS, 8)]
        with mock.patch('whatsapp_agent.alternativas.disponibilidad',
                        return_value={'fecha': '2026-09-26', 'servicios': masajes}):
            alts = alternativas.construir_alternativas('masaje_solo', '2026-09-26', 2)['alternativas']
        self.assertEqual(len(alts), 16)
        self.assertEqual(alts[-1]['itinerario'][0]['hora'], '21:30')

    def test_la_pausa_tambien_trae_todo(self):
        def combo(i):
            return {'tina': {'nombre': 'Tina Tronador', 'hora': f'{10 + i}:00', 'servicio_id': 1},
                    'masaje': {'nombre': 'Masaje Relajación o Descontracturante',
                               'hora': f'{11 + i}:15', 'servicio_id': 7},
                    'precio_total': 130000, 'precio_con_descuento': 110000,
                    'hay_descuento': True, 'etiqueta': 'Sin hidromasaje'}
        with mock.patch('whatsapp_agent.packs.disponibilidad_pack_tina_masaje',
                        return_value={'fecha': '2026-09-26',
                                      'alternativas': [combo(i) for i in range(14)]}):
            alts = alternativas.construir_alternativas('pausa', '2026-09-26', 2)['alternativas']
        self.assertEqual(len(alts), 14)

    def test_la_noche_mantiene_su_tope_de_seis(self):
        # Decisión de Jorge del 14-08-2026: no se toca.
        def opcion(i):
            return {'cabana': {'nombre': f'Cabaña {i}', 'hora_check_in': '16:00', 'servicio_id': i},
                    'tina': {'nombre': 'Tina Tronador', 'hora': '22:00', 'servicio_id': 1},
                    'precio_total': 130000, 'precio_con_descuento': 130000, 'hay_descuento': False}
        with mock.patch('whatsapp_agent.packs.disponibilidad_pack_cabana_tina',
                        return_value={'fecha': '2026-09-26',
                                      'alternativas': [opcion(i) for i in range(10)]}):
            alts = alternativas.construir_alternativas(
                'noche_aguas_calientes', '2026-09-26', 2)['alternativas']
        self.assertEqual(len(alts), alternativas.MAX_ALTERNATIVAS_NOCHE)


def _alt(nombre, hora, precio):
    return {'titulo': f'{nombre} · {hora}', 'precio_total': precio,
            'precio_con_descuento': precio, 'hay_descuento': False,
            'texto_sugerido': f'{nombre} {hora}',
            'itinerario': [{'servicio': nombre, 'hora': hora}]}


class LunaVeLaTarde(SimpleTestCase):
    def _tool(self, alts):
        with mock.patch('whatsapp_agent.availability.resolver_fecha',
                        return_value={'fecha_iso': '2026-09-26', 'dia_semana': 'sábado',
                                      'ambiguo': False, 'error': None}), \
                mock.patch('whatsapp_agent.alternativas.construir_alternativas',
                           return_value={'tipo': 'tina_sola', 'fecha': '2026-09-26', 'personas': 2,
                                         'nombre_experiencia': 'Tina', 'alternativas': alts}):
            return _tool_alternativas_experiencia(
                {'tipo': 'tina_sola', 'fecha': 'el sábado', 'personas': 2})

    def test_la_recomendada_es_de_verdad_la_mas_tarde(self):
        baratas = [_alt(t, h, 50000) for h in HORAS for t in ('Tina Tronador', 'Tina Hornopiren')]
        out = self._tool(baratas)
        self.assertEqual(out['recomendada']['itinerario'][0]['hora'], '21:30')

    def test_el_respaldo_trae_hidromasaje_aunque_haya_muchas_baratas(self):
        baratas = [_alt(t, h, 50000) for h in HORAS for t in ('Tina Tronador', 'Tina Hornopiren')]
        hidro = [_alt('Tina Hidromasaje Llaima', h, 60000) for h in HORAS]
        out = self._tool(baratas + hidro)
        nombres = [a['itinerario'][0]['servicio'] for a in out['otras_alternativas']]
        self.assertEqual(len(nombres), 8)
        self.assertIn('Tina Hidromasaje Llaima', nombres)
        self.assertTrue({'Tina Tronador', 'Tina Hornopiren'} & set(nombres), nombres)

    def test_el_respaldo_turna_los_grupos_de_precio(self):
        a1, a2 = _alt('Tina Tronador', '19:00', 50000), _alt('Tina Tronador', '17:00', 50000)
        b1 = _alt('Tina Hidromasaje Llaima', '21:30', 60000)
        self.assertEqual(_otras_variadas([a1, a2, b1], 8), [a1, b1, a2])
        self.assertEqual(_otras_variadas([a1, a2, b1], 2), [a1, b1])
