"""P-52 paso 3 · deploy 2b: Luna busca el horario del canje con la ficha de la gift card.

Flujo aprobado por Jorge el 25-09-2026: tras la bienvenida (deploy 2a), cuando
el cliente dice el día, Luna usa `horario_canje` —que solo ofrece lo que
incluye esa gift card— y, si el cliente acepta, el caso pasa a Deborah con el
resumen armado por el código. Luna nunca confirma ni cobra: la gift card ya
está pagada.

La agenda (alternativas.construir_alternativas), las fechas (resolver_fecha) y
el modelo (OpenRouterProvider.generate_with_tools) se simulan.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_canje_giftcard
"""
from __future__ import annotations

import datetime
import itertools
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from destino_puerto_varas.services.llm.openrouter_provider import LLMResult
from ventas.models import Cliente, GiftCard, WhatsAppMessage
from whatsapp_agent import agent, canje_giftcard, lector_giftcard
from whatsapp_agent.canje_giftcard import FICHAS, Ficha, opcion_de_canje
from whatsapp_agent.models import WhatsAppAgentConfig

TEL = '+56933334444'
MOTOR = 'whatsapp_agent.alternativas.construir_alternativas'
FECHAS = 'whatsapp_agent.availability.resolver_fecha'
PROVIDER = ('destino_puerto_varas.services.llm.openrouter_provider.'
            'OpenRouterProvider.generate_with_tools')
INTERRUPTOR = 'whatsapp_agent.canje_giftcard.LUNA_CONVERSA_EL_CANJE'
_ids = itertools.count(1)


def _proximo(dia_semana, semanas=1):
    """El próximo lunes (0) … domingo (6), al menos una semana adelante."""
    hoy = timezone.localdate()
    return hoy + datetime.timedelta(days=(dia_semana - hoy.weekday()) % 7 + 7 * semanas)


def _resuelve(fecha):
    return mock.patch(FECHAS, return_value={'fecha_iso': fecha.isoformat(), 'ambiguo': False,
                                            'dia_semana': 'x', 'error': None})


def _op(*lineas, precio=50000):
    return {'titulo': 'x', 'precio_total': precio, 'precio_con_descuento': precio,
            'hay_descuento': False, 'texto_sugerido': f'… ${precio}',
            'itinerario': [{'servicio': s, 'hora': h, 'servicio_id': i + 1}
                           for i, (s, h) in enumerate(lineas)]}


def _agenda(*opciones):
    return mock.patch(MOTOR, return_value={'tipo': 'x', 'fecha': 'x', 'personas': 2,
                                           'nombre_experiencia': 'x',
                                           'alternativas': list(opciones)})


class _Base(TestCase):
    def setUp(self):
        self.gc = GiftCard.objects.create(
            codigo='N7LTQ4ZX9PKA', monto_inicial=50000, monto_disponible=50000,
            fecha_vencimiento=timezone.localdate() + datetime.timedelta(days=300),
            estado='cobrado', servicio_asociado='tinas')

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()


class LasFichas(TestCase):
    def test_las_gift_cards_de_la_tabla_tienen_ficha(self):
        for clave in ('tinas', 'Tina hidromasaje 2 personas', 'tina_para_dos', 'pausa_junto_al_rio',
                      'tinas_masajes_semana', 'Masaje para 1 persona', 'masaje_pareja',
                      'alojamiento_romantico', 'ritual_del_rio', 'velada_simple_hidro'):
            self.assertIn(clave, FICHAS, clave)

    def test_monto_libre_y_las_antiguas_no_tienen_ficha(self):
        for clave in ('', 'monto_libre', 'masajes', 'cabanas', 'alojamiento_tinas'):
            gc = GiftCard(servicio_asociado=clave)
            self.assertIsNone(canje_giftcard.ficha_de(gc), clave)

    def test_el_interruptor_esta_encendido(self):
        # Jorge lo encendió el 25-09-2026 tras la prueba con el modelo real.
        self.assertIs(canje_giftcard.LUNA_CONVERSA_EL_CANJE, True)

    def test_mientras_deborah_no_responda_solo_lo_que_dice_la_carta(self):
        self.assertEqual(FICHAS['tinas'].tinas, 'sin_hidro')           # «sin hidromasaje»
        self.assertEqual(FICHAS['tina_para_dos'].tinas, 'cualquiera')  # «cualquiera de nuestras tinas»
        self.assertEqual(FICHAS['pausa_junto_al_rio'].tinas, 'sin_hidro')
        self.assertEqual(FICHAS['tinas_masajes_semana'].dias, 'dom_jue')
        self.assertEqual(FICHAS['tinas_masajes_finde'].dias, 'vie_sab')
        self.assertEqual(FICHAS['velada_gran_hidro'].tinas, 'hidro')


