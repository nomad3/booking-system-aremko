# -*- coding: utf-8 -*-
"""Recordatorios de Luna (H-109).

Lo que clava esta suite:

· La condición de "no molestar" es SILENCIO ACTUAL, no "nunca escribió después
  de la cotización" — un «gracias» a los 10 minutos no veta el recordatorio.
· Sin entrante <23h NO se genera nada: fuera de la ventana de sesión de Meta
  el mensaje libre no puede salir, y generar igual sería mentirle a la bitácora.
· Un recordatorio por tipo por propuesta/reserva, y uno por teléfono por
  corrida: la bitácora es la memoria, el cron puede correr cuantas veces sea.
· El pull del Go REVALIDA la ventana: lo que esperó demasiado muere como
  'fallido', no sale tarde.
"""
import json
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from ventas.models import Cliente, VentaReserva, WhatsAppMessage
from whatsapp_agent.models import PropuestaReserva, RecordatorioLuna
from whatsapp_agent.recordatorios import candidatos, persistir, silencio_ok
from whatsapp_agent.tests.test_giftcards_luna import _SinSenalesDeVenta

AHORA = timezone.now()


def _propuesta(pid, phone='+56911111111', estado='pendiente', horas_creada=7,
               vence_en_h=17, reserva_id=None):
    p = PropuestaReserva.objects.create(
        propuesta_id=pid, idempotency_key=pid, canal='whatsapp',
        external_id=phone, payload={}, cliente_data={}, servicios=[],
        total=50000, estado=estado, reserva_id=reserva_id,
        expires_at=AHORA + timedelta(hours=vence_en_h))
    PropuestaReserva.objects.filter(pk=p.pk).update(
        created_at=AHORA - timedelta(hours=horas_creada))
    p.refresh_from_db()
    return p


def _entrante(wid, phone, horas_atras):
    return WhatsAppMessage.objects.create(
        wa_message_id=wid, phone=phone, direction='in', body='hola',
        timestamp=AHORA - timedelta(hours=horas_atras))


class CotizacionListaTest(TestCase):

    def test_cotizacion_con_6h_y_silencio_genera_recordatorio(self):
        _propuesta('r1')
        _entrante('m1', '+56911111111', horas_atras=7)
        items = candidatos(AHORA)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['tipo'], 'cotizacion_lista')
        self.assertIn('cotización sigue disponible', items[0]['texto'])
        self.assertIn('http', items[0]['texto'])

    def test_cotizacion_muy_nueva_no_genera(self):
        _propuesta('r2', horas_creada=3)
        _entrante('m2', '+56911111111', horas_atras=5)
        self.assertEqual(candidatos(AHORA), [])

    def test_conversacion_viva_no_genera(self):
        # El cliente escribió hace 1h: hay conversación, no corresponde meterse.
        _propuesta('r3')
        _entrante('m3', '+56911111111', horas_atras=1)
        self.assertEqual(candidatos(AHORA), [])

    def test_un_gracias_viejo_no_veta_el_recordatorio(self):
        # Escribió DESPUÉS de la cotización (6.5h atrás) y luego silencio de
        # sobra: ese es justo el caso que hay que recuperar.
        _propuesta('r4', horas_creada=7)
        _entrante('m4', '+56911111111', horas_atras=6.5)
        items = candidatos(AHORA)
        self.assertEqual(len(items), 1)

    def test_fuera_de_ventana_meta_no_genera(self):
        _propuesta('r5', horas_creada=30, vence_en_h=17)
        _entrante('m5', '+56911111111', horas_atras=25)
        self.assertEqual(candidatos(AHORA), [])

    def test_sin_ningun_entrante_no_genera(self):
        _propuesta('r6')
        self.assertEqual(candidatos(AHORA), [])

    def test_no_duplica_si_ya_esta_en_bitacora(self):
        _propuesta('r7')
        _entrante('m7', '+56911111111', horas_atras=7)
        persistir(candidatos(AHORA))
        self.assertEqual(candidatos(AHORA), [])


