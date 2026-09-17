"""El inicio le dice a Google la misma hora de entrada y salida que el resto del sitio.

Jorge (17-09-2026): la página de inicio declaraba en sus datos estructurados
check-in 15:00 y check-out 12:00, mientras la pregunta frecuente de
alojamientos y las landings dicen 16:00 y 11:00. Un cliente que lo lee en
Google llega esperando salir a las 12.

Ejecutar:
    python manage.py test ventas.tests_horario_checkin_checkout
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.test import TestCase
from django.urls import reverse

RAIZ = Path(__file__).resolve().parent.parent


def _alojamiento_declarado(html: str) -> dict:
    """El bloque LodgingBusiness del JSON-LD de la página, ya parseado."""
    for bloque in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            datos = json.loads(bloque)
        except ValueError:
            continue
        nodos = datos.get('@graph', [datos]) if isinstance(datos, dict) else datos
        for nodo in nodos:
            if isinstance(nodo, dict) and nodo.get('@type') == 'LodgingBusiness':
                return nodo
    return {}


class ElInicioDiceLaHoraCorrecta(TestCase):
    def _horas(self, url):
        html = self.client.get(url).content.decode()
        nodo = _alojamiento_declarado(html)
        self.assertTrue(nodo, 'el inicio ya no declara el alojamiento en sus datos estructurados')
        return nodo.get('checkinTime'), nodo.get('checkoutTime')

    def test_inicio_boutique(self):
        self.assertEqual(self._horas(reverse('homepage')), ('16:00', '11:00'))

    def test_inicio_clasico(self):
        self.assertEqual(self._horas(reverse('homepage') + '?classic=1'), ('16:00', '11:00'))


class LaSemillaNoDevuelveLaHoraVieja(TestCase):
    def test_populate_seo_content_dice_16_y_11(self):
        # La semilla hace update_or_create: si alguien la corre de nuevo, PISA lo
        # que se editó en el admin. Que al menos pise con la hora correcta.
        texto = (RAIZ / 'populate_seo_content.py').read_text(encoding='utf-8')
        self.assertIn('Check-in desde las 16:00 hrs y check-out hasta las 11:00 hrs.', texto)
        self.assertNotIn('check-out hasta las 12:00', texto)
