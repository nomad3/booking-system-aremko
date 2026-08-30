"""El miércoles de «Cabaña y spa por el día» y el martes cerrado (2026-08-30).

Bug real, reportado por Jorge: ningún miércoles permitía vender el programa.
La víspera del miércoles es el martes, que está cerrado — sin slots — y el
chequeo de la noche anterior usaba disponibilidad(), que confunde «no se puede
VENDER el martes» con «la cabaña está OCUPADA el martes». Cerrado significa
vacía: lo ideal para recibir a las 10:00.

La corrección mide la víspera por OCUPACIÓN: bloqueos de día (así espeja el
iCal las noches de Booking/Airbnb), bloqueos de slot (así protege sus noches
este mismo programa) y reservas reales. Estas pruebas cubren el bug y, tan
importante como eso, que la corrección NO haya soltado la protección contra
huéspedes de verdad durmiendo la víspera.

Ejecutar:
    python manage.py test ventas.tests_dia_miercoles
"""
from __future__ import annotations

from django.test import TestCase

from ventas.models import (
    ReservaServicio, Servicio, ServicioBloqueo, ServicioSlotBloqueo,
)
from whatsapp_agent.packs import disponibilidad_dia

# Miércoles 2 y jueves 3 de septiembre de 2026; la víspera del miércoles es
# el martes 1 — cerrado, como todos los martes.
MIERCOLES = '2026-09-02'
MARTES = '2026-09-01'
JUEVES = '2026-09-03'

# Slots por día de semana, como en producción: el martes NO existe.
SIN_MARTES = {
    'monday': ['16:00'], 'wednesday': ['16:00'], 'thursday': ['16:00'],
    'friday': ['16:00'], 'saturday': ['16:00'], 'sunday': ['16:00'],
}


class MiercolesConMartesCerrado(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cabana = Servicio.objects.create(
            nombre='Cabaña Arrayán', tipo_servicio='cabana', precio_base=90000,
            duracion=60, activo=True, publicado_web=True,
            capacidad_minima=1, capacidad_maxima=4,
            slots_disponibles=SIN_MARTES)
        cls.tina = Servicio.objects.create(
            nombre='Tina Hidromasaje Puntiagudo', tipo_servicio='tina',
            precio_base=30000, duracion=120, activo=True, publicado_web=True,
            capacidad_minima=1, capacidad_maxima=4,
            slots_disponibles={'wednesday': ['11:30', '14:00', '16:30'],
                               'thursday': ['11:30', '14:00', '16:30']})
        cls.masaje = Servicio.objects.create(
            nombre='Masaje Relajación', tipo_servicio='masaje',
            precio_base=40000, duracion=50, activo=True, publicado_web=True,
            capacidad_minima=1, capacidad_maxima=4,
            slots_disponibles={'wednesday': ['11:45', '13:00', '14:15'],
                               'thursday': ['11:45', '13:00', '14:15']})

    def test_control_las_piezas_del_escenario_estan_vivas(self):
        """Control positivo: si el motor deja de ofrecer estas piezas el
        miércoles, las demás pruebas medirían un escenario muerto."""
        from whatsapp_agent.availability import disponibilidad

        for tipo in ('cabana', 'tina', 'masaje'):
            r = disponibilidad(MIERCOLES, 2, tipo, limite=None)
            self.assertTrue(r.get('servicios'),
                            f'el escenario no ofrece ningún {tipo} el miércoles')

    def test_el_miercoles_SE_VENDE_aunque_el_martes_este_cerrado(self):
        """El bug: el martes sin slots dejaba «sin cabaña libre la víspera»
        a todos los miércoles del calendario."""
        r = disponibilidad_dia(MIERCOLES)
        self.assertTrue(r.get('disponible'),
                        f"el miércoles sigue muerto: {r.get('nota')}")

    def test_un_huesped_durmiendo_la_vispera_SI_bloquea(self):
        """La contraparte que no se puede soltar: un huésped que duerme el
        martes sale a las 11:00 — choca con la llegada de las 10:00."""
        from ventas.models import Cliente, VentaReserva

        cliente = Cliente.objects.create(nombre='Huésped', telefono='+56911110000')
        venta = VentaReserva.objects.create(cliente=cliente)
        ReservaServicio.objects.create(venta_reserva=venta, servicio=self.cabana,
                                       fecha_agendamiento=MARTES,
                                       hora_inicio='16:00', cantidad_personas=2)
        r = disponibilidad_dia(MIERCOLES)
        self.assertFalse(r.get('disponible'))

    def test_una_noche_espejada_de_booking_SI_bloquea(self):
        """Las noches de Booking/Airbnb llegan como ServicioBloqueo (así las
        espeja el iCal). Ocupación real: la corrección debe respetarlas."""
        # `fecha` y `hora_slot` se llenan por el defecto ya conocido del
        # modelo (campos de otro modelo pegados) — mismo patrón que
        # tests_ical_cabanas.
        ServicioBloqueo.objects.create(servicio=self.cabana, activo=True,
                                       fecha_inicio=MARTES, fecha_fin=MARTES,
                                       motivo='Reserva Booking (iCal)',
                                       fecha=MARTES, hora_slot='N/A')
        r = disponibilidad_dia(MIERCOLES)
        self.assertFalse(r.get('disponible'))

    def test_la_noche_protegida_por_otro_programa_SI_bloquea(self):
        """bloquear_noche_previa deja ServicioSlotBloqueo: si otro día ya
        protegió esa noche, la cabaña no está para nadie más."""
        ServicioSlotBloqueo.objects.create(servicio=self.cabana, activo=True,
                                           fecha=MARTES, hora_slot='16:00',
                                           motivo='Cabaña y spa por el día')
        r = disponibilidad_dia(MIERCOLES)
        self.assertFalse(r.get('disponible'))

    def test_el_programa_del_dia_anterior_NO_bloquea_al_siguiente(self):
        """Un programa-día del miércoles usa la cabaña de 10:00 a 18:00 y deja
        la noche libre: el jueves puede venderse en la misma cabaña. La fila
        de las 10:00 es uso diurno, no un huésped durmiendo."""
        from ventas.models import Cliente, VentaReserva

        cliente = Cliente.objects.create(nombre='Del día', telefono='+56922220000')
        venta = VentaReserva.objects.create(cliente=cliente)
        ReservaServicio.objects.create(venta_reserva=venta, servicio=self.cabana,
                                       fecha_agendamiento=MIERCOLES,
                                       hora_inicio='10:00', cantidad_personas=2)
        r = disponibilidad_dia(JUEVES)
        self.assertTrue(r.get('disponible'),
                        f"el uso diurno del miércoles mató el jueves: {r.get('nota')}")
