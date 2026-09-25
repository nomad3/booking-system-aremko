"""Etapa 3 del encargo PROMPT_JEV_AREMKO.md: clasificar las correcciones con Jev.

Jev decide el tipo con su confianza; el texto lo redacta el camino de siempre y solo
cuando vale la pena. Lo que ya está en el Conocimiento, o repite una sugerencia anterior
(también las descartadas), no se propone de nuevo: en junio de 2026 el clasificador
propuso «enviar un link» 7 veces y se aprobaron reglas ya existentes.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_aprendizaje_jev
"""
from __future__ import annotations

from unittest import mock

from django.test import TestCase

from whatsapp_agent import aprendizaje
from whatsapp_agent.decisiones import Respuesta
from whatsapp_agent.models import AgenteFeedback, SugerenciaAprendizaje, WhatsAppAgentConfig

DECIDIR = 'whatsapp_agent.decisiones.decidir'
CLASIFICAR = 'whatsapp_agent.aprendizaje.clasificar'
CATALOGO = 'whatsapp_agent.grounding.catalogo_vivo'
BORRADOR = 'La tina está disponible el lunes a las 14:00 por $60.000 para dos.'
ENVIADO = 'Los lunes no ofrecemos tinas después de las 19:30 porque cerramos a las 21:30.'
REGLA = 'Los lunes no se ofrecen tinas después de las 19:30.'


def _jev(tipo='regla', confianza=0.9, generaliza=0.8, ya_esta=0.1):
    return Respuesta({'model': 'typesafe/jev-1.13', 'answers': {
        'que_cambio': {'type': 'choice', 'choice': tipo, 'confidence': confianza},
        'generaliza': {'type': 'noul', 'noul': generaliza},
        'ya_esta': {'type': 'noul', 'noul': ya_esta}}})


def _redaccion(texto=REGLA, error=''):
    return {'tipo': 'regla', 'texto_propuesto': texto, 'ref_catalogo': '', 'motivo': 'política',
            'modelo': 'google/gemini-2.5-flash', 'error': error}


