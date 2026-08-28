# -*- coding: utf-8 -*-
"""Que «Cabaña y spa por el día» no se cuente como Ritual del Río.

Los dos programas tienen los MISMOS componentes —cabaña, tina y masaje— y una
sola fecha de cabaña, así que sin una señal propia el día caería en el Ritual.
El daño sería doble: no se mediría lo nuevo, y el Ritual mostraría un
crecimiento que no es suyo. Nadie podría saber cuál de los dos se vende.

La señal es la hora de la cabaña: el día recibe a las 10:00 de la mañana; el
Ritual y el Refugio reservan a las 16:00, que es el check-in.
"""
from datetime import date

from django.test import TestCase

from ventas.api_aremko_cli import (DIA_HORA_CABANA, PROGRAMA_LABELS,
                                   clasificar_ventareservas_por_programa)
from ventas.models import Cliente, ReservaServicio, Servicio, VentaReserva

DIA = date(2026, 8, 31)


class _SinSenalesDeVenta:
    """Evita que crear VentaReserva a mano dispare las señales del sistema."""


class ElDiaNoSeCuentaComoRitual(TestCase):

    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Pedro', telefono='+56911111111')
        self.cab = Servicio.objects.create(nombre='Cabaña Pucón', precio_base=120000,
                                           duracion=60, tipo_servicio='cabana')
        self.tina = Servicio.objects.create(nombre='Tina Llaima', precio_base=50000,
                                            duracion=120, tipo_servicio='tina')
        self.mas = Servicio.objects.create(nombre='Masaje', precio_base=40000,
                                           duracion=50, tipo_servicio='masaje')

    def _venta(self, hora_cabana):
        v = VentaReserva.objects.create(cliente=self.cliente)
        for serv, hora in ((self.cab, hora_cabana), (self.tina, '16:30'),
                           (self.mas, '11:45')):
            ReservaServicio.objects.create(venta_reserva=v, servicio=serv,
                                           fecha_agendamiento=DIA, hora_inicio=hora)
        return v

    def test_la_cabaña_a_las_10_es_el_programa_del_dia(self):
        v = self._venta(DIA_HORA_CABANA)
        self.assertEqual(clasificar_ventareservas_por_programa([v.id])[v.id], 'dia')

    def test_la_cabaña_a_las_16_sigue_siendo_ritual(self):
        """La regla nueva no puede robarle ventas al Ritual: mismos
        componentes, distinta hora de llegada."""
        v = self._venta('16:00')
        self.assertEqual(clasificar_ventareservas_por_programa([v.id])[v.id], 'ritual')

    def test_conviven_sin_mezclarse(self):
        dia, ritual = self._venta(DIA_HORA_CABANA), self._venta('16:00')
        r = clasificar_ventareservas_por_programa([dia.id, ritual.id])
        self.assertEqual(r[dia.id], 'dia')
        self.assertEqual(r[ritual.id], 'ritual')

    def test_el_programa_tiene_etiqueta_propia(self):
        """Sin etiqueta, el tablero reventaría al buscar su fila."""
        claves = dict(PROGRAMA_LABELS)
        self.assertIn('dia', claves)
        self.assertIn('día', claves['dia'].lower())

    def test_una_tina_sola_a_las_10_no_es_el_programa(self):
        """La señal es la CABAÑA a las 10:00, no cualquier servicio."""
        v = VentaReserva.objects.create(cliente=self.cliente)
        ReservaServicio.objects.create(venta_reserva=v, servicio=self.tina,
                                       fecha_agendamiento=DIA, hora_inicio='10:00')
        self.assertNotEqual(clasificar_ventareservas_por_programa([v.id]).get(v.id), 'dia')


class ElPaseDelCliente(TestCase):
    """El pase es lo que el cliente lee el día que viene. Dos cosas fallaron
    ahí y las dos las vio Jorge probando en vivo: los servicios salían en el
    orden en que se creó la reserva (la tina de las 16:30 antes del masaje de
    las 14:15) y el título decía «Ritual del Río», que es otro producto y sí
    incluye la noche."""

    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Pedro', telefono='+56911111111')
        self.cab = Servicio.objects.create(nombre='Cabaña Acantilado', precio_base=110000,
                                           duracion=60, tipo_servicio='cabana')
        self.tina = Servicio.objects.create(nombre='Tina Hidromasaje Llaima', precio_base=60000,
                                            duracion=120, tipo_servicio='tina')
        self.mas = Servicio.objects.create(nombre='Masaje Relajación', precio_base=80000,
                                           duracion=50, tipo_servicio='masaje')

    def _venta(self, hora_cabana='10:00'):
        v = VentaReserva.objects.create(cliente=self.cliente)
        # A propósito en el MISMO orden en que las crea la cotización del día:
        # cabaña, tina, masaje. Si el pase no ordena, sale así.
        for serv, hora in ((self.cab, hora_cabana), (self.tina, '16:30'), (self.mas, '14:15')):
            ReservaServicio.objects.create(venta_reserva=v, servicio=serv,
                                           fecha_agendamiento=DIA, hora_inicio=hora)
        return v

    def test_los_servicios_salen_en_orden_cronologico(self):
        from ventas.views.ficha_reserva_view import _lineas_servicios
        nombres = [l['nombre'] for l in _lineas_servicios(self._venta())]
        self.assertEqual(nombres, ['Cabaña Acantilado', 'Masaje Relajación',
                                   'Tina Hidromasaje Llaima'])

    def test_el_descuento_va_al_final_aunque_tenga_hora_temprana(self):
        """Lleva fecha y hora de relleno; ordenar por hora lo subiría arriba."""
        from ventas.views.ficha_reserva_view import _lineas_servicios
        v = self._venta()
        desc = Servicio.objects.create(nombre='Descuento_Servicios', precio_base=-50000,
                                       duracion=1, tipo_servicio='otro')
        ReservaServicio.objects.create(venta_reserva=v, servicio=desc,
                                       fecha_agendamiento=DIA, hora_inicio='10:00')
        self.assertEqual(_lineas_servicios(v)[-1]['nombre'], 'Descuento')

    def test_el_titulo_dice_el_programa_del_dia(self):
        from ventas.views.ficha_reserva_view import _experiencia_nombre
        self.assertEqual(
            _experiencia_nombre(['cabana', 'tina', 'masaje'], '10:00'),
            'Cabaña y spa por el día')

    def test_el_titulo_del_ritual_no_cambia(self):
        """La regla nueva no puede robarle el nombre al Ritual."""
        from ventas.views.ficha_reserva_view import _experiencia_nombre
        self.assertEqual(
            _experiencia_nombre(['cabana', 'tina', 'masaje'], '16:00'),
            'Ritual del Río')

    def test_sin_hora_sigue_siendo_ritual(self):
        """Las reservas viejas no traen la hora al llamador: no pueden cambiar
        de nombre por este arreglo."""
        from ventas.views.ficha_reserva_view import _experiencia_nombre
        self.assertEqual(
            _experiencia_nombre(['cabana', 'tina', 'masaje']), 'Ritual del Río')

    def test_el_refugio_tampoco_cambia(self):
        from ventas.views.ficha_reserva_view import _experiencia_nombre
        self.assertEqual(
            _experiencia_nombre(['cabana', 'cabana', 'tina', 'masaje'], '10:00'),
            'Refugio Aremko')
