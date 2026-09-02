"""Cada línea agendable del itinerario dice CUÁL servicio es, no solo su nombre.

Fase 1 del plan para cotizar a mano (Jorge, 01-09-2026). El motor de
alternativas (H-061) ya devuelve horas validadas contra la grilla, pero el
itinerario venía con el nombre del servicio y nada más. Para convertir una
alternativa en cotización hace falta el `servicio_id`: sin él, el cajón tendría
que buscar por texto, y ahí se cuela el error el día que existan dos tinas de
nombre parecido.

Ejecutar:
    python manage.py test whatsapp_agent.tests_alternativas_servicio_id
"""
from __future__ import annotations

from django.test import TestCase

from whatsapp_agent.alternativas import _linea


class LaLineaDelItinerario(TestCase):
    def test_lleva_el_id_cuando_el_motor_lo_conoce(self):
        linea = _linea({'servicio_id': 12, 'nombre': 'Tina Llaima'},
                       'Tina Llaima', '18:00')
        self.assertEqual(linea['servicio_id'], 12)
        self.assertEqual(linea['servicio'], 'Tina Llaima')
        self.assertEqual(linea['hora'], '18:00')

    def test_la_linea_informativa_no_inventa_un_id(self):
        # «Llegada y desayuno» no es un servicio que se agende: darle un id
        # falso haría que el cajón intentara cotizarlo.
        linea = _linea(None, 'Llegada y desayuno', '10:00')
        self.assertNotIn('servicio_id', linea)

    def test_el_id_sale_como_numero(self):
        # El motor a veces lo trae como texto; el cajón lo manda a la API tal
        # cual y allá se espera un entero.
        self.assertEqual(_linea({'servicio_id': '7'}, 'Masaje', '15:30')['servicio_id'], 7)

    def test_sin_id_en_el_origen_tampoco_inventa(self):
        self.assertNotIn('servicio_id', _linea({'nombre': 'X'}, 'X', '12:00'))

    def test_el_nombre_mostrado_puede_diferir_del_servicio(self):
        # El Refugio muestra «Tina X (noche 1)» pero agenda el servicio X.
        linea = _linea({'servicio_id': 4}, 'Tina Puyehue (noche 1)', '19:00')
        self.assertEqual(linea['servicio'], 'Tina Puyehue (noche 1)')
        self.assertEqual(linea['servicio_id'], 4)


class TodosLosConstructoresUsanLaMismaLinea(TestCase):
    """Guarda de fuente: si mañana alguien agrega un tipo de experiencia y arma
    el itinerario a mano, el cajón no podrá cotizarlo y no habrá error visible
    — simplemente faltará el id."""

    def test_ningun_itinerario_se_arma_con_diccionario_suelto(self):
        import os

        from django.conf import settings

        ruta = os.path.join(settings.BASE_DIR, 'whatsapp_agent', 'alternativas.py')
        cuerpo = open(ruta, encoding='utf-8').read()
        # La línea del itinerario se arma en UN solo lugar: dentro de _linea().
        # Si aparece un segundo sitio, alguien la escribió a mano y esa línea
        # saldrá sin servicio_id — sin error visible, solo un cajón que no
        # puede cotizar esa experiencia.
        self.assertEqual(cuerpo.count("{'servicio':"), 1,
                         'hay un itinerario armado a mano: usa _linea() para '
                         'que la línea lleve su servicio_id')
