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
from whatsapp_agent.temas import (clasificar_conversacion, interpretar_respuesta,
                                  texto_de_conversacion, MAX_MENSAJES)

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
            content = '{"tema":"quedo_en_pensarlo","motivo":"dijo que confirmaba","confianza":"alta"}'
        r = clasificar_conversacion([_msg('a', '+56911111111')],
                                    generar=lambda s, u, m: R())
        self.assertEqual(r[0], 'quedo_en_pensarlo')

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
            ultimo_mensaje_visto=AHORA)
        salida = self._correr('--dry-run')
        self.assertIn('0 pendientes', salida)

    def test_reclasifica_si_llegaron_mensajes_nuevos(self):
        TemaConversacion.objects.create(
            telefono='+56911111111', tema='sin_cupo', confianza='alta',
            ultimo_mensaje_visto=AHORA - timedelta(days=3))
        salida = self._correr('--dry-run')
        self.assertIn('1 pendientes', salida)
