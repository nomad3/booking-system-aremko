"""«Tina para dos» entra a la vitrina de GiftCards (Jorge, 2026-08-04).

Contexto que conviene tener a mano al leer esto: en julio-2026 la decisión fue
la CONTRARIA — "solo se regalan experiencias, no tinas sueltas" — y se desactivó
todo lo que no fuera una de las 4 insignia. Jorge la revirtió a propósito.

El fondo de aquella decisión sigue en pie: no se regala un catálogo, se regalan
experiencias elegidas y con nombre. Lo que cambió es que la tina para dos ES una
experiencia con nombre propio, y a $50.000 es la puerta de entrada de quien
quiere regalar algo lindo sin gastar $210.000.

Ejecutar:
    python manage.py test ventas.tests_giftcard_tina
"""
from django.test import TestCase

from ventas.management.commands.cargar_experiencias_giftcard import INSIGNIAS


class TinaParaDosTest(TestCase):
    """Precio PLANO: $50.000 para dos, cualquier tina y cualquier día."""

    def _tina(self):
        return next(d for d in INSIGNIAS if d['id_experiencia'] == 'tina_para_dos')

    def test_la_tina_para_dos_existe_como_insignia(self):
        tina = self._tina()
        self.assertEqual(tina['nombre'], 'Tina para dos · junto al río')
        self.assertEqual(tina['monto_fijo'], 50000)

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

    def test_el_precio_es_PLANO_y_no_sigue_la_tarifa_del_catalogo(self):
        """Decisión de Jorge (2026-08-04): $50.000 para dos, cualquier tina y
        cualquier día — a propósito MÁS BARATA que comprarla suelta (una tina
        para dos ronda los $60.000), porque el trabajo de esta GiftCard es que
        alguien regale Aremko por primera vez.

        Si mañana suben las tinas, este monto no se mueve solo: hay que
        decidirlo. El test está para que el cambio sea deliberado.
        """
        self.assertEqual(self._tina()['monto_fijo'], 50000)

    def test_la_descripcion_NO_ata_la_giftcard_a_una_tina_ni_a_un_dia(self):
        """Si el texto nombrara una tina concreta o un día, recepción tendría que
        pelear en el mesón con un cliente que leyó otra cosa."""
        tina = self._tina()
        texto = (tina['descripcion'] + ' ' + tina['descripcion_giftcard']).lower()
        self.assertIn('cualquier', texto)
        for atadura in ('hidromasaje', 'dom-jue', 'lunes a jueves', 'fin de semana'):
            self.assertNotIn(atadura, texto, atadura)
