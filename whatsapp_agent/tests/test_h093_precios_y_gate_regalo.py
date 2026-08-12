# -*- coding: utf-8 -*-
"""H-093 (2026-08-12). Dos cosas que Jorge encontró probando en vivo.

1. EL PRECIO QUE LUNA DICE vs EL QUE COBRA.
   Luna ofrecía «el Refugio desde $270.000» y la cotización llegaba en
   $290.000 — el precio real vive en `packs.REFUGIO_PRECIO_PLANO`, pero el
   guion del prompt tenía una copia escrita a mano que quedó vieja. Ya había
   pasado con un masaje ($40.000 dicho, $50.000 cobrado) y la advertencia
   estaba en el prompt; el número de al lado, no. Estos tests atan el texto a
   las constantes: si mañana se mueve un precio y no se mueve el guion, la
   suite avisa antes que un cliente.

2. EL GATE DE LOS DATOS DEL REGALO.
   Deborah reportó cotizaciones de gift card generadas sin pedir nunca el
   nombre de quien recibe ni la dedicatoria. La causa: `sin_datos_regalo` es
   un booleano que pone el propio modelo, y la regla de cuándo usarlo vivía en
   palabras. En los logs de producción el gate no rechazó NI UNA vez. Ahora se
   verifica contra la conversación real.
"""
import re

from django.test import SimpleTestCase

from whatsapp_agent import packs
from whatsapp_agent.agent import (_sin_datos_regalo_verificado,
                                  _ya_pregunto_por_el_regalo)


def _fuente_prompt():
    import whatsapp_agent.prompt as prompt_mod
    return open(prompt_mod.__file__, encoding='utf-8').read()


def _clp(n):
    return f'{n:,}'.replace(',', '.')


class PrecioDelGuionCalzaConElCobradoTest(SimpleTestCase):
    """El guion no puede prometer un precio que el cotizador no respeta."""

    def test_refugio_dice_el_precio_plano_real(self):
        precio = _clp(packs.REFUGIO_PRECIO_PLANO)
        fuente = _fuente_prompt()
        self.assertIn(f'${precio}', fuente,
                      f'El prompt no menciona el precio real del Refugio (${precio})')
        for mencion in re.findall(r'\*Refugio\*[^;]{0,80}', fuente):
            self.assertIn(precio, mencion,
                          f'Mención del Refugio con precio que no es ${precio}: {mencion!r}')

    def test_ritual_dice_su_precio_promocional(self):
        """El Ritual SÍ es «desde»: $210.000 dom-jue, $240.000 vie/sáb."""
        precio = _clp(packs.RITUAL_PRECIO_DOMJUE)
        for mencion in re.findall(r'\*Ritual del Río\*[^;]{0,90}', _fuente_prompt()):
            self.assertIn(precio, mencion,
                          f'Mención del Ritual con precio que no es ${precio}: {mencion!r}')

    def test_la_ficha_que_manda_luna_usa_el_mismo_precio(self):
        """`enviar_ficha_experiencia` mandaba «desde $270.000» por su lado."""
        resumen = packs._FICHAS_EXPERIENCIA['refugio']['resumen']
        self.assertIn(_clp(packs.REFUGIO_PRECIO_PLANO), resumen)

    def test_el_refugio_no_se_ofrece_como_desde(self):
        """Es precio PLANO todos los días: «desde» sugiere que hay uno menor."""
        for mencion in re.findall(r'\*Refugio\*[^;]{0,80}', _fuente_prompt()):
            self.assertNotIn('desde', mencion.lower(), f'«desde» de más: {mencion!r}')
        self.assertNotIn('desde', packs._FICHAS_EXPERIENCIA['refugio']['resumen'].lower())

    def test_la_landing_y_el_cotizador_no_se_contradicen(self):
        """La landing leía su precio de la BD y el cotizador de una constante.
        Que el default del modelo calce evita que un ambiente nuevo nazca
        torcido (en prod el valor ya está guardado)."""
        from ventas.models import RefugioConfig
        campo = RefugioConfig._meta.get_field('precio_clp')
        self.assertEqual(campo.default, packs.REFUGIO_PRECIO_PLANO)


