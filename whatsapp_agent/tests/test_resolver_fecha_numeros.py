"""Fechas escritas con números en el resolvedor de Luna (25-09-2026).

Hallazgo al verificar las olitas: `resolver_fecha('2026-09-26')` devolvía
2027-09-09. Sin nombre de día, el resolvedor tomaba el PRIMER número de 1 o 2
cifras como día del mes ACTUAL: de «2026-09-26» tomaba el 09 (ya pasado → el
año siguiente), y de «26/10» el 26 de septiembre. La herramienta de horarios
de Luna invita al modelo a mandar AAAA-MM-DD, y el cliente escribe «26/10».

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_resolver_fecha_numeros
"""
from __future__ import annotations

from datetime import datetime
from unittest import mock

from django.test import SimpleTestCase

from whatsapp_agent.availability import _fecha_numerica, resolver_fecha

HOY = datetime(2026, 9, 25, 10, 0, 0)   # viernes


class FechasConNumeros(SimpleTestCase):
    def setUp(self):
        for objetivo in ('django.utils.timezone.now', 'django.utils.timezone.localtime'):
            parche = mock.patch(objetivo, return_value=HOY)
            parche.start()
            self.addCleanup(parche.stop)

    def _iso(self, texto):
        r = resolver_fecha(texto)
        self.assertFalse(r.get('ambiguo'), (texto, r))
        return r['fecha_iso']

    def test_aaaa_mm_dd(self):
        self.assertEqual(self._iso('2026-09-26'), '2026-09-26')     # antes: 2027-09-09
        self.assertEqual(self._iso('2026-10-01'), '2026-10-01')     # antes: 2027-09-10
        self.assertEqual(self._iso('2026/10/01'), '2026-10-01')
        self.assertEqual(resolver_fecha('2026-10-01')['dia_semana'], 'jueves')

    def test_dd_mm_aaaa(self):
        self.assertEqual(self._iso('26/10/2026'), '2026-10-26')
        self.assertEqual(self._iso('26-10-2026'), '2026-10-26')
        self.assertEqual(self._iso('26/10/26'), '2026-10-26')

    def test_dd_mm_sin_ano(self):
        self.assertEqual(self._iso('26/10'), '2026-10-26')          # antes: 26 de septiembre
        self.assertEqual(self._iso('el 1/10'), '2026-10-01')
        self.assertEqual(self._iso('5/1'), '2027-01-05')            # ya pasó este año

    def test_la_hora_no_se_confunde_con_la_fecha(self):
        self.assertEqual(self._iso('el 26/10 a las 18:00'), '2026-10-26')

    def test_dia_de_la_semana_que_calza(self):
        self.assertEqual(self._iso('sábado 26/09'), '2026-09-26')

    def test_dia_de_la_semana_que_no_calza_se_pregunta(self):
        r = resolver_fecha('domingo 26/09')
        self.assertTrue(r['ambiguo'])
        self.assertIn('es sábado, no domingo', r['error'])

    def test_una_fecha_que_no_existe(self):
        r = resolver_fecha('31/02')
        self.assertTrue(r['ambiguo'])
        self.assertIn('fecha inválida', r['error'])

    def test_un_rango_de_personas_no_es_una_fecha(self):
        # «2-3» sin año no se lee como 2 de marzo: sigue el camino de siempre.
        self.assertIsNone(_fecha_numerica('somos 2-3', HOY.date()))
        self.assertEqual(self._iso('somos 2-3 el sábado'), '2026-09-26')

    def test_lo_de_siempre_sigue_igual(self):
        self.assertEqual(self._iso('el sábado'), '2026-09-26')
        self.assertEqual(self._iso('mañana'), '2026-09-26')
        self.assertEqual(self._iso('sábado 3'), '2026-10-03')
        self.assertEqual(self._iso('26 de octubre'), '2026-10-26')
        self.assertEqual(self._iso('el 30'), '2026-09-30')

    # 26-09-2026 (P-62): «el 3» y «03-10» daban el 3-9-2027 —el número suelto saltaba un
    # año en vez de un mes— y un grupo recibió una cotización para el año siguiente.

    def test_el_numero_suelto_es_el_proximo_con_ese_numero(self):
        self.assertEqual(self._iso('el 3'), '2026-10-03')          # antes: 2027-09-03
        self.assertEqual(self._iso('3'), '2026-10-03')
        self.assertEqual(self._iso('para el 3'), '2026-10-03')
        self.assertEqual(self._iso('el 31'), '2026-10-31')         # septiembre no tiene 31

    def test_con_el_mes_nombrado_manda_el_mes(self):
        self.assertEqual(self._iso('3 de septiembre'), '2027-09-03')

    def test_dd_mm_con_guion(self):
        self.assertEqual(self._iso('03-10'), '2026-10-03')         # antes: 2027-09-03
        self.assertEqual(self._iso('el 03-10'), '2026-10-03')
        self.assertEqual(self._iso('3-11'), '2026-11-03')          # antes: el 3 de octubre
        self.assertEqual(self._iso('sábado 03-10'), '2026-10-03')
        self.assertEqual(self._iso('5-1'), '2027-01-05')           # ya pasó este año

    def test_un_rango_con_guion_no_es_fecha(self):
        for texto in ('somos 2-3', '2-3 personas', 'entre 2-3', 'para 4-5', '2-3 noches'):
            self.assertIsNone(_fecha_numerica(texto, HOY.date()), texto)
        self.assertEqual(self._iso('el 2-3 de octubre'), '2026-10-02')
