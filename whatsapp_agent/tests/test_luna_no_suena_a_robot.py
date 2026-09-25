"""Luna no debe sonar a robot (Jorge, 25-09-2026: «¿estás conversando con un robot?»).

La conversación real: cuatro mensajes seguidos con el mismo molde —«Perfecto,
Jorge. Para el lunes 28 de septiembre, después de las X hrs, tenemos
disponible la Tina Y… ¿Te gustaría reservar este horario o prefieres revisar
otra opción?»—, «Perfecto» cuando el cliente decía que no, y avance de a media
hora tras tres «más tarde». En 30 días de borradores, el 53% empezaba con
«Perfecto» y el 11% de los mensajes seguidos repetía las 3 primeras palabras.

Arreglo aprobado por Jorge («ve con las cuatro»): reglas de estilo (prompt y
herramienta), «más tarde» con criterio (al segundo, preguntar la hora; con una
hora dada, la más cercana), freno en código contra aperturas repetidas, y medir.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_luna_no_suena_a_robot
"""
from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase, TestCase

from destino_puerto_varas.services.llm.openrouter_provider import LLMResult
from whatsapp_agent import agent, prompt
from whatsapp_agent.agent import (_con_tipo_de_tina, _sin_repetir_apertura,
                                  _tool_alternativas_experiencia, _ultima_hora_ofrecida,
                                  _veces_mas_tarde, quitar_arranque, repite_apertura)

GENERATE = 'destino_puerto_varas.services.llm.openrouter_provider.OpenRouterProvider.generate'
PROVIDER = ('destino_puerto_varas.services.llm.openrouter_provider.'
            'OpenRouterProvider.generate_with_tools')
ANTERIOR = ('Perfecto, Jorge. Para el lunes 28 de septiembre, después de las 14:30 hrs, tenemos '
            'disponible la Tina Hidromasaje Villarrica a las 16:30 hrs para 2 personas, con un '
            'valor de $60.000. ¿Te gustaría reservar este horario o prefieres revisar otra opción?')
BORRADOR = ('Perfecto, Jorge. Para el lunes 28 de septiembre, después de las 16:30 hrs, tenemos '
            'disponible la Tina Hornopiren a las 17:00 hrs para 2 personas, con un valor de '
            '$50.000. ¿Te gustaría reservar este horario o prefieres revisar otra opción?')
HISTORIAL = f'[Cliente]: mas tarde\n[Aremko]: {ANTERIOR}'
# Reescrituras reales del freno en prod (25-09-2026, antes de exigirle el tono).
REESCRITA_SUPER = ('¡Súper! Para el lunes, a las 17:00 hrs, tenemos disponible la Tina Hornopiren '
                   'para 2 personas, con un valor de $50.000. ¿Te acomoda esa hora?')
REESCRITA_HOLA = ('¡Hola! Para el lunes 28 de septiembre, te cuento que tenemos disponible la Tina '
                  'Hornopiren a las 17:00 hrs para 2 personas, con un valor de $50.000. ¿Te tinca '
                  'reservar esta opción?')


def _llm(texto, ok=True):
    return LLMResult(texto, 'google/gemini-2.5-flash', 120, 40, 700, error='' if ok else 'falló')


class DetectaLaAperturaRepetida(SimpleTestCase):
    def test_el_caso_real(self):
        self.assertTrue(repite_apertura(BORRADOR, ANTERIOR))

    def test_perfecto_tras_perfecto_aunque_siga_distinto(self):
        self.assertTrue(repite_apertura('Perfecto. A las 16:30 hay una clásica.', ANTERIOR))

    def test_las_mismas_tres_palabras(self):
        self.assertTrue(repite_apertura('Para el lunes tengo otra.', 'Para el lunes hay una.'))

    def test_arranque_distinto_no_es_repetir(self):
        self.assertFalse(repite_apertura('A las 17:00 queda la clásica Hornopiren.', ANTERIOR))
        self.assertFalse(repite_apertura('Perfecto, te la dejo.', 'A las 17:00 queda una.'))

    def test_quitar_la_muletilla(self):
        self.assertTrue(quitar_arranque(BORRADOR).startswith('Para el lunes 28'))
        self.assertEqual(quitar_arranque('Excelente, a las 19:00 hay una.'), 'A las 19:00 hay una.')
        self.assertEqual(quitar_arranque('¡Perfecto! Te la dejo.'), 'Te la dejo.')
        self.assertEqual(quitar_arranque('¡Súper! A las 14:30 hay una.'), 'A las 14:30 hay una.')

    def test_una_muletilla_tras_otra_tambien_es_repetir(self):
        # Probado en prod: la reescritura cambiaba «Perfecto» por «¡Súper!».
        self.assertTrue(repite_apertura(REESCRITA_SUPER, ANTERIOR))