class PrecioFormateadoTest(SimpleTestCase):
    """`intcomma` con locale 'es' escribe «290 000» con espacio duro — y ese
    espacio además rompía los links de WhatsApp donde se intercala el precio."""

    def test_formato_chileno_con_punto(self):
        from ventas.models import RefugioConfig
        self.assertEqual(RefugioConfig(precio_clp=290000).precio_fmt, '290.000')
        self.assertEqual(RefugioConfig(precio_clp=1250000).precio_fmt, '1.250.000')

    def test_la_landing_no_deja_precios_escritos_a_mano(self):
        import ventas
        import os
        ruta = os.path.join(os.path.dirname(ventas.__file__),
                            'templates', 'ventas', 'refugio_landing.html')
        html = open(ruta, encoding='utf-8').read()
        self.assertNotIn('270.000', html)
        self.assertNotIn('270000', html)


class GateDatosDelRegaloTest(SimpleTestCase):
    """El flag `sin_datos_regalo` vale solo si Luna preguntó de verdad."""

    HISTORIAL_PREGUNTO = (
        '[Cliente]: quiero regalar un masaje\n'
        '[Aremko]: ¡Qué lindo regalo! ¿A nombre de quién va la gift card?\n'
        '[Cliente]: no importa, mándala sin nombre\n'
    )
    HISTORIAL_NO_PREGUNTO = (
        '[Cliente]: quiero regalar un masaje para dos\n'
        '[Aremko]: Perfecto, el Masaje para Dos vale $80.000. ¿Te la preparo?\n'
        '[Cliente]: sí\n'
    )

    def test_reconoce_que_pregunto_por_el_destinatario(self):
        self.assertTrue(_ya_pregunto_por_el_regalo(self.HISTORIAL_PREGUNTO))

    def test_reconoce_la_pregunta_por_la_dedicatoria(self):
        self.assertTrue(_ya_pregunto_por_el_regalo(
            '[Aremko]: ¿Quieres dejar una dedicatoria corta?\n'))

    def test_sin_acentos_tambien_cuenta(self):
        """Luna escribe con y sin tildes según el turno."""
        self.assertTrue(_ya_pregunto_por_el_regalo(
            '[Aremko]: a nombre de quien la dejamos?\n'))

    def test_no_se_deja_enganar_por_lo_que_dice_el_cliente(self):
        """Si el que nombra la dedicatoria es el CLIENTE, Luna no preguntó."""
        self.assertFalse(_ya_pregunto_por_el_regalo(
            '[Cliente]: quiero una dedicatoria bonita\n'
            '[Aremko]: ¡Perfecto! Te preparo la cotización.\n'))

    def test_el_caso_de_deborah_el_flag_se_ignora(self):
        """Luna declara sin_datos_regalo=true sin haber preguntado nunca."""
        self.assertFalse(_sin_datos_regalo_verificado(
            {'sin_datos_regalo': True}, self.HISTORIAL_NO_PREGUNTO))

    def test_si_pregunto_el_flag_se_respeta(self):
        """Al cliente que de verdad no quiso personalizar no se le insiste."""
        self.assertTrue(_sin_datos_regalo_verificado(
            {'sin_datos_regalo': True}, self.HISTORIAL_PREGUNTO))

    def test_sin_flag_nunca_pasa(self):
        self.assertFalse(_sin_datos_regalo_verificado({}, self.HISTORIAL_PREGUNTO))
        self.assertFalse(_sin_datos_regalo_verificado(
            {'sin_datos_regalo': False}, self.HISTORIAL_PREGUNTO))

    def test_historial_vacio_no_es_permiso(self):
        self.assertFalse(_sin_datos_regalo_verificado({'sin_datos_regalo': True}, ''))
        self.assertFalse(_sin_datos_regalo_verificado({'sin_datos_regalo': True}, None))
