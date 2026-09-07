"""El alojamiento NO incluye tina. La web no puede decir que sí.

Jorge (07-09-2026): «ahí aparece que el alojamiento incluye tinas, lo que es
falso; el mismo cliente ahora se quiere aprovechar de lo que dice la página».

Venía del mismo cliente de la reserva 6777. Una promesa falsa en la web no es
un error de redacción: es algo que un cliente puede exigir, y con razón.

Estaba dicho en TRES lugares, no en uno:
  · el beneficio «Desayuno Incluido» de la categoría Cabañas, que vive en la
    base de datos (SEOContent) y decía «acceso por dos horas a la tina»
  · category_detail_boutique.html y category_detail.html, con una frase peor:
    «Las cabañas Aremko incluyen tina caliente privada»

Sacar una y dejar las otras habría dejado al cliente apuntando a la siguiente.

Ejecutar:
    python manage.py test ventas.tests_alojamiento_sin_tina
"""
from __future__ import annotations

import re
from pathlib import Path

from django.test import TestCase

PLANTILLAS = [
    'ventas/templates/ventas/category_detail_boutique.html',
    'ventas/templates/ventas/category_detail.html',
]

# Formas de decir «el alojamiento trae tina» que no deben volver al sitio.
PROMESAS_FALSAS = [
    r'cabañas?\s+\w*\s*incluyen?\s+tina',
    r'alojamiento\s+incluye\s+tina',
    r'acceso\s+por\s+dos\s+horas\s+a\s+la\s+tina',
    r'tina\s+incluida',
    r'con\s+tina\s+incluida',
]


class LaWebNoPrometeTinaConElAlojamiento(TestCase):
    def _texto(self, ruta):
        return Path(ruta).read_text(encoding='utf-8').lower()

    def test_ninguna_plantilla_dice_que_la_cabana_incluye_tina(self):
        for ruta in PLANTILLAS:
            texto = self._texto(ruta)
            for patron in PROMESAS_FALSAS:
                hallado = re.search(patron, texto)
                self.assertIsNone(
                    hallado,
                    f'{ruta} volvió a prometer tina con el alojamiento: '
                    f'«{hallado.group(0) if hallado else ""}»')

    def test_los_comentarios_no_se_ven_en_la_pagina(self):
        # En Django {# #} comenta UNA línea. Un comentario de varias con esa
        # sintaxis se renderiza como texto: quedó visible en producción hasta
        # que se miró la página de verdad (07-09-2026).
        for ruta in PLANTILLAS:
            texto = Path(ruta).read_text(encoding='utf-8')
            for bloque in re.findall(r'\{#(.*?)#\}', texto, re.S):
                self.assertNotIn(
                    '\n', bloque,
                    f'{ruta}: comentario multilínea con llave-numeral. '
                    'Django solo comenta una línea así — usa comment/endcomment.')

    def test_la_pagina_sigue_ofreciendo_la_tina_como_agregado(self):
        # No se trata de esconder la tina —es lo que más se vende— sino de
        # decir que se suma aparte.
        texto = self._texto(PLANTILLAS[0])
        self.assertIn('suma una tina caliente', texto)
        self.assertIn('se reserva aparte', texto)


class ElBeneficioGuardadoTampocoLoPromete(TestCase):
    """El texto de la tarjeta vive en la base, no en la plantilla: si alguien
    lo reescribe en el admin, esta prueba lo caza igual."""

    def test_el_beneficio_de_cabanas_no_menciona_la_tina(self):
        from ventas.models import CategoriaServicio, SEOContent

        cat = CategoriaServicio.objects.create(nombre='Cabañas')
        seo = SEOContent.objects.create(
            categoria=cat,
            beneficio_1_titulo='Desayuno Incluido',
            beneficio_1_descripcion='Desayuno sureño con productos locales, '
                                    'servido en tu cabaña. Amenities de lujo.')
        for b in seo.get_beneficios():
            self.assertNotIn(
                'tina', (b.get('descripcion') or '').lower(),
                f'el beneficio «{b.get("titulo")}» promete tina y no corresponde')
