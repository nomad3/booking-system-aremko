# -*- coding: utf-8 -*-
"""Calendario .ics por cabaña (H-106 Fase 1, Jorge 2026-08-14).

«Vincular Booking con Aremko para que las reservas que toman en Booking se
tomen en Aremko y viceversa. Esto nos evitará dobles reservas de una cabaña.»

Los casos de acá salieron de mirar producción, no de imaginar:

  · 6561 → Torre, 21 y 22 de agosto (dos noches seguidas, mismo servicio_id)
  · 6330 → Acantilado, 23 y 24 de julio
  · 6381 → Torre + «Persona Adicional» el MISMO día (1 noche, no 2)
  · 1170 → TRES cabañas distintas en una sola reserva
"""
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from ventas.ical import _bloques_consecutivos, construir_ics, tramos_ocupados
from ventas.models import (CalendarioCabana, Cliente, ReservaServicio,
                           Servicio, ServicioBloqueo, VentaReserva)
# Las señales de CRM sobre VentaReserva consultan `crm_service_history`, que no
# existe en la base de test por el drift AR-033/034: al fallar dejan la
# transacción abortada y revienta todo lo que venga después. No son el sujeto de
# estos tests. Mismo apaño que en whatsapp_agent.
from whatsapp_agent.tests.test_giftcards_luna import _SinSenalesDeVenta


def _cabana(nombre='Cabaña Torre', capacidad=2):
    return Servicio.objects.create(
        nombre=nombre, tipo_servicio='cabana', precio_base=60000, duracion=1440,
        capacidad_maxima=capacidad, capacidad_minima=1, publicado_web=True)


def _adicional(nombre='Persona Adicional en Cabaña'):
    """Los dos servicios que se cuelan con tipo_servicio='cabana'."""
    return Servicio.objects.create(
        nombre=nombre, tipo_servicio='cabana', precio_base=20000, duracion=60,
        capacidad_maxima=1, capacidad_minima=1, publicado_web=False)


class BloquesConsecutivosTest(TestCase):
    """Noches sueltas no son una estadía larga con la cabaña tomada al medio."""

    def test_dos_noches_seguidas_son_un_bloque(self):
        self.assertEqual(
            _bloques_consecutivos([date(2026, 8, 21), date(2026, 8, 22)]),
            [(date(2026, 8, 21), date(2026, 8, 22))])

    def test_noches_separadas_son_bloques_distintos(self):
        self.assertEqual(
            _bloques_consecutivos([date(2026, 8, 5), date(2026, 8, 20)]),
            [(date(2026, 8, 5), date(2026, 8, 5)),
             (date(2026, 8, 20), date(2026, 8, 20))])

    def test_sin_fechas(self):
        self.assertEqual(_bloques_consecutivos([]), [])


