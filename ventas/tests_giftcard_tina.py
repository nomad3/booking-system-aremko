"""«Tina para dos» entra a la vitrina de GiftCards (Jorge, 2026-08-04).

Contexto que conviene tener a mano al leer esto: en julio-2026 la decisión fue
la CONTRARIA — "solo se regalan experiencias, no tinas sueltas" — y se desactivó
todo lo que no fuera una de las 4 insignia. Jorge la revirtió a propósito.

El fondo de aquella decisión sigue en pie: no se regala un catálogo, se regalan
experiencias elegidas y con nombre. Lo que cambió es que la tina para dos ES una
experiencia con nombre propio, y a $60.000 es la puerta de entrada de quien
quiere regalar algo lindo sin gastar $210.000.

Ejecutar:
    python manage.py test ventas.tests_giftcard_tina
"""
from django.test import TestCase

from ventas.management.commands.cargar_experiencias_giftcard import INSIGNIAS


class TinaParaDosTest(TestCase):

    def _tina(self):
        return next(d for d in INSIGNIAS if d['id_experiencia'] == 'tina_para_dos')

    def test_la_tina_para_dos_existe_como_insignia(self):
        tina = self._tina()
        self.assertEqual(tina['nombre'], 'Tina para dos · junto al río')
        self.assertEqual(tina['monto_fijo'], 60000)

    def test_aparece_en_la_vitrina(self):
        """Sin esto la experiencia existe en la base pero NO se ve: la vitrina
        muestra solo las de IDS_INSIGNIA, no todas las activas."""
        import inspect
        from ventas.views import giftcard_views
        fuente = inspect.getsource(giftcard_views)
        self.assertIn("'tina_para_dos'", fuente)

    def test_la_vitrina_va_de_menor_a_mayor_precio(self):
        """El orden de IDS_INSIGNIA ES el orden en pantalla. Si alguien agrega
        una experiencia al final sin mirar el precio, la escalera se rompe."""
        import re
        import inspect
        from ventas.views import giftcard_views
        fuente = inspect.getsource(giftcard_views)
        bloque = fuente[fuente.index('IDS_INSIGNIA ='):]
        bloque = bloque[:bloque.index(']')]
        ids_en_pantalla = re.findall(r"'([a-z_]+)'", bloque)

        montos = {d['id_experiencia']: d['monto_fijo'] for d in INSIGNIAS}
        precios = [montos[i] for i in ids_en_pantalla if i in montos]
        self.assertEqual(precios, sorted(precios),
                         'la vitrina dejó de ir de menor a mayor precio')
        self.assertEqual(ids_en_pantalla[0], 'tina_para_dos')

    def test_sigue_siendo_la_UNICA_sin_masaje_ni_alojamiento(self):
        """Si alguien mete otra "suelta", que sea una decisión y no un descuido."""
        tina = self._tina()
        texto = (tina['descripcion'] + tina['descripcion_giftcard']).lower()
        self.assertNotIn('masaje', texto)
        self.assertNotIn('cabaña', texto)
        self.assertIn('tina caliente', texto)

    def test_todas_las_insignia_tienen_orden_unico(self):
        ordenes = [d['orden'] for d in INSIGNIAS]
        self.assertEqual(len(ordenes), len(set(ordenes)), 'hay órdenes repetidos')
