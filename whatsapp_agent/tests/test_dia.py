# -*- coding: utf-8 -*-
"""Pruebas de «Cabaña y spa por el día».

Lo que se cuida acá es la regla que hace único a este producto: exige la
cabaña libre la noche ANTERIOR y la del día. Si esa regla falla hacia el lado
permisivo, se vende un día para el que la cabaña no va a estar lista a las
10:00 de la mañana — y el cliente llega desde Osorno a una puerta cerrada.

El otro cuidado es la jerarquía de horarios: solo las combinaciones que
cierran con la tina de las 16:30 entregan las ocho horas que promete el
nombre. Ofrecer una corta habiendo una larga libre es cobrar lo mismo por
medio día menos.
"""
from datetime import date, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase

from whatsapp_agent import packs

LUNES = date(2026, 8, 31)
MARTES = date(2026, 9, 1)
MIERCOLES = date(2026, 9, 2)
DOMINGO = date(2026, 8, 30)


def _serv(sid, nombre, slots):
    return {'servicio_id': sid, 'nombre': nombre, 'slots_libres': list(slots),
            'precio_total': 100000}


CAB = [_serv(1, 'Cabaña Pucón', ['16:00'])]
MASAJES = [_serv(9, 'Masaje Relajación', ['11:45', '13:00', '14:15'])]
TINAS = [_serv(5, 'Tina Llaima', ['11:30', '14:00', '16:30'])]


def _mock(cab_previa, cab_dia, masajes=None, tinas=None):
    """Simula el motor: responde según la fecha y el tipo que le pidan."""
    def _disp(f, personas, tipo, limite=None, incluir_slots_programa=False):
        if tipo == 'cabana':
            return {'servicios': cab_dia if f == LUNES else cab_previa}
        if tipo == 'masaje':
            return {'servicios': MASAJES if masajes is None else masajes}
        return {'servicios': TINAS if tinas is None else tinas}
    return _disp


class LaReglaDeLasDosNoches(SimpleTestCase):
    """La noche anterior importa tanto como la del día, y por razones distintas:
    la anterior para que la cabaña esté lista a las 10:00, la del día porque el
    cliente la ocupa hasta la tarde."""

    def _pedir(self, cab_previa, cab_dia):
        with patch('whatsapp_agent.availability.disponibilidad',
                   side_effect=_mock(cab_previa, cab_dia)), \
             patch('whatsapp_agent.packs._desayuno_de_cabana', return_value=None):
            return packs.disponibilidad_dia(LUNES.isoformat())

    def test_libre_las_dos_noches_se_vende(self):
        r = self._pedir(CAB, CAB)
        self.assertTrue(r['disponible'], r.get('nota'))
        self.assertEqual(r['itinerario']['cabana']['nombre'], 'Cabaña Pucón')

    def test_ocupada_la_noche_anterior_NO_se_vende(self):
        """El caso peligroso: la cabaña está libre el lunes, pero alguien
        durmió el domingo y se va a las 11:00. A las 10:00 no está lista."""
        r = self._pedir([], CAB)
        self.assertFalse(r['disponible'])
        self.assertIn('noche anterior', r['nota'])

    def test_ocupada_la_noche_del_dia_NO_se_vende(self):
        r = self._pedir(CAB, [])
        self.assertFalse(r['disponible'])

    def test_tiene_que_ser_la_MISMA_cabaña(self):
        """Una libre el domingo y otra distinta el lunes no sirve: el cliente
        no se cambia de cabaña a mitad de día."""
        otra = [_serv(2, 'Cabaña Villarrica', ['16:00'])]
        r = self._pedir(otra, CAB)
        self.assertFalse(r['disponible'])


