# -*- coding: utf-8 -*-
"""Clasificación de temas de conversaciones sin cotización (P-31).

Lo que fija, en orden de riesgo:

· El parseo NUNCA tumba el lote: JSON envuelto en ```, categoría inventada o
  texto suelto caen en 'otro' con confianza baja — visibles en el informe, no
  escondidos.
· No se paga dos veces por la misma conversación (se cachea), pero SÍ se
  reclasifica si llegaron mensajes nuevos.
· Los que ya cotizaron quedan fuera: de ellos no hay nada que explicar.
· `--dry-run` no llama al modelo.
"""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ventas.models import WhatsAppMessage
from whatsapp_agent.models import PropuestaReserva, TemaConversacion
from whatsapp_agent.temas import (VERSION_TAXONOMIA, clasificar_conversacion,
                                  interpretar_respuesta, texto_de_conversacion,
                                  MAX_MENSAJES)

AHORA = timezone.now()


def _msg(wid, phone, cuerpo='hola', direction='in', horas_atras=1):
    return WhatsAppMessage.objects.create(
        wa_message_id=wid, phone=phone, direction=direction, body=cuerpo,
        timestamp=AHORA - timedelta(hours=horas_atras))


class InterpretarRespuestaTest(TestCase):

    def test_json_limpio(self):
        self.assertEqual(
            interpretar_respuesta('{"tema":"sin_cupo","motivo":"quería el 20 y estaba lleno","confianza":"alta"}'),
            ('sin_cupo', 'quería el 20 y estaba lleno', 'alta'))

    def test_json_envuelto_en_backticks(self):
        crudo = '```json\n{"tema":"postventa","motivo":"agradeció","confianza":"alta"}\n```'
        self.assertEqual(interpretar_respuesta(crudo)[0], 'postventa')

    def test_texto_alrededor_del_json(self):
        crudo = 'Claro, acá va:\n{"tema":"info_general","motivo":"preguntó dónde quedan","confianza":"media"}\nEspero sirva.'
        self.assertEqual(interpretar_respuesta(crudo)[0], 'info_general')

    def test_categoria_inventada_cae_en_otro_y_lo_dice(self):
        tema, motivo, conf = interpretar_respuesta('{"tema":"cliente_enojado","motivo":"x"}')
        self.assertEqual(tema, 'otro')
        self.assertIn('cliente_enojado', motivo)
        self.assertEqual(conf, 'baja')

    def test_basura_no_revienta(self):
        for crudo in ('', None, 'no sé qué responder', '{roto'):
            tema, _motivo, conf = interpretar_respuesta(crudo)
            self.assertEqual((tema, conf), ('otro', 'baja'))

    def test_confianza_rara_cae_a_media(self):
        self.assertEqual(
            interpretar_respuesta('{"tema":"sin_cupo","confianza":"altísima"}')[2], 'media')


class TextoDeConversacionTest(TestCase):

    def test_marca_quien_habla_y_corta_el_largo(self):
        msgs = [_msg('a', '+56911111111', 'hola quiero una tina'),
                _msg('b', '+56911111111', 'tenemos a las 18', direction='out')]
        texto = texto_de_conversacion(msgs)
        self.assertIn('[cliente] hola quiero una tina', texto)
        self.assertIn('[aremko] tenemos a las 18', texto)

    def test_manda_solo_el_arranque(self):
        msgs = [_msg(f'm{i}', '+56911111111', f'mensaje {i}') for i in range(40)]
        self.assertEqual(len(texto_de_conversacion(msgs).splitlines()), MAX_MENSAJES)

    def test_un_adjunto_sin_texto_no_desaparece(self):
        m = _msg('img', '+56911111111', '')
        m.msg_type = 'image'
        self.assertIn('(image)', texto_de_conversacion([m]))


class ClasificarConversacionTest(TestCase):

    def test_usa_el_generador_inyectado(self):
        class R:
            content = '{"tema":"dijo_que_pagaba","motivo":"quedó de transferir","confianza":"alta"}'
        r = clasificar_conversacion([_msg('a', '+56911111111')],
                                    generar=lambda s, u, m: R())
        self.assertEqual(r[0], 'dijo_que_pagaba')

    def test_una_categoria_de_la_taxonomia_vieja_ya_no_vale(self):
        # 'quedo_en_pensarlo' era v1 y se partió en cuatro. Si el modelo la
        # devolviera igual, tiene que caer en 'otro' y quedar a la vista, no
        # colarse como si fuera una categoría vigente.
        class R:
            content = '{"tema":"quedo_en_pensarlo","motivo":"x","confianza":"alta"}'
        r = clasificar_conversacion([_msg('a', '+56911111111')],
                                    generar=lambda s, u, m: R())
        self.assertEqual(r[0], 'otro')

    def test_un_error_del_modelo_devuelve_None_y_no_lanza(self):
        def explota(s, u, m):
            raise RuntimeError('502 del proveedor')
        self.assertIsNone(
            clasificar_conversacion([_msg('a', '+56911111111')], generar=explota))


