"""H-090 — el cambio de ambientación lo ejecuta el CÓDIGO, y nadie afirma lo que no hizo.

Caso real (Jorge, 2026-08-01, probando H-089): Luna ofreció perfecto cambiar la R1
por la R2. Jorge dijo "claro". Luna respondió "La Ambientación romántica R2 ha sido
agregada a tu carrito"… y el carrito seguía con la R1, $92.000.

Los logs fueron concluyentes: tras el "claro" **no se llamó NINGUNA herramienta**.
El modelo narró la acción en vez de ejecutarla.

Por qué: la instrucción con el índice y las tools viajaba en el RESULTADO de la tool
del turno anterior. En el turno del "claro" el modelo ya no la tiene —solo ve el
historial de texto— y tuvo que deducir qué hacer. Pedirle que recuerde y encadene
dos llamadas era pedirle justo lo que este agente hace mal (ver H-085).

Dos guardias, los dos en código:
  1. `acepto_el_cambio` + `aplicar_upgrade_si_acepto`: el código hace el cambio y
     el código redacta la confirmación.
  2. `afirma_mutacion_sin_tool`: si un texto dice que algo se agregó/cambió y
     ninguna tool tocó el carrito, no sale sin que un humano lo vea.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_h090_cambio_en_codigo
"""
from django.test import SimpleTestCase

from whatsapp_agent.agent import acepto_el_cambio, instruccion_sin_reservas
from whatsapp_agent.escalation import afirma_mutacion_sin_tool

R2_NOMBRE = 'Ambientación romántica R2'
OFERTA = ('[Aremko]: El ramo de flores ya viene incluido en la Ambientación romántica R2, '
          'que tiene un valor de $68.000. Si te gustaría, podemos cambiar tu Ambientación '
          'romántica R1 por esta opción superior. ¿Te parece bien?')


class AceptoElCambioTest(SimpleTestCase):
    """Exige DOS señales: el cliente asiente Y Luna ofreció ese cambio."""

    def test_el_caso_real_claro_despues_de_la_oferta(self):
        self.assertTrue(acepto_el_cambio('claro', OFERTA, R2_NOMBRE))

    def test_otros_asentimientos_tambien_valen(self):
        for txt in ('si', 'sí', 'dale', 'ok', 'ya', 'perfecto'):
            self.assertTrue(acepto_el_cambio(txt, OFERTA, R2_NOMBRE), txt)

    def test_sin_oferta_previa_no_cambia_nada(self):
        # "claro" a cualquier otra cosa NO autoriza a tocar el carrito.
        historial = '[Aremko]: ¿Te gustaría agregar un masaje?'
        self.assertFalse(acepto_el_cambio('claro', historial, R2_NOMBRE))

    def test_oferta_de_otra_cosa_no_dispara(self):
        # Menciona "cambiar" pero no la ambientación destino.
        historial = '[Aremko]: ¿Quieres cambiar la tina por otra?'
        self.assertFalse(acepto_el_cambio('claro', historial, R2_NOMBRE))

    def test_negacion_no_es_asentimiento(self):
        for txt in ('no', 'no gracias', 'mejor no'):
            self.assertFalse(acepto_el_cambio(txt, OFERTA, R2_NOMBRE), txt)

    def test_mensaje_con_datos_nuevos_no_es_asentimiento_puro(self):
        # "sí, pero para 3" trae información nueva: que decida el modelo, no el atajo.
        self.assertFalse(acepto_el_cambio('si pero para 3 personas', OFERTA, R2_NOMBRE))

    def test_historial_vacio_o_sin_destino(self):
        self.assertFalse(acepto_el_cambio('claro', '', R2_NOMBRE))
        self.assertFalse(acepto_el_cambio('claro', OFERTA, ''))

    def test_solo_mira_el_ULTIMO_mensaje_de_luna(self):
        # La oferta quedó atrás y después Luna preguntó otra cosa: ya no aplica.
        historial = OFERTA + '\n[Cliente]: espera\n[Aremko]: ¿Te ayudo con algo más?'
        self.assertFalse(acepto_el_cambio('claro', historial, R2_NOMBRE))