class ElHorarioDelCanje(_Base):
    SIN_HIDRO = FICHAS['tinas']

    def _opcion(self, ficha, fecha, *opciones, **args):
        with _resuelve(fecha), _agenda(*opciones):
            return opcion_de_canje(self.gc, ficha, {'fecha': 'el sábado', **args})

    def test_ofrece_una_tina_sin_hidromasaje_desde_la_primera_hora(self):
        # Solo tina (Jorge, 25-09-2026): la primera hora libre de lo que cubre.
        sabado = _proximo(5)
        r = self._opcion(self.SIN_HIDRO, sabado,
                         _op(('Tina Hidromasaje Llaima', '14:00'), precio=60000),
                         _op(('Tina Tronador', '18:00')),
                         _op(('Tina Hornopiren', '20:00')))
        self.assertTrue(r['success'])
        self.assertEqual(r['itinerario'], [{'servicio': 'Tina Tronador', 'hora': '18:00',
                                            'servicio_id': 1}])
        self.assertTrue(r['opcion'].startswith('sábado '), r['opcion'])
        self.assertTrue(r['opcion'].endswith(': Tina Tronador a las 18:00'), r['opcion'])
        self.assertNotIn('$', r['opcion'])

    def test_si_pide_una_hora_ofrece_la_mas_cercana(self):
        r = self._opcion(self.SIN_HIDRO, _proximo(5),
                         _op(('Tina Tronador', '14:00')), _op(('Tina Tronador', '18:00')),
                         _op(('Tina Tronador', '20:00')), hora='17:30')
        self.assertIn('Tina Tronador a las 18:00', r['opcion'])

    def test_la_de_hidromasaje_solo_ofrece_hidromasaje(self):
        r = self._opcion(FICHAS['Tina hidromasaje 2 personas'], _proximo(5),
                         _op(('Tina Tronador', '20:00')),
                         _op(('Tina Hidromasaje Villarrica', '16:30'), precio=60000))
        self.assertIn('Tina Hidromasaje Villarrica a las 16:30', r['opcion'])

    def test_la_de_cualquier_tina_ofrece_la_primera_hora_sea_cual_sea(self):
        r = self._opcion(FICHAS['tina_para_dos'], _proximo(5),
                         _op(('Tina Hidromasaje Llaima', '11:30'), precio=60000),
                         _op(('Tina Tronador', '17:00')))
        self.assertIn('Tina Hidromasaje Llaima a las 11:30', r['opcion'])

    def test_si_no_queda_lo_que_cubre_lo_dice(self):
        r = self._opcion(self.SIN_HIDRO, _proximo(5),
                         _op(('Tina Hidromasaje Llaima', '18:00'), precio=60000))
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'sin_horario')

    def test_una_de_domingo_a_jueves_no_se_ofrece_un_sabado(self):
        r = self._opcion(FICHAS['tinas_masajes_semana'], _proximo(5),
                         _op(('Tina Tronador', '16:30'), ('Masaje Relajación o Descontracturante', '18:45')))
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'dia_no_incluido')
        self.assertIn('de domingo a jueves', r['mensaje'])

    def test_una_de_viernes_o_sabado_no_se_ofrece_un_miercoles(self):
        r = self._opcion(FICHAS['tinas_masajes_finde'], _proximo(2),
                         _op(('Tina Tronador', '16:30'), ('Masaje Relajación o Descontracturante', '18:45')))
        self.assertEqual(r['error'], 'dia_no_incluido')

    def test_no_despues_del_vencimiento(self):
        self.gc.fecha_vencimiento = timezone.localdate() + datetime.timedelta(days=3)
        r = self._opcion(self.SIN_HIDRO, _proximo(5, semanas=2), _op(('Tina Tronador', '18:00')))
        self.assertEqual(r['error'], 'despues_del_vencimiento')

    def test_no_una_fecha_pasada(self):
        r = self._opcion(self.SIN_HIDRO, timezone.localdate() - datetime.timedelta(days=1),
                         _op(('Tina Tronador', '18:00')))
        self.assertEqual(r['error'], 'fecha_pasada')

    def test_la_pausa_ofrece_tina_y_los_dos_masajes(self):
        r = self._opcion(FICHAS['pausa_junto_al_rio'], _proximo(3),
                         _op(('Tina Hidromasaje Llaima', '16:30'),
                             ('Masaje Relajación o Descontracturante', '18:45'), precio=120000),
                         _op(('Tina Tronador', '16:30'),
                             ('Masaje Relajación o Descontracturante', '18:45'), precio=110000))
        self.assertIn('Tina Tronador a las 16:30 y 2 masajes a las 18:45', r['opcion'])

    def test_el_masaje_de_una_persona_no_ofrece_otro_masaje(self):
        # El tailandés cuesta lo mismo y es más tarde: sin el filtro, ganaría.
        r = self._opcion(FICHAS['Masaje para 1 persona'], _proximo(3),
                         _op(('Masaje Tailandes (Nuevo)', '20:00'), precio=40000),
                         _op(('Masaje Relajación o Descontracturante', '13:00'), precio=40000))
        self.assertIn('Masaje Relajación o Descontracturante a las 13:00', r['opcion'])

    def test_la_de_piedras_calientes_ofrece_piedras_calientes(self):
        # La relajación es más barata: sin el filtro, ganaría.
        r = self._opcion(FICHAS['masaje_piedras'], _proximo(3),
                         _op(('Masaje Relajación o Descontracturante', '20:00'), precio=40000),
                         _op(('Masaje Piedras Calientes', '15:30'), precio=45000))
        self.assertIn('Masaje Piedras Calientes a las 15:30', r['opcion'])

    def test_si_viene_acompanado_el_segundo_masaje_se_paga_aparte(self):
        r = self._opcion(FICHAS['Masaje para 1 persona'], _proximo(3),
                         _op(('Masaje Relajación o Descontracturante', '13:00'), precio=80000),
                         personas=2)
        self.assertTrue(r['success'])
        self.assertEqual(r['diferencia_a_pagar'], 40000)
        self.assertIn('2 masajes a las 13:00', r['opcion'])
        self.assertIn('el otro se paga aparte: $40.000', r['opcion'])

    def test_una_tina_para_2_no_se_estira_a_4_personas(self):
        r = self._opcion(self.SIN_HIDRO, _proximo(5), _op(('Tina Tronador', '18:00')), personas=4)
        self.assertEqual(r['error'], 'personas_distintas')

    def test_la_noche_dice_la_llegada_y_el_desayuno(self):
        r = self._opcion(FICHAS['alojamiento_romantico'], _proximo(3),
                         _op(('Cabaña Tepa', '16:00'), ('Tina Tronador', '22:00'), precio=130000))
        self.assertIn('Cabaña Tepa (llegada 16:00) y Tina Tronador a las 22:00, con desayuno',
                      r['opcion'])

    def test_al_confirmar_arma_el_resumen_para_deborah(self):
        sabado = _proximo(5)
        with _resuelve(sabado), _agenda(_op(('Cabaña Tepa', '16:00'), ('Tina Tronador', '22:00'))):
            r = opcion_de_canje(self.gc, FICHAS['alojamiento_romantico'],
                                {'fecha': 'el sábado', 'confirmar': True})
        self.assertTrue(r['confirmado'])
        resumen = r['resumen_para_deborah']
        self.assertTrue(resumen.startswith('Canje listo · '), resumen)
        self.assertIn('código N7LTQ4ZX9PKA', resumen)
        self.assertIn(f'{sabado:%d-%m-%Y}', resumen)
        self.assertIn('Cabaña Tepa 16:00 + Tina Tronador 22:00', resumen)
        self.assertIn('agregar la ambientación romántica', resumen)
        self.assertLessEqual(len(resumen), 200)

    def test_si_la_agenda_falla_no_revienta(self):
        with _resuelve(_proximo(5)), mock.patch(MOTOR, side_effect=RuntimeError('boom')):
            r = opcion_de_canje(self.gc, self.SIN_HIDRO, {'fecha': 'el sábado'})
        self.assertFalse(r['success'])


