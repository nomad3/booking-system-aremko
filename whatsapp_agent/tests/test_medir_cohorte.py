"""Etapa 0 del encargo PROMPT_JEV_AREMKO.md: medir la cohorte antes de clasificar.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_medir_cohorte
"""
from __future__ import annotations

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from whatsapp_agent.management.commands.medir_cohorte_aprendizaje import grupo_de_la_correccion
from whatsapp_agent.models import AgenteFeedback

SUSTANTIVO = ('La tina con hidromasaje está disponible a las 14:00 por $60.000 para dos.',
              'Para esa fecha no quedan tinas, pero sí cabañas con desayuno desde el viernes.')


class LosGrupos(TestCase):
    def test_uno_por_criterio(self):
        self.assertEqual(grupo_de_la_correccion('', 'algo'), 'vacio')
        self.assertEqual(grupo_de_la_correccion('A las 14:00 hay una.', 'ya, te llamo'), 'corto')
        self.assertEqual(grupo_de_la_correccion(
            'A las 14:00 hay una tina, $50.000.',
            'Hola! Te confirmo la de las 14:00, sale $50.000 para los dos, ¿te sirve?'),
            'retoque_cifra')
        self.assertEqual(grupo_de_la_correccion(
            'Tenemos la tina clásica disponible el lunes por la tarde para dos personas.',
            'Tenemos la tina clásica disponible el lunes en la tarde para 2 personas.'),
            'retoque_parecido')
        self.assertEqual(grupo_de_la_correccion(*SUSTANTIVO), 'sustantivo')


class ElComando(TestCase):
    def _fb(self, borrador, enviado, editado=True, procesado=False, dias_atras=0):
        fb = AgenteFeedback.objects.create(phone='+56911112222', borrador=borrador,
                                           enviado=enviado, editado=editado, procesado=procesado)
        if dias_atras:
            AgenteFeedback.objects.filter(pk=fb.pk).update(
                created_at=timezone.now() - timedelta(days=dias_atras))
        return fb

    def _correr(self, **opts):
        out = StringIO()
        call_command('medir_cohorte_aprendizaje', stdout=out, **opts)
        return out.getvalue()

    def test_reparte_y_cuenta_la_cohorte(self):
        self._fb('Hola', 'Hola', editado=False)                   # sin tocar
        self._fb('A las 14:00 hay una.', 'ya, te llamo')          # corto
        self._fb(*SUSTANTIVO)                                     # cohorte
        self._fb(*SUSTANTIVO, procesado=True)                     # sustantivo ya procesado
        self._fb(*SUSTANTIVO, dias_atras=40)                      # fuera de 30 días
        salida = self._correr()
        self.assertIn('4 borradores · 3 editados', salida)
        self.assertIn('sin tocar    1', salida)
        self.assertIn('cortos < 40: 1 · sustantivos: 2', salida)
        self.assertIn('Cohorte a clasificar (sustantivos sin procesar): 1', salida)

    def test_la_ventana_se_elige(self):
        self._fb(*SUSTANTIVO)
        self._fb(*SUSTANTIVO, dias_atras=40)
        self.assertIn('sin procesar): 2', self._correr(dias=90))

    def test_no_escribe_nada(self):
        fb = self._fb(*SUSTANTIVO)
        self._correr()
        fb.refresh_from_db()
        self.assertFalse(fb.procesado)
