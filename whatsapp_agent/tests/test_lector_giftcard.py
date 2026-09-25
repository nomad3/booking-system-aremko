"""P-52 paso 3 · primer deploy: Luna ve la foto de la gift card (25-09-2026).

Jorge: «normalmente el cliente solo manda la foto». El lector la lee con el
mismo modelo de Luna, busca el código (tolerando O/0, I/1 y 1 o 2 caracteres
mal leídos) y reconoce los vouchers antiguos «R ####». Si en el turno sin
responder hay una gift card, el canje pasa a Deborah con la tarjeta ya
identificada en el motivo, sin pedirle el código al cliente.

Deploy 2a (25-09-2026, flujo aprobado por Jorge): si la gift card se puede usar
y la foto llega sola (o con un saludo), Luna prepara la bienvenida: saluda,
confirma cuál es y pide el día. Lo que el cliente responda después lo sigue
viendo Deborah, con la gift card identificada, hasta el deploy 2b.

El modelo nunca se llama de verdad: se reemplaza `_preguntar_al_modelo` (y
`_bytes_de`, para no abrir archivos).

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_lector_giftcard
"""
from __future__ import annotations

import datetime
import itertools
from decimal import Decimal
from unittest import mock

from django.db import DatabaseError
from django.test import TestCase
from django.utils import timezone

from ventas.models import Cliente, GiftCard, Pago, VentaReserva, WhatsAppMessage
from whatsapp_agent import agent, lector_giftcard
from whatsapp_agent.models import LecturaImagen, SugerenciaAgenteWhatsApp, WhatsAppAgentConfig

TEL = '+56922223333'
MODELO = 'whatsapp_agent.lector_giftcard._preguntar_al_modelo'
BYTES = 'whatsapp_agent.lector_giftcard._bytes_de'
BORRADOR = 'whatsapp_agent.agent._producir_borrador'
_ids = itertools.count(1)


def _lee(tipo='giftcard_aremko', codigo=None):
    """El modelo «lee» esto en la foto."""
    return mock.patch(MODELO, return_value=({'tipo': tipo, 'codigo': codigo, 'legible': True},
                                            2100, 1800))


def _borrador_normal():
    return mock.patch(BORRADOR, return_value={
        'texto': '¡Hola! Te ayudo altiro.', 'escalar': False, 'motivo': '', 'modelo': 'luna',
        'error': '', 'input_tokens': 10, 'output_tokens': 5, 'latency_ms': 900})


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nombre='Natalia González', telefono=TEL)

    def setUp(self):
        cfg = WhatsAppAgentConfig.get_solo()
        cfg.activo, cfg.modo, cfg.ausencia_activa = True, 'borrador', False
        cfg.save()
        bytes_falsos = mock.patch(BYTES, return_value=b'\xff\xd8foto')
        bytes_falsos.start()
        self.addCleanup(bytes_falsos.stop)

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def _mensaje(self, minutos_atras=5, pendiente=True, **campos):
        datos = dict(wa_message_id=f'wamid.test{next(_ids)}', phone=TEL, direction='in',
                     body='', msg_type='text', requiere_atencion=pendiente,
                     timestamp=timezone.now() - datetime.timedelta(minutes=minutos_atras))
        datos.update(campos)
        return WhatsAppMessage.objects.create(**datos)

    def _foto(self, minutos_atras=5, pendiente=True, **campos):
        datos = dict(msg_type='image', mime_type='image/jpeg', media_file='whatsapp/foto.jpg')
        datos.update(campos)
        return self._mensaje(minutos_atras=minutos_atras, pendiente=pendiente, **datos)

    def _giftcard(self, codigo, monto=90000, saldo=None, vence_en=300,
                  experiencia='tina_para_dos'):
        return GiftCard.objects.create(
            codigo=codigo, monto_inicial=monto,
            monto_disponible=monto if saldo is None else saldo,
            fecha_vencimiento=timezone.localdate() + datetime.timedelta(days=vence_en),
            estado='cobrado', servicio_asociado=experiencia, destinatario_nombre='Natalia González')


