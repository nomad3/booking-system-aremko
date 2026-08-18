# -*- coding: utf-8 -*-
"""Embudo de conversaciones de Luna (P-30, Fase 1).

Lo que clava esta suite:

· El estado se calcula al vuelo — una `pendiente` vencida cuenta como expirada
  aunque el comando de expiración nunca haya corrido. Sin esto el tablero
  miente el día que el cron falla, y en silencio.
· Rechazada y expirada NO se mezclan: son problemas distintos (oferta vs
  seguimiento) y la plata de cada una se informa por separado.
· Solo WhatsApp; Instagram no entra.
· Los salientes no crean conversación (si no, una campaña inflaría el embudo).
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from ventas.models import Cliente, Servicio, WhatsAppMessage
from whatsapp_agent.embudo import embudo, estado_efectivo, servicios_que_mueren
from whatsapp_agent.models import PropuestaReserva

AHORA = timezone.now()
HOY = timezone.localdate()
DESDE = HOY - timedelta(days=30)


def _propuesta(pid, estado='pendiente', vence_h=24, total=50000, dias_atras=1,
               servicios=None, canal='whatsapp', payload=None):
    p = PropuestaReserva.objects.create(
        propuesta_id=pid, idempotency_key=pid, canal=canal,
        external_id='+56911111111', payload=payload or {}, cliente_data={},
        servicios=servicios or [], total=total, estado=estado,
        expires_at=AHORA + timedelta(hours=vence_h))
    # created_at es auto_now_add: se corrige después para poder ubicarla en el tiempo.
    PropuestaReserva.objects.filter(pk=p.pk).update(
        created_at=AHORA - timedelta(days=dias_atras))
    p.refresh_from_db()
    return p


def _mensaje(wid, phone, direction='in', dias_atras=1):
    return WhatsAppMessage.objects.create(
        wa_message_id=wid, phone=phone, direction=direction, body='hola',
        timestamp=AHORA - timedelta(days=dias_atras))


class EstadoEfectivoTest(TestCase):

    def test_pendiente_vencida_cuenta_como_expirada(self):
        self.assertEqual(
            estado_efectivo('pendiente', AHORA - timedelta(hours=1), AHORA),
            'expirada')

    def test_pendiente_vigente_sigue_pendiente(self):
        self.assertEqual(
            estado_efectivo('pendiente', AHORA + timedelta(hours=5), AHORA),
            'pendiente')

    def test_una_creada_vencida_sigue_siendo_venta(self):
        # Vencer no deshace una reserva: pisarla borraría la conversión.
        self.assertEqual(
            estado_efectivo('creada', AHORA - timedelta(days=9), AHORA), 'creada')


class EmbudoTest(TestCase):

    def test_los_tres_escalones_y_sus_tasas(self):
        _mensaje('m1', '+56911111111')
        _mensaje('m2', '+56922222222')
        _propuesta('p1', estado='creada')
        _propuesta('p2', estado='descartada')
        d = embudo(DESDE, HOY, AHORA)
        self.assertEqual(d['conversaciones'], 2)
        self.assertEqual(d['cotizaciones'], 2)
        self.assertEqual(d['reservas'], 1)
        self.assertEqual(d['pct_cotiza_a_reserva'], 50.0)
        self.assertEqual(d['pct_conv_a_reserva'], 50.0)

    def test_la_pendiente_vencida_pesa_como_expirada_sin_correr_el_cron(self):
        _propuesta('viva', estado='pendiente', vence_h=5, total=10000)
        _propuesta('muerta', estado='pendiente', vence_h=-48, total=90000)
        d = embudo(DESDE, HOY, AHORA)
        estados = {e['estado']: e for e in d['por_estado']}
        self.assertEqual(estados['expirada']['n'], 1)
        self.assertEqual(estados['expirada']['plata'], 90000)
        self.assertEqual(estados['pendiente']['n'], 1)
        # Y en la base sigue diciendo 'pendiente': el tablero no la tocó.
        self.assertEqual(
            PropuestaReserva.objects.get(propuesta_id='muerta').estado, 'pendiente')

    def test_rechazada_y_expirada_no_se_mezclan(self):
        _propuesta('rech', estado='descartada', total=30000)
        _propuesta('exp', estado='pendiente', vence_h=-48, total=70000)
        d = embudo(DESDE, HOY, AHORA)
        self.assertEqual(d['plata_rechazada'], 30000)
        self.assertEqual(d['plata_sin_decision'], 70000)
        self.assertEqual(d['plata_perdida'], 100000)

    def test_instagram_no_entra(self):
        _propuesta('ig', estado='creada', canal='instagram')
        self.assertEqual(embudo(DESDE, HOY, AHORA)['cotizaciones'], 0)

    def test_los_salientes_no_crean_conversacion(self):
        # Si contaran, un blast de campaña inflaría el embudo y bajaría la tasa.
        _mensaje('out1', '+56933333333', direction='out')
        self.assertEqual(embudo(DESDE, HOY, AHORA)['conversaciones'], 0)

    def test_el_mensaje_de_prueba_de_meta_queda_fuera(self):
        # La fila real de prod: 2017, +1 631 555 1181, el webhook de prueba.
        WhatsAppMessage.objects.create(
            wa_message_id='meta-test', phone='+16315551181', direction='in',
            body='test', timestamp=timezone.make_aware(
                timezone.datetime(2017, 9, 8, 20, 36)))
        d = embudo(date(2017, 1, 1), HOY, AHORA)
        self.assertEqual(d['conversaciones'], 0)
        self.assertEqual(d['desde'], date(2026, 6, 1))

    def test_un_telefono_con_varios_mensajes_es_una_conversacion(self):
        _mensaje('a', '+56911111111')
        _mensaje('b', '+56911111111')
        _mensaje('c', '+56911111111')
        self.assertEqual(embudo(DESDE, HOY, AHORA)['conversaciones'], 1)


class ServiciosQueMuerenTest(TestCase):

    def setUp(self):
        self.tina = Servicio.objects.create(
            nombre='Tina Hidromasaje Llaima', tipo_servicio='tina',
            precio_base=30000, duracion=120, capacidad_maxima=4,
            capacidad_minima=1)

    def test_solo_cuenta_las_caidas(self):
        _propuesta('viva', estado='creada',
                   servicios=[{'servicio_id': self.tina.id}])
        _propuesta('muerta', estado='descartada',
                   servicios=[{'servicio_id': self.tina.id}])
        filas = servicios_que_mueren(list(PropuestaReserva.objects.all()), AHORA)
        self.assertEqual(filas, [{'nombre': 'Tina Hidromasaje Llaima', 'n': 1}])

    def test_el_mismo_servicio_repetido_en_una_cotizacion_cuenta_una_vez(self):
        _propuesta('m', estado='descartada', servicios=[
            {'servicio_id': self.tina.id}, {'servicio_id': self.tina.id}])
        filas = servicios_que_mueren(list(PropuestaReserva.objects.all()), AHORA)
        self.assertEqual(filas[0]['n'], 1)

    def test_las_giftcards_van_a_su_propia_fila(self):
        # No llevan servicio_id; sin esto desaparecerían del análisis.
        _propuesta('gc', estado='descartada', servicios=[],
                   payload={'giftcards': [{'experiencia_id': 'tinas'}]})
        filas = servicios_que_mueren(list(PropuestaReserva.objects.all()), AHORA)
        self.assertEqual(filas, [{'nombre': 'Gift Card', 'n': 1}])


class PaginaTest(TestCase):
    """El template renderiza y está cerrado al público.

    Los tests de arriba prueban los números; este prueba la PÁGINA — un
    template roto no los haría fallar.
    """

    URL = '/ventas/analytics/embudo-luna/'

    def test_pide_login(self):
        resp = self.client.get(self.URL)
        self.assertIn(resp.status_code, (302, 403))
        if resp.status_code == 302:
            self.assertIn('login', resp['Location'])

    def test_renderiza_para_staff_con_datos(self):
        from django.contrib.auth.models import User
        User.objects.create_superuser('jefe', 'j@aremko.cl', 'x')
        self.client.login(username='jefe', password='x')
        _mensaje('m1', '+56911111111')
        _propuesta('p1', estado='creada', total=120000)
        _propuesta('p2', estado='pendiente', vence_h=-48, total=80000)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.content.decode()
        self.assertIn('Embudo de Luna', cuerpo)
        self.assertIn('Expiró sin decisión', cuerpo)   # la vencida se muestra separada
        # Formato chileno: punto de miles. `intcomma` con locale es imprime
        # «80 000» con espacio, que acá se lee mal.
        self.assertIn('$80.000', cuerpo)

    def test_ventana_invalida_cae_al_default(self):
        from django.contrib.auth.models import User
        User.objects.create_superuser('jefe2', 'j2@aremko.cl', 'x')
        self.client.login(username='jefe2', password='x')
        self.assertEqual(self.client.get(self.URL + '?dias=abc').status_code, 200)
        self.assertEqual(self.client.get(self.URL + '?dias=9999').status_code, 200)


class EnlaceEnElAdminTest(TestCase):
    """El tablero tiene que ser ALCANZABLE, no solo existir.

    La primera versión quedó publicada sin enlace en ninguna parte: Jorge entró
    al admin y no lo encontró. Una página que hay que saber de memoria para
    visitarla no existe.
    """

    def _entrar(self):
        from django.contrib.auth.models import User
        User.objects.create_superuser('jefa', 'jefa@aremko.cl', 'x')
        self.client.login(username='jefa', password='x')

    def test_la_portada_del_admin_enlaza_el_embudo(self):
        self._entrar()
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/ventas/analytics/embudo-luna/', resp.content.decode())

    def test_la_seccion_crm_tambien_lo_enlaza(self):
        # Es donde Jorge entró a buscarlo: el botón de la portada no le bastó
        # porque él navega hacia ADENTRO de CRM y Marketing.
        self._entrar()
        resp = self.client.get('/ventas/admin/section/crm/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/ventas/analytics/embudo-luna/', resp.content.decode())
