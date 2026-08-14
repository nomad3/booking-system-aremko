# -*- coding: utf-8 -*-
"""Noche de Aguas Calientes: cada cabaña con cada tina (Jorge, 2026-08-14).

«Buscando disponibilidad de Noche de Aguas Calientes para el 22 de agosto solo
le da dos opciones al cliente. ¿Por qué no ofrece entre las opciones tina de
hidromasaje que hay disponible también para ese día en horarios cercanos?»

Eran DOS topes apilados: `elegir_tina_mas_tarde` se quedaba con UNA tina —la
Tronador de 22:00 le ganaba por media hora a la Hidromasaje de 21:30— y esa
misma se repetía en todas las cabañas; encima había un corte a 2 opciones.
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from whatsapp_agent import alternativas, packs


def _serv(nombre, precio, slots):
    return {'nombre': nombre, 'precio_total': precio, 'slots_libres': slots}


# El caso real del 22 de agosto: 2 cabañas, 2 tinas (una de ellas hidromasaje).
CABANAS = [_serv('Cabaña Arrayán', 110000, ['16:00']),
           _serv('Cabaña Tepa', 110000, ['16:00'])]
TINAS = [_serv('Tina Tronador', 50000, ['20:00', '22:00']),
         _serv('Tina Hidromasaje Villarrica', 60000, ['19:00', '21:30'])]


def _disponibilidad(f, personas, tipo, limite=None):
    return {'servicios': CABANAS if tipo == 'cabana' else TINAS}


class CadaCabanaConCadaTinaTest(SimpleTestCase):

    def _alternativas(self):
        with patch('whatsapp_agent.availability.disponibilidad', _disponibilidad), \
             patch('whatsapp_agent.packs._descuento_pack_cabana', return_value=0):
            return packs.disponibilidad_pack_cabana_tina(
                '2026-08-22', personas=2, todas=True)['alternativas']

    def test_el_22_pasa_de_2_a_4_opciones(self):
        self.assertEqual(len(self._alternativas()), 4)

    def test_la_hidromasaje_aparece_entre_las_opciones(self):
        """El reclamo textual de Jorge."""
        nombres = {a['tina']['nombre'] for a in self._alternativas()}
        self.assertIn('Tina Hidromasaje Villarrica', nombres)
        self.assertIn('Tina Tronador', nombres)

    def test_la_mas_tarde_va_primero(self):
        """La regla de siempre pasa de filtro a criterio de orden."""
        horas = [a['tina']['hora'] for a in self._alternativas()]
        self.assertEqual(horas, ['22:00', '22:00', '21:30', '21:30'])

    def test_cada_tina_aporta_su_horario_mas_tarde(self):
        """De los dos slots de cada tina se usa el último, no todos."""
        for a in self._alternativas():
            if a['tina']['nombre'] == 'Tina Tronador':
                self.assertEqual(a['tina']['hora'], '22:00')
            else:
                self.assertEqual(a['tina']['hora'], '21:30')

    def test_el_precio_suma_la_tina_que_corresponde(self):
        """La hidromasaje cuesta $10.000 más y eso tiene que verse."""
        por_tina = {a['tina']['nombre']: a['precio_total']
                    for a in self._alternativas()}
        self.assertEqual(por_tina['Tina Tronador'], 160000)
        self.assertEqual(por_tina['Tina Hidromasaje Villarrica'], 170000)

    def test_sin_todas_el_comportamiento_viejo_no_cambia(self):
        """La landing, la tool de Luna y el ruteo de packs siguen igual."""
        with patch('whatsapp_agent.availability.disponibilidad', _disponibilidad), \
             patch('whatsapp_agent.packs._descuento_pack_cabana', return_value=0):
            res = packs.disponibilidad_pack_cabana_tina('2026-08-22', personas=2)
        self.assertNotIn('alternativas', res)
        self.assertEqual(len(res['opciones']), 2)
        self.assertEqual(res['tina_mas_tarde'], '22:00')


class TopeDeSeisTest(SimpleTestCase):
    """Con 3 cabañas y 3 tinas serían 9 combinaciones; se muestran 6."""

    def test_el_picker_topea_en_6(self):
        cabanas = [_serv(f'Cabaña {i}', 110000, ['16:00']) for i in range(3)]
        tinas = [_serv(f'Tina {i}', 50000, [f'2{i}:00']) for i in range(3)]

        def _disp(f, personas, tipo, limite=None):
            return {'servicios': cabanas if tipo == 'cabana' else tinas}

        with patch('whatsapp_agent.availability.disponibilidad', _disp), \
             patch('whatsapp_agent.packs._descuento_pack_cabana', return_value=0):
            res = alternativas.construir_alternativas(
                'noche_aguas_calientes', '2026-08-22', 2)
        self.assertEqual(len(res['alternativas']), 6)


class SinTinaNoSeCaeTest(SimpleTestCase):
    """Si no hay ninguna tina >= 16:00, la cabaña sola sigue ofreciéndose."""

    def test_sin_tinas_no_hay_alternativas_pero_si_opciones(self):
        def _disp(f, personas, tipo, limite=None):
            return {'servicios': CABANAS if tipo == 'cabana' else []}

        with patch('whatsapp_agent.availability.disponibilidad', _disp), \
             patch('whatsapp_agent.packs._descuento_pack_cabana', return_value=0):
            res = packs.disponibilidad_pack_cabana_tina(
                '2026-08-22', personas=2, todas=True)
        self.assertEqual(res['alternativas'], [])
        self.assertEqual(len(res['opciones']), 2)
        self.assertIn('no hay tina disponible', res['nota'])
