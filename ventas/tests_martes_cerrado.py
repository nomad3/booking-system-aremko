"""Aremko cierra los MARTES: ese día no se puede reservar por la web.

Caso real (Jorge, 2026-08-02): "el día martes lo tenemos bloqueado ya que no
existe horarios ni slot para ese día pero sigue disponible por la web. revisa
para cabaña arrayan por ejemplo".

Diagnóstico en producción: `get-available-hours` respondía bien (`[]` el martes),
pero **`check-availability` decía `available: true`** — y ese es el endpoint que
habilita el botón "Agregar al carrito".

Causa: `is_slot_available()` validaba tres cosas (día bloqueado, slot bloqueado,
reserva existente) pero **nunca que la hora fuera un slot configurado para ese día
de la semana**. Como los martes no reserva nadie, el martes siempre figuraba libre.

Ejecutar:
    python manage.py test ventas.tests_martes_cerrado
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import CategoriaServicio, Servicio
from .views.availability_views import _hhmm, hora_es_slot_del_dia, is_slot_available

# Semana de referencia: lunes 3 a domingo 9 de agosto de 2026.
LUNES, MARTES, MIERCOLES = date(2026, 8, 3), date(2026, 8, 4), date(2026, 8, 5)

# Grilla real de una cabaña: check-in fijo 16:00, SIN martes.
SLOTS_CABANA = {
    'monday': ['16:00'], 'wednesday': ['16:00'], 'thursday': ['16:00'],
    'friday': ['16:00'], 'saturday': ['16:00'], 'sunday': ['16:00'],
}


class NormalizarHoraTest(TestCase):
    """La hora llega en formatos distintos según el camino (JSON, form, ORM)."""

    def test_formatos_equivalentes(self):
        for crudo in ('16:00', '16:00:00', ' 16:00 ', '6:00'):
            esperado = '06:00' if crudo.strip().startswith('6') else '16:00'
            self.assertEqual(_hhmm(crudo), esperado, crudo)

    def test_valores_raros_no_rompen(self):
        self.assertEqual(_hhmm(None), '')
        self.assertEqual(_hhmm(''), '')


class HoraEsSlotDelDiaTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.cat = CategoriaServicio.objects.create(id=9201, nombre='Alojamientos')
        cls.arrayan = Servicio.objects.create(
            id=9211, nombre='Cabaña Arrayan', categoria=cls.cat, tipo_servicio='cabana',
            precio_base=Decimal('100000'), duracion=60, activo=True,
            publicado_web=True, slots_disponibles=SLOTS_CABANA)
        # "Sin grilla" en la práctica es {} — el campo es NOT NULL, así que None
        # no existe en la BD real.
        cls.sin_grilla = Servicio.objects.create(
            id=9212, nombre='Servicio sin horarios', categoria=cls.cat, tipo_servicio='otro',
            precio_base=Decimal('20000'), duracion=60, activo=True,
            slots_disponibles={})

    def test_el_martes_no_tiene_slot(self):
        self.assertFalse(hora_es_slot_del_dia(self.arrayan, MARTES, '16:00'))

    def test_los_demas_dias_si(self):
        for f in (LUNES, MIERCOLES):
            self.assertTrue(hora_es_slot_del_dia(self.arrayan, f, '16:00'), f)

    def test_una_hora_que_no_existe_en_la_grilla_se_rechaza(self):
        # Aunque el día opere, las 03:00 no son un slot de la cabaña.
        self.assertFalse(hora_es_slot_del_dia(self.arrayan, MIERCOLES, '03:00'))

    def test_tolera_el_formato_con_segundos(self):
        self.assertTrue(hora_es_slot_del_dia(self.arrayan, MIERCOLES, '16:00:00'))

    def test_servicio_SIN_grilla_sigue_permitido(self):
        """Permisivo a propósito: hay servicios que se venden sin horarios y
        rechazarlos los dejaría invendibles. Lo que se cierra es el caso claro
        (el servicio declara horarios pero no para ese día)."""
        for f in (LUNES, MARTES, MIERCOLES):
            self.assertTrue(hora_es_slot_del_dia(self.sin_grilla, f, '16:00'), f)


class IsSlotAvailableTest(TestCase):
    """El guardia completo, que es lo que consume el endpoint del botón."""

    @classmethod
    def setUpTestData(cls):
        cls.cat = CategoriaServicio.objects.create(id=9201, nombre='Alojamientos')
        cls.arrayan = Servicio.objects.create(
            id=9211, nombre='Cabaña Arrayan', categoria=cls.cat, tipo_servicio='cabana',
            precio_base=Decimal('100000'), duracion=60, activo=True,
            publicado_web=True, slots_disponibles=SLOTS_CABANA)

    def test_EL_CASO_REAL_martes_deja_de_estar_disponible(self):
        self.assertFalse(is_slot_available(self.arrayan, MARTES, '16:00'))

    def test_miercoles_sigue_disponible(self):
        self.assertTrue(is_slot_available(self.arrayan, MIERCOLES, '16:00'))


class EndpointCheckAvailabilityTest(TestCase):
    """El endpoint tal como lo llama el navegador."""

    @classmethod
    def setUpTestData(cls):
        cls.cat = CategoriaServicio.objects.create(id=9201, nombre='Alojamientos')
        cls.arrayan = Servicio.objects.create(
            id=9211, nombre='Cabaña Arrayan', categoria=cls.cat, tipo_servicio='cabana',
            precio_base=Decimal('100000'), duracion=60, activo=True,
            publicado_web=True, slots_disponibles=SLOTS_CABANA)

    def _check(self, fecha, hora='16:00'):
        r = self.client.get(reverse('ventas:check_slot_availability'),
                            {'servicio_id': self.arrayan.id,
                             'fecha': fecha.isoformat(), 'hora': hora})
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_martes_responde_no_disponible(self):
        self.assertEqual(self._check(MARTES), {'available': False})

    def test_miercoles_responde_disponible(self):
        self.assertEqual(self._check(MIERCOLES), {'available': True})

    def test_horas_del_martes_vienen_vacias(self):
        # El otro endpoint ya estaba bien; se fija para que siga así.
        r = self.client.get(reverse('ventas:get_available_hours'),
                            {'servicio_id': self.arrayan.id, 'fecha': MARTES.isoformat()})
        self.assertEqual(r.json()['horas_disponibles'], [])


class FiltroDiasCerradosTest(TestCase):
    """El filtro que alimenta el calendario del modal (día no elegible)."""

    def test_cabana_sin_martes_devuelve_el_indice_js_del_martes(self):
        from ventas.templatetags.ventas_extras import dias_cerrados_js
        # flatpickr usa Date.getDay(): 0=domingo … 2=martes.
        self.assertEqual(dias_cerrados_js(SLOTS_CABANA), '2')

    def test_sin_grilla_no_desactiva_nada(self):
        from ventas.templatetags.ventas_extras import dias_cerrados_js
        for valor in ({}, None, ['16:00']):
            self.assertEqual(dias_cerrados_js(valor), '', repr(valor))

    def test_abierto_todos_los_dias_no_desactiva_nada(self):
        from ventas.templatetags.ventas_extras import dias_cerrados_js
        self.assertEqual(dias_cerrados_js(dict(SLOTS_CABANA, tuesday=['16:00'])), '')
