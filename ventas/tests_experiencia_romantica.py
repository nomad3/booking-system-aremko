"""
Tests del configurador de Experiencia Romántica (Fase 1, Puerta B).

Cubre la lógica pura de mapeo (ocasión + color → SKU real), que es lo más
delicado: debe elegir el SKU correcto y NUNCA confundir la Caja de chocolates
—que vive en la misma categoría Ambientaciones— con una decoración.

No toca la BD (SimpleTestCase con objetos simulados), inmune al drift AR-034.

Ejecutar:
    python manage.py test ventas.tests_experiencia_romantica
"""
from __future__ import annotations

from django.test import SimpleTestCase

from ventas.views.experiencia_romantica_view import resolver_ambientacion, _norm


class _FakeServicio:
    def __init__(self, nombre):
        self.nombre = nombre


CATALOGO = [
    _FakeServicio('Decoración Simple · Azul'),
    _FakeServicio('Decoración Simple · Rosado'),
    _FakeServicio('Decoración Cumpleaños con Torta · Azul'),
    _FakeServicio('Decoración Cumpleaños con Torta · Rosado'),
    _FakeServicio('Caja de chocolates'),
]


class ResolverAmbientacionTest(SimpleTestCase):

    def _nombre(self, ocasion, color):
        s = resolver_ambientacion(ocasion, color, CATALOGO)
        return s.nombre if s else None

    def test_mapea_los_cuatro_skus(self):
        self.assertEqual(self._nombre('romantica', 'rosado'), 'Decoración Simple · Rosado')
        self.assertEqual(self._nombre('romantica', 'azul'), 'Decoración Simple · Azul')
        self.assertEqual(self._nombre('cumpleanos', 'azul'), 'Decoración Cumpleaños con Torta · Azul')
        self.assertEqual(self._nombre('cumpleanos', 'rosado'), 'Decoración Cumpleaños con Torta · Rosado')

    def test_chocolates_nunca_es_ambientacion(self):
        # En ningún caso el resolver debe devolver la Caja de chocolates.
        for ocasion in ('romantica', 'cumpleanos'):
            for color in ('azul', 'rosado', '', 'otro'):
                s = resolver_ambientacion(ocasion, color, CATALOGO)
                if s is not None:
                    self.assertNotIn('chocolate', _norm(s.nombre))

    def test_fallback_por_ocasion_si_falta_color(self):
        # Catálogo sin la variante de color pedida → cae al mismo ocasión igual.
        catalogo = [_FakeServicio('Decoración Simple · Rosado')]
        s = resolver_ambientacion('romantica', 'azul', catalogo)
        self.assertEqual(s.nombre, 'Decoración Simple · Rosado')

    def test_sin_catalogo_devuelve_none(self):
        self.assertIsNone(resolver_ambientacion('romantica', 'rosado', []))
