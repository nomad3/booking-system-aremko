"""
Tests del configurador de Experiencia Romántica (Fase 1, Puerta B).

Cubre la lógica pura del mapeo de ambientaciones (taxonomía confirmada con
Jorge/Deborah, jul-2026) y la regla de espacio de las tinas de cumpleaños:

  · ROMÁNTICAS — sin color, cualquier tina. R1 (id 22) base; R2 (id 23) + ramo.
  · CUMPLEAÑOS — color (azul/rosado) + con/sin torta; solo tinas Hornopirén/
    Osorno/Llaima. Sin torta: 24 azul / 66 rosado. Con torta: 25 azul / 65 rosado.

No toca la BD (SimpleTestCase), inmune al drift AR-034.

Ejecutar:
    python manage.py test ventas.tests_experiencia_romantica
"""
from __future__ import annotations

from django.test import SimpleTestCase

from ventas.views.experiencia_romantica_view import (
    resolver_ambientacion_id, tina_admite_cumple, tina_admite_grupo,
    es_ocasion_grupo, _norm, ROMANTICA_IDS, CUMPLE_IDS,
)


class ResolverAmbientacionTest(SimpleTestCase):

    def test_romantica_nivel_r1_r2(self):
        self.assertEqual(resolver_ambientacion_id('romantica', nivel='r1'), 22)
        self.assertEqual(resolver_ambientacion_id('romantica', nivel='r2'), 23)

    def test_romantica_default_es_r1(self):
        # Sin nivel explícito, la romántica cae a R1 (la base).
        self.assertEqual(resolver_ambientacion_id('romantica'), 22)

    def test_romantica_ignora_color_y_torta(self):
        # Las románticas no tienen color: pasar color/torta no cambia el SKU.
        self.assertEqual(
            resolver_ambientacion_id('romantica', nivel='r2', color='azul', torta='con_torta'), 23)

    def test_cumple_matriz_completa(self):
        self.assertEqual(resolver_ambientacion_id('cumpleanos', torta='sin_torta', color='azul'), 24)
        self.assertEqual(resolver_ambientacion_id('cumpleanos', torta='sin_torta', color='rosado'), 66)
        self.assertEqual(resolver_ambientacion_id('cumpleanos', torta='con_torta', color='azul'), 25)
        self.assertEqual(resolver_ambientacion_id('cumpleanos', torta='con_torta', color='rosado'), 65)

    def test_cumple_default_sin_torta_rosado(self):
        self.assertEqual(resolver_ambientacion_id('cumpleanos'), 66)

    def test_grupo_reusa_ambientacion_de_cumpleanos(self):
        # El grupo (V-13) es una celebración tipo cumpleaños: mismo color+torta.
        self.assertEqual(resolver_ambientacion_id('grupo', torta='sin_torta', color='azul'), 24)
        self.assertEqual(resolver_ambientacion_id('grupo', torta='sin_torta', color='rosado'), 66)
        self.assertEqual(resolver_ambientacion_id('grupo', torta='con_torta', color='azul'), 25)
        self.assertEqual(resolver_ambientacion_id('grupo', torta='con_torta', color='rosado'), 65)

    def test_grupo_default_sin_torta_rosado(self):
        self.assertEqual(resolver_ambientacion_id('grupo'), 66)

    def test_despedida_reusa_ambientacion_de_cumpleanos(self):
        # V-14: la despedida usa el mismo modo grupo → ambientación de cumpleaños.
        self.assertEqual(resolver_ambientacion_id('despedida', torta='con_torta', color='rosado'), 65)
        self.assertEqual(resolver_ambientacion_id('despedida'), 66)

    def test_es_ocasion_grupo(self):
        self.assertTrue(es_ocasion_grupo('grupo'))
        self.assertTrue(es_ocasion_grupo('despedida'))
        for oc in ('romantica', 'cumpleanos', 'x', ''):
            self.assertFalse(es_ocasion_grupo(oc), oc)

    def test_ocasion_desconocida_devuelve_none(self):
        self.assertIsNone(resolver_ambientacion_id('otra_cosa'))
        self.assertIsNone(resolver_ambientacion_id(''))

    def test_ids_no_se_solapan(self):
        # Ningún ID de romántica coincide con uno de cumpleaños (SKUs distintos).
        romanticas = set(ROMANTICA_IDS.values())
        cumples = set(CUMPLE_IDS.values())
        self.assertEqual(romanticas & cumples, set())


class TinaAdmiteCumpleTest(SimpleTestCase):

    def test_tinas_permitidas(self):
        for nombre in ('Tina Hornopirén', 'Tina Osorno', 'Tina Llaima',
                       'hornopiren', 'OSORNO', 'Tina  Llaima  (grupal)'):
            self.assertTrue(tina_admite_cumple(nombre), nombre)

    def test_tinas_no_permitidas(self):
        for nombre in ('Tina Tronador', 'Tina Puntiagudo', 'Tina Puyehue',
                       'Tina Villarrica', 'Tina Calbuco'):
            self.assertFalse(tina_admite_cumple(nombre), nombre)

    def test_norm_quita_acentos(self):
        self.assertEqual(_norm('Hornopirén'), 'hornopiren')


class TinaAdmiteGrupoTest(SimpleTestCase):
    """Modo grupo (V-13): solo Calbuco y Osorno son tinas grupales."""

    def test_tinas_grupales(self):
        for nombre in ('Tina Calbuco', 'CALBUCO', 'Tina Osorno', 'osorno', 'Tina Calbuco (grupo)'):
            self.assertTrue(tina_admite_grupo(nombre), nombre)

    def test_tinas_no_grupales(self):
        for nombre in ('Tina Hornopirén', 'Tina Llaima', 'Tina Tronador', 'Tina Puyehue'):
            self.assertFalse(tina_admite_grupo(nombre), nombre)
