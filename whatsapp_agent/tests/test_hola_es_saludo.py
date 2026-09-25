"""Un «hola» solo recibe el saludo de Luna, no la carta de precios (Jorge, 25-09-2026).

Jorge: «si el cliente solo escribe Hola, debería recibir el saludo de Luna y no el
listado de servicios. El listado de servicios es cuando preguntan solo precios o qué
servicios tienen». Luna era inconsistente: en 60 días, 92 de 201 borradores a un
«hola» solo llevaban la carta completa. Y de los que solo saludaron, tras la carta el
30% no volvió a escribir en 48 h; tras un saludo, el 17%, y casi la mitad dijo qué
quería («Quiero reservar para 1 noche 02 septiembre», «Somos 2 adultos y dos niños»).

En la apertura (primer contacto o regreso) el saludo lo escribe el código; con la
conversación en curso responde Luna, pero sin la carta en el prompt de ese turno.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_hola_es_saludo
"""
from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase, TestCase

from destino_puerto_varas.services.llm.openrouter_provider import LLMResult
from whatsapp_agent import agent, prompt
from whatsapp_agent.agent import es_solo_saludo

PROVIDER = ('destino_puerto_varas.services.llm.openrouter_provider.'
            'OpenRouterProvider.generate_with_tools')
CARTA = 'Estos son nuestros servicios y experiencias 🌿\n✓ Masaje — $40.000\n✓ Tina — $50.000'


class QueEsSoloUnSaludo(SimpleTestCase):
    def test_saludos(self):
        for texto in ('hola', 'Hola!', 'Hola, buenas tardes', 'Buen día', 'holaaa 👋',
                      'Hola, ¿cómo estás?', 'Buenas noches', 'Hola Luna', 'hola hola', 'Buenas'):
            self.assertTrue(es_solo_saludo(texto), texto)

    def test_lo_que_no_es_solo_un_saludo(self):
        for texto in ('hola, precios porfa', 'Hola quisiera información', '¿Costo de los servicios?',
                      'hola tienen tinas?', 'hola para el lunes', '', '👋', '¿qué?',
                      'que tal los precios'):
            self.assertFalse(es_solo_saludo(texto), texto)


class ElSaludoDeLuna(SimpleTestCase):
    def test_los_textos(self):
        self.assertEqual(prompt.saludo_de_luna('primer_contacto', 'Jorge'),
                         '¡Hola, Jorge! 🌿 Te saluda Luna, tu asistente en Aremko Spa Boutique. '
                         '¿En qué te puedo ayudar?')
        self.assertEqual(prompt.saludo_de_luna('regreso', ''),
                         '¡Hola! 🌿 Te saluda Luna, de Aremko. ¡Qué gusto tenerte de vuelta! '
                         '¿En qué te puedo ayudar?')
        self.assertEqual(prompt.saludo_de_luna('en_conversacion', 'Jorge'), '')

    def test_es_el_mismo_saludo_del_ejemplo_del_prompt(self):
        self.assertIn('«¡Hola, Jorge! 🌿 Te saluda Luna, tu asistente en Aremko Spa Boutique.»',
                      prompt.bloque_saludo('primer_contacto', 'Jorge'))


def _turno(mensaje, estado):
    visto = {}

    def generate_with_tools(self, messages, tools, tool_executor, **kwargs):
        visto['system'] = messages[0]['content']
        return LLMResult('¿En qué te puedo ayudar?', 'google/gemini-2.5-flash', 10, 5, 100)

    with mock.patch(PROVIDER, generate_with_tools), \
            mock.patch('whatsapp_agent.carta.carta_de_precios', return_value=CARTA):
        d = agent._producir_borrador_inner(agent.get_config(), mensaje, '', saludo_estado=estado,
                                           saludo_nombre='Jorge', phone='+56911112222')
    return d, visto


class EnElTurno(TestCase):
    def test_hola_en_la_apertura_lo_contesta_el_codigo(self):
        d, visto = _turno('hola', 'primer_contacto')
        self.assertEqual(d['texto'], prompt.saludo_de_luna('primer_contacto', 'Jorge'))
        self.assertEqual(d['modelo'], 'codigo')
        self.assertNotIn('system', visto)   # ni se llamó al modelo

    def test_hola_de_quien_vuelve(self):
        d, _ = _turno('Hola, buenas tardes', 'regreso')
        self.assertIn('¡Qué gusto tenerte de vuelta!', d['texto'])

    def test_hola_con_la_conversacion_en_curso_va_sin_carta(self):
        _, visto = _turno('hola', 'en_conversacion')
        self.assertNotIn('CARTA DE PRECIOS', visto['system'])
        self.assertNotIn('✓ Masaje', visto['system'])

    def test_quien_pide_precios_sigue_recibiendo_la_carta(self):
        for mensaje in ('¿Costo de los servicios?', 'hola, quisiera información'):
            _, visto = _turno(mensaje, 'primer_contacto')
            self.assertIn('CARTA DE PRECIOS', visto['system'], mensaje)
            self.assertIn('✓ Masaje — $40.000', visto['system'], mensaje)
