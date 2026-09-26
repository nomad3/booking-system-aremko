"""Etapa 3 del encargo PROMPT_JEV_AREMKO.md: clasificar las correcciones con Jev.

Jev decide el tipo con su confianza; el texto lo redacta el camino de siempre y solo
cuando vale la pena. Lo que ya está en el Conocimiento, o repite una sugerencia anterior
(también las descartadas), no se propone de nuevo: en junio de 2026 el clasificador
propuso «enviar un link» 7 veces y se aprobaron reglas ya existentes.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_aprendizaje_jev
"""
from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from ventas.models import WhatsAppMessage

from whatsapp_agent import aprendizaje
from whatsapp_agent.decisiones import Respuesta
from whatsapp_agent.models import AgenteFeedback, SugerenciaAprendizaje, WhatsAppAgentConfig

DECIDIR = 'whatsapp_agent.decisiones.decidir'
CLASIFICAR = 'whatsapp_agent.aprendizaje.clasificar'
CATALOGO = 'whatsapp_agent.grounding.catalogo_vivo'
BORRADOR = 'La tina está disponible el lunes a las 14:00 por $60.000 para dos.'
ENVIADO = 'Los lunes no ofrecemos tinas después de las 19:30 porque cerramos a las 21:30.'
REGLA = 'Los lunes no se ofrecen tinas después de las 19:30.'


