"""La Agenda Operativa no le muestra comentarios del programador a Deborah.

Los comentarios {# #} de Django son de UNA línea. Si abren en una y cierran en
otra, Django no los reconoce como comentario y los imprime como texto. En la
Agenda Operativa había uno así entre el botón de cobrar y el de check-out, y se
dibujaba una vez por cada huésped que salía ese día.

Ya existe una prueba que revisa el CÓDIGO de las plantillas
(ventas.tests_templates_comentarios). Esta revisa la PÁGINA: que se dibuje de
verdad y que no traiga texto que nadie debería leer. Las dos hacen falta —
la primera atrapa el error antes; esta atrapa lo que la primera no anticipó.

Ejecutar:
    python manage.py test ventas.tests_agenda_sin_comentarios
"""
from __future__ import annotations

import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import (
    Cliente, ReservaServicio, Servicio, VentaReserva,
)


class LaAgendaNoMuestraComentarios(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='agenda_test', email='a@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Huésped', telefono='+56911111111')
        # capacidad_maxima >= 2 es obligatorio: la agenda usa ese mínimo para
        # distinguir una cabaña de verdad de otros servicios marcados 'cabana'
        # (ver CAPACIDAD_MINIMA_ALOJAMIENTO). Sin él no se dibuja ninguna
        # tarjeta de check-out y esta prueba queda comprobando una página vacía.
        cabana = Servicio.objects.create(nombre='Cabaña Tepa', precio_base=90000,
                                         duracion=60, tipo_servicio='cabana',
                                         capacidad_maxima=2)
        # Una estadía que termina hoy: así se dibuja la tarjeta de check-out,
        # que es justo donde estaba el comentario.
        venta = VentaReserva.objects.create(cliente=cliente)
        ReservaServicio.objects.create(
            venta_reserva=venta, servicio=cabana,
            fecha_agendamiento=timezone.localdate() - timedelta(days=1),
            hora_inicio='16:00')

    def setUp(self):
        self.client.force_login(self.staff)
        # El comentario vive en la tarjeta de check-out, y esa sección solo se
        # dibuja con este filtro. Sin él la prueba daba verde por vacía: estaba
        # comprobando la ausencia de un texto en una página que no lo contenía
        # de ninguna manera.
        r = self.client.get(reverse('ventas:agenda_operativa') + '?filtro=checkout')
        self.assertEqual(r.status_code, 200, 'la agenda no se dibujó')
        self.html = r.content.decode()

    def test_control_la_tarjeta_de_checkout_SI_se_dibuja(self):
        """Control positivo. Las pruebas de abajo comprueban que algo NO está;
        si la sección desapareciera, pasarían igual sin comprobar nada. Esta se
        cae primero y avisa que el escenario dejó de servir."""
        # 'id="cierre-' lleva el id de la reserva pegado, así que solo existe
        # si una tarjeta se dibujó. La clase CSS 'checkout-cierre' NO sirve como
        # control: aparece en la hoja de estilos aunque no haya ni una tarjeta,
        # y dejaba esta prueba en verde sin comprobar nada.
        self.assertIn('id="cierre-', self.html,
                      'no se dibujó ninguna tarjeta de check-out: las pruebas '
                      'de este archivo no estarían comprobando nada')

    def test_no_se_ve_el_comentario_del_check_out(self):
        self.assertNotIn('Cerrar la estadía sin pasar por el admin', self.html)
        self.assertNotIn('sin recargar la agenda', self.html)

    def test_no_se_filtra_sintaxis_de_plantilla(self):
        """Cualquier marcador de Django que llegue a la página es un error:
        significa que algo no se procesó."""
        for resto in ('{#', '#}', '{%', '%}'):
            self.assertNotIn(resto, self.html, f'quedó sin procesar: {resto}')

    def test_la_agenda_sigue_teniendo_su_contenido(self):
        """La contraparte: borrar de más también deja la prueba en verde."""
        self.assertIn('checkout', self.html.lower())