class LeerLaFoto(_Base):
    def test_codigo_exacto_identifica_la_gift_card_y_su_estado(self):
        gc = self._giftcard('N7LTQ4ZX9PKA')
        with _lee(codigo='N7LTQ4ZX9PKA'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertEqual(lectura['tipo'], 'giftcard_aremko')
        self.assertEqual(lectura['giftcard_id'], gc.pk)
        self.assertEqual(lectura['forma'], 'exacto')
        self.assertIn('código N7LTQ4ZX9PKA', lectura['resumen'])
        self.assertIn('lista para usar ($90.000)', lectura['resumen'])
        self.assertIn(f'vence {gc.fecha_vencimiento:%d-%m-%Y}', lectura['resumen'])

    def test_la_letra_o_leida_como_cero_y_la_i_como_uno(self):
        gc = self._giftcard('AB0CDEFGH1JK')
        with _lee(codigo='ABOCDEFGHIJK'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertEqual(lectura['giftcard_id'], gc.pk)
        self.assertEqual(lectura['forma'], 'o_por_cero')

    def test_un_caracter_mal_leido_la_encuentra_y_lo_dice(self):
        gc = self._giftcard('N7LTQ4ZX9PKA')
        with _lee(codigo='N7LTQ4ZX9PKB'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertEqual(lectura['giftcard_id'], gc.pk)
        self.assertEqual(lectura['forma'], 'tolerancia')
        self.assertIn('código N7LTQ4ZX9PKA', lectura['resumen'])
        self.assertIn('se leyó con 1 carácter de diferencia', lectura['resumen'])

    def test_el_caracter_que_el_modelo_se_comio(self):
        # Caso real (25-09-2026, gift card 389): leyó 11 de los 12 caracteres.
        gc = self._giftcard('N7LTQ4ZX9PKA')
        with _lee(codigo='N7LTQ4Z9PKA'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertEqual(lectura['giftcard_id'], gc.pk)
        self.assertEqual(lectura['forma'], 'tolerancia')
        self.assertIn('se leyó con 1 carácter de diferencia', lectura['resumen'])

    def test_con_dos_de_diferencia_lo_dice_en_plural(self):
        self._giftcard('N7LTQ4ZX9PKA')
        with _lee(codigo='N7LTQ4ZX9PBB'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertIn('se leyó con 2 caracteres de diferencia', lectura['resumen'])

    def test_tres_caracteres_mal_no_inventa_una(self):
        self._giftcard('N7LTQ4ZX9PKA')
        with _lee(codigo='N7LTQ4ZX9XXX'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertEqual(lectura['tipo'], 'giftcard_aremko')
        self.assertIsNone(lectura['giftcard_id'])
        self.assertEqual(lectura['resumen'], 'el código leído (N7LTQ4ZX9XXX) no está en el sistema')

    def test_si_dos_quedan_igual_de_cerca_no_elige(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._giftcard('N7LTQ4ZX9PBB')
        with _lee(codigo='N7LTQ4ZX9PKB'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertIsNone(lectura['giftcard_id'])

    def test_voucher_antiguo_apunta_a_su_reserva(self):
        # En la prueba real los vouchers salieron como gift card con código «R5602».
        VentaReserva.objects.create(id=5602, cliente=self.cliente)
        with _lee(codigo='R 5602'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertEqual(lectura['tipo'], 'voucher_antiguo')
        self.assertEqual(lectura['voucher'], 5602)
        self.assertEqual(lectura['resumen'], 'R 5602 → reserva #5602 (Natalia González)')

    def test_voucher_sin_reserva_lo_dice(self):
        with _lee(codigo='R5999'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertEqual(lectura['tipo'], 'voucher_antiguo')
        self.assertEqual(lectura['resumen'], 'R 5999: no existe la reserva #5999')

    def test_gift_card_sin_codigo_legible(self):
        for codigo in (None, 'null', ''):
            with self.subTest(codigo=codigo), _lee(codigo=codigo):
                lectura = lector_giftcard.leer(self._foto())
                self.assertEqual(lectura['tipo'], 'giftcard_aremko')
                self.assertEqual(lectura['resumen'],
                                 'foto de gift card, pero no se alcanza a leer el código')

    def test_usada_dice_en_que_reserva_y_no_cuando_vence(self):
        gc = self._giftcard('N7LTQ4ZX9PKA', saldo=0)
        canje = VentaReserva.objects.create(cliente=self.cliente)
        # bulk_create: sin señales (un Pago con gift card la descontaría otra vez).
        Pago.objects.bulk_create([Pago(venta_reserva=canje, monto=Decimal('90000'),
                                       metodo_pago='giftcard', giftcard=gc)])
        with _lee(codigo='N7LTQ4ZX9PKA'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertIn(f'ya usada en la reserva #{canje.pk}', lectura['resumen'])
        self.assertNotIn('vence', lectura['resumen'])

    def test_vencida_dice_cuando_vencio(self):
        gc = self._giftcard('N7LTQ4ZX9PKA', vence_en=-3)
        with _lee(codigo='N7LTQ4ZX9PKA'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertIn(f'vencida el {gc.fecha_vencimiento:%d-%m-%Y}', lectura['resumen'])
        self.assertNotIn('vence ', lectura['resumen'])

    def test_con_saldo_parcial_dice_cuanto_queda(self):
        self._giftcard('N7LTQ4ZX9PKA', saldo=30000)
        with _lee(codigo='N7LTQ4ZX9PKA'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertIn('le quedan $30.000', lectura['resumen'])

    def test_si_la_compra_no_se_ha_pagado_lo_avisa(self):
        self._giftcard('N7LTQ4ZX9PKA')
        with _lee(codigo='N7LTQ4ZX9PKA'), \
                mock.patch('ventas.services.giftcard_estado.compra_sin_pagar', return_value=True):
            lectura = lector_giftcard.leer(self._foto())
        self.assertIn('por cobrar: la venta', lectura['resumen'])

    def test_de_un_comprobante_no_se_guarda_lo_que_dice(self):
        with _lee(tipo='comprobante', codigo='OPERACION 99887766'):
            lectura = lector_giftcard.leer(self._foto())
        self.assertEqual(lectura['tipo'], 'comprobante')
        self.assertEqual(lectura['codigo'], '')
        self.assertEqual(lectura['resumen'], '')

    def test_un_tipo_desconocido_cuenta_como_otro(self):
        with _lee(tipo='meme', codigo=None):
            self.assertEqual(lector_giftcard.leer(self._foto())['tipo'], 'otro')

    def test_cada_foto_se_lee_una_sola_vez(self):
        self._giftcard('N7LTQ4ZX9PKA')
        foto = self._foto()
        with _lee(codigo='N7LTQ4ZX9PKA') as modelo:
            primera = lector_giftcard.leer(foto)
            segunda = lector_giftcard.leer(foto)
        self.assertEqual(modelo.call_count, 1)
        self.assertEqual(primera['resumen'], segunda['resumen'])
        guardada = LecturaImagen.objects.get(wa_message_id=foto.wa_message_id)
        self.assertEqual((guardada.phone, guardada.tokens, guardada.latency_ms), (TEL, 2100, 1800))

    def test_si_el_modelo_falla_no_hay_lectura_ni_queda_guardado_el_error(self):
        foto = self._foto()
        with mock.patch(MODELO, side_effect=TimeoutError('openrouter')):
            self.assertIsNone(lector_giftcard.leer(foto))
        self.assertFalse(LecturaImagen.objects.exists())
        with _lee(tipo='otro'):
            self.assertEqual(lector_giftcard.leer(foto)['tipo'], 'otro')  # se reintenta después

    def test_antes_de_migrar_la_tabla_igual_lee(self):
        # Entre el deploy y el `migrate` de Jorge la tabla no existe.
        self._giftcard('N7LTQ4ZX9PKA')
        sin_tabla = DatabaseError('no existe la relación whatsapp_agent_lecturaimagen')
        with _lee(codigo='N7LTQ4ZX9PKA'), \
                mock.patch.object(LecturaImagen.objects, 'filter', side_effect=sin_tabla), \
                mock.patch.object(LecturaImagen.objects, 'update_or_create', side_effect=sin_tabla):
            lectura = lector_giftcard.leer(self._foto())
        self.assertIn('código N7LTQ4ZX9PKA', lectura['resumen'])

    def test_no_lee_stickers_ni_mensajes_sin_foto(self):
        sticker = self._foto(msg_type='sticker', mime_type='image/webp')
        texto = self._mensaje(body='hola')
        with _lee() as modelo:
            self.assertIsNone(lector_giftcard.leer(sticker))
            self.assertIsNone(lector_giftcard.leer(texto))
        modelo.assert_not_called()

    def test_una_foto_mandada_como_documento_si_se_lee(self):
        self._giftcard('N7LTQ4ZX9PKA')
        documento = self._foto(msg_type='document', mime_type='image/jpeg')
        with _lee(codigo='N7LTQ4ZX9PKA'):
            self.assertEqual(lector_giftcard.leer(documento)['tipo'], 'giftcard_aremko')


class LunaPasaElCanjeADeborah(_Base):
    def test_una_gift_card_ya_usada_pasa_con_la_tarjeta_identificada(self):
        self._giftcard('N7LTQ4ZX9PKA', saldo=0)
        foto = self._foto()
        with _lee(codigo='N7LTQ4ZX9PKA'), _borrador_normal() as borrador:
            sug = agent.generar_sugerencia(TEL)
        borrador.assert_not_called()
        self.assertEqual(sug.wa_message_id, foto.wa_message_id)
        self.assertTrue(sug.escalar)
        self.assertEqual(sug.texto, '')
        self.assertTrue(sug.motivo_escalar.startswith('Canje de gift card · '), sug.motivo_escalar)
        self.assertIn('código N7LTQ4ZX9PKA', sug.motivo_escalar)
        self.assertIn('ya usada', sug.motivo_escalar)

    def test_foto_y_despues_el_texto_tambien(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._foto(minutos_atras=6)
        texto = self._mensaje(minutos_atras=5, body='Hola! Me regalaron esta gift card, '
                                                    'quiero agendar para el sábado')
        with _lee(codigo='N7LTQ4ZX9PKA'), _borrador_normal() as borrador:
            sug = agent.generar_sugerencia(TEL)
        borrador.assert_not_called()
        self.assertEqual(sug.wa_message_id, texto.wa_message_id)
        self.assertIn('código N7LTQ4ZX9PKA', sug.motivo_escalar)

    def test_voucher_antiguo_pasa_como_voucher(self):
        VentaReserva.objects.create(id=5602, cliente=self.cliente)
        self._foto()
        with _lee(codigo='R 5602'), _borrador_normal():
            sug = agent.generar_sugerencia(TEL)
        self.assertEqual(sug.motivo_escalar,
                         'Canje de voucher antiguo · R 5602 → reserva #5602 (Natalia González)')

    def test_dos_gift_cards_en_el_turno(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._foto(minutos_atras=7)
        self._foto(minutos_atras=6)
        with _lee(codigo='N7LTQ4ZX9PKA'), _borrador_normal():
            sug = agent.generar_sugerencia(TEL)
        self.assertTrue(sug.motivo_escalar.endswith('(y 1 foto más de gift card)'),
                        sug.motivo_escalar)
        self.assertLessEqual(len(sug.motivo_escalar), 200)

    def test_un_comprobante_sigue_el_camino_de_siempre(self):
        self._foto()
        self._mensaje(body='Listo, ahí va la transferencia')
        with _lee(tipo='comprobante'), _borrador_normal() as borrador:
            sug = agent.generar_sugerencia(TEL)
        borrador.assert_called_once()
        self.assertFalse(sug.escalar)
        self.assertEqual(sug.texto, '¡Hola! Te ayudo altiro.')

    def test_si_el_lector_falla_luna_sigue_como_antes(self):
        self._foto()
        self._mensaje(body='hola')
        with mock.patch(MODELO, side_effect=RuntimeError('caído')), \
                _borrador_normal() as borrador:
            sug = agent.generar_sugerencia(TEL)
        borrador.assert_called_once()
        self.assertEqual(sug.texto, '¡Hola! Te ayudo altiro.')

    def test_aunque_la_busqueda_reviente_luna_sigue(self):
        self._foto()
        self._mensaje(body='hola')
        with mock.patch('whatsapp_agent.lector_giftcard.fotos_de_canje_pendientes',
                        side_effect=DatabaseError('boom')), _borrador_normal() as borrador:
            sug = agent.generar_sugerencia(TEL)
        borrador.assert_called_once()
        self.assertFalse(sug.escalar)

    def test_una_foto_ya_respondida_no_cuenta(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._foto(minutos_atras=30, pendiente=False)
        self._mensaje(body='¿tienen masajes el domingo?')
        with _lee(codigo='N7LTQ4ZX9PKA') as modelo, _borrador_normal() as borrador:
            agent.generar_sugerencia(TEL)
        modelo.assert_not_called()
        borrador.assert_called_once()

    def test_una_foto_de_hace_mas_de_una_semana_no_cuenta(self):
        self._foto(minutos_atras=8 * 24 * 60)
        self._mensaje(body='hola')
        with _lee(codigo='N7LTQ4ZX9PKA') as modelo, _borrador_normal() as borrador:
            agent.generar_sugerencia(TEL)
        modelo.assert_not_called()
        borrador.assert_called_once()

    def test_lee_a_lo_mas_tres_fotos_por_turno(self):
        for minutos in (9, 8, 7, 6, 5):
            self._foto(minutos_atras=minutos)
        with _lee(tipo='otro') as modelo, _borrador_normal():
            agent.generar_sugerencia(TEL)
        self.assertEqual(modelo.call_count, 3)

    def test_la_sugerencia_queda_guardada_y_no_se_vuelve_a_leer(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._foto()
        with _lee(codigo='N7LTQ4ZX9PKA') as modelo, _borrador_normal():
            primera = agent.generar_sugerencia(TEL)
            segunda = agent.generar_sugerencia(TEL)
        self.assertEqual(modelo.call_count, 1)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(SugerenciaAgenteWhatsApp.objects.count(), 1)

    def test_con_luna_apagada_no_se_lee_ninguna_foto(self):
        cfg = WhatsAppAgentConfig.get_solo()
        cfg.activo = False
        cfg.save()
        self._foto()
        with _lee(codigo='N7LTQ4ZX9PKA') as modelo:
            self.assertIsNone(agent.generar_sugerencia(TEL))
        modelo.assert_not_called()


class LunaDaLaBienvenidaAlCanje(_Base):
    def _vence(self, gc):
        meses = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
                 'septiembre', 'octubre', 'noviembre', 'diciembre')
        f = gc.fecha_vencimiento
        return f'{f.day} de {meses[f.month - 1]} de {f.year}'

    def _sugerencia(self, codigo='N7LTQ4ZX9PKA'):
        with _lee(codigo=codigo), _borrador_normal() as borrador:
            sug = agent.generar_sugerencia(TEL)
        self.borrador = borrador
        return sug

    def test_foto_sola_trae_la_bienvenida_de_luna(self):
        gc = self._giftcard('N7LTQ4ZX9PKA')
        self._foto(cliente=self.cliente)
        sug = self._sugerencia()
        self.borrador.assert_not_called()
        self.assertFalse(sug.escalar)
        self.assertEqual(sug.modelo, 'lector de fotos · bienvenida')
        self.assertEqual(sug.texto, (
            '¡Hola, Natalia! 🌿 Te saluda Luna, tu asistente en Aremko Spa Boutique.\n\n'
            f'Recibí tu gift card «Tina para dos» 🎁 Está lista para usar hasta el {self._vence(gc)}.'
            '\n\n¿Qué día te gustaría venir? Te busco el horario.'))

    def test_con_un_saludo_antes_tambien_y_se_presenta_una_vez(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._mensaje(minutos_atras=6, body='Hola buenas tardes', contact_name='Natalia')
        self._foto(minutos_atras=5)
        sug = self._sugerencia()
        self.assertFalse(sug.escalar)
        self.assertTrue(sug.texto.startswith('¡Hola, Natalia! 🌿 Te saluda Luna'), sug.texto)
        self.assertEqual(sug.texto.count('Te saluda Luna'), 1)

    def test_en_una_conversacion_en_curso_no_se_vuelve_a_presentar(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._mensaje(minutos_atras=90, pendiente=False, body='hola, consulta')
        self._mensaje(minutos_atras=80, direction='out', pendiente=False, body='¡Hola! Cuéntame')
        self._foto(minutos_atras=5)
        sug = self._sugerencia()
        self.assertTrue(sug.texto.startswith('Recibí tu gift card «Tina para dos»'), sug.texto)

    def test_si_le_queda_saldo_dice_cuanto(self):
        gc = self._giftcard('N7LTQ4ZX9PKA', saldo=30000)
        self._foto()
        sug = self._sugerencia()
        self.assertIn(f'Le quedan $30.000 por usar hasta el {self._vence(gc)}.', sug.texto)

    def test_la_de_monto_libre_dice_el_monto(self):
        self._giftcard('N7LTQ4ZX9PKA', experiencia='')
        self._foto()
        self.assertIn('Recibí tu gift card de $90.000 🎁', self._sugerencia().texto)

    def test_la_mandada_como_documento_tambien(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._foto(msg_type='document', mime_type='image/jpeg')
        self.assertFalse(self._sugerencia().escalar)

    def test_una_vencida_pasa_a_deborah(self):
        self._giftcard('N7LTQ4ZX9PKA', vence_en=-3)
        self._foto()
        sug = self._sugerencia()
        self.assertTrue(sug.escalar)
        self.assertIn('vencida el', sug.motivo_escalar)

    def test_una_con_la_compra_sin_pagar_pasa_a_deborah(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._foto()
        with mock.patch('ventas.services.giftcard_estado.compra_sin_pagar', return_value=True):
            sug = self._sugerencia()
        self.assertTrue(sug.escalar)
        self.assertIn('por cobrar', sug.motivo_escalar)

    def test_si_el_codigo_no_esta_pasa_a_deborah(self):
        self._foto()
        sug = self._sugerencia(codigo='ZZZZ9Q8W7E6R')
        self.assertTrue(sug.escalar)
        self.assertIn('no está en el sistema', sug.motivo_escalar)

    def test_si_trae_una_pregunta_pasa_a_deborah(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._foto(minutos_atras=6)
        self._mensaje(minutos_atras=5, body='¿sirve para masaje?')
        self.assertTrue(self._sugerencia().escalar)

    def test_si_trae_un_audio_pasa_a_deborah(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._foto(minutos_atras=6)
        self._mensaje(minutos_atras=5, msg_type='audio', media_file='whatsapp/nota.ogg',
                      mime_type='audio/ogg')
        self.assertTrue(self._sugerencia().escalar)

    def test_con_otra_foto_al_lado_pasa_a_deborah(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._foto(minutos_atras=6)                       # la gift card
        self._foto(minutos_atras=5)                       # otra cosa (se lee primero)
        lecturas = [({'tipo': 'comprobante', 'codigo': None}, 2000, 1500),
                    ({'tipo': 'giftcard_aremko', 'codigo': 'N7LTQ4ZX9PKA'}, 2000, 1500)]
        with mock.patch(MODELO, side_effect=lecturas), _borrador_normal():
            sug = agent.generar_sugerencia(TEL)
        self.assertTrue(sug.escalar)
        self.assertIn('código N7LTQ4ZX9PKA', sug.motivo_escalar)

    def test_si_tiene_una_reserva_proxima_pasa_a_deborah(self):
        # La gift card puede ser para pagar esa reserva.
        self._giftcard('N7LTQ4ZX9PKA')
        self._foto()
        with mock.patch('whatsapp_agent.agent._reserva_vigente_del_cliente', return_value=object()):
            sug = self._sugerencia()
        self.assertTrue(sug.escalar)
        self.assertIn('lista para usar', sug.motivo_escalar)

    def test_si_la_bienvenida_falla_pasa_a_deborah(self):
        self._giftcard('N7LTQ4ZX9PKA')
        self._foto()
        with mock.patch('whatsapp_agent.lector_giftcard.bienvenida_de_canje',
                        side_effect=RuntimeError('boom')):
            sug = self._sugerencia()
        self.assertTrue(sug.escalar)
        self.assertIn('código N7LTQ4ZX9PKA', sug.motivo_escalar)


class DespuesDeLaBienvenida(_Base):
    """El cliente ya mandó la foto y la bienvenida salió: lo que responda (el
    día, la hora) lo agenda Deborah, con la gift card identificada."""

    def _canje_iniciado(self, **giftcard):
        self._giftcard('N7LTQ4ZX9PKA', **giftcard)
        foto = self._foto(minutos_atras=30)
        with _lee(codigo='N7LTQ4ZX9PKA'):
            lector_giftcard.leer(foto)
        WhatsAppMessage.objects.filter(pk=foto.pk).update(requiere_atencion=False)
        self._mensaje(minutos_atras=20, direction='out', pendiente=False,
                      body='Recibí tu gift card. ¿Qué día te gustaría venir?')

    def test_lo_que_responde_el_cliente_pasa_a_deborah_con_la_gift_card(self):
        self._canje_iniciado()
        self._mensaje(minutos_atras=2, body='el sábado a las 18 porfa')
        with _lee() as modelo, _borrador_normal() as borrador:
            sug = agent.generar_sugerencia(TEL)
        modelo.assert_not_called()
        borrador.assert_not_called()
        self.assertTrue(sug.escalar)
        self.assertTrue(sug.motivo_escalar.startswith('Canje de gift card en curso · Tina para dos'),
                        sug.motivo_escalar)
        self.assertIn('código N7LTQ4ZX9PKA', sug.motivo_escalar)

    def test_ya_usada_luna_vuelve_a_lo_normal(self):
        self._canje_iniciado()
        GiftCard.objects.filter(codigo='N7LTQ4ZX9PKA').update(monto_disponible=0)
        self._mensaje(minutos_atras=2, body='¿a qué hora es el check-in?')
        with _borrador_normal() as borrador:
            sug = agent.generar_sugerencia(TEL)
        borrador.assert_called_once()
        self.assertFalse(sug.escalar)

    def test_pasados_tres_dias_luna_vuelve_a_lo_normal(self):
        self._canje_iniciado()
        LecturaImagen.objects.update(created_at=timezone.now() - datetime.timedelta(days=4))
        self._mensaje(minutos_atras=2, body='hola')
        with _borrador_normal() as borrador:
            agent.generar_sugerencia(TEL)
        borrador.assert_called_once()

    def test_otro_cliente_no_se_ve_afectado(self):
        self._canje_iniciado()
        self._mensaje(minutos_atras=2, body='hola', phone='+56977778888')
        with _borrador_normal() as borrador:
            agent.generar_sugerencia('+56977778888')
        borrador.assert_called_once()


class LunaVeLaFotoEnElHistorial(_Base):
    def test_el_historial_muestra_lo_que_dice_la_foto(self):
        self._giftcard('N7LTQ4ZX9PKA')
        foto = self._foto(minutos_atras=10, body='mira')
        with _lee(codigo='N7LTQ4ZX9PKA'):
            lector_giftcard.leer(foto)
        historial = agent._historial_texto(TEL, timezone.now(), 10)
        self.assertIn('[Cliente]: mira (foto: ', historial)
        self.assertIn('código N7LTQ4ZX9PKA', historial)
        self.assertNotIn('(image)', historial)

    def test_el_historial_no_lee_fotos_nuevas(self):
        self._foto(minutos_atras=10)
        with _lee(codigo='N7LTQ4ZX9PKA') as modelo:
            historial = agent._historial_texto(TEL, timezone.now(), 10)
        modelo.assert_not_called()
        self.assertIn('[Cliente]: (image)', historial)

    def test_un_comprobante_leido_sigue_viendose_como_imagen(self):
        foto = self._foto(minutos_atras=10)
        with _lee(tipo='comprobante'):
            lector_giftcard.leer(foto)
        self.assertIn('[Cliente]: (image)', agent._historial_texto(TEL, timezone.now(), 10))
