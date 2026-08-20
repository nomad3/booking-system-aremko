# -*- coding: utf-8 -*-
"""Estudio de primeras respuestas (P-34) — la parte pura, sin BD.

Lo que clava esta suite:

· «Termina preguntando» tolera emojis/puntuación después del `?` — el estilo
  real de la casa cierra con 🌿 y no por eso deja de ser una pregunta de cierre.
· La respuesta que se estudia es la PRIMERA con precio, no la primera a secas:
  el saludo inicial no es lo que mata o salva la conversación.
· Una conversación sin respuesta-con-precio devuelve None y se cuenta aparte:
  morir sin que te digan el precio es fricción/demora, no un problema de guion.
"""
from datetime import datetime, timedelta

from django.test import SimpleTestCase

from whatsapp_agent.estudio_respuestas import (analizar_conversacion,
                                               rasgos_de_respuesta,
                                               resumen_grupo,
                                               termina_preguntando)

T0 = datetime(2026, 8, 20, 10, 0, 0)


def _t(minutos):
    return T0 + timedelta(minutes=minutos)


class TerminaPreguntandoTest(SimpleTestCase):

    def test_pregunta_al_final(self):
        self.assertTrue(termina_preguntando('La tina vale $50.000. ¿Te reservo el sábado?'))

    def test_emoji_despues_de_la_pregunta_no_la_anula(self):
        self.assertTrue(termina_preguntando('¿Te acomoda a las 17:00? 🌿'))

    def test_texto_despues_de_la_pregunta_si_la_anula(self):
        self.assertFalse(termina_preguntando('¿Cuándo vienes? Te esperamos, saludos'))

    def test_sin_pregunta(self):
        self.assertFalse(termina_preguntando('El valor es $50.000 por persona. Saludos'))
        self.assertFalse(termina_preguntando(''))


class RasgosTest(SimpleTestCase):

    def test_cuenta_precios_y_horarios(self):
        r = rasgos_de_respuesta('Cabaña $110.000 y tina $ 50.000, desde las 16:00. '
                                'Reserva en https://aremko.cl ¿Te tinca?')
        self.assertEqual(r['n_precios'], 2)
        self.assertTrue(r['menciona_horarios'])
        self.assertTrue(r['tiene_link'])
        self.assertTrue(r['termina_preguntando'])

    def test_numero_sin_signo_peso_no_es_precio(self):
        self.assertEqual(rasgos_de_respuesta('somos 110.000 fans')['n_precios'], 0)


class AnalizarConversacionTest(SimpleTestCase):

    def test_sin_respuesta_con_precio_devuelve_none(self):
        msgs = [('in', 'hola, precios?', _t(0)),
                ('out', 'Hola! ¿Para cuántas personas?', _t(1))]
        self.assertIsNone(analizar_conversacion(msgs))

    def test_estudia_la_primera_con_precio_no_la_primera_a_secas(self):
        msgs = [
            ('in', 'hola, precio de las tinas?', _t(0)),
            ('out', '¡Hola! ¿Para cuántas personas sería?', _t(1)),
            ('in', 'para 2', _t(5)),
            ('out', 'Para 2 la tina vale $50.000. ¿Te reservo?', _t(6)),
            ('in', 'gracias, lo veo', _t(10)),
        ]
        a = analizar_conversacion(msgs)
        self.assertIn('$50.000', a['texto'])
        # El gap se mide contra el ÚLTIMO entrante previo («para 2», t+5).
        self.assertEqual(a['gap_seg'], 60.0)
        self.assertTrue(a['respuesta_rapida'])
        self.assertTrue(a['cliente_respondio'])
        self.assertEqual(a['n_in_despues'], 1)

    def test_silencio_despues_del_precio(self):
        msgs = [('in', 'precio?', _t(0)),
                ('out', 'La tina vale $50.000 por persona.', _t(20))]
        a = analizar_conversacion(msgs)
        self.assertFalse(a['cliente_respondio'])
        self.assertFalse(a['respuesta_rapida'])  # 20 min > 90s
        self.assertFalse(a['termina_preguntando'])


class ResumenGrupoTest(SimpleTestCase):

    def test_agrega_sobre_la_lista(self):
        a1 = analizar_conversacion([
            ('in', 'precio?', _t(0)),
            ('out', 'Vale $50.000. ¿Te reservo?', _t(1)),
            ('in', 'sí!', _t(2)),
        ])
        a2 = analizar_conversacion([
            ('in', 'precio?', _t(0)),
            ('out', 'Vale $50.000.', _t(30)),
        ])
        r = resumen_grupo([a1, a2])
        self.assertEqual(r['n'], 2)
        self.assertEqual(r['pct_termina_preguntando'], 50.0)
        self.assertEqual(r['pct_cliente_respondio'], 50.0)
        self.assertEqual(r['pct_respuesta_rapida'], 50.0)

    def test_vacio(self):
        self.assertEqual(resumen_grupo([]), {'n': 0})
