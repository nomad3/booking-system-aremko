"""H-088 — horarios de tina/masaje salen como UNA recomendación, no como lista.

Caso real (Jorge, 2026-08-01): "quiero una tina con ambientacion para 2 personas para
el proximo miercoles" → Luna respondió con DOS tinas en viñetas con asterisco, justo
lo que H-081 prohíbe.

Causa raíz: dos instrucciones "SIEMPRE" contradictorias.
  · La descripción de `consultar_disponibilidad` decía "úsala SIEMPRE para responder
    precio o disponibilidad".
  · La REGLA DURA H-081 decía "para horarios de tina/masaje llama SIEMPRE a
    `alternativas_experiencia`".
Ganó la primera: vive pegada a la decisión de llamar la función. Y como esa
herramienta devuelve TODAS las tinas con TODOS sus slots, la forma del dato ERA una
lista — el modelo solo la transcribió.

El arreglo se fuerza en CÓDIGO (misma lección que H-083/H-084): con fecha + tipo
tina/masaje, la herramienta devuelve la recomendación única. Si el dato no viene
como lista, no se puede listar.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_h088_una_opcion_tina
"""
from django.test import SimpleTestCase

from whatsapp_agent.agent import _TOOLS, ruta_una_recomendacion


class RutaUnaRecomendacionTest(SimpleTestCase):
    """La decisión pura: ¿esta consulta se responde con UNA opción o con el listado?"""

    def test_tina_con_fecha_va_a_una_recomendacion(self):
        # El caso real que falló.
        self.assertEqual(ruta_una_recomendacion('tina', 'el próximo miércoles'), 'tina_sola')

    def test_masaje_con_fecha_va_a_una_recomendacion(self):
        self.assertEqual(ruta_una_recomendacion('masaje', '2026-08-05'), 'masaje_solo')

    def test_sin_fecha_sigue_el_listado(self):
        # "¿cuánto vale una tina?" es pregunta de PRECIO: el listado es correcto.
        self.assertIsNone(ruta_una_recomendacion('tina', None))
        self.assertIsNone(ruta_una_recomendacion('tina', ''))
        self.assertIsNone(ruta_una_recomendacion('masaje', None))

    def test_cabanas_no_cambian(self):
        # Las cabañas tienen su propia regla anti-overbooking; no se tocan.
        self.assertIsNone(ruta_una_recomendacion('cabana', 'el sábado'))

    def test_sin_tipo_sigue_el_listado(self):
        # Sin tipo es el MENÚ (tinas + masajes + cabañas): ahí enumerar es legítimo.
        self.assertIsNone(ruta_una_recomendacion(None, 'el sábado'))
        self.assertIsNone(ruta_una_recomendacion('', 'el sábado'))

    def test_normaliza_mayusculas_y_espacios(self):
        for crudo in ('TINA', ' tina ', 'Tina'):
            self.assertEqual(ruta_una_recomendacion(crudo, 'mañana'), 'tina_sola', crudo)

    def test_tipo_desconocido_no_rompe(self):
        self.assertIsNone(ruta_una_recomendacion('helicoptero', 'mañana'))


class DescripcionDeLaToolTest(SimpleTestCase):
    """La contradicción que confundía al modelo tiene que estar muerta."""

    def _descripcion(self, nombre):
        for t in _TOOLS:
            f = t.get('function') or {}
            if f.get('name') == nombre:
                return f.get('description') or ''
        self.fail(f'tool {nombre} no encontrada')

    def test_ya_no_dice_usala_siempre_para_disponibilidad(self):
        desc = self._descripcion('consultar_disponibilidad')
        self.assertNotIn('SIEMPRE para responder precio o disponibilidad', desc)

    def test_declara_la_excepcion_de_tina_y_masaje(self):
        desc = self._descripcion('consultar_disponibilidad')
        self.assertIn('alternativas_experiencia', desc)
        self.assertIn('recomendada', desc)

    def test_la_otra_tool_sigue_pidiendo_una_sola(self):
        desc = self._descripcion('alternativas_experiencia')
        self.assertIn('recomendada', desc)
