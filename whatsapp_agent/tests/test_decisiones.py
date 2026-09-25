"""Etapa 2 del encargo PROMPT_JEV_AREMKO.md: el cliente del modelo de decisión.

La regla que gobierna todo: `decidir()` nunca lanza y, ante cualquier falla, devuelve
None («hoy no hay opinión») para que quien llama siga exactamente como antes.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_decisiones
"""
from __future__ import annotations

from unittest import mock

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings

from whatsapp_agent import decisiones
from whatsapp_agent.decisiones import decidir
from whatsapp_agent.models import DecisionAgente, WhatsAppAgentConfig

POST = 'whatsapp_agent.decisiones.requests.post'
PREGUNTAS = {'que_cambio': {'type': 'choice', 'instructions': '¿Qué cambió?',
                            'criteria': {'regla': 'una política', 'tono': 'solo redacción'}}}
BUENA = {'model': 'typesafe/jev-1.13', 'usage': {'cost': 0.00004},
         'answers': {'que_cambio': {'type': 'choice', 'choice': 'regla', 'score': None,
                                    'noul': None, 'confidence': 0.91}}}


def _respuesta_http(status=200, datos=BUENA, json_error=False):
    r = mock.Mock(status_code=status)
    if json_error:
        r.json.side_effect = ValueError('no es JSON')
    else:
        r.json.return_value = datos
    return r


@override_settings(OPENROUTER_API_KEY='llave-de-prueba', DECISIONES_RUTA='',
                   DECISIONES_MODELO='', DECISIONES_ESPERA_SEG='')
class Decidir(TestCase):
    def setUp(self):
        cache.clear()

    def test_respuesta_buena(self):
        with mock.patch(POST, return_value=_respuesta_http()) as post:
            r = decidir('Deborah cambió la política', PREGUNTAS, uso='prueba', referencia='7')
        self.assertEqual(r.opcion('que_cambio'), 'regla')
        self.assertAlmostEqual(r.confianza('que_cambio'), 0.91)
        self.assertEqual(post.call_args.args[0], decisiones.RUTA_POR_DEFECTO)
        self.assertEqual(post.call_args.kwargs['json']['model'], 'typesafe/jev-1.13')
        self.assertEqual(post.call_args.kwargs['timeout'], 2.0)
        d = DecisionAgente.objects.get()
        self.assertEqual((d.uso, d.referencia, d.error), ('prueba', '7', ''))
        self.assertAlmostEqual(d.confianza, 0.91)

    def test_las_fallas_devuelven_none_sin_lanzar(self):
        casos = {
            'timeout': dict(side_effect=requests.Timeout()),
            'HTTP 500': dict(return_value=_respuesta_http(status=500)),
            'JSON basura': dict(return_value=_respuesta_http(json_error=True)),
            'sin decisiones': dict(return_value=_respuesta_http(datos={'model': 'x'})),
            'red caída': dict(side_effect=requests.ConnectionError()),
            'algo raro': dict(side_effect=RuntimeError('explotó')),
        }
        for nombre, falla in casos.items():
            cache.clear()
            with mock.patch(POST, **falla):
                self.assertIsNone(decidir(f'estado {nombre}', PREGUNTAS, uso=nombre), nombre)
        self.assertEqual(DecisionAgente.objects.exclude(error='').count(), len(casos))

    @override_settings(OPENROUTER_API_KEY='')
    def test_sin_llave_ni_siquiera_llama(self):
        with mock.patch(POST) as post:
            self.assertIsNone(decidir('estado', PREGUNTAS))
        post.assert_not_called()

    def test_lo_mismo_no_se_pregunta_dos_veces(self):
        with mock.patch(POST, return_value=_respuesta_http()) as post:
            primera = decidir('el mismo estado', PREGUNTAS)
            segunda = decidir('el mismo estado', PREGUNTAS)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(primera.opcion('que_cambio'), segunda.opcion('que_cambio'))

    def test_una_falla_no_se_guarda_en_la_cache(self):
        with mock.patch(POST, return_value=_respuesta_http(status=503)):
            self.assertIsNone(decidir('estado', PREGUNTAS))
        with mock.patch(POST, return_value=_respuesta_http()) as post:
            self.assertIsNotNone(decidir('estado', PREGUNTAS))
        post.assert_called_once()

    def test_ruta_modelo_y_espera_se_leen_en_cada_llamada(self):
        with override_settings(DECISIONES_RUTA='https://otra.ruta/decisions',
                               DECISIONES_MODELO='otro/modelo', DECISIONES_ESPERA_SEG='3.5'), \
                mock.patch(POST, return_value=_respuesta_http()) as post:
            decidir('estado nuevo', PREGUNTAS)
        self.assertEqual(post.call_args.args[0], 'https://otra.ruta/decisions')
        self.assertEqual(post.call_args.kwargs['json']['model'], 'otro/modelo')
        self.assertEqual(post.call_args.kwargs['timeout'], 3.5)

    def test_si_falla_el_registro_la_decision_no_se_pierde(self):
        with mock.patch(POST, return_value=_respuesta_http()), \
                mock.patch.object(DecisionAgente.objects, 'create', side_effect=RuntimeError('BD')):
            r = decidir('estado', PREGUNTAS)
        self.assertEqual(r.opcion('que_cambio'), 'regla')

    def test_el_error_no_muestra_la_llave(self):
        with mock.patch(POST, side_effect=requests.ConnectionError('llave-de-prueba en la URL')):
            decidir('estado', PREGUNTAS)
        self.assertNotIn('llave-de-prueba', DecisionAgente.objects.get().error)


class ElInterruptor(TestCase):
    def test_viene_apagado(self):
        self.assertFalse(WhatsAppAgentConfig.get_solo().usar_jev_en_aprendizaje)
