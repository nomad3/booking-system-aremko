"""Las cabañas del día siguen visibles en la Agenda Operativa hasta la noche.

Reportado por Jorge (2026-08-31): pasadas las 16:00 las cabañas desaparecían
del listado. El personal que entra en el turno de tarde abría la agenda, no
veía ninguna cabaña y concluía que no había huéspedes alojados.

La causa: la agenda trataba la cabaña como cualquier servicio con duración
—«termina» a la hora de inicio + duración— cuando en realidad el huésped se
queda a dormir. Dos síntomas del mismo error: desaparecía del filtro por
defecto y, si se la forzaba a aparecer, salía marcada «✓ COMPLETADO».

Ejecutar:
    python manage.py test ventas.tests_agenda_cabanas_todo_el_dia
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import Cliente, ReservaServicio, Servicio, VentaReserva
from ventas.views.agenda_operativa_view import es_alojamiento


class LasCabanasNoDesaparecenALas16(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='agenda_cab', email='a@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Familia Soto',
                                         telefono='+56911111111')
        hoy = timezone.localdate()

        # Una cabaña de verdad: capacidad 2 (ver CAPACIDAD_MINIMA_ALOJAMIENTO).
        cls.cabana = Servicio.objects.create(
            nombre='Cabaña Tepa', precio_base=90000, duracion=60,
            tipo_servicio='cabana', capacidad_maxima=2)
        # Un servicio normal que SÍ termina: la tina.
        tina = Servicio.objects.create(
            nombre='Tina Calbuco', precio_base=60000, duracion=60,
            tipo_servicio='tina', capacidad_maxima=6)
        # Un modificador de precio marcado 'cabana' pero que NO es alojamiento.
        cls.adicional = Servicio.objects.create(
            nombre='Persona Adicional en Cabaña', precio_base=25000, duracion=60,
            tipo_servicio='cabana', capacidad_maxima=1)

        venta = VentaReserva.objects.create(cliente=cliente)
        for servicio in (cls.cabana, tina, cls.adicional):
            ReservaServicio.objects.create(
                venta_reserva=venta, servicio=servicio,
                fecha_agendamiento=hoy, hora_inicio='16:00')

    def setUp(self):
        self.client.force_login(self.staff)

    def _agenda_a_las(self, hora):
        """La agenda tal como la ve alguien que la abre a esa hora."""
        return self.client.get(reverse('ventas:agenda_operativa'),
                               {'desde_hora': hora})

    def test_a_las_19_la_cabana_sigue_en_la_lista(self):
        html = self._agenda_a_las('19:00').content.decode()
        self.assertIn('Cabaña Tepa', html,
                      'la cabaña desapareció del turno de tarde: es justo el '
                      'error que hacía creer que no había huéspedes')

    def test_a_las_19_la_cabana_no_dice_COMPLETADO(self):
        html = self._agenda_a_las('19:00').content.decode()
        i = html.find('Cabaña Tepa')
        # Control: sin esta línea, cuando la cabaña desaparece la prueba pasa
        # por vacía — buscaba una etiqueta al lado de algo que no está.
        self.assertNotEqual(i, -1, 'la cabaña no está en la página')
        bloque = html[max(0, i - 3000):i + 500]
        self.assertNotIn('COMPLETADO', bloque,
                         'mostrarla marcada como completada engaña igual que '
                         'ocultarla')

    def test_la_tina_si_desaparece_cuando_termina(self):
        # El arreglo es para el alojamiento, no una amnistía general: un
        # servicio que de verdad terminó no debe seguir pidiendo atención.
        html = self._agenda_a_las('19:00').content.decode()
        # Control positivo: la página SÍ está dibujando servicios de las 16:00.
        self.assertIn('Cabaña Tepa', html)
        self.assertNotIn('Tina Calbuco', html)

    def test_antes_de_su_hora_la_cabana_tambien_aparece(self):
        html = self._agenda_a_las('10:00').content.decode()
        self.assertIn('Cabaña Tepa', html)

    def test_una_persona_adicional_no_es_alojamiento(self):
        # 'cabana' con capacidad 1 es un modificador de precio, no un lugar
        # donde dormir: no tiene por qué quedarse todo el día en la agenda.
        self.assertTrue(es_alojamiento(
            ReservaServicio(servicio=self.cabana)))
        self.assertFalse(es_alojamiento(
            ReservaServicio(servicio=self.adicional)))
