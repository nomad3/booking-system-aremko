# -*- coding: utf-8 -*-
"""H-094: la secuencia de preguntas la manda la herramienta, no Luna.

Jorge (2026-08-12, viendo una cotización de $80.000 armada sin preguntar nada):
«Debe preguntar uno a uno los datos. Nombre del destinatario, después si quiere
incluir una frase por favor escríbala. Correo suyo donde llegará la giftcard,
nombre suyo. Así pregunta por pregunta se completan estos datos y luego se
prepara la cotización.»

Tres intentos de cerrar esta puerta, y por qué los dos primeros fallaron:

  01:46 — Luna saltó al cierre y la carta salió «para su hijo». Se bloqueó
          cuando destinatario Y dedicatoria venían vacíos, con `sin_datos_regalo`
          como escape.
  18:20 — El flag se verificó contra el historial (H-093). El log muestra que el
          gate disparó… y que EN EL MISMO SEGUNDO se creó la propuesta igual:
          Luna reintentó con un nombre inventado, y como los campos ya no venían
          vacíos, la puerta no se cerró.
  Ahora — los datos además tienen que haber salido de la boca del cliente, y la
          herramienta devuelve UNA pregunta por vez en el orden de Jorge.
"""
from django.test import TestCase

from ventas.models import GiftCardExperiencia
from whatsapp_agent.giftcards import _lo_dijo_el_cliente, preparar_giftcard
from whatsapp_agent.models import PropuestaReserva

TEL = '+56958655810'


def _experiencia():
    return GiftCardExperiencia.objects.create(
        id_experiencia='masaje_pareja', categoria='masajes',
        nombre='Masaje para Dos', descripcion='Dos masajes',
        descripcion_giftcard='Detalle', imagen='giftcards/x.jpg',
        monto_fijo=80000, activo=True)


def _preparar(historial='', **campos):
    """Una llamada a la herramienta como la haría Luna."""
    gc = {'experiencia_id': 'masaje_pareja'}
    gc.update(campos.pop('gc', {}))
    return preparar_giftcard(
        canal='whatsapp', external_id=TEL,
        cliente_data=campos.pop('cliente', {}),
        giftcards_data=[gc], historial=historial, **campos)


class LoDijoElClienteTest(TestCase):
    """El corazón del arreglo: distinguir el dato del cliente del invento."""

    HIST = ('[Cliente]: quiero regalar algo\n'
            '[Aremko]: ¿A nombre de quién va?\n'
            '[Cliente]: para Alda Toloza\n')

    def test_reconoce_el_nombre_que_escribio_el_cliente(self):
        self.assertTrue(_lo_dijo_el_cliente('Alda Toloza', self.HIST))

    def test_tolera_tildes_y_mayusculas(self):
        hist = '[Cliente]: se llama maria jose\n'
        self.assertTrue(_lo_dijo_el_cliente('María José', hist))

    def test_rechaza_el_nombre_inventado(self):
        """El caso exacto de las 18:20:17."""
        self.assertFalse(_lo_dijo_el_cliente('Su hijo', self.HIST))
        self.assertFalse(_lo_dijo_el_cliente('Carolina', self.HIST))

    def test_no_le_sirve_lo_que_dijo_ARemko(self):
        """Si el nombre solo aparece en boca de Luna, no cuenta."""
        hist = ('[Aremko]: ¿Se la dejamos a nombre de Carolina?\n'
                '[Cliente]: dale\n')
        self.assertFalse(_lo_dijo_el_cliente('Carolina', hist))

    def test_nombre_corto_se_busca_literal(self):
        """«Ana» no sobrevive al filtro de palabras: hay un camino aparte."""
        self.assertTrue(_lo_dijo_el_cliente('Ana', '[Cliente]: para ana\n'))
        self.assertFalse(_lo_dijo_el_cliente('Ana', '[Cliente]: para pedro\n'))

    def test_sin_historial_no_hay_permiso(self):
        self.assertFalse(_lo_dijo_el_cliente('Alda', ''))