class ComandoTest(TestCase):

    def setUp(self):
        # Conversada y sin cotizar: candidata.
        for i in range(5):
            _msg(f'c{i}', '+56911111111', f'consulta {i}', horas_atras=10 - i)
        # Conversada pero YA cotizó: fuera.
        for i in range(5):
            _msg(f'v{i}', '+56922222222', f'quiero reservar {i}', horas_atras=10 - i)
        PropuestaReserva.objects.create(
            propuesta_id='p1', idempotency_key='p1', canal='whatsapp',
            external_id='+56922222222', payload={}, cliente_data={}, servicios=[],
            total=1000, estado='creada', expires_at=AHORA + timedelta(hours=5))
        # Un solo mensaje: bajo el mínimo, fuera.
        _msg('u1', '+56933333333', 'hola')

    def _correr(self, *args):
        salida = StringIO()
        call_command('clasificar_conversaciones', *args, stdout=salida)
        return salida.getvalue()

    def test_dry_run_no_escribe_ni_llama(self):
        salida = self._correr('--dry-run')
        self.assertIn('1 conversaciones sin cotizar', salida)
        self.assertIn('dry-run', salida)
        self.assertEqual(TemaConversacion.objects.count(), 0)

    def test_deja_fuera_al_que_ya_cotizo_y_al_de_un_mensaje(self):
        salida = self._correr('--dry-run')
        # Solo +56911111111 califica: el que cotizó y el de 1 mensaje no.
        self.assertIn('1 conversaciones sin cotizar', salida)

    def test_no_reclasifica_si_no_hay_mensajes_nuevos(self):
        TemaConversacion.objects.create(
            telefono='+56911111111', tema='sin_cupo', confianza='alta',
            ultimo_mensaje_visto=AHORA, version_taxonomia=VERSION_TAXONOMIA)
        salida = self._correr('--dry-run')
        self.assertIn('0 pendientes', salida)

    def test_reclasifica_si_llegaron_mensajes_nuevos(self):
        TemaConversacion.objects.create(
            telefono='+56911111111', tema='sin_cupo', confianza='alta',
            ultimo_mensaje_visto=AHORA - timedelta(days=3),
            version_taxonomia=VERSION_TAXONOMIA)
        salida = self._correr('--dry-run')
        self.assertIn('1 pendientes', salida)

    def test_reclasifica_lo_etiquetado_con_taxonomia_vieja(self):
        # Sin esto, el informe sumaría categorías v1 con categorías v2 —un
        # número que no significa nada y que mirándolo no se nota.
        TemaConversacion.objects.create(
            telefono='+56911111111', tema='sin_cupo', confianza='alta',
            ultimo_mensaje_visto=AHORA,
            version_taxonomia=VERSION_TAXONOMIA - 1)
        self.assertIn('1 pendientes', self._correr('--dry-run'))


class FallaDelProveedorTest(TestCase):
    """Un error de la llamada NO es una clasificación.

    En el lote de prueba, 3 de 25 quedaron como 'otro · respuesta ilegible'
    porque `LLMResult` informa el problema en `.error` y deja `.text` vacío, y
    yo no miraba ese campo. Peor que el dato equivocado era la consecuencia:
    como quedaban «clasificadas», no se reintentaban nunca.
    """

    def test_un_error_del_proveedor_no_se_guarda_como_categoria(self):
        class RError:
            error = 'HTTP 429 rate limit'
            text = ''
        self.assertIsNone(
            clasificar_conversacion([_msg('a', '+56911111111')],
                                    generar=lambda s, u, m: RError()))

    def test_respuesta_vacia_tampoco(self):
        class RVacio:
            error = ''
            text = '   '
        self.assertIsNone(
            clasificar_conversacion([_msg('b', '+56911111111')],
                                    generar=lambda s, u, m: RVacio()))

    def test_reintenta_y_el_segundo_intento_sirve(self):
        estado = {'n': 0}

        class ROk:
            error = ''
            text = '{"tema":"sin_cupo","motivo":"no había el sábado","confianza":"alta"}'

        class RError:
            error = 'timeout'
            text = ''

        def flaky(s, u, m):
            estado['n'] += 1
            return RError() if estado['n'] == 1 else ROk()

        r = clasificar_conversacion([_msg('c', '+56911111111')], generar=flaky)
        self.assertEqual(r[0], 'sin_cupo')
        self.assertEqual(estado['n'], 2)

    def test_texto_ilegible_SI_se_guarda_como_otro(self):
        # Distinto del error de red: acá el modelo contestó, mal. Eso es
        # información sobre el modelo y tiene que quedar a la vista.
        class RBasura:
            error = ''
            text = 'no entendí la pregunta'
        r = clasificar_conversacion([_msg('d', '+56911111111')],
                                    generar=lambda s, u, m: RBasura())
        self.assertEqual((r[0], r[2]), ('otro', 'baja'))


class RecuperarFallasTecnicasTest(TestCase):

    def test_el_otro_por_falla_tecnica_vuelve_a_la_cola(self):
        for i in range(5):
            _msg(f'r{i}', '+56911111111', f'consulta {i}', horas_atras=10 - i)
        TemaConversacion.objects.create(
            telefono='+56911111111', tema='otro', confianza='baja',
            motivo='respuesta del modelo ilegible',
            ultimo_mensaje_visto=AHORA, version_taxonomia=VERSION_TAXONOMIA)
        salida = StringIO()
        call_command('clasificar_conversaciones', '--dry-run', stdout=salida)
        self.assertIn('1 pendientes', salida.getvalue())

    def test_un_otro_legitimo_NO_vuelve_a_la_cola(self):
        for i in range(5):
            _msg(f's{i}', '+56922222222', f'consulta {i}', horas_atras=10 - i)
        TemaConversacion.objects.create(
            telefono='+56922222222', tema='otro', confianza='media',
            motivo='pidió trabajo en el spa',
            ultimo_mensaje_visto=AHORA, version_taxonomia=VERSION_TAXONOMIA)
        salida = StringIO()
        call_command('clasificar_conversaciones', '--dry-run', stdout=salida)
        self.assertIn('0 pendientes', salida.getvalue())
