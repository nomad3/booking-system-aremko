"""Etapa 1 del encargo PROMPT_JEV_AREMKO.md: qué corrección de Deborah enseña algo.

`es_desacuerdo_sustantivo` es pura y decide qué se clasifica (y qué puede terminar
tocando el Conocimiento), así que se prueba criterio por criterio.

Van en SimpleTestCase y no como funciones sueltas en test_logic.py (como pedía el
encargo) porque `manage.py test` no ejecuta funciones sueltas: las 47 de ese archivo
no corren nunca.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_desacuerdo_sustantivo
"""
from __future__ import annotations

from django.test import SimpleTestCase

from whatsapp_agent.aprendizaje import _normalizado, es_desacuerdo_sustantivo

BORRADOR = 'La tina con hidromasaje está disponible a las 14:00 por $60.000 para dos personas.'
OTRA_COSA = 'Para esa fecha no quedan tinas, pero sí cabañas con desayuno desde el viernes.'


class LosCincoCriterios(SimpleTestCase):
    def test_1_los_dos_textos_con_algo(self):
        self.assertFalse(es_desacuerdo_sustantivo('', OTRA_COSA))
        self.assertFalse(es_desacuerdo_sustantivo(BORRADOR, '   '))
        self.assertFalse(es_desacuerdo_sustantivo(None, None))

    def test_2_lo_enviado_corto_no_enseña(self):
        self.assertFalse(es_desacuerdo_sustantivo(BORRADOR, 'ya, te llamo al tiro'))

    def test_3_si_repite_la_hora_o_el_precio_luna_acerto(self):
        self.assertFalse(es_desacuerdo_sustantivo(
            BORRADOR, 'Hola! Te la dejo a las 14:00, son $60.000 los dos, ¿te parece bien?'))
        self.assertFalse(es_desacuerdo_sustantivo(
            BORRADOR, 'Te confirmo: sale $ 60.000 para los dos, con hidromasaje y todo.'))

    def test_4_si_se_parece_es_un_retoque(self):
        self.assertFalse(es_desacuerdo_sustantivo(
            'Tenemos la tina clásica disponible el lunes por la tarde para dos personas.',
            'Tenemos la tina clásica disponible el lunes en la tarde para 2 personas.'))

    def test_5_lo_demas_es_un_desacuerdo_sustantivo(self):
        self.assertTrue(es_desacuerdo_sustantivo(BORRADOR, OTRA_COSA))

    def test_un_precio_corregido_si_enseña(self):
        # Deborah cambió el precio: no repite la cifra de Luna → puede ser un hecho de catálogo.
        self.assertTrue(es_desacuerdo_sustantivo(
            BORRADOR, 'Ojo que esa tina ahora vale $70.000 para dos, y queda a las 16:30 horas.'))


class LasTildes(SimpleTestCase):
    def test_se_comparan_sin_tildes(self):
        self.assertEqual(_normalizado('  Está   CLÁSICA\n'), 'esta clasica')
        self.assertFalse(es_desacuerdo_sustantivo(
            'Está disponible la tina clásica el lunes para dos personas, ¿te acomoda?',
            'Esta disponible la tina clasica el lunes para dos personas, ¿te acomoda?'))


class LasPlantillasNoSonCorrecciones(SimpleTestCase):
    """Segunda corrida en seco del 25-09: 9 de 12 propuestas eran el link de la cotización o
    del Pase que Deborah manda con un botón. En 30 días, 123 de 594 (21%)."""

    def test_el_link_de_la_cotizacion(self):
        self.assertFalse(es_desacuerdo_sustantivo(
            '¡Perfecto! Te preparo la cotización (total $140,000) y te la enviamos en un momento.',
            'Hola 🌿 Te preparamos la cotización de tu experiencia en Aremko. Revísala con calma y, '
            'si todo está bien, tócala para aprobarla: https://www.aremko.cl/ventas/propuesta/abc123/'))

    def test_el_link_del_pase(self):
        self.assertFalse(es_desacuerdo_sustantivo(
            'Perfecto, me alegra saber que todo está listo con el pago.',
            'Hola, acá está tu Pase para Aremko 🔑 https://www.aremko.cl/ventas/reserva/NjkwNQ:1x/ '
            'Adentro está el QR que muestras al llegar'))

    def test_otro_link_si_puede_enseñar(self):
        self.assertTrue(es_desacuerdo_sustantivo(
            BORRADOR, 'Para llegar usa este mapa https://maps.app.goo.gl/abc y pregunta en recepción.'))

