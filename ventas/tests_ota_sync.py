# -*- coding: utf-8 -*-
"""Importación de calendarios OTA (H-106 Fase 2, P-27).

Lo que estos tests clavan, en orden de gravedad:

· **Espejar, no acumular** — la cancelación en Booking LIBERA la noche acá.
  Un importador que solo suma cierra la cabaña para siempre en silencio.
· **Lectura fallida no toca nada** — una caída de Booking no puede liberar
  noches vendidas reconstruyendo con un feed a medias.
· **Sin eco** — el bloqueo importado NO vuelve a salir en nuestro .ics.
· Los bloqueos manuales de Jorge jamás se tocan ni dejan de exportarse.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from ventas.ical import tramos_ocupados
from ventas.models import (CalendarioCabana, Cliente, ReservaServicio,
                           ServicioBloqueo, VentaReserva)
from ventas.ota_sync import (MOTIVO_PREFIJO_OTA, espejar_cabana, parsear_ics,
                             sincronizar_todo)
from ventas.tests_ical_cabanas import _cabana
from whatsapp_agent.tests.test_giftcards_luna import _SinSenalesDeVenta

HOY = date(2026, 8, 16)


def _ics(*eventos):
    """VCALENDAR mínimo estilo Booking, con CRLF como llega de verdad."""
    lineas = ['BEGIN:VCALENDAR', 'VERSION:2.0',
              'PRODID:-//BookingSync//Test//EN']
    for inicio, fin, uid in eventos:
        lineas += ['BEGIN:VEVENT',
                   f'UID:{uid}',
                   f'DTSTART;VALUE=DATE:{inicio.strftime("%Y%m%d")}',
                   f'DTEND;VALUE=DATE:{fin.strftime("%Y%m%d")}',
                   'SUMMARY:CLOSED - Not available',
                   'END:VEVENT']
    lineas.append('END:VCALENDAR')
    return '\r\n'.join(lineas) + '\r\n'


class ParserTest(TestCase):

    def test_evento_de_dos_noches_conserva_el_fin_exclusivo(self):
        eventos = parsear_ics(_ics((date(2026, 10, 5), date(2026, 10, 7), 'abc')))
        self.assertEqual(eventos,
                         [(date(2026, 10, 5), date(2026, 10, 7), 'abc',
                           'CLOSED - Not available')])

    def test_linea_plegada_se_despliega(self):
        texto = _ics((date(2026, 10, 5), date(2026, 10, 6), 'abc'))
        plegado = texto.replace('SUMMARY:CLOSED - Not available',
                                'SUMMARY:CLOSED - Not\r\n  available')
        self.assertEqual(parsear_ics(plegado)[0][3], 'CLOSED - Not available')

    def test_sin_dtend_es_un_dia(self):
        texto = ('BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:x\r\n'
                 'DTSTART;VALUE=DATE:20261005\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n')
        self.assertEqual(parsear_ics(texto),
                         [(date(2026, 10, 5), date(2026, 10, 6), 'x', '')])

    def test_datetime_se_tolera_tomando_la_fecha(self):
        texto = ('BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:x\r\n'
                 'DTSTART:20261005T140000Z\r\nDTEND:20261007T100000Z\r\n'
                 'END:VEVENT\r\nEND:VCALENDAR\r\n')
        self.assertEqual(parsear_ics(texto)[0][:2],
                         (date(2026, 10, 5), date(2026, 10, 7)))

    def test_calendario_vacio_es_valido_y_sin_eventos(self):
        # El export de Booking sin reservas es exactamente esto.
        self.assertEqual(
            parsear_ics('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n'),
            [])

    def test_html_de_error_no_es_un_calendario(self):
        with self.assertRaises(ValueError):
            parsear_ics('<html><body>Service unavailable</body></html>')

    def test_fecha_ilegible_invalida_el_feed_entero(self):
        texto = ('BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\n'
                 'DTSTART;VALUE=DATE:corrupto\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n')
        with self.assertRaises(ValueError):
            parsear_ics(texto)


class EspejoTest(TestCase):

    def setUp(self):
        self.torre = _cabana()
        self.cal = CalendarioCabana.objects.create(servicio=self.torre)

    def _ota(self):
        return ServicioBloqueo.objects.filter(
            servicio=self.torre, motivo__startswith=MOTIVO_PREFIJO_OTA)

    def test_crea_el_bloqueo_con_fechas_inclusivas(self):
        # Booking publica 5→7 (salida el 7): las noches tomadas son 5 y 6.
        espejar_cabana(self.cal, [('Booking', date(2026, 10, 5),
                                   date(2026, 10, 7), 'u1', 'CLOSED')], hoy=HOY)
        b = self._ota().get()
        self.assertEqual((b.fecha_inicio, b.fecha_fin),
                         (date(2026, 10, 5), date(2026, 10, 6)))
        self.assertTrue(b.activo)
        self.assertIn('Booking', b.motivo)
        self.assertIn('u1', b.notas)

    def test_espeja_no_acumula(self):
        evento = ('Booking', date(2026, 10, 5), date(2026, 10, 7), 'u1', '')
        espejar_cabana(self.cal, [evento], hoy=HOY)
        espejar_cabana(self.cal, [evento], hoy=HOY)
        self.assertEqual(self._ota().count(), 1)  # dos corridas, un bloqueo

    def test_la_cancelacion_en_booking_libera_la_noche(self):
        espejar_cabana(self.cal, [('Booking', date(2026, 10, 5),
                                   date(2026, 10, 7), 'u1', '')], hoy=HOY)
        espejar_cabana(self.cal, [], hoy=HOY)  # el feed ya no trae el evento
        self.assertEqual(self._ota().count(), 0)

    def test_el_bloqueo_manual_de_jorge_no_se_toca(self):
        # `fecha`/`hora_slot` son del modelo fusionado por el class faltante
        # (P-28): NOT NULL, se llenan como en producción.
        manual = ServicioBloqueo.objects.create(
            servicio=self.torre, fecha_inicio=date(2026, 11, 1),
            fecha_fin=date(2026, 11, 3), motivo='Mantención de la tina',
            fecha=date(2026, 11, 1), hora_slot='N/A')
        espejar_cabana(self.cal, [], hoy=HOY)
        manual.refresh_from_db()
        self.assertTrue(manual.activo)

    def test_el_pasado_no_se_espeja(self):
        r = espejar_cabana(self.cal, [('Booking', HOY - timedelta(days=3),
                                       HOY - timedelta(days=1), 'u1', '')],
                           hoy=HOY)
        self.assertEqual(r['creados'], 0)

    def test_actualiza_ultima_lectura_ok(self):
        self.assertIsNone(self.cal.ultima_lectura_ok)
        espejar_cabana(self.cal, [], hoy=HOY)
        self.cal.refresh_from_db()
        self.assertIsNotNone(self.cal.ultima_lectura_ok)


class OverbookingTest(_SinSenalesDeVenta, TestCase):

    def setUp(self):
        self.torre = _cabana()
        self.cal = CalendarioCabana.objects.create(servicio=self.torre)
        cliente = Cliente.objects.create(nombre='Prueba',
                                         telefono='+56911111111')
        self.venta = VentaReserva.objects.create(cliente=cliente, total=0,
                                                 estado_reserva='confirmada')
        ReservaServicio.objects.create(
            venta_reserva=self.venta, servicio=self.torre,
            fecha_agendamiento=date(2026, 10, 5), hora_inicio='16:00',
            cantidad_personas=2)

    def test_el_choque_se_reporta_y_el_bloqueo_igual_se_crea(self):
        r = espejar_cabana(self.cal, [('Booking', date(2026, 10, 5),
                                       date(2026, 10, 6), 'u1', '')], hoy=HOY)
        # Espejo fiel: el bloqueo va igual (la OTA YA vendió esa noche)...
        self.assertEqual(r['creados'], 1)
        # ...y el choque sale con el ID para resolverlo a mano.
        self.assertEqual([o[0] for o in r['overbookings']], [self.venta.id])


class SinEcoTest(TestCase):
    """Lo importado de la OTA no puede volver a la OTA por nuestro .ics."""

    def setUp(self):
        self.torre = _cabana()
        self.cal = CalendarioCabana.objects.create(servicio=self.torre)

    def test_el_bloqueo_ota_no_se_exporta_y_el_manual_si(self):
        espejar_cabana(self.cal, [('Booking', date(2026, 10, 5),
                                   date(2026, 10, 7), 'u1', '')], hoy=HOY)
        ServicioBloqueo.objects.create(
            servicio=self.torre, fecha_inicio=date(2026, 11, 1),
            fecha_fin=date(2026, 11, 1), motivo='Mantención',
            fecha=date(2026, 11, 1), hora_slot='N/A')
        titulos = [t[3] for t in tramos_ocupados(self.torre.id)]
        self.assertEqual(titulos, ['No disponible'])  # solo el manual


class SincronizarTodoTest(TestCase):

    def setUp(self):
        self.torre = _cabana()
        self.cal = CalendarioCabana.objects.create(
            servicio=self.torre,
            url_booking='https://ical.booking.com/v1/export?t=x')

    def _ota(self):
        return ServicioBloqueo.objects.filter(
            servicio=self.torre, motivo__startswith=MOTIVO_PREFIJO_OTA)

    def test_flujo_completo_lee_y_espeja(self):
        feed = _ics((date(2026, 10, 5), date(2026, 10, 7), 'u1'))
        informes = sincronizar_todo(leer=lambda url: feed, hoy=HOY)
        self.assertEqual(self._ota().count(), 1)
        self.assertIn('1 bloqueos OTA', informes[0])

    def test_lectura_fallida_conserva_los_bloqueos_existentes(self):
        espejar_cabana(self.cal, [('Booking', date(2026, 10, 5),
                                   date(2026, 10, 7), 'u1', '')], hoy=HOY)
        lectura_previa = CalendarioCabana.objects.get(pk=self.cal.pk).ultima_lectura_ok

        def leer_roto(url):
            raise ValueError('timeout simulado')

        informes = sincronizar_todo(leer=leer_roto, hoy=HOY)
        self.assertEqual(self._ota().count(), 1)  # nada se borró
        self.assertIn('SIN CAMBIOS', informes[0])
        self.cal.refresh_from_db()
        self.assertEqual(self.cal.ultima_lectura_ok, lectura_previa)

    def test_html_de_error_tampoco_borra(self):
        espejar_cabana(self.cal, [('Booking', date(2026, 10, 5),
                                   date(2026, 10, 7), 'u1', '')], hoy=HOY)
        informes = sincronizar_todo(leer=lambda url: '<html>503</html>', hoy=HOY)
        self.assertEqual(self._ota().count(), 1)
        self.assertIn('SIN CAMBIOS', informes[0])

    def test_dry_run_no_escribe(self):
        feed = _ics((date(2026, 10, 5), date(2026, 10, 7), 'u1'))
        informes = sincronizar_todo(dry_run=True, leer=lambda url: feed, hoy=HOY)
        self.assertEqual(self._ota().count(), 0)
        self.assertIn('dry-run', informes[0])

    def test_sin_url_no_se_intenta(self):
        self.cal.url_booking = ''
        self.cal.save()
        self.assertEqual(sincronizar_todo(leer=lambda url: '', hoy=HOY), [])
