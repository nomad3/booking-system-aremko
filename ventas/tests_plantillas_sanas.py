# -*- coding: utf-8 -*-
"""Chequeos de higiene sobre TODAS las plantillas del proyecto.

Nacieron de un error real: el 2026-08-10 un comentario `{# … #}` de tres
líneas se imprimió tal cual en la página de pago del Pase, a la vista del
cliente. Django solo trata `{# … #}` como comentario cuando abre y cierra en
la MISMA línea; en varias líneas es texto.
"""
import os
import re

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = settings.BASE_DIR
IGNORAR = ('/.git', 'node_modules', '/venv', 'staticfiles', '/site-packages')


def plantillas():
    for raiz, _, archivos in os.walk(RAIZ):
        if any(p in raiz for p in IGNORAR):
            continue
        for nombre in archivos:
            if nombre.endswith('.html'):
                yield os.path.join(raiz, nombre)


class ComentariosDePlantillaTest(SimpleTestCase):

    def test_ningun_comentario_corto_queda_abierto(self):
        """`{#` tiene que cerrar en su propia línea. Si no, se imprime."""
        abiertos = []
        for ruta in plantillas():
            with open(ruta, encoding='utf-8', errors='ignore') as f:
                for n, linea in enumerate(f, 1):
                    for m in re.finditer(r'\{#', linea):
                        if '#}' not in linea[m.end():]:
                            rel = os.path.relpath(ruta, RAIZ)
                            abiertos.append(f'{rel}:{n} → {linea.strip()[:70]}')
        self.assertEqual(
            abiertos, [],
            'Comentario {# … #} sin cerrar en su línea: Django lo imprime como '
            'texto. Usar {% comment %}…{% endcomment %} para varias líneas.\n'
            + '\n'.join(abiertos))

    def test_el_detector_reconoce_el_caso_que_fallo(self):
        """Sin esto, un detector roto pasaría el test anterior en silencio."""
        malo = '{# comentario que sigue\n   en la línea de abajo #}\n'
        primera = malo.splitlines()[0]
        self.assertTrue(re.search(r'\{#', primera))
        self.assertNotIn('#}', primera)

        bueno = '{# comentario de una línea #}'
        m = re.search(r'\{#', bueno)
        self.assertIn('#}', bueno[m.end():])