class LaReservaLaConfirmaDeborah(TestCase):
    def test_detecta_cuando_el_borrador_da_la_reserva_por_hecha(self):
        for texto in ('¡Listo! Tu reserva quedó confirmada', 'Quedó agendado para el sábado',
                      'Te reservé la tina Tronador', 'Tu reserva confirmada 🌿'):
            self.assertTrue(canje_giftcard.afirma_reserva(texto), texto)

    def test_una_pregunta_no_es_confirmar(self):
        for texto in ('¿Te lo reservo?', '¿Te acomoda el sábado a las 20:00?',
                      'Le paso el caso a Deborah para que te confirme',
                      '¿Quieres que te lo deje listo?'):
            self.assertFalse(canje_giftcard.afirma_reserva(texto), texto)


def _modelo(texto, *llamadas):
    """Simula a Luna: ejecuta de verdad las herramientas que «pide» y responde `texto`."""
    visto = {}

    def generate_with_tools(self, messages, tools, tool_executor, **kwargs):
        visto['messages'], visto['tools'] = messages, tools
        hechas = [{'name': n, 'arguments': a, 'result': tool_executor(n, a)} for n, a in llamadas]
        visto['hechas'] = hechas
        return LLMResult(texto, 'google/gemini-2.5-flash', 100, 20, 900, tool_calls_executed=hechas)

    return mock.patch(PROVIDER, generate_with_tools), visto