class TramosDeUnaCabanaTest(_SinSenalesDeVenta, TestCase):

    def setUp(self):
        self.torre = _cabana()
        self.cliente = Cliente.objects.create(nombre='Prueba',
                                              telefono='+56911111111')

    def _reserva(self, servicio, fechas, estado='confirmada'):
        v = VentaReserva.objects.create(cliente=self.cliente, total=0,
                                        estado_reserva=estado)
        for f in fechas:
            ReservaServicio.objects.create(
                venta_reserva=v, servicio=servicio, fecha_agendamiento=f,
                hora_inicio='16:00', cantidad_personas=2)
        return v

    def test_dos_noches_seguidas_son_UN_evento_que_termina_al_dia_siguiente(self):
        """El caso 6561: la salida se deriva, no está en la base."""
        v = self._reserva(self.torre, [date(2026, 8, 21), date(2026, 8, 22)])
        tramos = tramos_ocupados(self.torre.id)
        self.assertEqual(len(tramos), 1)
        inicio, fin, uid, _titulo = tramos[0]
        self.assertEqual(inicio, date(2026, 8, 21))
        self.assertEqual(fin, date(2026, 8, 23), 'DTEND es exclusivo: el 23 sale')
        self.assertIn(f'reserva-{v.id}-{self.torre.id}', uid)

    def test_el_adicional_del_mismo_dia_no_agrega_una_noche(self):
        """El caso 6381: Torre + Persona Adicional el mismo día = 1 noche."""
        extra = _adicional()
        v = self._reserva(self.torre, [date(2026, 7, 24)])
        ReservaServicio.objects.create(
            venta_reserva=v, servicio=extra,
            fecha_agendamiento=date(2026, 7, 24), hora_inicio='16:00',
            cantidad_personas=1)
        tramos = tramos_ocupados(self.torre.id)
        self.assertEqual(len(tramos), 1)
        self.assertEqual(tramos[0][1], date(2026, 7, 25))

    def test_el_calendario_del_adicional_sale_vacio(self):
        """Aunque alguien pida el .ics de «Persona Adicional», no publica
        fechas: no es un lugar donde dormir."""
        extra = _adicional()
        self._reserva(extra, [date(2026, 7, 24)])
        self.assertEqual(tramos_ocupados(extra.id), [])

    def test_dos_cabanas_en_una_reserva_no_se_pisan(self):
        """El caso 1170: cada cabaña publica SU tramo, con UID propio."""
        tepa = _cabana('Cabaña Tepa')
        v = VentaReserva.objects.create(cliente=self.cliente, total=0)
        for f in (date(2026, 8, 20), date(2026, 8, 21)):
            ReservaServicio.objects.create(venta_reserva=v, servicio=self.torre,
                                           fecha_agendamiento=f,
                                           hora_inicio='16:00', cantidad_personas=2)
        ReservaServicio.objects.create(venta_reserva=v, servicio=tepa,
                                       fecha_agendamiento=date(2026, 8, 22),
                                       hora_inicio='16:00', cantidad_personas=2)

        t_torre, t_tepa = tramos_ocupados(self.torre.id), tramos_ocupados(tepa.id)
        self.assertEqual((t_torre[0][0], t_torre[0][1]),
                         (date(2026, 8, 20), date(2026, 8, 22)))
        self.assertEqual((t_tepa[0][0], t_tepa[0][1]),
                         (date(2026, 8, 22), date(2026, 8, 23)))
        self.assertNotEqual(t_torre[0][2], t_tepa[0][2], 'UIDs distintos')

    def test_una_reserva_cancelada_libera_la_fecha(self):
        self._reserva(self.torre, [date(2026, 9, 1)], estado='cancelada')
        self.assertEqual(tramos_ocupados(self.torre.id), [])

    def test_los_bloqueos_manuales_tambien_se_publican(self):
        """93 bloqueos en producción: si no salen, Booking vende un día que
        Jorge cerró a mano."""
        # `fecha` y `hora_slot` son obligatorios por un defecto del modelo:
        # a `ServicioBloqueo` se le pegaron los campos de un segundo modelo
        # (bloqueo por slot) al que le falta la línea `class`. Se llenan para
        # que el test corra; el defecto está reportado aparte.
        ServicioBloqueo.objects.create(
            servicio=self.torre, fecha_inicio=date(2026, 10, 1),
            fecha_fin=date(2026, 10, 3), motivo='Mantenimiento',
            fecha=date(2026, 10, 1), hora_slot='16:00')
        tramos = tramos_ocupados(self.torre.id)
        self.assertEqual(len(tramos), 1)
        self.assertEqual(tramos[0][0], date(2026, 10, 1))
        self.assertEqual(tramos[0][1], date(2026, 10, 4),
                         'fecha_fin es inclusiva; DTEND es exclusivo')
        self.assertTrue(tramos[0][2].startswith('bloqueo-'))

    def test_un_bloqueo_de_UN_dia_es_una_noche(self):
        """La forma real de los 93 de producción: fecha_inicio == fecha_fin."""
        ServicioBloqueo.objects.create(
            servicio=self.torre, fecha_inicio=date(2026, 8, 13),
            fecha_fin=date(2026, 8, 13), motivo='Cerrado',
            fecha=date(2026, 8, 13), hora_slot='N/A')
        inicio, fin, _uid, _t = tramos_ocupados(self.torre.id)[0]
        self.assertEqual((inicio, fin), (date(2026, 8, 13), date(2026, 8, 14)))

    def test_un_bloqueo_desactivado_libera_la_fecha(self):
        """Publicar un bloqueo que Jorge reabrió deja la cabaña cerrada en
        Booking para siempre: se pierden ventas y nadie reclama."""
        b = ServicioBloqueo.objects.create(
            servicio=self.torre, fecha_inicio=date(2026, 11, 5),
            fecha_fin=date(2026, 11, 5), motivo='Se canceló',
            fecha=date(2026, 11, 5), hora_slot='N/A')
        ServicioBloqueo.objects.filter(pk=b.pk).update(activo=False)
        self.assertEqual(tramos_ocupados(self.torre.id), [])


