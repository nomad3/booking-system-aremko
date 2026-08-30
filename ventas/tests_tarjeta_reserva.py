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


class AgregarPagoFase2(TestCase):
    """Fase 2: registrar un pago desde la tarjeta, con guardado chico.

    Lo que se protege acá es plata: que el pago quede con su monto, su método
    y QUIÉN lo registró, y que los totales de la reserva se recalculen de
    verdad (Pago.save() llama a calcular_total(); si alguien rompe esa cadena,
    el saldo miente y se cobra mal o dos veces).
    """

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='pago_test', email='p@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Pedro Osorno',
                                         telefono='+56911112222')
        cls.venta = VentaReserva.objects.create(cliente=cliente)
        tina = Servicio.objects.create(nombre='Tina Llaima', precio_base=30000,
                                       duracion=120, tipo_servicio='tina')
        ReservaServicio.objects.create(venta_reserva=cls.venta, servicio=tina,
                                       fecha_agendamiento='2026-09-07',
                                       hora_inicio='16:30', cantidad_personas=2)
        cls.venta.refresh_from_db()
        cls.url = reverse('ventas:tarjeta_agregar_pago', args=[cls.venta.pk])

    def _post(self, **datos):
        self.client.force_login(self.staff)
        return self.client.post(self.url, datos)

    def test_un_pago_queda_completo_y_los_totales_se_recalculan(self):
        total_antes = int(self.venta.total or 0)
        self.assertGreater(total_antes, 0, 'el escenario necesita una venta con total')

        r = self._post(monto='10000', metodo_pago='efectivo')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertEqual(d['pagado'], 10000)
        self.assertEqual(d['saldo'], total_antes - 10000)

        pago = self.venta.pagos.latest('id')
        self.assertEqual(int(pago.monto), 10000)
        self.assertEqual(pago.metodo_pago, 'efectivo')
        self.assertEqual(pago.usuario, self.staff,
                         'sin usuario no se sabe quién recibió la plata')
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado_pago, 'parcial')

    def test_el_segundo_pago_completa_y_el_estado_pasa_a_pagado(self):
        """El camino de la segunda vez: el primer pago siempre funciona en las
        demos; el que revienta es el segundo."""
        total = int(self.venta.total or 0)
        self._post(monto='10000', metodo_pago='efectivo')
        r = self._post(monto=str(total - 10000), metodo_pago='transferencia')
        d = r.json()
        self.assertEqual(d['saldo'], 0)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado_pago, 'pagado')
        self.assertEqual(self.venta.pagos.count(), 2)

    def test_acepta_el_monto_como_lo_escribe_deborah(self):
        """«$60.000» y «60000» son el mismo número."""
        r = self._post(monto='$10.000', metodo_pago='efectivo')
        self.assertEqual(r.json()['pagado'], 10000)

    def test_monto_invalido_no_crea_nada(self):
        for malo in ('', '0', '-5000', 'abc', '10.5x'):
            r = self._post(monto=malo, metodo_pago='efectivo')
            self.assertEqual(r.status_code, 400, f'aceptó monto {malo!r}')
        self.assertEqual(self.venta.pagos.count(), 0)

    def test_metodo_desconocido_no_crea_nada(self):
        r = self._post(monto='10000', metodo_pago='criptomoneda')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.venta.pagos.count(), 0)

    def test_giftcard_y_descuento_no_se_ofrecen_ni_se_aceptan(self):
        """giftcard exige el objeto GiftCard y descuento no es plata que entró:
        los dos tienen su lugar en el admin, no en el celular."""
        for especial in ('giftcard', 'descuento'):
            r = self._post(monto='10000', metodo_pago=especial)
            self.assertEqual(r.status_code, 400, f'aceptó {especial}')
        self.assertEqual(self.venta.pagos.count(), 0)

    def test_los_metodos_salen_del_modelo_no_de_una_sexta_copia(self):
        from ventas.models import Pago as PagoModel
        from ventas.views.tarjeta_reserva_view import METODOS_PAGO_TARJETA

        codigos_modelo = {c for c, _ in PagoModel.METODOS_PAGO}
        codigos_tarjeta = {c for c, _ in METODOS_PAGO_TARJETA}
        self.assertTrue(codigos_tarjeta <= codigos_modelo)
        self.assertEqual(codigos_modelo - codigos_tarjeta,
                         {'giftcard', 'descuento'})

    def test_sin_login_no_hay_pago(self):
        r = self.client.post(self.url, {'monto': '10000', 'metodo_pago': 'efectivo'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.venta.pagos.count(), 0)

    def test_por_GET_no_se_paga(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_la_tarjeta_ofrece_el_formulario(self):
        self.client.force_login(self.staff)
        html = self.client.get(reverse('ventas:tarjeta_reserva',
                                       args=[self.venta.pk])).content.decode()
        self.assertIn('Agregar pago', html)
        self.assertIn('value="efectivo"', html)
        self.assertNotIn('value="giftcard"', html)
        self.assertNotIn('value="descuento"', html)

    def test_el_pago_nuevo_aparece_al_recargar(self):
        """El JS actualiza al vuelo, pero la verdad vive en el servidor: al
        recargar, el pago tiene que estar."""
        self._post(monto='10000', metodo_pago='efectivo')
        html = self.client.get(reverse('ventas:tarjeta_reserva',
                                       args=[self.venta.pk])).content.decode()
        self.assertIn('Efectivo', html)