class LunaConversaElCanje(_Base):
    """Después de la bienvenida: el cliente responde y Luna busca el horario."""

    def setUp(self):
        super().setUp()
        encendido = mock.patch(INTERRUPTOR, True)
        encendido.start()
        self.addCleanup(encendido.stop)
        cfg = WhatsAppAgentConfig.get_solo()
        cfg.activo, cfg.modo, cfg.ausencia_activa = True, 'borrador', False
        cfg.save()
        Cliente.objects.create(nombre='Natalia González', telefono=TEL)
        foto = self._mensaje(minutos_atras=30, msg_type='image', mime_type='image/jpeg',
                             media_file='whatsapp/foto.jpg')
        with mock.patch('whatsapp_agent.lector_giftcard._bytes_de', return_value=b'x'), \
                mock.patch('whatsapp_agent.lector_giftcard._preguntar_al_modelo',
                           return_value=({'tipo': 'giftcard_aremko', 'codigo': 'N7LTQ4ZX9PKA'},
                                         2000, 1500)):
            lector_giftcard.leer(foto)
        WhatsAppMessage.objects.filter(pk=foto.pk).update(requiere_atencion=False)
        self._mensaje(minutos_atras=20, direction='out', pendiente=False,
                      body='Recibí tu gift card «Tina para 2» 🎁 ¿Qué día te gustaría venir?')
        self.sabado = _proximo(5)

    def _mensaje(self, minutos_atras=2, pendiente=True, **campos):
        datos = dict(wa_message_id=f'wamid.canje{next(_ids)}', phone=TEL, direction='in',
                     body='', msg_type='text', requiere_atencion=pendiente,
                     timestamp=timezone.now() - datetime.timedelta(minutes=minutos_atras))
        datos.update(campos)
        return WhatsAppMessage.objects.create(**datos)

    def _turno(self, texto_cliente, texto_luna, *llamadas, opciones=()):
        self._mensaje(body=texto_cliente)
        parche, visto = _modelo(texto_luna, *llamadas)
        with parche, _resuelve(self.sabado), _agenda(*(opciones or (_op(('Tina Tronador', '20:00')),))):
            sug = agent.generar_sugerencia(TEL)
        return sug, visto

    def test_luna_busca_el_horario_con_la_ficha_y_lo_ofrece(self):
        texto = 'El sábado tengo la Tina Tronador a las 20:00 🌿 ¿Te acomoda?'
        sug, visto = self._turno('el sábado porfa', texto, ('horario_canje', {'fecha': 'el sábado'}))
        self.assertFalse(sug.escalar, sug.motivo_escalar)
        self.assertEqual(sug.texto, texto)
        self.assertEqual([t['function']['name'] for t in visto['tools']], ['horario_canje'])
        prompt_usuario = visto['messages'][1]['content']
        self.assertIn('CANJE DE GIFT CARD EN CURSO', prompt_usuario)
        self.assertIn('1 tina sin hidromasaje para 2 personas', prompt_usuario)

    def test_si_acepta_pasa_a_deborah_con_el_resumen_del_codigo(self):
        sug, _ = self._turno('sí, perfecto', 'Listo, le paso tu reserva a Deborah',
                             ('horario_canje', {'fecha': 'el sábado', 'confirmar': True}))
        self.assertTrue(sug.escalar)
        self.assertTrue(sug.motivo_escalar.startswith('Canje listo · '), sug.motivo_escalar)
        self.assertIn('código N7LTQ4ZX9PKA', sug.motivo_escalar)
        self.assertIn('Tina Tronador 20:00', sug.motivo_escalar)

    def test_si_dice_si_y_luna_no_confirma_igual_pasa_a_deborah(self):
        sug, _ = self._turno('sí', '¡Genial! Nos vemos el sábado 🌿')
        self.assertTrue(sug.escalar)
        self.assertIn('el cliente aceptó', sug.motivo_escalar)
        self.assertIn('código N7LTQ4ZX9PKA', sug.motivo_escalar)

    def test_si_el_borrador_da_la_reserva_por_hecha_pasa_a_deborah(self):
        sug, _ = self._turno('el sábado a las 20', '¡Listo! Tu reserva quedó confirmada 🌿',
                             ('horario_canje', {'fecha': 'el sábado', 'hora': '20:00'}))
        self.assertTrue(sug.escalar)
        self.assertIn('la reserva quedó hecha', sug.motivo_escalar)

    def test_si_el_borrador_menciona_un_precio_pasa_a_deborah(self):
        sug, _ = self._turno('el sábado', 'El sábado tengo la Tronador a las 20:00, $50.000.',
                             ('horario_canje', {'fecha': 'el sábado'}))
        self.assertTrue(sug.escalar)
        self.assertIn('mencionaba un precio', sug.motivo_escalar)

    def test_si_luna_deriva_el_motivo_trae_la_gift_card(self):
        sug, _ = self._turno('¿y si vamos con hidromasaje?', '[ESCALAR: pide hidromasaje]')
        self.assertTrue(sug.escalar)
        self.assertTrue(sug.motivo_escalar.startswith('Canje de gift card · pide hidromasaje · '),
                        sug.motivo_escalar)
        self.assertIn('código N7LTQ4ZX9PKA', sug.motivo_escalar)

    def test_luna_no_puede_vender_durante_el_canje(self):
        # Ni se le ofrece una herramienta de venta, ni se ejecuta si la pide igual.
        sug, visto = self._turno('el sábado', 'El sábado a las 20:00 🌿 ¿Te acomoda?',
                                 ('agregar_servicio_carrito', {'servicio_id': 1}))
        self.assertNotIn('agregar_servicio_carrito', [t['function']['name'] for t in visto['tools']])
        self.assertEqual(visto['hechas'][0]['result']['error'], 'no_disponible_en_canje')

    def test_con_el_interruptor_apagado_lo_ve_deborah_como_en_el_deploy_2a(self):
        self._mensaje(body='el sábado')
        parche, visto = _modelo('no debería llamarse')
        with parche, mock.patch(INTERRUPTOR, False):
            sug = agent.generar_sugerencia(TEL)
        self.assertEqual(visto, {})
        self.assertTrue(sug.escalar)
        self.assertTrue(sug.motivo_escalar.startswith('Canje de gift card en curso · '))

    def test_la_de_monto_libre_la_sigue_viendo_deborah(self):
        GiftCard.objects.filter(pk=self.gc.pk).update(servicio_asociado='')
        self._mensaje(body='el sábado')
        parche, visto = _modelo('no debería llamarse')
        with parche:
            sug = agent.generar_sugerencia(TEL)
        self.assertEqual(visto, {})
        self.assertTrue(sug.escalar)
        self.assertTrue(sug.motivo_escalar.startswith('Canje de gift card en curso · '))