class SecuenciaDePreguntasTest(TestCase):
    """El orden de Jorge: destinatario → frase → correo → nombre."""

    def setUp(self):
        _experiencia()

    def test_1_primero_pregunta_por_el_destinatario(self):
        r = _preparar(historial='[Cliente]: quiero regalar un masaje\n')
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'falta_destinatario')
        self.assertIn('nombre', r['siguiente_pregunta'].lower())
        self.assertFalse(PropuestaReserva.objects.exists())

    def test_2_con_destinatario_pregunta_por_la_frase(self):
        r = _preparar(historial='[Cliente]: para Alda\n',
                      gc={'destinatario_nombre': 'Alda'})
        self.assertEqual(r['error'], 'falta_dedicatoria')
        self.assertIn('frase', r['siguiente_pregunta'].lower())

    def test_3_con_la_frase_pregunta_el_correo(self):
        r = _preparar(historial='[Cliente]: para Alda\n[Cliente]: que la quiero mucho\n',
                      gc={'destinatario_nombre': 'Alda',
                          'mensaje': 'que la quiero mucho'})
        self.assertEqual(r['error'], 'falta_email')
        self.assertIn('correo', r['siguiente_pregunta'].lower())

    def test_4_con_el_correo_pregunta_el_nombre_del_comprador(self):
        r = _preparar(historial='[Cliente]: para Alda\n[Cliente]: que la quiero mucho\n',
                      gc={'destinatario_nombre': 'Alda',
                          'mensaje': 'que la quiero mucho'},
                      cliente={'email': 'jorge@aremko.cl'})
        self.assertEqual(r['error'], 'falta_nombre_comprador')
        self.assertIn('nombre', r['siguiente_pregunta'].lower())

    def test_5_con_los_cuatro_datos_recien_cotiza(self):
        r = _preparar(historial='[Cliente]: para Alda\n[Cliente]: que la quiero mucho\n',
                      gc={'destinatario_nombre': 'Alda',
                          'mensaje': 'que la quiero mucho'},
                      cliente={'email': 'jorge@aremko.cl', 'nombre': 'Jorge Aguilera'})
        self.assertTrue(r['success'], r)
        self.assertEqual(r['total'], 80000)
        self.assertEqual(PropuestaReserva.objects.count(), 1)

    def test_cada_paso_manda_UNA_sola_pregunta(self):
        r = _preparar(historial='[Cliente]: quiero regalar un masaje\n')
        self.assertEqual(r['siguiente_pregunta'].count('?'), 1)
        self.assertIn('NO vuelvas a llamar esta herramienta', r['mensaje'])


class NoSePuedeEsquivarTest(TestCase):
    """Lo que pasó a las 18:20:17: reintentar con un dato inventado."""

    def setUp(self):
        _experiencia()

    def test_el_nombre_inventado_no_abre_la_puerta(self):
        r = _preparar(historial='[Cliente]: quiero regalar un masaje\n[Cliente]: masaje\n',
                      gc={'destinatario_nombre': 'Su esposa',
                          'mensaje': 'Con todo mi cariño'},
                      cliente={'email': 'jorge@aremko.cl', 'nombre': 'Jorge Aguilera'})
        self.assertFalse(r['success'], r)
        self.assertEqual(r['error'], 'destinatario_no_lo_dijo_el_cliente')
        self.assertFalse(PropuestaReserva.objects.exists())

    def test_la_dedicatoria_inventada_tampoco(self):
        r = _preparar(historial='[Cliente]: para Alda\n',
                      gc={'destinatario_nombre': 'Alda',
                          'mensaje': 'Con todo mi cariño en este día tan especial'},
                      cliente={'email': 'jorge@aremko.cl', 'nombre': 'Jorge Aguilera'})
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'dedicatoria_no_la_dijo_el_cliente')

    def test_el_flag_solo_salta_la_frase_no_el_destinatario(self):
        """`sin_datos_regalo` es para quien no quiere dedicatoria — nunca fue
        un permiso para saltarse el nombre de quien recibe el regalo."""
        r = _preparar(historial='[Cliente]: quiero regalar un masaje\n',
                      sin_datos_regalo=True,
                      cliente={'email': 'jorge@aremko.cl', 'nombre': 'Jorge Aguilera'})
        self.assertEqual(r['error'], 'falta_destinatario')

    def test_quien_no_quiere_frase_llega_a_la_cotizacion(self):
        r = _preparar(historial='[Cliente]: para Alda\n[Cliente]: no, sin mensaje\n',
                      sin_datos_regalo=True,
                      gc={'destinatario_nombre': 'Alda'},
                      cliente={'email': 'jorge@aremko.cl', 'nombre': 'Jorge Aguilera'})
        self.assertTrue(r['success'], r)


class ElCasoDeJorgeTest(TestCase):
    """La conversación del screenshot, tal cual."""

    def setUp(self):
        _experiencia()

    def test_decir_masaje_no_alcanza_para_una_cotizacion(self):
        historial = ('[Cliente]: quiero regalar algo\n'
                     '[Aremko]: ¿te gustaría regalar un masaje, una tina...?\n'
                     '[Cliente]: masaje\n')
        r = _preparar(historial=historial,
                      cliente={'nombre': 'Jorge Aguilera González',
                               'email': 'ecolonco@gmail.com'})
        self.assertFalse(r['success'],
                         'Con «masaje» y nada más NO puede salir una cotización')
        self.assertEqual(r['error'], 'falta_destinatario')
        self.assertEqual(PropuestaReserva.objects.count(), 0)