class CotizacionPorVencerTest(TestCase):

    def test_por_vencer_genera_aviso_urgente(self):
        _propuesta('v1', horas_creada=22, vence_en_h=2)
        _entrante('mv1', '+56911111111', horas_atras=10)
        items = candidatos(AHORA)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['tipo'], 'cotizacion_por_vencer')
        self.assertIn('vence a las', items[0]['texto'])

    def test_ya_expirada_no_genera(self):
        _propuesta('v2', horas_creada=30, vence_en_h=-2)
        _entrante('mv2', '+56911111111', horas_atras=10)
        self.assertEqual(candidatos(AHORA), [])

    def test_en_zona_de_vencer_no_manda_el_aviso_suave(self):
        # A 2h de expirar corresponde SOLO el urgente, no los dos.
        _propuesta('v3', horas_creada=22, vence_en_h=2)
        _entrante('mv3', '+56911111111', horas_atras=10)
        tipos = [i['tipo'] for i in candidatos(AHORA)]
        self.assertEqual(tipos, ['cotizacion_por_vencer'])


class PagoPendienteTest(_SinSenalesDeVenta, TestCase):

    def _reserva_sin_pagar(self, telefono='+56922222222', horas_creada=8):
        v = VentaReserva.objects.create(
            cliente=Cliente.objects.create(nombre='Cliente pago',
                                           telefono=telefono),
            total=90000, estado_reserva='pendiente', estado_pago='pendiente')
        VentaReserva.objects.filter(pk=v.pk).update(
            fecha_creacion=AHORA - timedelta(hours=horas_creada))
        return v

    def test_reserva_aprobada_sin_pago_genera_recordatorio(self):
        v = self._reserva_sin_pagar()
        _propuesta('p1', phone='+56922222222', estado='creada',
                   horas_creada=8, reserva_id=v.id)
        _entrante('mp1', '+56922222222', horas_atras=8)
        items = candidatos(AHORA)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['tipo'], 'pago_pendiente')
        self.assertEqual(items[0]['reserva_id'], v.id)
        self.assertIn('Pase', items[0]['texto'])

    def test_reserva_pagada_no_genera(self):
        v = self._reserva_sin_pagar()
        VentaReserva.objects.filter(pk=v.pk).update(estado_pago='pagado')
        _propuesta('p2', phone='+56922222222', estado='creada',
                   horas_creada=8, reserva_id=v.id)
        _entrante('mp2', '+56922222222', horas_atras=8)
        self.assertEqual(candidatos(AHORA), [])

    def test_reserva_muy_reciente_no_genera(self):
        # Aprobó hace 2h: darle aire antes de recordarle el pago.
        v = self._reserva_sin_pagar(horas_creada=2)
        _propuesta('p3', phone='+56922222222', estado='creada',
                   horas_creada=2, reserva_id=v.id)
        _entrante('mp3', '+56922222222', horas_atras=5)
        self.assertEqual(candidatos(AHORA), [])

    def test_dos_propuestas_misma_reserva_generan_uno_solo(self):
        # H-060: una adición deja una segunda propuesta apuntando a la misma venta.
        v = self._reserva_sin_pagar()
        _propuesta('p4', phone='+56922222222', estado='creada',
                   horas_creada=8, reserva_id=v.id)
        _propuesta('p5', phone='+56922222222', estado='creada',
                   horas_creada=7, reserva_id=v.id)
        _entrante('mp4', '+56922222222', horas_atras=8)
        items = [i for i in candidatos(AHORA) if i['tipo'] == 'pago_pendiente']
        self.assertEqual(len(items), 1)


class UnoPorTelefonoTest(_SinSenalesDeVenta, TestCase):

    def test_dos_motivos_mismo_telefono_sale_solo_el_mas_urgente(self):
        # Al mismo cliente le calzan "por vencer" y "pago pendiente" en la
        # misma corrida: recibe UNO (el más urgente); el otro, después.
        v = VentaReserva.objects.create(
            cliente=Cliente.objects.create(nombre='Doble', telefono='+56933333333'),
            total=50000, estado_reserva='pendiente', estado_pago='pendiente')
        VentaReserva.objects.filter(pk=v.pk).update(
            fecha_creacion=AHORA - timedelta(hours=10))
        _propuesta('d1', phone='+56933333333', estado='creada',
                   horas_creada=10, reserva_id=v.id)
        _propuesta('d2', phone='+56933333333', horas_creada=22, vence_en_h=2)
        _entrante('md1', '+56933333333', horas_atras=9)
        items = candidatos(AHORA)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['tipo'], 'cotizacion_por_vencer')