class ConJev(TestCase):
    def setUp(self):
        self.config = WhatsAppAgentConfig.get_solo()
        self.config.conocimiento = 'Check-in a partir de las 16:00 hrs.'
        self.config.save()
        parche = mock.patch(CATALOGO, return_value='CATÁLOGO')
        parche.start()
        self.addCleanup(parche.stop)

    def _clasificar(self, jev, redaccion=None):
        with mock.patch(DECIDIR, return_value=jev) as decidir, \
                mock.patch(CLASIFICAR, return_value=redaccion or _redaccion()) as redactar:
            d = aprendizaje.clasificar_con_jev(self.config, BORRADOR, ENVIADO, referencia=7)
        return d, decidir, redactar

    def test_regla_que_vale_la_pena(self):
        d, decidir, redactar = self._clasificar(_jev())
        self.assertEqual((d['tipo'], d['texto_propuesto'], d['error']), ('regla', REGLA, ''))
        self.assertIn('typesafe/jev-1.13', d['modelo'])
        self.assertEqual(decidir.call_args.kwargs['referencia'], '7')
        estado = decidir.call_args.args[0]
        self.assertEqual((estado['borrador'], estado['enviado']), (BORRADOR, ENVIADO))
        self.assertIn('Check-in', estado['conocimiento'])
        redactar.assert_called_once()

    def test_sin_opinion_de_jev_va_el_clasificador_de_siempre(self):
        d, _, redactar = self._clasificar(None, redaccion=_redaccion())
        self.assertEqual(d, _redaccion())
        redactar.assert_called_once()

    def test_poca_confianza_no_se_marca_puntual_en_silencio(self):
        d, _, redactar = self._clasificar(_jev(confianza=0.55))
        self.assertIn('no concluyente', d['error'])
        redactar.assert_not_called()

    def test_tono_no_gasta_la_redaccion(self):
        d, _, redactar = self._clasificar(_jev(tipo='tono'))
        self.assertEqual((d['tipo'], d['error']), ('tono', ''))
        redactar.assert_not_called()

    def test_regla_que_no_generaliza(self):
        d, _, redactar = self._clasificar(_jev(generaliza=0.3))
        self.assertEqual(d['tipo'], 'puntual')
        self.assertIn('no generaliza', d['motivo'])
        redactar.assert_not_called()

    def test_lo_que_ya_esta_en_el_conocimiento(self):
        d, _, redactar = self._clasificar(_jev(ya_esta=0.8))
        self.assertEqual(d['tipo'], 'puntual')
        self.assertIn('ya está en el Conocimiento', d['motivo'])
        redactar.assert_not_called()

    def test_si_la_redaccion_falla_queda_sin_procesar(self):
        d, _, _ = self._clasificar(_jev(), redaccion=_redaccion(texto='', error='modelo caído'))
        self.assertEqual(d['error'], 'modelo caído')
        d, _, _ = self._clasificar(_jev(), redaccion=_redaccion(texto=''))
        self.assertIn('sin texto propuesto', d['error'])

    def test_no_repite_una_sugerencia_descartada(self):
        SugerenciaAprendizaje.objects.create(tipo='regla', estado='descartada',
                                             texto_propuesto='Los lunes no se ofrecen tinas '
                                                             'después de las 19:30 hrs.')
        d, _, _ = self._clasificar(_jev())
        self.assertEqual(d['tipo'], 'puntual')
        self.assertIn('repite la sugerencia', d['motivo'])
        self.assertIn('descartada', d['motivo'])

    def test_no_repite_una_linea_del_conocimiento(self):
        d, _, _ = self._clasificar(_jev(), redaccion=_redaccion(texto='Check-in desde las 16:00 hrs.'))
        self.assertEqual(d['tipo'], 'puntual')
        self.assertEqual(d['motivo'], 'ya está en el Conocimiento')


class ElInterruptor(TestCase):
    def setUp(self):
        self.fb = AgenteFeedback.objects.create(phone='+56911112222', borrador=BORRADOR,
                                                enviado=ENVIADO, editado=True)

    def test_apagado_es_el_camino_de_siempre(self):
        with mock.patch(CLASIFICAR, return_value=_redaccion()) as viejo, \
                mock.patch('whatsapp_agent.aprendizaje.clasificar_con_jev') as jev:
            res = aprendizaje.procesar_pendientes(10)
        jev.assert_not_called()
        viejo.assert_called_once()
        self.assertEqual((res['procesados'], res['creadas']), (1, 1))

    def test_prendido_clasifica_con_jev(self):
        config = WhatsAppAgentConfig.get_solo()
        config.usar_jev_en_aprendizaje = True
        config.save()
        with mock.patch('whatsapp_agent.aprendizaje.clasificar_con_jev',
                        return_value=dict(_redaccion(), error='no concluyente: regla con confianza 0.55')
                        ) as jev:
            res = aprendizaje.procesar_pendientes(10)
        self.assertEqual(jev.call_args.kwargs['referencia'], self.fb.id)
        self.fb.refresh_from_db()
        self.assertFalse(self.fb.procesado)       # no concluyente: lo mira una persona
        self.assertEqual((res['errores'], res['creadas']), (1, 0))

    def test_prendido_y_red_caida_igual_que_hoy(self):
        config = WhatsAppAgentConfig.get_solo()
        config.usar_jev_en_aprendizaje = True
        config.save()
        with mock.patch(CATALOGO, return_value='CATÁLOGO'), \
                mock.patch(DECIDIR, return_value=None), \
                mock.patch(CLASIFICAR, return_value=_redaccion()) as viejo:
            res = aprendizaje.procesar_pendientes(10)
        viejo.assert_called_once()
        self.assertEqual((res['procesados'], res['creadas']), (1, 1))
