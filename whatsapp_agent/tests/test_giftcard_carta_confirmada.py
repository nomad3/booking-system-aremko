# -*- coding: utf-8 -*-
"""La carta que se vende también tiene que haberla pedido el cliente (H-099).

Caso real, 2026-08-15. Bárbara quería regalar «tina para dos + una tabla de
quesos» = $80.000. Luna cotizó **Masaje para Dos**, la única carta del catálogo
que vale exactamente $80.000, y la clienta recibió un link para aprobar el
regalo equivocado. El id era válido, así que ningún control saltó.

Lo que faltaba: el pedido no cabía en una sola carta —lleva un producto— y el
modelo, en vez de decir que no podía, buscó una carta que cuadrara con el monto.
El camino correcto ya existía (cotizar la tina y sumarle el producto, que viaja
DENTRO del regalo, ver test_giftcards_agregados).

Mismo principio que H-094 con el destinatario: un dato que el modelo puede
fabricar no es un dato del cliente.
"""
from django.test import TestCase

from whatsapp_agent.giftcards import preparar_giftcard

from .test_giftcards_luna import CLIENTE, _experiencia

# Lo que escribió la clienta: habla de TINA y de una tabla. Nunca dice «masaje».
HISTORIAL = ('[Cliente]: quiero regalar una gift card de tina para dos con una tabla de quesos\n'
             '[Aremko]: ¿A nombre de quién va?\n'
             '[Cliente]: para Paulo y Monse\n'
             '[Aremko]: ¿Quieres dejarles una frase?\n'
             '[Cliente]: pongan que los quiero mucho\n'
             '[Aremko]: Te enviamos la gift card a maria@prueba.cl — ¿está bien?\n'
             '[Cliente]: sí\n'
             '[Aremko]: La compra queda a nombre de María Prueba, ¿está bien así?\n'
             '[Cliente]: sí\n')

CONFIRMACION_MASAJE = '¿Confirmas que es la Gift Card Masaje para Dos ($80.000)?'


class CartaConfirmadaPorElClienteTests(TestCase):
    """El catálogo se arma parecido al real: varias cartas comparten «dos» y
    «velada», que es justo lo que hace que esas palabras no elijan nada."""

    @classmethod
    def setUpTestData(cls):
        _experiencia('tina_para_dos', 'Tina para dos · junto al río', 50000)
        _experiencia('masaje_pareja', 'Masaje para Dos', 80000)
        _experiencia('pausa_junto_al_rio', 'Pausa junto al río · para dos', 110000)
        _experiencia('ritual_del_rio', 'Ritual del Río · para dos', 210000)
        _experiencia('velada_dulce', 'Velada Sorpresa · Dulce', 98000)
        _experiencia('velada_flores', 'Velada Sorpresa · con Flores', 118000)

    def _preparar(self, experiencia_id, historial=HISTORIAL, mensaje=''):
        return preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=dict(CLIENTE), historial=historial, mensaje=mensaje,
            giftcards_data=[{'experiencia_id': experiencia_id, 'cantidad': 1,
                             'destinatario_nombre': 'Paulo y Monse',
                             'mensaje': 'los quiero mucho'}])

    def test_no_cotiza_la_carta_que_el_cliente_nunca_nombro(self):
        """El caso de Bárbara: pidió tina, Luna trae masaje."""
        r = self._preparar('masaje_pareja')

        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'falta_confirmar_experiencia')
        # La pregunta que Luna copia al cliente lleva nombre Y precio: son las
        # dos cosas que estaban mal en la cotización que se envió.
        self.assertIn('Masaje para Dos', r['mensaje'])
        self.assertIn('80.000', r['mensaje'])

    def test_cotiza_sin_molestar_la_carta_que_el_cliente_si_pidio(self):
        r = self._preparar('tina_para_dos')

        self.assertTrue(r['success'], r.get('mensaje'))
        self.assertEqual(r['total'], 50000)

    def test_el_si_del_cliente_habilita_la_carta_que_no_nombro(self):
        """Luna puede sugerir: lo que no puede es decidir sola. Mostrada la
        carta con su precio, el sí del cliente vale."""
        historial = HISTORIAL + f'[Aremko]: {CONFIRMACION_MASAJE}\n'

        r = self._preparar('masaje_pareja', historial=historial, mensaje='sí, esa')

        self.assertTrue(r['success'], r.get('mensaje'))
        self.assertEqual(r['total'], 80000)

    def test_un_no_no_habilita_nada(self):
        historial = HISTORIAL + f'[Aremko]: {CONFIRMACION_MASAJE}\n'

        r = self._preparar('masaje_pareja', historial=historial,
                           mensaje='no, esa no')

        self.assertFalse(r['success'])

    def test_distingue_entre_variantes_de_la_misma_familia(self):
        """«velada» y «sorpresa» están en las dos: lo que elige es «dulce»."""
        historial = HISTORIAL.replace(
            'una gift card de tina para dos con una tabla de quesos',
            'la velada sorpresa dulce')

        buena = self._preparar('velada_dulce', historial=historial)
        otra = self._preparar('velada_flores', historial=historial)

        self.assertTrue(buena['success'], buena.get('mensaje'))
        self.assertFalse(otra['success'])

    def test_si_el_cliente_no_nombro_ninguna_carta_se_pregunta(self):
        historial = HISTORIAL.replace(
            'una gift card de tina para dos con una tabla de quesos',
            'algo lindo para regalar')

        r = self._preparar('masaje_pareja', historial=historial)

        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'falta_confirmar_experiencia')

    def test_la_instruccion_interna_le_recuerda_el_camino_del_agregado(self):
        """Que no vuelva a resolver «carta + producto» eligiendo otra carta."""
        r = self._preparar('masaje_pareja')

        self.assertIn('agregá el producto aparte', r['instruccion'])