class PersistirTest(TestCase):

    def test_persistir_respeta_el_tope(self):
        for n in range(3):
            phone = f'+569444444{n:02d}'
            _propuesta(f't{n}', phone=phone)
            _entrante(f'mt{n}', phone, horas_atras=7)
        creados = persistir(candidatos(AHORA), tope=2)
        self.assertEqual(len(creados), 2)
        self.assertEqual(RecordatorioLuna.objects.count(), 2)
        # Los que quedaron fuera del tope siguen siendo candidatos.
        self.assertEqual(len(candidatos(AHORA)), 1)


@override_settings(LUNA_API_KEY='clave-test')
class EndpointsGoTest(TestCase):
    """El contrato que consume el runner del Go (H-109)."""

    headers = {'HTTP_X_API_KEY': 'clave-test'}

    def _recordatorio(self, phone='+56955555555', horas_entrante=5):
        _entrante(f'me-{phone}', phone, horas_atras=horas_entrante)
        return RecordatorioLuna.objects.create(
            tipo='cotizacion_lista', phone=phone, texto='Hola, tu cotización…')

    def test_pending_devuelve_los_pendientes_en_ventana(self):
        r = self._recordatorio()
        resp = self.client.get('/api/whatsapp/pending-luna-nudges', **self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['pending'][0]['recordatorio_id'], r.id)
        self.assertEqual(data['pending'][0]['phone'], '+56955555555')

    def test_pending_marca_fallido_lo_que_perdio_la_ventana(self):
        r = self._recordatorio(phone='+56955555566', horas_entrante=30)
        resp = self.client.get('/api/whatsapp/pending-luna-nudges', **self.headers)
        self.assertEqual(resp.json()['count'], 0)
        r.refresh_from_db()
        self.assertEqual(r.estado, 'fallido')
        self.assertIn('ventana', r.error)

    def test_mark_sent_cierra_y_registra_el_saliente(self):
        r = self._recordatorio()
        resp = self.client.post(
            '/api/whatsapp/luna-nudges/mark-sent',
            data=json.dumps({'recordatorio_id': r.id, 'wa_message_id': 'wamid.test1'}),
            content_type='application/json', **self.headers)
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertEqual(r.estado, 'enviado')
        self.assertIsNotNone(r.enviado_at)
        self.assertTrue(WhatsAppMessage.objects.filter(
            wa_message_id='wamid.test1', direction='out').exists())

    def test_mark_sent_es_idempotente(self):
        r = self._recordatorio()
        body = json.dumps({'recordatorio_id': r.id, 'wa_message_id': 'wamid.test2'})
        self.client.post('/api/whatsapp/luna-nudges/mark-sent', data=body,
                         content_type='application/json', **self.headers)
        resp = self.client.post('/api/whatsapp/luna-nudges/mark-sent', data=body,
                                content_type='application/json', **self.headers)
        self.assertTrue(resp.json().get('idempotent'))
        self.assertEqual(WhatsAppMessage.objects.filter(
            wa_message_id='wamid.test2').count(), 1)

    def test_mark_failed_guarda_el_error(self):
        r = self._recordatorio()
        resp = self.client.post(
            '/api/whatsapp/luna-nudges/mark-failed',
            data=json.dumps({'recordatorio_id': r.id, 'error': 'número inválido'}),
            content_type='application/json', **self.headers)
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertEqual(r.estado, 'fallido')
        self.assertEqual(r.error, 'número inválido')

    def test_sin_api_key_rechaza(self):
        resp = self.client.get('/api/whatsapp/pending-luna-nudges')
        self.assertIn(resp.status_code, (401, 403))


class SilencioOkTest(TestCase):

    def test_umbral_por_tipo(self):
        _entrante('s1', '+56966666666', horas_atras=3)
        # 3h de silencio: alcanza para el urgente (≥2h), no para el suave (≥4h).
        self.assertTrue(silencio_ok('+56966666666', AHORA, 'cotizacion_por_vencer'))
        self.assertFalse(silencio_ok('+56966666666', AHORA, 'cotizacion_lista'))
