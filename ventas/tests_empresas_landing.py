"""La página de empresas dice lo mismo que el brochure de venta.

Jorge (06-09-2026): la página publicada decía "12 capacidad máxima" cuando la
sala recibe 18, ofrecía tres propuestas parecidas sin ningún precio, y
declaraba un horario (9:00-13:00) distinto al del programa. Cristián no puede
mostrar un brochure que contradiga la propia web de Aremko.

Se dejaron DOS programas —"menos opciones venden más"— con precio visible,
que es lo que faltaba para que quien decide pueda llevarlo a su jefe.

Estas pruebas fijan los números que tienen que coincidir entre la web, el
brochure y la realidad del lugar. Si alguien cambia uno solo, avisan.

Ejecutar:
    python manage.py test ventas.tests_empresas_landing
"""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse


class LaPaginaDeEmpresas(TestCase):
    def setUp(self):
        self.html = self.client.get(reverse('empresas')).content.decode()


class LosNumerosQueDebenCoincidir(LaPaginaDeEmpresas):
    def test_la_capacidad_es_18(self):
        # La sala recibe 18 y las tinas reciben justo 18: Osorno (6),
        # Calbuco (4) y las cuatro hidromasaje (8).
        self.assertIn('18', self.html)
        self.assertNotIn('hasta 12 personas', self.html)

    def test_la_bajada_no_arrastra_la_frase_vieja(self):
        # Al reemplazar el texto quedó "…elevar la productividad, Una mañana
        # completa…": dos frases pegadas, visible en producción.
        self.assertNotIn('elevar la productividad', self.html)

    def test_el_horario_es_de_930_a_14(self):
        # 9:30 y no 9:00: desde Puerto Montt son 60 km, y a las 9:00 el grupo
        # tendría que salir a las 8:00 (Jorge, 07-09-2026).
        self.assertIn('9:30 a 14:00', self.html)
        self.assertNotIn('9:00-13:00', self.html)

    def test_ofrece_coordinar_el_transporte(self):
        # Dieciocho personas en bus llegan juntas, y nadie maneja de vuelta
        # después de las tinas.
        self.assertIn('transporte', self.html)


class LosDosProgramas(LaPaginaDeEmpresas):
    def test_ofrece_la_manana_aremko(self):
        self.assertIn('La Mañana Aremko', self.html)

    def test_ofrece_deshielo(self):
        self.assertIn('Deshielo', self.html)

    def test_ya_no_ofrece_las_tres_antiguas(self):
        # Eran tres propuestas parecidas y sin precio: quien entraba tenía que
        # elegir entre ellas sin saber cuánto costaba ninguna.
        self.assertNotIn('Experiencia Ejecutiva Completa', self.html)
        self.assertNotIn('Desayuno &amp; Wellness', self.html)
        self.assertNotIn('Tres Propuestas', self.html)


class LosPreciosSeVen(LaPaginaDeEmpresas):
    """Lo que más faltaba. Sin precio, quien lee no puede llevarlo a su jefe:
    dice "mándame más información" y ahí se muere la venta.

    Los precios salieron de un cálculo corregido: las tinas se cobran POR
    PERSONA, no por tina. Una mañana para 18 vale $910.000 a precio de lista
    ($50.555 por cabeza), así que vender a $45.000 era vender bajo lista sin
    saberlo. Jorge eligió el punto medio: $50.000 y $60.000."""

    def test_muestra_el_precio_de_la_manana(self):
        self.assertIn('$50.000', self.html)

    def test_muestra_el_precio_de_deshielo(self):
        self.assertIn('$60.000', self.html)

    def test_dice_que_el_precio_es_por_persona(self):
        self.assertIn('por persona', self.html)


class ElFormularioSigueLosProgramas(LaPaginaDeEmpresas):
    def test_las_opciones_son_las_de_hoy(self):
        self.assertIn('manana_aremko', self.html)
        self.assertIn('deshielo', self.html)

    def test_ofrece_tambien_giftcards_y_convenio(self):
        # Son las otras dos cosas que una empresa compra, y no estaban.
        self.assertIn('giftcards', self.html)
        self.assertIn('convenio', self.html)

    def test_ya_no_ofrece_las_opciones_antiguas(self):
        self.assertNotIn('experiencia_completa', self.html)
        self.assertNotIn('solo_tinas', self.html)
