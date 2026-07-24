"""V-04 · Velada Sorpresa — 4 niveles × hidromasaje como GiftCardExperiencia +
elegidor (1 card que abre las opciones). Tests puros (sin DB)."""
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import reverse

from .management.commands.cargar_experiencias_giftcard import (
    VELADAS, VELADA_NIVELES, HIDRO_EXTRA, IMG_VELADA,
)
from .views.giftcard_views import (
    VELADA_NIVELES_CHOOSER, VELADA_HIDRO_EXTRA,
)

MONTOS_ESPERADOS = {
    'velada_simple': 82000,  'velada_simple_hidro': 92000,
    'velada_dulce': 98000,   'velada_dulce_hidro': 108000,
    'velada_flores': 118000, 'velada_flores_hidro': 128000,
    'velada_gran': 134000,   'velada_gran_hidro': 144000,
}


class VeladaNivelesCommandTest(SimpleTestCase):

    def test_son_ocho_niveles(self):
        self.assertEqual(len(VELADAS), 8)

    def test_ids_y_montos(self):
        got = {v['id_experiencia']: v['monto_fijo'] for v in VELADAS}
        self.assertEqual(got, MONTOS_ESPERADOS)

    def test_hidromasaje_suma_10000(self):
        by_id = {v['id_experiencia']: v['monto_fijo'] for v in VELADAS}
        for clave in ('simple', 'dulce', 'flores', 'gran'):
            self.assertEqual(
                by_id[f'velada_{clave}_hidro'] - by_id[f'velada_{clave}'], HIDRO_EXTRA)

    def test_todos_tienen_imagen_y_categoria(self):
        for v in VELADAS:
            self.assertEqual(v['imagen'], IMG_VELADA)
            self.assertEqual(v['categoria'], 'packs')
            self.assertTrue(v['descripcion_giftcard'])

    def test_ids_unicos(self):
        ids = [v['id_experiencia'] for v in VELADAS]
        self.assertEqual(len(ids), len(set(ids)))


class ChooserConsistenciaTest(SimpleTestCase):
    """El elegidor y el command DEBEN coincidir en claves y precios base, o el
    link `?exp=velada_<clave>` apuntaría a un nivel inexistente."""

    def test_claves_y_bases_coinciden(self):
        cmd = {n['clave']: n['monto'] for n in VELADA_NIVELES}
        chooser = {n['clave']: n['base'] for n in VELADA_NIVELES_CHOOSER}
        self.assertEqual(cmd, chooser)

    def test_hidro_extra_coincide(self):
        self.assertEqual(HIDRO_EXTRA, VELADA_HIDRO_EXTRA)


class ChooserRenderTest(SimpleTestCase):
    """Valida el template del elegidor + su contexto (sin request → sin context
    processors; en prod el view usa render(request,...) como todo el sitio)."""

    def test_template_renderiza(self):
        html = render_to_string('ventas/giftcard_velada.html', {
            'niveles': VELADA_NIVELES_CHOOSER,
            'hidro_extra': VELADA_HIDRO_EXTRA,
            'foto': 'https://x/img.jpg',
        })
        self.assertIn('Velada Sorpresa', html)
        # Los 4 niveles como valores de radio + el toggle hidromasaje.
        for clave in ('simple', 'dulce', 'flores', 'gran'):
            self.assertIn(f'value="{clave}"', html)
        self.assertIn('id="hidro"', html)
        # La base del wizard para armar el link en JS.
        self.assertIn(reverse('ventas:giftcard_wizard'), html)
