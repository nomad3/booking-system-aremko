"""Tarjeta de Reserva móvil — Fase 1: lectura + copiar Pase (2026-08-30).

Lo que estas pruebas protegen no es que "la página cargue":

  · que la plata vaya PRIMERO (esa fue la petición de Jorge para el admin, y
    acá nace bien de entrada);
  · que el mensaje del Pase sea EL MISMO que muestra el admin — está extraído
    a mensaje_pase() justamente para que no puedan divergir;
  · que el texto NO se muestre en el cuerpo (viaja en JS y se copia con el
    botón): mostrarlo era media pantalla perdida en el celular;
  · que sea solo para staff — lleva teléfono y saldo del cliente.

Ejecutar:
    python manage.py test ventas.tests_tarjeta_reserva
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ventas.models import Cliente, Pago, ReservaServicio, Servicio, VentaReserva
from ventas.views.ficha_reserva_view import mensaje_pase


class TarjetaBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='tarjeta_test', email='t@test.cl', password='x')
        cls.cliente = Cliente.objects.create(nombre='Priscila Varela',
                                             telefono='+56926210906')
        cls.venta = VentaReserva.objects.create(cliente=cls.cliente)
        tina = Servicio.objects.create(nombre='Tina Villarrica', precio_base=30000,
                                       duracion=120, tipo_servicio='tina')
        ReservaServicio.objects.create(venta_reserva=cls.venta, servicio=tina,
                                       fecha_agendamiento='2026-09-05',
                                       hora_inicio='19:00', cantidad_personas=2)
        Pago.objects.create(venta_reserva=cls.venta, monto=60000,
                            metodo_pago='mercado_pago')
        cls.url = reverse('ventas:tarjeta_reserva', args=[cls.venta.pk])

    def _html(self):
        self.client.force_login(self.staff)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()


class SoloParaStaff(TarjetaBase):
    def test_sin_login_no_se_ve(self):
        """La tarjeta lleva teléfono y saldo del cliente: es una pantalla
        interna, no una página."""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)


class LaPlataPrimero(TarjetaBase):
    def test_el_dinero_va_antes_que_los_servicios(self):
        html = self._html()
        self.assertLess(html.find('id="dinero"'), html.find('id="servicios"'),
                        'la plata tiene que ser lo primero que se ve')

    def test_los_tres_numeros_por_separado(self):
        """Total, pagado y saldo se muestran los tres: saldo_pendiente es un
        campo almacenado (H-060) y una inconsistencia entre ellos tiene que
        saltar a la vista, no esconderse en un solo número."""
        html = self._html()
        for rotulo in ('Total', 'Pagado', 'Saldo'):
            self.assertIn(rotulo, html)


class ElPaseSeCopiaNoSeMuestra(TarjetaBase):
    def test_el_mensaje_va_en_el_boton_no_en_el_cuerpo(self):
        html = self._html()
        # Está para el JS (escapado)...
        self.assertIn('Pase para Aremko', html)
        self.assertIn('btnCopiarPase', html)
        # ...pero el guion del admin NO viene: eso es material de recepción,
        # no de la tarjeta.
        self.assertNotIn('Recórrelo con el cliente', html)

    def test_es_el_mismo_mensaje_que_muestra_el_admin(self):
        """El texto está extraído a mensaje_pase() para que el admin y la
        tarjeta no puedan divergir. Esta prueba clava las dos puntas."""
        from django.contrib import admin as django_admin

        from ventas.admin import VentaReservaAdmin

        msg = mensaje_pase(self.venta)
        self.assertIn('Pase para Aremko', msg)
        self.assertIn('Priscila,', msg)          # primer nombre, con saludo
        self.assertIn('aremko.cl', msg)          # la URL de la ficha viaja adentro

        admin_html = VentaReservaAdmin(VentaReserva, django_admin.site)\
            .pase_guion_display(self.venta)
        self.assertIn(msg, admin_html,
                      'el admin dejó de usar mensaje_pase(): los textos van a divergir')


class LoQueYaTiene(TarjetaBase):
    def test_muestra_servicio_y_pago(self):
        html = self._html()
        self.assertIn('Tina Villarrica', html)
        self.assertIn('19:00', html)
        self.assertIn('60', html.replace('.', ''))   # el pago de $60.000

    def test_tiene_la_salida_al_admin(self):
        """La tarjeta es lectura (fase 1): editar en serio sigue siendo el
        admin, y el camino tiene que estar a un toque."""
        self.assertIn(f'/admin/ventas/ventareserva/{self.venta.pk}/change/',
                      self._html())


class SeLlegaDesdeElAdmin(TarjetaBase):
    def test_el_admin_ofrece_la_tarjeta(self):
        """Sin entrada visible, la tarjeta existe pero nadie la usa — la
        lección de los tres menús de la semana pasada."""
        self.client.force_login(self.staff)
        html = self.client.get(reverse('admin:ventas_ventareserva_change',
                                       args=[self.venta.pk])).content.decode()
        self.assertIn(self.url, html)