class LosDiasQueSeVenden(SimpleTestCase):
    def _pedir(self, f):
        with patch('whatsapp_agent.availability.disponibilidad',
                   side_effect=_mock(CAB, CAB)), \
             patch('whatsapp_agent.packs._desayuno_de_cabana', return_value=None):
            return packs.disponibilidad_dia(f.isoformat())

    def test_el_martes_no_se_vende(self):
        """Aremko cierra los martes por mantención."""
        r = self._pedir(MARTES)
        self.assertFalse(r['disponible'])
        self.assertIn('lunes, miércoles y jueves', r['nota'])

    def test_el_domingo_no_se_vende(self):
        """Las cabañas del sábado se desocupan a las 11:00: no alcanzan a
        prepararse para recibir a las 10:00."""
        self.assertFalse(self._pedir(DOMINGO)['disponible'])

    def test_el_miercoles_si(self):
        with patch('whatsapp_agent.availability.disponibilidad',
                   side_effect=lambda f, p, tipo, limite=None,
                   incluir_slots_programa=False: {
                       'servicios': CAB if tipo == 'cabana'
                       else (MASAJES if tipo == 'masaje' else TINAS)}), \
             patch('whatsapp_agent.packs._desayuno_de_cabana', return_value=None):
            self.assertTrue(packs.disponibilidad_dia(MIERCOLES.isoformat())['disponible'])


class LaJerarquiaDeHorarios(SimpleTestCase):
    """Solo las combinaciones con tina a las 16:30 dan las ocho horas."""

    def _pedir(self, masajes, tinas):
        with patch('whatsapp_agent.availability.disponibilidad',
                   side_effect=_mock(CAB, CAB, masajes, tinas)), \
             patch('whatsapp_agent.packs._desayuno_de_cabana', return_value=None):
            return packs.disponibilidad_dia(LUNES.isoformat())

    def test_con_todo_libre_elige_la_de_las_ocho_horas(self):
        it = self._pedir(MASAJES, TINAS)['itinerario']
        self.assertEqual(it['tina']['hora'], '16:30')
        self.assertEqual(it['masaje']['hora'], '11:45')

    def test_sin_16_30_baja_al_respaldo_y_no_inventa(self):
        """Sin la tina de las 16:30 quedan las cortas. Tiene que elegir una
        combinación REAL de la lista, no armar uno que se pise."""
        tinas = [_serv(5, 'Tina Llaima', ['11:30', '14:00'])]
        it = self._pedir(MASAJES, tinas)['itinerario']
        self.assertIn((it['masaje']['hora'], it['tina']['hora']),
                      packs.DIA_COMBINACIONES)
        self.assertNotEqual(it['tina']['hora'], '16:30')

    def test_prefiere_la_tina_estandar_sobre_la_de_hidromasaje(self):
        """Precio plano: gastar la tina cara sin necesidad se come el margen."""
        tinas = [_serv(7, 'Tina Hidromasaje Calbuco', ['16:30']),
                 _serv(5, 'Tina Llaima', ['16:30'])]
        r = self._pedir(MASAJES, tinas)
        self.assertEqual(r['itinerario']['tina']['nombre'], 'Tina Llaima')
        self.assertFalse(r['es_hidromasaje'])

    def test_sin_masaje_no_hay_programa(self):
        r = self._pedir([_serv(9, 'Masaje', [])], TINAS)
        self.assertFalse(r['disponible'])
        self.assertIn('calce', r['nota'])

    def test_no_usa_los_horarios_reservados_al_ritual(self):
        """15:30/18:00/20:30/21:45 son del Ritual y del Refugio. Este producto
        no puede quitárselos."""
        reservados = {'15:30', '18:00', '20:30', '21:45'}
        for masaje_hora, _ in packs.DIA_COMBINACIONES:
            self.assertNotIn(masaje_hora, reservados)


class ElPrecioYLaForma(SimpleTestCase):
    def test_precio_plano(self):
        self.assertEqual(packs.DIA_PRECIO_PLANO, 200000)

    def test_fecha_invalida_avisa(self):
        self.assertIn('error', packs.disponibilidad_dia('no-es-fecha'))

    def test_las_cinco_combinaciones_y_el_orden(self):
        """Las tres primeras cierran a las 16:30 —las de ocho horas— y van
        antes que las de respaldo. Si alguien reordena la lista, esto avisa."""
        self.assertEqual(len(packs.DIA_COMBINACIONES), 5)
        self.assertTrue(all(t == '16:30' for _, t in packs.DIA_COMBINACIONES[:3]))
        self.assertTrue(all(t != '16:30' for _, t in packs.DIA_COMBINACIONES[3:]))