class NoRepreguntarLoYaCotizadoTests(TestCase):
    """H-102 — con la cotización lista, la herramienta no reinicia el guion.

    Jorge, 2026-08-15 15:38: cotización de tina enviada, tabla de quesos ya
    sumada ($70.000), y Luna volvió a llamar la herramienta sin el destinatario.
    El control de duplicados estaba DESPUÉS de las cuatro preguntas, así que el
    guion arrancó de cero: «¿A nombre de quién va la gift card?» — con el dato
    en pantalla dos mensajes más arriba.
    """

    @classmethod
    def setUpTestData(cls):
        _experiencia('tina_para_dos', 'Tina para dos · junto al río', 50000)

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        from whatsapp_agent.models import PropuestaReserva

        self.key = 'gc-+56911111111-tina_para_dos-1'
        self.previa = PropuestaReserva.objects.create(
            propuesta_id='prop-vigente-1', idempotency_key=self.key,
            canal='whatsapp', external_id='+56911111111',
            payload={'giftcards': [{'experiencia_id': 'tina_para_dos', 'precio': 50000,
                                    'cantidad': 1, 'destinatario_nombre': 'Martin'}],
                     'servicios': [], 'productos': [{'producto_id': 1, 'cantidad': 1}]},
            cliente_data={}, servicios=[], total=70000,   # 50.000 + la tabla
            expires_at=timezone.now() + timedelta(hours=12))

    def _preparar_sin_destinatario(self):
        return preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=dict(CLIENTE), idempotency_key=self.key,
            historial='[Cliente]: quiero regalar una tina para dos\n', mensaje='sí',
            giftcards_data=[{'experiencia_id': 'tina_para_dos', 'cantidad': 1}])

    def test_devuelve_la_cotizacion_vigente_en_vez_de_preguntar_de_nuevo(self):
        r = self._preparar_sin_destinatario()

        self.assertTrue(r['success'])
        self.assertTrue(r['duplicada'])
        self.assertNotIn('A nombre de quién', str(r.get('mensaje', '')))

    def test_el_total_incluye_lo_que_se_sumo_despues(self):
        """La tabla se agregó a la propuesta: son $70.000, no los $50.000 de la
        carta sola."""
        r = self._preparar_sin_destinatario()

        self.assertEqual(r['total'], 70000)

    def test_una_venta_nueva_sigue_pidiendo_el_destinatario(self):
        """El guion de H-094 queda intacto donde corresponde: sin cotización
        previa, sin destinatario no se cotiza."""
        r = preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=dict(CLIENTE), idempotency_key='gc-otra-distinta-1',
            historial='[Cliente]: quiero regalar una tina para dos\n', mensaje='sí',
            giftcards_data=[{'experiencia_id': 'tina_para_dos', 'cantidad': 1}])

        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'falta_destinatario')
