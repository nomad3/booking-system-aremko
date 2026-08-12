# -*- coding: utf-8 -*-
"""Chequeos de higiene sobre TODAS las plantillas del proyecto.

Nacieron de un error real: el 2026-08-10 un comentario `{# … #}` de tres
líneas se imprimió tal cual en la página de pago del Pase, a la vista del
cliente. Django solo trata `{# … #}` como comentario cuando abre y cierra en
la MISMA línea; en varias líneas es texto.
"""
import os
import re
from pathlib import Path

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


class GiftCardsNuncaSeLlamanCartaTest(SimpleTestCase):
    """Jorge (2026-08-12): «en un párrafo habla de carta. Debe hablar siempre
    de Gift Cards».

    El producto se llama Gift Card en la web, en el admin y en el email. Que
    en un mensaje se llame «carta» hace dudar de si es otra cosa. Adentro del
    código «carta» sigue valiendo como sinónimo —lee bien en los comentarios—;
    lo que no puede pasar es que salga a la pantalla del cliente.
    """

    # Textos que el cliente lee, o que Luna lee y tiende a repetir.
    FUENTES = (
        'whatsapp_agent/giftcards.py',
        'whatsapp_agent/prompt.py',
    )
    # `carta` seguida de algo que la delata como el producto.
    PATRON = re.compile(
        r"['\"][^'\"]*\b(?:la|una|esa|tu|cada|dos|las)\s+cartas?\b[^'\"]*['\"]",
        re.IGNORECASE)

    def test_ningun_texto_visible_dice_carta(self):
        raiz = Path(__file__).resolve().parent.parent
        problemas = []
        for relativa in self.FUENTES:
            ruta = raiz / relativa
            for n, linea in enumerate(ruta.read_text(encoding='utf-8').splitlines(), 1):
                sin_comentario = linea.split('#')[0]
                if self.PATRON.search(sin_comentario):
                    problemas.append(f'{relativa}:{n}: {linea.strip()[:90]}')
        self.assertFalse(
            problemas,
            'Texto visible que dice «carta» en vez de «gift card»:\n' + '\n'.join(problemas))