class ElFrenoReescribe(SimpleTestCase):
    def test_sin_mensaje_anterior_no_toca_nada(self):
        with mock.patch(GENERATE) as gen:
            self.assertEqual(_sin_repetir_apertura(BORRADOR, '', 'm')[0], BORRADOR)
        gen.assert_not_called()

    def test_si_no_repite_no_llama_al_modelo(self):
        with mock.patch(GENERATE) as gen:
            texto, extra = _sin_repetir_apertura('A las 17:00 queda la clásica.', HISTORIAL, 'm')
        gen.assert_not_called()
        self.assertEqual(extra, (0, 0, 0))

    def test_si_repite_usa_la_reescritura_que_conserva_hora_y_precio(self):
        nueva = 'La siguiente es a las 17:00, la clásica Hornopiren: sale $50.000. ¿Te sirve?'
        with mock.patch(GENERATE, return_value=_llm(nueva)) as gen:
            texto, extra = _sin_repetir_apertura(BORRADOR, HISTORIAL, 'google/gemini-2.5-flash')
        self.assertEqual(texto, nueva)
        self.assertEqual(extra, (120, 40, 700))
        self.assertIn('Mensaje anterior de Luna', gen.call_args.args[1])

    def test_si_la_reescritura_pierde_el_precio_se_quita_la_muletilla(self):
        with mock.patch(GENERATE, return_value=_llm('A las 17:00 queda la clásica. ¿Te sirve?')):
            texto, _ = _sin_repetir_apertura(BORRADOR, HISTORIAL, 'm')
        self.assertEqual(texto, quitar_arranque(BORRADOR))
        self.assertIn('$50.000', texto)

    def test_si_la_reescritura_tambien_repite_se_quita_la_muletilla(self):
        with mock.patch(GENERATE, return_value=_llm('Perfecto, a las 17:00 y $50.000.')):
            texto, _ = _sin_repetir_apertura(BORRADOR, HISTORIAL, 'm')
        self.assertFalse(texto.startswith('Perfecto'))

    def test_si_la_reescritura_inventa_una_hora_se_quita_la_muletilla(self):
        nueva = 'La siguiente es a las 17:00 o a las 19:00, sale $50.000. ¿Te sirve?'
        with mock.patch(GENERATE, return_value=_llm(nueva)):
            texto, _ = _sin_repetir_apertura(BORRADOR, HISTORIAL, 'm')
        self.assertEqual(texto, quitar_arranque(BORRADOR))

    def test_si_la_reescritura_afirma_una_reserva_se_quita_la_muletilla(self):
        nueva = 'Te reservé la clásica Hornopiren a las 17:00 por $50.000.'
        with mock.patch(GENERATE, return_value=_llm(nueva)):
            texto, _ = _sin_repetir_apertura(BORRADOR, HISTORIAL, 'm')
        self.assertEqual(texto, quitar_arranque(BORRADOR))

    def test_el_link_tambien_se_conserva(self):
        con_link = 'Perfecto, aquí está tu Pase: https://aremko.cl/pase/abc123.'
        with mock.patch(GENERATE, return_value=_llm('Aquí va tu Pase, ahí está todo.')):
            texto, _ = _sin_repetir_apertura(con_link, HISTORIAL, 'm')
        self.assertIn('https://aremko.cl/pase/abc123', texto)

    def test_las_reescrituras_reales_de_prod_se_descartan(self):
        for nueva in (REESCRITA_SUPER, REESCRITA_HOLA):
            with mock.patch(GENERATE, return_value=_llm(nueva)):
                texto, _ = _sin_repetir_apertura(BORRADOR, HISTORIAL, 'm')
            self.assertEqual(texto, quitar_arranque(BORRADOR), nueva)

    def test_la_reescritura_con_muletilla_se_descarta_aunque_la_anterior_no_tuviera(self):
        anterior = '[Aremko]: Para el lunes 28 hay una clásica a las 14:30, sale $50.000.'
        borrador = 'Para el lunes 28 hay otra clásica a las 17:00, sale $50.000.'
        with mock.patch(GENERATE, return_value=_llm('¡Súper! A las 17:00 hay otra, $50.000.')):
            texto, _ = _sin_repetir_apertura(borrador, anterior, 'm')
        self.assertEqual(texto, borrador)

    def test_la_reescritura_que_saluda_a_mitad_de_conversacion_se_descarta(self):
        nueva = '¡Hola! A las 17:00 queda la clásica Hornopiren, sale $50.000. ¿Te sirve?'
        with mock.patch(GENERATE, return_value=_llm(nueva)):
            texto, _ = _sin_repetir_apertura(BORRADOR, HISTORIAL, 'm')
        self.assertEqual(texto, quitar_arranque(BORRADOR))

    def test_la_reescritura_con_jerga_se_descarta(self):
        nueva = 'A las 17:00 queda la clásica Hornopiren, sale $50.000. ¿Te tinca?'
        with mock.patch(GENERATE, return_value=_llm(nueva)):
            texto, _ = _sin_repetir_apertura(BORRADOR, HISTORIAL, 'm')
        self.assertEqual(texto, quitar_arranque(BORRADOR))

    def test_la_reescritura_pide_el_tono_de_aremko(self):
        nueva = 'La siguiente es a las 17:00, la clásica Hornopiren: sale $50.000. ¿Te sirve?'
        with mock.patch(GENERATE, return_value=_llm(nueva)) as gen:
            _sin_repetir_apertura(BORRADOR, HISTORIAL, 'm')
        sistema = gen.call_args.args[0]
        for regla in ('sin chilenismos', 'No saludes', '«Súper»'):
            self.assertIn(regla, sistema)

    def test_si_el_modelo_falla_igual_se_quita_la_muletilla(self):
        with mock.patch(GENERATE, side_effect=RuntimeError('caído')):
            texto, extra = _sin_repetir_apertura(BORRADOR, HISTORIAL, 'm')
        self.assertTrue(texto.startswith('Para el lunes'))
        self.assertEqual(extra, (0, 0, 0))


