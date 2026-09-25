"""Etapa 4 del encargo PROMPT_JEV_AREMKO.md: la corrida en seco que Jorge lee.

`procesar_aprendizaje --solo-sustantivos --dias 30 --en-seco --jev` clasifica las
correcciones que enseñan algo, las más recientes primero, e imprime qué decidiría: sin
crear sugerencias ni marcar nada. Sin opciones, todo sigue igual que antes (el botón).

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_corrida_en_seco
"""
from __future__ import annotations

from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from whatsapp_agent import aprendizaje
from whatsapp_agent.models import AgenteFeedback, SugerenciaAprendizaje

JEV = 'whatsapp_agent.aprendizaje.clasificar_con_jev'
VIEJO = 'whatsapp_agent.aprendizaje.clasificar'
SUSTANTIVO = ('La tina con hidromasaje está disponible a las 14:00 por $60.000 para dos.',
              'Para esa fecha no quedan tinas, pero sí cabañas con desayuno desde el viernes.')
CORTO = ('A las 14:00 hay una.', 'ya, te llamo')


def _regla(*_, **__):
    return {'tipo': 'regla', 'texto_propuesto': 'Ofrecer cabaña si no quedan tinas.',
            'ref_catalogo': '', 'motivo': 'política', 'modelo': 'jev', 'error': '',
            'confianza': 0.91}


class LaCorridaEnSeco(TestCase):
    def _fb(self, textos, dias_atras=0):
        fb = AgenteFeedback.objects.create(phone='+56911112222', borrador=textos[0],
                                           enviado=textos[1], editado=True)
        if dias_atras:
            AgenteFeedback.objects.filter(pk=fb.pk).update(
                created_at=timezone.now() - timedelta(days=dias_atras))
        return fb

    def test_no_escribe_nada(self):
        fb = self._fb(SUSTANTIVO)
        with mock.patch(JEV, side_effect=_regla):
            res = aprendizaje.procesar_pendientes(10, solo_sustantivos=True, en_seco=True,
                                                  forzar_jev=True)
        self.assertEqual(res['creadas'], 1)
        self.assertEqual(SugerenciaAprendizaje.objects.count(), 0)
        fb.refresh_from_db()
        self.assertFalse(fb.procesado)
        fila = res['detalle'][0]
        self.assertEqual((fila['borrador'], fila['confianza']), (SUSTANTIVO[0], 0.91))

    def test_solo_sustantivos_los_mas_recientes_primero(self):
        viejo = self._fb(SUSTANTIVO, dias_atras=3)
        self._fb(CORTO)
        nuevo = self._fb(SUSTANTIVO, dias_atras=1)
        with mock.patch(JEV, side_effect=_regla) as jev:
            res = aprendizaje.procesar_pendientes(10, solo_sustantivos=True, en_seco=True,
                                                  forzar_jev=True)
        self.assertEqual([f['feedback_id'] for f in res['detalle']], [nuevo.id, viejo.id])
        self.assertEqual(jev.call_count, 2)

    def test_la_ventana_y_el_limite(self):
        self._fb(SUSTANTIVO, dias_atras=40)
        recientes = [self._fb(SUSTANTIVO, dias_atras=d) for d in (1, 2, 3)]
        with mock.patch(JEV, side_effect=_regla):
            en_la_ventana = aprendizaje.procesar_pendientes(10, solo_sustantivos=True,
                                                            en_seco=True, dias=30, forzar_jev=True)
            con_limite = aprendizaje.procesar_pendientes(2, solo_sustantivos=True, en_seco=True,
                                                         dias=30, forzar_jev=True)
        self.assertEqual([f['feedback_id'] for f in en_la_ventana['detalle']],
                         [r.id for r in recientes])
        self.assertEqual([f['feedback_id'] for f in con_limite['detalle']],
                         [recientes[0].id, recientes[1].id])

    def test_jev_forzado_con_el_interruptor_apagado(self):
        self._fb(SUSTANTIVO)
        with mock.patch(JEV, side_effect=_regla) as jev, mock.patch(VIEJO) as viejo:
            aprendizaje.procesar_pendientes(10, en_seco=True, forzar_jev=True)
        jev.assert_called_once()
        viejo.assert_not_called()

    def test_sin_opciones_todo_igual_que_antes(self):
        corto = self._fb(CORTO, dias_atras=2)      # el botón no filtra y va del más antiguo
        self._fb(SUSTANTIVO, dias_atras=1)
        with mock.patch(VIEJO, return_value=dict(_regla(), tipo='tono')) as viejo:
            res = aprendizaje.procesar_pendientes(10)
        self.assertEqual(res['detalle'][0]['feedback_id'], corto.id)
        self.assertEqual(viejo.call_count, 2)
        self.assertEqual(AgenteFeedback.objects.filter(procesado=True).count(), 2)

    def test_el_comando_imprime_la_ficha(self):
        self._fb(SUSTANTIVO)
        no_concluyente = dict(_regla(), error='no concluyente: regla con confianza 0.41',
                              confianza=0.41)
        self._fb(SUSTANTIVO, dias_atras=1)
        out = StringIO()
        with mock.patch(JEV, side_effect=[_regla(), no_concluyente]):
            call_command('procesar_aprendizaje', solo_sustantivos=True, en_seco=True, jev=True,
                         dias=30, limite=50, stdout=out)
        salida = out.getvalue()
        self.assertIn('PROPONDRÍA REGLA · confianza 0.91', salida)
        self.assertIn('«Ofrecer cabaña si no quedan tinas.»', salida)
        self.assertIn('NO CONCLUYENTE · confianza 0.41', salida)
        self.assertIn('Deborah: Para esa fecha no quedan tinas', salida)
        self.assertIn('EN SECO (nada se guardó) · 2 correcciones', salida)
        self.assertEqual(SugerenciaAprendizaje.objects.count(), 0)