def _jev(que_hizo='avanzo_el_proceso', confianza=0.9, que_cambio='regla', generaliza=0.8,
         ya_esta=0.1):
    return Respuesta({'model': 'typesafe/jev-1.13', 'answers': {
        'que_hizo': {'type': 'choice', 'choice': que_hizo, 'confidence': confianza},
        'que_cambio': {'type': 'choice', 'choice': que_cambio, 'confidence': 0.8},
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

    def test_la_conversacion_llega_a_jev(self):
        with mock.patch(DECIDIR, return_value=_jev(que_hizo='otra_cosa')) as decidir:
            aprendizaje.clasificar_con_jev(self.config, BORRADOR, ENVIADO,
                                           contexto='[Cliente]: ¿hay tina el lunes a las 20?')
        self.assertEqual(decidir.call_args.args[0]['conversacion_hasta_la_pregunta'],
                         '[Cliente]: ¿hay tina el lunes a las 20?')

    def test_regla_que_vale_la_pena(self):
        d, decidir, redactar = self._clasificar(_jev())
        self.assertEqual((d['tipo'], d['texto_propuesto'], d['error']), ('regla', REGLA, ''))
        self.assertIn('typesafe/jev-1.13', d['modelo'])
        self.assertEqual(decidir.call_args.kwargs['referencia'], '7')
        estado = decidir.call_args.args[0]
        self.assertEqual((estado['borrador'], estado['enviado']), (BORRADOR, ENVIADO))
        self.assertIn('Check-in', estado['conocimiento'])
        redactar.assert_called_once()
        self.assertIn('paso siguiente', redactar.call_args.kwargs['pista'])
        self.assertTrue(d['motivo'].startswith('avanzo_el_proceso'))

    def test_sin_opinion_de_jev_va_el_clasificador_de_siempre(self):
        d, _, redactar = self._clasificar(None, redaccion=_redaccion())
        self.assertEqual(d, _redaccion())
        redactar.assert_called_once()

    def test_poca_confianza_no_se_marca_puntual_en_silencio(self):
        d, _, redactar = self._clasificar(_jev(confianza=0.55))
        self.assertIn('no concluyente', d['error'])
        redactar.assert_not_called()

    def test_otra_cosa_no_gasta_la_redaccion(self):
        d, _, redactar = self._clasificar(_jev(que_hizo='otra_cosa'))
        self.assertEqual((d['tipo'], d['error']), ('puntual', ''))
        redactar.assert_not_called()

    def test_otra_opcion_para_ese_cliente_no_es_catalogo(self):
        # Corrida en seco del 25-09: «Luna: Hornopiren 14:30 → Deborah: Llaima 16:30» salía
        # como hecho de catálogo con 0,97. Es una decisión para ese cliente.
        d, _, redactar = self._clasificar(_jev(que_hizo='otra_opcion_para_ese_cliente',
                                               que_cambio='hecho_catalogo'))
        self.assertEqual(d['tipo'], 'puntual')
        self.assertIn('otra_opcion_para_ese_cliente', d['motivo'])
        redactar.assert_not_called()

    def test_corrigio_un_precio_es_catalogo(self):
        d, _, redactar = self._clasificar(_jev(que_hizo='corrigio_dato', que_cambio='hecho_catalogo'))
        self.assertEqual(d['tipo'], 'hecho_catalogo')
        self.assertIn('catálogo', redactar.call_args.kwargs['pista'])

    def test_corrigio_otra_cosa_es_regla(self):
        d, _, redactar = self._clasificar(_jev(que_hizo='corrigio_dato', que_cambio='tono'))
        self.assertEqual(d['tipo'], 'regla')
        self.assertIn('regla GENERAL', redactar.call_args.kwargs['pista'])

    def test_sin_respuesta_a_que_hizo_no_concluye(self):
        sin = Respuesta({'model': 'x', 'answers': {'que_cambio': {'type': 'choice',
                                                                  'choice': 'regla',
                                                                  'confidence': 0.99}}})
        d, _, redactar = self._clasificar(sin)
        self.assertIn('no concluyente', d['error'])
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


class LaRedaccionTieneQueSerUnaRegla(TestCase):
    """Segunda corrida en seco del 25-09: el redactor copió una instrucción del prompt."""
    COPIADA = ('Si el cliente pregunta QUÉ INCLUYE o QUÉ CONTIENE una ambientación, responde con el '
               'detalle que acompaña a su nombre en esta lista, redactado natural y en PROSA (nunca '
               'como lista con viñetas ni asteriscos); si esa ambientación no trae detalle acá, dile '
               'con calidez que le confirmas los detalles con el equipo.')

    def setUp(self):
        self.config = WhatsAppAgentConfig.get_solo()
        parche = mock.patch(CATALOGO, return_value='CATÁLOGO')
        parche.start()
        self.addCleanup(parche.stop)

    def test_lo_copiado_del_prompt_no_se_propone(self):
        self.assertFalse(aprendizaje._parece_una_regla(self.COPIADA))
        with mock.patch(DECIDIR, return_value=_jev()), \
                mock.patch(CLASIFICAR, return_value=_redaccion(texto=self.COPIADA)):
            d = aprendizaje.clasificar_con_jev(self.config, BORRADOR, ENVIADO)
        self.assertIn('no parece una regla', d['error'])

    def test_una_regla_de_verdad_si(self):
        self.assertTrue(aprendizaje._parece_una_regla(
            'La tabla se agrega aparte: no está incluida en la experiencia romántica.'))
        self.assertFalse(aprendizaje._parece_una_regla('corta'))
        self.assertFalse(aprendizaje._parece_una_regla('Primera línea.\nSegunda línea larga aquí.'))


class SinRepetirEnLaMismaCorrida(TestCase):
    def test_la_segunda_igual_no_se_propone(self):
        for _ in range(2):
            AgenteFeedback.objects.create(phone='+56911112222', borrador=BORRADOR,
                                          enviado=ENVIADO, editado=True)
        with mock.patch(CATALOGO, return_value='CATÁLOGO'), \
                mock.patch(DECIDIR, return_value=_jev()), \
                mock.patch(CLASIFICAR, return_value=_redaccion()):
            res = aprendizaje.procesar_pendientes(10, en_seco=True, forzar_jev=True)
        self.assertEqual(res['creadas'], 1)
        self.assertEqual(res['detalle'][1]['tipo'], 'puntual')


class LaPistaDelRedactor(TestCase):
    def test_sin_pista_el_prompt_de_siempre(self):
        antes = aprendizaje.build_clasificador_user(BORRADOR, ENVIADO)
        self.assertEqual(antes, aprendizaje.build_clasificador_user(BORRADOR, ENVIADO, ''))
        self.assertNotIn('NOTA:', antes)
        self.assertIn('NOTA: una pista', aprendizaje.build_clasificador_user(BORRADOR, ENVIADO,
                                                                            'una pista'))


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


class ElContexto(TestCase):
    def _msg(self, wid, phone, direction, body, minutos_atras):
        return WhatsAppMessage.objects.create(
            wa_message_id=wid, phone=phone, direction=direction, body=body,
            timestamp=timezone.now() - timedelta(minutes=minutos_atras))

    def test_la_conversacion_hasta_la_pregunta(self):
        self._msg('w1', '+569111', 'in', 'hola', 30)
        self._msg('w2', '+569111', 'out', '¡Hola! ¿En qué te ayudo?', 29)
        self._msg('w3', '+569111', 'in', '¿hay tina el lunes a las 20?', 28)
        self._msg('w4', '+569111', 'out', 'Los lunes cerramos a las 21:30.', 27)   # después
        self._msg('w9', '+569999', 'in', 'otro cliente', 28.5)                      # otro teléfono, antes
        fb = AgenteFeedback.objects.create(phone='+569111', wa_message_id='w3',
                                           borrador=BORRADOR, enviado=ENVIADO, editado=True)
        self.assertEqual(aprendizaje.contexto_de_la_correccion(fb),
                         '[Cliente]: hola\n[Aremko]: ¡Hola! ¿En qué te ayudo?\n'
                         '[Cliente]: ¿hay tina el lunes a las 20?')

    def test_solo_los_ultimos_mensajes(self):
        for i in range(10):
            self._msg(f'm{i}', '+569111', 'in', f'mensaje {i}', 60 - i)
        fb = AgenteFeedback.objects.create(phone='+569111', wa_message_id='m9',
                                           borrador=BORRADOR, enviado=ENVIADO, editado=True)
        lineas = aprendizaje.contexto_de_la_correccion(fb, mensajes=3).splitlines()
        self.assertEqual(lineas, ['[Cliente]: mensaje 7', '[Cliente]: mensaje 8',
                                  '[Cliente]: mensaje 9'])

    def test_sin_mensaje_referenciado_usa_el_telefono(self):
        self._msg('x1', '+569111', 'in', '¿precio de la tina?', 5)
        fb = AgenteFeedback.objects.create(phone='+569111', wa_message_id='no-existe',
                                           borrador=BORRADOR, enviado=ENVIADO, editado=True)
        self.assertEqual(aprendizaje.contexto_de_la_correccion(fb), '[Cliente]: ¿precio de la tina?')

    def test_el_lote_le_pasa_el_contexto(self):
        self._msg('w3', '+569111', 'in', '¿hay tina el lunes a las 20?', 28)
        AgenteFeedback.objects.create(phone='+569111', wa_message_id='w3', borrador=BORRADOR,
                                      enviado=ENVIADO, editado=True)
        config = WhatsAppAgentConfig.get_solo()
        config.usar_jev_en_aprendizaje = True
        config.save()
        with mock.patch('whatsapp_agent.aprendizaje.clasificar_con_jev',
                        return_value=dict(_redaccion(), tipo='tono')) as jev:
            aprendizaje.procesar_pendientes(10)
        self.assertEqual(jev.call_args.kwargs['contexto'], '[Cliente]: ¿hay tina el lunes a las 20?')