class MasTardeConCriterio(SimpleTestCase):
    def test_cuenta_los_mas_tarde_seguidos(self):
        self.assertEqual(_veces_mas_tarde('mas tarde', ''), 1)
        self.assertEqual(_veces_mas_tarde('mas tarde', HISTORIAL), 2)
        self.assertEqual(_veces_mas_tarde('y más tarde?', f'[Cliente]: más tarde\n{HISTORIAL}'), 3)
        otro = '[Cliente]: para 2 personas\n[Aremko]: A las 14:00 hay una.'
        self.assertEqual(_veces_mas_tarde('mas tarde', otro), 1)
        self.assertEqual(_veces_mas_tarde('para el lunes', HISTORIAL), 0)
        self.assertEqual(_veces_mas_tarde('después te confirmo si vamos o no con mi señora', ''), 0)

    def _luna(self, alts, **extra):
        with mock.patch('whatsapp_agent.availability.resolver_fecha',
                        return_value={'fecha_iso': '2026-09-28', 'dia_semana': 'lunes',
                                      'ambiguo': False, 'error': None}), \
                mock.patch('whatsapp_agent.alternativas.construir_alternativas',
                           return_value={'tipo': 'tina_sola', 'fecha': '2026-09-28', 'personas': 2,
                                         'nombre_experiencia': 'Tina', 'alternativas': alts}):
            return _tool_alternativas_experiencia(
                dict({'tipo': 'tina_sola', 'fecha': 'lunes', 'personas': 2}, **extra))

    def _alts(self, *horas):
        return [{'titulo': f'Tina · {h}', 'precio_total': 50000, 'precio_con_descuento': 50000,
                 'hay_descuento': False, 'texto_sugerido': h,
                 'itinerario': [{'servicio': 'Tina Tronador', 'hora': h}]} for h in horas]

    def test_al_segundo_mas_tarde_pregunta_la_hora(self):
        out = self._luna(self._alts('14:00', '14:30', '16:30', '17:00', '19:00', '21:30'),
                         despues_de='14:30', preguntar_hora=True)
        self.assertIsNone(out['recomendada'])
        self.assertEqual(out['ultima_hora'], '21:30')
        self.assertIn('qué hora le acomoda', out['instruccion'])

    def test_si_quedan_pocas_ofrece_la_siguiente(self):
        out = self._luna(self._alts('14:00', '19:00', '21:30'), despues_de='14:00',
                         preguntar_hora=True)
        self.assertEqual(out['recomendada']['titulo'], 'Tina · 19:00')

    def test_con_una_hora_dada_la_mas_cercana(self):
        out = self._luna(self._alts('14:00', '16:30', '19:00', '21:30'), hora='19:15')
        self.assertEqual(out['recomendada']['titulo'], 'Tina · 19:00')

    def test_la_ultima_hora_ofrecida_no_cuenta_la_de_la_pregunta(self):
        # La conversación real de prod: oferta 14:30, luego la pregunta «hasta las 19:30».
        conversacion = (
            '[Cliente]: mas tarde\n'
            '[Aremko]: ¡Súper! Para el lunes, a las 14:30 hrs, tenemos disponible la Tina '
            'Tronador para 2 personas, con un valor de $50.000. ¿Te acomoda esa hora?\n'
            '[Cliente]: mas tarde\n'
            '[Aremko]: Perfecto. Para el lunes, tenemos horarios disponibles hasta las 19:30 hrs. '
            '¿Qué hora te acomoda?')
        self.assertEqual(_ultima_hora_ofrecida(conversacion), '14:30')
        self.assertEqual(_ultima_hora_ofrecida('[Aremko]: Hay tinas hasta 19:30. ¿Qué hora?\n'), None)
        self.assertEqual(_ultima_hora_ofrecida(''), None)

    def test_el_tipo_de_tina_viaja_con_la_oferta(self):
        out = self._luna(self._alts('14:00', '16:30'))
        self.assertEqual(out['recomendada']['tina_tipo'], 'clásica (sin hidromasaje)')
        self.assertEqual(out['otras_alternativas'][0]['tina_tipo'], 'clásica (sin hidromasaje)')
        hidro = {'itinerario': [{'servicio': 'Tina Hidromasaje Villarrica', 'hora': '14:00'}]}
        self.assertEqual(_con_tipo_de_tina(hidro)['tina_tipo'], 'con hidromasaje')
        masaje = {'itinerario': [{'servicio': 'Masaje Relajación', 'hora': '15:00'}]}
        self.assertNotIn('tina_tipo', _con_tipo_de_tina(masaje))


