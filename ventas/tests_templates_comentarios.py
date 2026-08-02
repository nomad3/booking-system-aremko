"""Ningún comentario `{# #}` puede abrirse en una línea y cerrarse en otra.

En Django `{# ... #}` es de UNA SOLA LÍNEA. Si abarca varias, el motor NO lo
trata como comentario: **lo imprime tal cual en la página**.

Caso real (Jorge, 2026-08-02): el checkout de la agenda salió a producción con
mis comentarios de diseño visibles en pantalla, dentro de cada tarjeta de
cliente. Al escanear el repo aparecieron 4 más, preexistentes — uno en el wizard
de GiftCards, que ve el cliente final.

Para comentarios de varias líneas va `{% comment %}…{% endcomment %}`.

Ejecutar:
    python manage.py test ventas.tests_templates_comentarios
"""
import io
import pathlib

from django.conf import settings
from django.test import SimpleTestCase

IGNORAR = ('node_modules', '/staticfiles/', '/.git/')


def _comentarios_multilinea():
    """(archivo, línea, texto) de cada `{#` que no cierra en su misma línea."""
    raiz = pathlib.Path(settings.BASE_DIR)
    hallazgos = []
    for ruta in raiz.rglob('*.html'):
        s = str(ruta)
        if any(x in s for x in IGNORAR):
            continue
        try:
            lineas = io.open(ruta, encoding='utf-8').read().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for i, linea in enumerate(lineas, 1):
            if '{#' in linea and '#}' not in linea[linea.index('{#'):]:
                hallazgos.append((ruta.relative_to(raiz), i, linea.strip()[:80]))
    return hallazgos


class ComentariosDeTemplateTest(SimpleTestCase):

    def test_no_hay_comentarios_almohadilla_multilinea(self):
        hallazgos = _comentarios_multilinea()
        if hallazgos:
            detalle = '\n'.join(f'  {f}:{n}  →  {t}' for f, n, t in hallazgos)
            self.fail(
                f'{len(hallazgos)} comentario(s) {{# #}} abren en una línea y cierran en '
                f'otra: Django los IMPRIME en la página. Usa {{% comment %}}…'
                f'{{% endcomment %}} para varias líneas.\n{detalle}')

    def test_el_detector_reconoce_el_patron_malo(self):
        """Que el test anterior pase porque está limpio, no porque no mire nada."""
        linea_mala = '    {# esto abre y no cierra acá'
        self.assertTrue('{#' in linea_mala
                        and '#}' not in linea_mala[linea_mala.index('{#'):])
        linea_buena = '    {# esto abre y cierra en la misma línea #}'
        self.assertFalse('#}' not in linea_buena[linea_buena.index('{#'):])