class FormatoIcsTest(TestCase):
    """Lo que se le entrega a Booking tiene que ser iCal válido de verdad."""

    def _ics(self):
        return construir_ics('Cabaña Torre', [
            (date(2026, 8, 21), date(2026, 8, 23),
             'reserva-6561-3-2026-08-21@aremko.cl', 'Reservado (RES-6561)')])

    def test_estructura_minima_del_rfc(self):
        ics = self._ics()
        for obligatoria in ('BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:',
                            'BEGIN:VEVENT', 'UID:', 'DTSTAMP:', 'END:VEVENT',
                            'END:VCALENDAR'):
            self.assertIn(obligatoria, ics)

    def test_fechas_de_dia_completo_y_fin_exclusivo(self):
        ics = self._ics()
        self.assertIn('DTSTART;VALUE=DATE:20260821', ics)
        self.assertIn('DTEND;VALUE=DATE:20260823', ics)

    def test_las_lineas_terminan_en_crlf(self):
        """El RFC lo exige y hay lectores que se ponen quisquillosos."""
        ics = self._ics()
        self.assertTrue(ics.endswith('\r\n'))
        self.assertNotIn('\n\n', ics)
        for linea in ics.split('\r\n'):
            self.assertNotIn('\n', linea)

    def test_no_se_filtra_el_nombre_del_huesped(self):
        """El .ics queda en manos de Booking: va el número de reserva y nada
        más. Ni nombre, ni teléfono, ni cuánto pagó."""
        ics = construir_ics('Cabaña Torre', [
            (date(2026, 8, 21), date(2026, 8, 22), 'reserva-1-3-x@aremko.cl',
             'Reservado (RES-1)')])
        self.assertIn('RES-1', ics)
        for filtracion in ('@gmail', '+569', 'telefono', 'total'):
            self.assertNotIn(filtracion, ics.lower())


class UrlDelCalendarioTest(_SinSenalesDeVenta, TestCase):

    def setUp(self):
        self.torre = _cabana()
        self.cal = CalendarioCabana.objects.create(servicio=self.torre)

    def test_el_token_abre_el_calendario_sin_login(self):
        """Booking lo lee sin sesión: por eso el secreto va en la URL."""
        r = self.client.get(f'/ventas/ical/{self.cal.token}/cabana-torre.ics')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/calendar', r['Content-Type'])
        self.assertIn('BEGIN:VCALENDAR', r.content.decode())

    def test_un_token_que_no_existe_da_404(self):
        r = self.client.get('/ventas/ical/token-inventado/cabana-torre.ics')
        self.assertEqual(r.status_code, 404)

    def test_desactivar_corta_la_url(self):
        CalendarioCabana.objects.filter(pk=self.cal.pk).update(activo=False)
        r = self.client.get(f'/ventas/ical/{self.cal.token}/cabana-torre.ics')
        self.assertEqual(r.status_code, 404)

    def test_no_se_cachea(self):
        """Si Booking cachea, la ventana de doble venta se agranda."""
        r = self.client.get(f'/ventas/ical/{self.cal.token}/cabana-torre.ics')
        self.assertIn('no-store', r['Cache-Control'])

    def test_cada_cabana_tiene_su_propio_token(self):
        otra = CalendarioCabana.objects.create(servicio=_cabana('Cabaña Tepa'))
        self.assertNotEqual(self.cal.token, otra.token)

    def test_no_se_publica_la_ocupacion_vieja(self):
        """En la primera prueba real (Torre) el .ics traía 211 eventos y 208
        eran de fechas pasadas: 40 KB en cada lectura de Booking, y el
        histórico de ocupación de la cabaña regalado a un tercero. Las OTAs
        ignoran el pasado; no hay razón para mandárselo."""
        cliente = Cliente.objects.create(nombre='Viejo', telefono='+56922222222')
        v = VentaReserva.objects.create(cliente=cliente, total=0)
        ReservaServicio.objects.create(
            venta_reserva=v, servicio=self.torre,
            fecha_agendamiento=date(2024, 3, 10), hora_inicio='16:00',
            cantidad_personas=2)
        cuerpo = self.client.get(
            f'/ventas/ical/{self.cal.token}/cabana-torre.ics').content.decode()
        self.assertNotIn('20240310', cuerpo)

    def test_el_huesped_que_sigue_alojado_no_se_corta(self):
        """Llegó antes de la ventana pero todavía no se va: sus noches
        pendientes TIENEN que seguir bloqueadas."""
        from django.utils import timezone as tz
        hoy = tz.localdate()
        cliente = Cliente.objects.create(nombre='Sigue', telefono='+56933333333')
        v = VentaReserva.objects.create(cliente=cliente, total=0)
        for delta in (-2, -1, 0, 1):
            ReservaServicio.objects.create(
                venta_reserva=v, servicio=self.torre,
                fecha_agendamiento=hoy + timedelta(days=delta),
                hora_inicio='16:00', cantidad_personas=2)
        cuerpo = self.client.get(
            f'/ventas/ical/{self.cal.token}/cabana-torre.ics').content.decode()
        self.assertIn((hoy + timedelta(days=2)).strftime('%Y%m%d'), cuerpo,
                      'la salida del que sigue alojado tiene que aparecer')

    def test_regenerar_el_token_invalida_la_url_vieja(self):
        viejo = self.cal.token
        nuevo = self.cal.regenerar_token()
        self.assertNotEqual(viejo, nuevo)
        self.assertEqual(
            self.client.get(f'/ventas/ical/{viejo}/cabana-torre.ics').status_code,
            404)
        self.assertEqual(
            self.client.get(f'/ventas/ical/{nuevo}/cabana-torre.ics').status_code,
            200)