class ElPromptLoDice(SimpleTestCase):
    def test_reglas_de_estilo(self):
        texto = prompt.build_system_prompt('', '', '', '')
        for regla in ('NO empieces con «Perfecto»', 'solo al saludar', 'SOLO lo que cambia',
                      'Nunca narres tu búsqueda', '«clásica»', 'No repitas la pregunta de cierre'):
            self.assertIn(regla, texto)


def _turno(mensaje, historial, texto_modelo, llamadas=()):
    visto = {}

    def generate_with_tools(self, messages, tools, tool_executor, **kwargs):
        visto['resultados'] = [tool_executor(n, a) for n, a in llamadas]
        return LLMResult(texto_modelo, 'google/gemini-2.5-flash', 100, 20, 900)

    with mock.patch(PROVIDER, generate_with_tools):
        d = agent._producir_borrador_inner(agent.get_config(), mensaje, historial,
                                           saludo_estado='en_conversacion', phone='+56911112222')
    return d, visto


class EnElTurnoCompleto(TestCase):
    def test_el_borrador_repetido_sale_reescrito(self):
        nueva = 'La siguiente es a las 17:00, la clásica Hornopiren: sale $50.000. ¿Te sirve?'
        with mock.patch(GENERATE, return_value=_llm(nueva)):
            d, _ = _turno('mas tarde', HISTORIAL, BORRADOR)
        self.assertEqual(d['texto'], nueva)
        self.assertFalse(d['escalar'])

    def test_el_freno_va_antes_del_link_de_el_pase(self):
        # La reescritura no ve el link que se suma al final, así que no puede perderlo.
        link = ' https://aremko.cl/pase/abc123'
        nueva = 'La siguiente es a las 17:00, la clásica Hornopiren: sale $50.000. ¿Te sirve?'
        with mock.patch(GENERATE, return_value=_llm(nueva)) as gen, \
                mock.patch('whatsapp_agent.agent.sumar_pase_si_pregunta',
                           side_effect=lambda t, m, p: t + link):
            d, _ = _turno('mas tarde', HISTORIAL, BORRADOR)
        self.assertNotIn(link.strip(), gen.call_args.args[1])
        self.assertEqual(d['texto'], nueva + link)

    def test_el_segundo_mas_tarde_llega_a_la_herramienta(self):
        with mock.patch('whatsapp_agent.agent._tool_alternativas_experiencia',
                        return_value={'success': True}) as herramienta, \
                mock.patch(GENERATE, return_value=_llm('¿Qué hora te acomoda? Hay hasta las 21:30.')):
            _turno('mas tarde', HISTORIAL, '¿Qué hora te acomoda? Hay hasta las 21:30.',
                   llamadas=[('alternativas_experiencia',
                              {'tipo': 'tina_sola', 'fecha': 'lunes', 'personas': 2,
                               'despues_de': '16:30'})])
        self.assertTrue(herramienta.call_args.args[0]['preguntar_hora'])

    def test_al_tercer_mas_tarde_no_vuelve_a_preguntar(self):
        # Probado en prod: el modelo pasaba el «hasta las 21:30» de la pregunta como
        # `despues_de` y contestaba «no hay más tarde» sin ofrecer nada. Se sigue desde
        # la última hora OFRECIDA (16:30).
        ya_pregunto = (f'{HISTORIAL}\n[Cliente]: mas tarde\n'
                       '[Aremko]: ¿Qué hora te acomoda? Ese día hay hasta las 21:30.')
        with mock.patch('whatsapp_agent.agent._tool_alternativas_experiencia',
                        return_value={'success': True}) as herramienta, \
                mock.patch(GENERATE, return_value=_llm('A las 17:00 hay una clásica.')):
            _turno('mas tarde', ya_pregunto, 'A las 17:00 hay una clásica, sale $50.000.',
                   llamadas=[('alternativas_experiencia',
                              {'tipo': 'tina_sola', 'fecha': 'lunes', 'personas': 2,
                               'despues_de': '21:30'})])
        args = herramienta.call_args.args[0]
        self.assertNotIn('preguntar_hora', args)
        self.assertEqual(args['despues_de'], '16:30')

    def test_tambien_por_la_consulta_general(self):
        with mock.patch('whatsapp_agent.agent._tool_alternativas_experiencia',
                        return_value={'success': True}) as herramienta, \
                mock.patch(GENERATE, return_value=_llm('¿Qué hora te acomoda?')):
            _turno('mas tarde', HISTORIAL, '¿Qué hora te acomoda?',
                   llamadas=[('consultar_disponibilidad',
                              {'personas': 2, 'fecha': 'lunes', 'tipo': 'tina',
                               'despues_de': '16:30'}),
                             ('consultar_disponibilidad',
                              {'personas': 2, 'fecha': 'lunes', 'tipo': 'tina', 'hora': '19:00'})])
        primera, segunda = [c.args[0] for c in herramienta.call_args_list]
        self.assertTrue(primera['preguntar_hora'])
        self.assertEqual(segunda['hora'], '19:00')
        self.assertNotIn('preguntar_hora', segunda)