class AfirmaMutacionSinToolTest(SimpleTestCase):
    """La red de seguridad: no afirmar cambios que nadie hizo."""

    TEXTO_REAL = ('¡Excelente! La Ambientación romántica R2 ha sido agregada a tu carrito. '
                  '¿Te gustaría sumar algo más?')

    def test_el_texto_real_del_bug_se_caza(self):
        self.assertTrue(afirma_mutacion_sin_tool(self.TEXTO_REAL, []))

    def test_no_dispara_si_una_tool_si_agrego(self):
        tools = [{'name': 'agregar_servicio_carrito', 'result': {'success': True}}]
        self.assertFalse(afirma_mutacion_sin_tool(self.TEXTO_REAL, tools))

    def test_una_tool_que_FALLO_no_justifica_la_afirmacion(self):
        tools = [{'name': 'agregar_servicio_carrito',
                  'result': {'success': False, 'error': 'requiere_confirmacion'}}]
        self.assertTrue(afirma_mutacion_sin_tool(self.TEXTO_REAL, tools))

    def test_una_tool_que_no_muta_tampoco_justifica(self):
        tools = [{'name': 'consultar_disponibilidad', 'result': {'servicios': []}}]
        self.assertTrue(afirma_mutacion_sin_tool(self.TEXTO_REAL, tools))

    def test_varias_formas_de_afirmar(self):
        for txt in ('La R2 ha sido agregada a tu carrito.',
                    'Ya quedó agregada tu ambientación.',
                    'Agregué la tina a tu reserva.',
                    'Cambié tu ambientación por la R2.',
                    'Quité el masaje del carrito.'):
            self.assertTrue(afirma_mutacion_sin_tool(txt, []), txt)

    def test_no_dispara_con_texto_que_solo_ofrece(self):
        # Ofrecer, cotizar o preguntar NO es afirmar que se hizo algo.
        for txt in ('¿Te gustaría agregarla a tu reserva?',
                    'Te puedo ofrecer la Ambientación R1 por $32.000.',
                    'La tina Llaima está disponible a las 16:30.',
                    '¿Quieres que la agregue?'):
            self.assertFalse(afirma_mutacion_sin_tool(txt, []), txt)

    def test_la_tilde_decide_hice_vs_haria(self):
        """El falso positivo que cazó este mismo test al escribirlo.

        "agregue" (subjuntivo) y "agregué" (pasado) solo se distinguen por la
        tilde. Sin exigirla, la red escalaba "¿quieres que la agregue?", una de
        las frases más comunes de Luna — habría sido ruido constante para Deborah.
        """
        self.assertFalse(afirma_mutacion_sin_tool('¿Quieres que la agregue?', []))
        self.assertFalse(afirma_mutacion_sin_tool('Puedo agregarla si quieres.', []))
        self.assertTrue(afirma_mutacion_sin_tool('Ya la agregué a tu carrito.', []))

    def test_texto_vacio_no_rompe(self):
        self.assertFalse(afirma_mutacion_sin_tool('', []))
        self.assertFalse(afirma_mutacion_sin_tool(None, None))


class InstruccionSinReservasTest(SimpleTestCase):
    """H-091: 'no tienes reservas' no es un callejón si hay algo armándose.

    Caso real (Jorge, 2026-08-01): con una COTIZACIÓN en curso aceptó una
    ambientación y Luna escaló "no se encontró la reserva para agregar la
    ambientación". `buscar_reservas_cliente` devolvía `reservas: []` a secas, y el
    modelo leyó ese vacío como que no había nada que hacer — cuando la salida
    existía: sumarlo a la cotización con las tools del carrito.
    """

    def test_con_cotizacion_manda_al_carrito_y_prohibe_escalar(self):
        txt = instruccion_sin_reservas(hay_cotizacion=True, hay_carrito=False)
        self.assertIn('cotización en curso', txt)
        self.assertIn('agregar_servicio_carrito', txt)
        self.assertIn('NO escales', txt)

    def test_con_carrito_tambien_da_salida(self):
        txt = instruccion_sin_reservas(hay_cotizacion=False, hay_carrito=True)
        self.assertIn('carrito', txt)
        self.assertIn('NO escales', txt)

    def test_la_cotizacion_manda_sobre_el_carrito(self):
        txt = instruccion_sin_reservas(hay_cotizacion=True, hay_carrito=True)
        self.assertIn('cotización en curso', txt)

    def test_sin_nada_ofrece_empezar_de_cero(self):
        txt = instruccion_sin_reservas(hay_cotizacion=False, hay_carrito=False)
        self.assertIn('no tiene reservas creadas ni nada armado', txt)
        self.assertNotIn('NO escales', txt)
