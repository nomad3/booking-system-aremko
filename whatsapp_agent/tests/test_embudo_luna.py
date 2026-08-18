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
from whatsapp_agent.embudo import (candidatos_sin_cotizar, embudo,
                                   estado_efectivo, servicios_que_mueren,
                                   temas_de_las_caidas, ventanas_de_7_dias)
from whatsapp_agent.models import PropuestaReserva, TemaConversacion
from whatsapp_agent.temas import VERSION_TAXONOMIA

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


class VentanasDe7DiasTest(TestCase):
    """Todas las ventanas duran 7 días, ancladas a hoy y hacia atrás.

    Con semanas de calendario la primera y la última siempre quedaban a medias
    y sus porcentajes se leían como caídas (5,6% y 7,8% contra un ~12% estable).
    Jorge pidió ventanas móviles: «la última, la vigente, los últimos 7 días y
    así hacia atrás».
    """

    def test_todas_duran_exactamente_7_dias(self):
        vs = ventanas_de_7_dias(date(2026, 6, 1), date(2026, 8, 18))
        self.assertTrue(vs)
        for ini, fin in vs:
            self.assertEqual((fin - ini).days, 6)

    def test_la_ultima_termina_hoy(self):
        hasta = date(2026, 8, 18)
        vs = ventanas_de_7_dias(date(2026, 6, 1), hasta)
        self.assertEqual(vs[-1], (date(2026, 8, 12), hasta))

    def test_no_se_pisan_ni_dejan_huecos(self):
        vs = ventanas_de_7_dias(date(2026, 6, 1), date(2026, 8, 18))
        for (_, fin_previa), (ini_sig, _) in zip(vs, vs[1:]):
            self.assertEqual(ini_sig - fin_previa, timedelta(days=1))

    def test_los_dias_sobrantes_se_descartan_y_se_informan(self):
        # 10 días dan una sola ventana de 7; los 3 más viejos quedan fuera.
        desde, hasta = date(2026, 8, 9), date(2026, 8, 18)
        vs = ventanas_de_7_dias(desde, hasta)
        self.assertEqual(len(vs), 1)
        d = embudo(desde, hasta, AHORA)
        self.assertEqual(d['dias_descartados'], 3)

    def test_menos_de_7_dias_no_da_ninguna_ventana(self):
        self.assertEqual(
            ventanas_de_7_dias(date(2026, 8, 15), date(2026, 8, 18)), [])


class CandidatosSinCotizarTest(TestCase):
    """Fuente única del comando `clasificar_conversaciones` y del panel de
    temas: si esta definición cambia, cambia en los dos lugares a la vez."""

    def test_escribio_pero_nunca_cotizo_es_candidato(self):
        for i in range(4):
            _mensaje(f'a{i}', '+56911111111', dias_atras=3)
        candidatos = candidatos_sin_cotizar(DESDE, HOY)
        self.assertEqual([t for t, _, _ in candidatos], ['+56911111111'])

    def test_el_que_ya_cotizo_no_es_candidato_aunque_sea_de_otro_mes(self):
        for i in range(4):
            _mensaje(f'b{i}', '+56922222222', dias_atras=3)
        # La cotización es VIEJA, de fuera de la ventana — igual lo saca:
        # ya se resolvió, no es una venta perdida de esta ventana.
        _propuesta('vieja', canal='whatsapp', dias_atras=90)
        PropuestaReserva.objects.filter(propuesta_id='vieja').update(
            external_id='+56922222222')
        candidatos = candidatos_sin_cotizar(DESDE, HOY)
        self.assertEqual(candidatos, [])

    def test_menos_del_minimo_de_mensajes_no_es_candidato(self):
        _mensaje('c0', '+56933333333', dias_atras=3)
        self.assertEqual(candidatos_sin_cotizar(DESDE, HOY, min_mensajes=4), [])
        self.assertEqual(
            [t for t, _, _ in candidatos_sin_cotizar(DESDE, HOY, min_mensajes=1)],
            ['+56933333333'])


class TemasDeLasCaidasTest(TestCase):

    def _candidato(self, tel, n=4):
        for i in range(n):
            _mensaje(f'{tel}-{i}', tel, dias_atras=3)

    def test_reparte_por_tema_con_porcentaje(self):
        self._candidato('+56911111111')
        self._candidato('+56922222222')
        TemaConversacion.objects.create(
            telefono='+56911111111', tema='sin_cupo', confianza='alta',
            version_taxonomia=VERSION_TAXONOMIA)
        TemaConversacion.objects.create(
            telefono='+56922222222', tema='sin_cupo', confianza='alta',
            version_taxonomia=VERSION_TAXONOMIA)
        d = temas_de_las_caidas(DESDE, HOY)
        self.assertEqual(d['temas'], [{'tema': 'sin_cupo',
                                       'nombre': 'Quería una fecha u hora que no había',
                                       'n': 2, 'pct': 100.0}])

    def test_declara_su_cobertura_cuando_falta_clasificar(self):
        self._candidato('+56911111111')
        self._candidato('+56922222222')
        TemaConversacion.objects.create(
            telefono='+56911111111', tema='sin_cupo', confianza='alta',
            version_taxonomia=VERSION_TAXONOMIA)
        # +56922222222 quedó SIN clasificar.
        d = temas_de_las_caidas(DESDE, HOY)
        self.assertEqual(d['total_sin_cotizar'], 2)
        self.assertEqual(d['total_clasificadas'], 1)
        self.assertEqual(d['faltan_clasificar'], 1)
        self.assertEqual(d['cobertura_pct'], 50.0)

    def test_taxonomia_vieja_no_cuenta_como_clasificada(self):
        # Mismo principio que el comando: una fila v1 no puede sumar en un
        # informe que lee categorías v2 — mezclaría cosas que ya no significan
        # lo mismo.
        self._candidato('+56911111111')
        TemaConversacion.objects.create(
            telefono='+56911111111', tema='sin_cupo', confianza='alta',
            version_taxonomia=VERSION_TAXONOMIA - 1)
        d = temas_de_las_caidas(DESDE, HOY)
        self.assertEqual(d['total_clasificadas'], 0)
        self.assertEqual(d['temas'], [])

    def test_sin_candidatos_la_cobertura_es_cero_y_no_revienta(self):
        d = temas_de_las_caidas(DESDE, HOY)
        self.assertEqual(d, {'temas': [], 'total_sin_cotizar': 0,
                             'total_clasificadas': 0, 'faltan_clasificar': 0,
                             'cobertura_pct': 0.0})

    def test_el_embudo_completo_incluye_los_temas(self):
        self._candidato('+56911111111')
        TemaConversacion.objects.create(
            telefono='+56911111111', tema='freno_en_los_datos', confianza='alta',
            version_taxonomia=VERSION_TAXONOMIA)
        d = embudo(DESDE, HOY, AHORA)
        self.assertEqual(d['temas_que_no_cotizan'][0]['tema'], 'freno_en_los_datos')
        self.assertEqual(d['temas_total_sin_cotizar'], 1)
