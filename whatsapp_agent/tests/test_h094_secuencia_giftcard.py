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
        r = _preparar(historial=('[Cliente]: para Alda\n'
                                 '[Cliente]: que la quiero mucho\n'
                                 '[Cliente]: jorge@aremko.cl\n'),
                      gc={'destinatario_nombre': 'Alda',
                          'mensaje': 'que la quiero mucho'},
                      cliente={'email': 'jorge@aremko.cl'})
        self.assertEqual(r['error'], 'falta_nombre_comprador')
        self.assertIn('nombre', r['siguiente_pregunta'].lower())

    def test_5_con_los_cuatro_datos_recien_cotiza(self):
        """Cliente nuevo: escribe él sus datos, así que son 4 preguntas y ya."""
        r = _preparar(historial=('[Cliente]: para Alda\n'
                                 '[Cliente]: que la quiero mucho\n'
                                 '[Cliente]: jorge@aremko.cl\n'
                                 '[Cliente]: Jorge Aguilera\n'),
                      gc={'destinatario_nombre': 'Alda',
                          'mensaje': 'que la quiero mucho'},
                      cliente={'email': 'jorge@aremko.cl', 'nombre': 'Jorge Aguilera'})
        self.assertTrue(r['success'], r)
        self.assertEqual(r['total'], 80000)
        self.assertEqual(PropuestaReserva.objects.count(), 1)

    def test_cada_paso_manda_UNA_sola_pregunta(self):
        r = _preparar(historial='[Cliente]: quiero regalar un masaje\n')
        self.assertEqual(r['siguiente_pregunta'].count('?'), 1)
        # Lo que Luna tiene que hacer va en `instruccion`; `mensaje` es lo que
        # lee el cliente (H-095).
        self.assertIn('esperá la respuesta del cliente', r['instruccion'])


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
        r = _preparar(historial=('[Cliente]: para Alda\n'
                                 '[Cliente]: no, sin mensaje\n'
                                 '[Cliente]: jorge@aremko.cl\n'
                                 '[Cliente]: Jorge Aguilera\n'),
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


class NadaInternoLlegaAlClienteTest(TestCase):
    """H-095: el 2026-08-12 a las 14:45, al cliente le llegó palabra por palabra
    «ALTO. Todavía no se puede cotizar. Mandá al cliente EXACTAMENTE esta
    pregunta y nada más...». El prompt le pide a Luna copiar el campo `mensaje`
    tal cual cuando la venta sale bien, y ella lo generalizó al error."""

    def setUp(self):
        _experiencia()

    def test_el_campo_que_se_copia_trae_SOLO_la_pregunta(self):
        r = _preparar(historial='[Cliente]: quiero regalar un masaje\n')
        # Si Luna copia `mensaje` tal cual, el cliente lee algo correcto.
        self.assertEqual(r['mensaje'], r['siguiente_pregunta'])
        for plomeria in ('ALTO', 'herramienta', 'Mandá al cliente', 'success'):
            self.assertNotIn(plomeria, r['mensaje'])

    def test_lo_interno_viaja_aparte(self):
        r = _preparar(historial='[Cliente]: quiero regalar un masaje\n')
        self.assertIn('No completes el dato vos', r['instruccion'])

    def test_la_guarda_reconoce_un_borrador_interno(self):
        from whatsapp_agent import escalation
        self.assertTrue(escalation.parece_instruccion_interna(
            'ALTO. Todavía no se puede cotizar. Mandá al cliente EXACTAMENTE '
            'esta pregunta y nada más: «¿A nombre de quién va?»'))
        self.assertTrue(escalation.parece_instruccion_interna(
            'NO vuelvas a llamar esta herramienta hasta que responda'))

    def test_la_guarda_no_molesta_a_un_mensaje_normal(self):
        from whatsapp_agent import escalation
        for bueno in ('¿A nombre de quién va la gift card? Contame su nombre 🌿',
                      '¡Listo! Te preparé la cotización para que la revises. 🌿',
                      'La Tina para dos junto al río vale $50.000. ¿Te sirve?'):
            self.assertFalse(escalation.parece_instruccion_interna(bueno), bueno)

    def test_el_borrador_filtrado_se_reemplaza_por_la_pregunta(self):
        from whatsapp_agent import escalation
        pendiente = escalation.pregunta_pendiente([
            {'name': 'preparar_giftcard',
             'result': {'success': False, 'siguiente_pregunta': '¿A nombre de quién va?'}}])
        self.assertEqual(pendiente, '¿A nombre de quién va?')

    def test_sin_pregunta_pendiente_no_hay_reemplazo(self):
        from whatsapp_agent import escalation
        self.assertEqual(escalation.pregunta_pendiente([]), '')
        self.assertEqual(escalation.pregunta_pendiente(
            [{'name': 'ver_carrito', 'result': {'success': True}}]), '')


class ResponderNoRepiteLaPreguntaTest(TestCase):
    """H-096 (2026-08-12, 15:17): Luna preguntó el nombre, Jorge contestó
    «Martin aguilera», y volvió a preguntar exactamente lo mismo.

    El mensaje de ESTE turno no viaja dentro del historial —el agente lo pasa
    aparte, igual que en `_cliente_eligio_producto`—, así que la respuesta
    recién dada no contaba como algo dicho por el cliente."""

    def setUp(self):
        _experiencia()

    def test_el_nombre_recien_dicho_cuenta(self):
        self.assertTrue(_lo_dijo_el_cliente(
            'Martin Aguilera',
            historial='[Aremko]: ¿A nombre de quién va la gift card?\n',
            mensaje='Martin aguilera'))

    def test_sin_el_mensaje_del_turno_se_repetiria_la_pregunta(self):
        """La prueba de que el bug era ese y no otro."""
        self.assertFalse(_lo_dijo_el_cliente(
            'Martin Aguilera',
            historial='[Aremko]: ¿A nombre de quién va la gift card?\n'))

    def test_contestar_el_nombre_avanza_a_la_frase(self):
        r = _preparar(historial='[Aremko]: ¿A nombre de quién va?\n',
                      mensaje='Martin aguilera',
                      gc={'destinatario_nombre': 'Martin Aguilera'})
        self.assertEqual(r['error'], 'falta_dedicatoria',
                         'Contestar el nombre tiene que AVANZAR, no repetir')

    def test_la_frase_recien_escrita_tambien_cuenta(self):
        r = _preparar(historial='[Cliente]: para Martin\n',
                      mensaje='que lo quiero mucho',
                      gc={'destinatario_nombre': 'Martin',
                          'mensaje': 'que lo quiero mucho'})
        self.assertEqual(r['error'], 'falta_email')


class HablaComoChilenaTest(TestCase):
    """Jorge: «Me habla con el modismo argentino Contame su nombre»."""

    def setUp(self):
        _experiencia()

    def test_ninguna_pregunta_usa_voseo(self):
        vistos = []
        for kw in ({}, {'gc': {'destinatario_nombre': 'Alda'},
                        'historial': '[Cliente]: para Alda\n'}):
            hist = kw.pop('historial', '[Cliente]: quiero regalar\n')
            r = _preparar(historial=hist, **kw)
            vistos.append(r['siguiente_pregunta'])
        for pregunta in vistos:
            for arg in ('contame', 'querés', 'escribila', 'podés', 'tenés',
                        'decime', 'avisame'):
                self.assertNotIn(arg, pregunta.lower(),
                                 f'Modismo argentino en: {pregunta!r}')

    def test_usa_las_formas_chilenas(self):
        r = _preparar(historial='[Cliente]: quiero regalar\n')
        self.assertIn('cuéntame', r['siguiente_pregunta'].lower())


class PrecioDeRegaloUnicoTest(TestCase):
    """Jorge (15:16): «me ofrece Noche de aguas calientes por 160.000 (el valor
    normal) y luego me dice que la misma experiencia cuesta 130.000 (el valor
    de la giftcard)». Dos precios para lo mismo en 30 segundos."""

    def _fuente(self):
        import whatsapp_agent.prompt as prompt_mod
        return open(prompt_mod.__file__, encoding='utf-8').read()

    def test_el_prompt_prohibe_mezclar_los_dos_precios(self):
        fuente = self._fuente()
        self.assertIn('los precios de la sección 2 dejan de existir', fuente)
        self.assertIn('llamá\n`catalogo_giftcards` ANTES de decir un solo precio', fuente)

    def test_el_prompt_aclara_que_la_giftcard_puede_valer_menos(self):
        """Que sea más barata es la oferta, no un error a corregir."""
        self.assertIn('puede valer\nMENOS que la reserva', self._fuente())


class UnDedazoNoTrabaLaVentaTest(TestCase):
    """H-097 (2026-08-12, 15:27): Jorge tipeó «Martin Aguilkera», Luna corrigió
    el typo a «Martin Aguilera», y la guarda —que exigía coincidencia casi
    exacta— lo dio por inventado y volvió a preguntar. La protección contra
    nombres inventados se había vuelto un callejón sin salida: peor que el
    problema que evitaba, porque una carta mal dirigida se corrige y una venta
    en loop se pierde."""

    def setUp(self):
        _experiencia()

    def test_el_typo_del_cliente_calza_con_el_nombre_corregido(self):
        self.assertTrue(_lo_dijo_el_cliente(
            'Martin Aguilera', historial='', mensaje='Martin Aguilkera'))

    def test_sigue_rechazando_un_nombre_de_verdad_inventado(self):
        """La tolerancia es para dedazos, no para cualquier cosa."""
        self.assertFalse(_lo_dijo_el_cliente(
            'Carolina Pérez', historial='', mensaje='Martin Aguilkera'))
        self.assertFalse(_lo_dijo_el_cliente(
            'Su esposa', historial='[Cliente]: quiero regalar un masaje\n'))

    def test_con_el_typo_la_venta_avanza(self):
        r = _preparar(historial='[Aremko]: ¿A nombre de quién va?\n',
                      mensaje='Martin Aguilkera',
                      gc={'destinatario_nombre': 'Martin Aguilera'})
        self.assertEqual(r['error'], 'falta_dedicatoria',
                         'Un dedazo no puede dejar la venta en loop')


class NuncaDosVecesLaMismaPreguntaTest(TestCase):
    """La red de fondo: si la pregunta ya se hizo y el dato sigue sin validar,
    la conversación pasa a una persona en vez de repetirse."""

    def setUp(self):
        _experiencia()

    def test_repetir_la_pregunta_escala_en_vez_de_insistir(self):
        historial = ('[Cliente]: quiero regalar algo\n'
                     '[Aremko]: ¿A nombre de quién va la gift card? Cuéntame su nombre 🌿\n')
        r = _preparar(historial=historial, mensaje='no sé, la que sea')
        self.assertEqual(r['error'], 'pregunta_en_loop')
        self.assertTrue(r['escalar_por_loop'])
        self.assertNotIn('siguiente_pregunta', r)

    def test_la_primera_vez_si_pregunta(self):
        r = _preparar(historial='[Aremko]: ¡Hola! ¿En qué te ayudo?\n',
                      mensaje='quiero regalar algo')
        self.assertEqual(r['error'], 'falta_destinatario')
        self.assertIn('siguiente_pregunta', r)

    def test_una_pregunta_distinta_no_cuenta_como_repeticion(self):
        """Avanzar de una pregunta a la siguiente es lo normal, no un loop."""
        historial = '[Aremko]: ¿A nombre de quién va la gift card? Cuéntame su nombre 🌿\n'
        r = _preparar(historial=historial, mensaje='Alda',
                      gc={'destinatario_nombre': 'Alda'})
        self.assertEqual(r['error'], 'falta_dedicatoria')
        self.assertIn('siguiente_pregunta', r)


class ElCorreoYElNombreSeConfirmanTest(TestCase):
    """H-098 (2026-08-12, 15:41): la secuencia avanzó bien hasta la frase y ahí
    saltó directo a la cotización. Jorge: «no ha pedido el nombre de la persona
    que regala ni su mail para que le llegue la giftcards».

    Estaban en su ficha, y yo los había dado por completados. Mal: la gift card
    viaja por ese correo. Si en la ficha quedó uno viejo, la carta se pierde y
    nadie se entera —ni el que compró, ni el que iba a recibir el regalo."""

    def setUp(self):
        _experiencia()

    LISTO = {'gc': {'destinatario_nombre': 'Martin Aguilera',
                    'mensaje': 'Hijo, te quiero mucho'}}
    HIST = ('[Cliente]: Martin Aguilera\n'
            '[Cliente]: Hijo, te quiero mucho\n')

    def test_con_ficha_completa_igual_confirma_el_correo(self):
        r = _preparar(historial=self.HIST,
                      cliente={'nombre': 'Jorge Aguilera', 'email': 'jorge@aremko.cl'},
                      **self.LISTO)
        self.assertEqual(r['error'], 'falta_confirmar_email')
        self.assertIn('jorge@aremko.cl', r['siguiente_pregunta'])
        self.assertIn('prefieres otro correo', r['siguiente_pregunta'])
        self.assertFalse(PropuestaReserva.objects.exists())

    def test_despues_del_correo_confirma_el_nombre(self):
        hist = self.HIST + '[Aremko]: Te enviamos la gift card a jorge@aremko.cl — ¿está bien?\n'
        r = _preparar(historial=hist, mensaje='sí',
                      cliente={'nombre': 'Jorge Aguilera', 'email': 'jorge@aremko.cl'},
                      **self.LISTO)
        self.assertEqual(r['error'], 'falta_confirmar_nombre')
        self.assertIn('Jorge Aguilera', r['siguiente_pregunta'])

    def test_con_los_dos_confirmados_recien_cotiza(self):
        hist = (self.HIST +
                '[Aremko]: Te enviamos la gift card a jorge@aremko.cl — ¿está bien?\n'
                '[Cliente]: sí\n'
                '[Aremko]: La compra queda a nombre de Jorge Aguilera, ¿está bien así?\n')
        r = _preparar(historial=hist, mensaje='sí',
                      cliente={'nombre': 'Jorge Aguilera', 'email': 'jorge@aremko.cl'},
                      **self.LISTO)
        self.assertTrue(r['success'], r)
        self.assertEqual(r['total'], 80000)

    def test_el_correo_que_escribe_el_cliente_no_se_repregunta(self):
        """Si lo tipeó él, ya lo vio: no hay nada que confirmar."""
        hist = self.HIST + '[Cliente]: mandala a otro@correo.cl\n'
        r = _preparar(historial=hist,
                      cliente={'nombre': 'Jorge Aguilera', 'email': 'otro@correo.cl'},
                      **self.LISTO)
        self.assertEqual(r['error'], 'falta_confirmar_nombre',
                         'El correo que escribió el cliente no se vuelve a preguntar')

    def test_un_correo_que_nunca_aparecio_en_el_chat_no_pasa(self):
        """El caso que motivó todo: el dato sale de la ficha y nadie lo ve."""
        r = _preparar(historial=self.HIST,
                      cliente={'nombre': 'Jorge Aguilera', 'email': 'viejo@antiguo.cl'},
                      **self.LISTO)
        self.assertEqual(r['error'], 'falta_confirmar_email')
