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


class AgregarProductoFase3(TestCase):
    """Fase 3: agregar un producto desde la tarjeta.

    Las dos reglas del negocio que se protegen:

    · El stock se descuenta al ENTREGAR, no al vender (la señal
      actualizar_inventario solo actúa con fecha_entrega). Vender NO puede
      tocar inventario — ya hubo un bug de descuento doble por no respetarlo.
    · El precio se congela al momento de la venta: si el catálogo sube
      mañana, lo ya vendido no cambia.
    """

    @classmethod
    def setUpTestData(cls):
        from ventas.models import Producto

        cls.staff = get_user_model().objects.create_superuser(
            username='prod_test', email='pr@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Carmen Puerto Montt',
                                         telefono='+56933334444')
        cls.venta = VentaReserva.objects.create(cliente=cliente)
        # Del menú de comanda del CLIENTE, sin venta_meson: el caso que el
        # primer filtro (solo venta_meson) dejaba fuera por error.
        cls.jugo = Producto.objects.create(nombre='Jugo Natural de Frambuesa',
                                           precio_base=3500, cantidad_disponible=10,
                                           comanda_cliente=True, venta_meson=False)
        # Venta en mesón sin menú del cliente (espumante: cara a cara, pero no
        # a la vista en el link público).
        cls.espumante = Producto.objects.create(nombre='Espumante Valdivieso',
                                                precio_base=12000, cantidad_disponible=6,
                                                venta_meson=True, comanda_cliente=False)
        cls.agotado = Producto.objects.create(nombre='Chocolate Agotado',
                                              precio_base=5000, cantidad_disponible=0,
                                              venta_meson=True)
        # Interno con stock: lo que NO debe aparecer ni aceptarse.
        cls.interno = Producto.objects.create(nombre='Artesanías Inventario',
                                              precio_base=0, cantidad_disponible=50,
                                              venta_meson=False, comanda_cliente=False)
        cls.url = reverse('ventas:tarjeta_agregar_producto', args=[cls.venta.pk])

    def _post(self, **datos):
        self.client.force_login(self.staff)
        return self.client.post(self.url, datos)

    def test_agrega_congela_el_precio_y_sube_el_total(self):
        r = self._post(producto_id=self.jugo.pk, cantidad='2')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['producto']['subtotal'], 7000)
        self.assertEqual(d['total'], 7000)
        self.assertEqual(d['saldo'], 7000)

        linea = self.venta.reservaproductos.get()
        self.assertEqual(int(linea.precio_unitario_venta), 3500)

        # El congelamiento de verdad: sube el catálogo, lo vendido no cambia.
        self.jugo.precio_base = 9999
        self.jugo.save()
        self.venta.calcular_total()
        self.venta.refresh_from_db()
        self.assertEqual(int(self.venta.total), 7000,
                         'el precio no quedó congelado: lo vendido cambió con el catálogo')

    def test_vender_NO_descuenta_stock(self):
        """El stock se descuenta al ENTREGAR. Si vender también descontara,
        cada producto se descontaría dos veces — ese bug ya existió."""
        self._post(producto_id=self.jugo.pk, cantidad='2')
        self.jugo.refresh_from_db()
        self.assertEqual(self.jugo.cantidad_disponible, 10)

    def test_entregar_SI_descuenta_y_una_sola_vez(self):
        """La otra mitad de la regla: al poner fecha_entrega, la señal
        descuenta exactamente la cantidad, desde este camino también."""
        from django.utils import timezone as tz

        self._post(producto_id=self.jugo.pk, cantidad='2')
        linea = self.venta.reservaproductos.get()
        linea.fecha_entrega = tz.localdate()
        linea.save()
        self.jugo.refresh_from_db()
        self.assertEqual(self.jugo.cantidad_disponible, 8)

    def test_no_se_vende_lo_que_no_hay(self):
        r = self._post(producto_id=self.jugo.pk, cantidad='11')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Queda(n) 10', r.json()['mensaje'])
        self.assertEqual(self.venta.reservaproductos.count(), 0)

    def test_el_agotado_no_aparece_en_el_selector(self):
        self.client.force_login(self.staff)
        html = self.client.get(reverse('ventas:tarjeta_reserva',
                                       args=[self.venta.pk])).content.decode()
        self.assertIn('Jugo Natural de Frambuesa', html)
        self.assertNotIn('Chocolate Agotado', html)

    def test_ofrece_LO_MISMO_que_el_admin(self):
        """La pregunta de Jorge que destapó el error: ¿son los mismos
        productos que el admin? Deben serlo — el criterio es UNO
        (productos_vendibles): menú del cliente + venta en mesón, con stock.
        El primer filtro (solo mesón) habría escondido los jugos."""
        self.client.force_login(self.staff)
        html = self.client.get(reverse('ventas:tarjeta_reserva',
                                       args=[self.venta.pk])).content.decode()
        self.assertIn('Jugo Natural de Frambuesa', html)   # menú del cliente
        self.assertIn('Espumante Valdivieso', html)        # venta en mesón
        self.assertNotIn('Artesanías Inventario', html)    # interno: fuera

    def test_el_interno_ni_se_acepta_por_POST_directo(self):
        """El candado del endpoint: una pestaña desactualizada o una llamada
        directa tampoco pueden colar un producto interno."""
        r = self._post(producto_id=self.interno.pk, cantidad='1')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.venta.reservaproductos.count(), 0)

    def test_el_de_meson_puro_SI_se_acepta(self):
        r = self._post(producto_id=self.espumante.pk, cantidad='1')
        self.assertTrue(r.json()['ok'])

    def test_la_segunda_linea_acumula(self):
        self._post(producto_id=self.jugo.pk, cantidad='1')
        r = self._post(producto_id=self.jugo.pk, cantidad='3')
        self.assertEqual(r.json()['total'], 3500 * 4)
        self.assertEqual(self.venta.reservaproductos.count(), 2)

    def test_entradas_invalidas_no_crean_nada(self):
        casos = (
            {'producto_id': '', 'cantidad': '1'},
            {'producto_id': '999999', 'cantidad': '1'},
            {'producto_id': str(self.jugo.pk), 'cantidad': '0'},
            {'producto_id': str(self.jugo.pk), 'cantidad': 'abc'},
            {'producto_id': str(self.jugo.pk), 'cantidad': '-2'},
        )
        for datos in casos:
            r = self._post(**datos)
            self.assertEqual(r.status_code, 400, f'aceptó {datos}')
        self.assertEqual(self.venta.reservaproductos.count(), 0)

    def test_sin_login_no_hay_producto(self):
        r = self.client.post(self.url, {'producto_id': self.jugo.pk, 'cantidad': '1'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.venta.reservaproductos.count(), 0)

    def test_por_GET_no_se_agrega(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 405)


class AgregarServicioFase4(TestCase):
    """Fase 4: agregar servicio desde el calendario del admin, reutilizado.

    La tarjeta NO reimplementa disponibilidad: abre calendario_seleccion en un
    overlay y define window.servicioAgregado — el mismo protocolo que usa el
    modal del admin. Lo que se prueba acá son las dos puntas de ese cable.
    """

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='cal_test', email='c@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Rosa Frutillar',
                                         telefono='+56955556666')
        cls.venta = VentaReserva.objects.create(cliente=cliente)

    def test_la_tarjeta_abre_el_calendario_de_SU_reserva(self):
        self.client.force_login(self.staff)
        html = self.client.get(reverse('ventas:tarjeta_reserva',
                                       args=[self.venta.pk])).content.decode()
        self.assertIn(f'calendario-seleccion/?reserva_id={self.venta.pk}', html)
        self.assertIn('servicioAgregado', html,
                      'sin el callback, el calendario agrega pero la tarjeta '
                      'nunca se entera')

    def test_el_iframe_del_calendario_carga_con_bandera_no_con_src(self):
        """Bug real (Jorge, 30-08): el iframe nacía con src="" y la carga floja
        preguntaba `if (!frame.src)`. Leer .src en un iframe sin cargar devuelve
        la URL de la página —truthy—, así que el calendario nunca se asignaba y
        el overlay quedaba en blanco. La guardia correcta es una bandera."""
        self.client.force_login(self.staff)
        html = self.client.get(reverse('ventas:tarjeta_reserva',
                                       args=[self.venta.pk])).content.decode()
        self.assertNotIn('id="calFrame" src=', html,
                         'el iframe volvió a nacer con src: la carga floja se rompe')
        self.assertIn('calCargado', html)

    def test_el_calendario_que_abre_el_overlay_responde(self):
        """Si el calendario se rompe, el botón de la tarjeta abre una pantalla
        muerta. Esta prueba es el canario de esa dependencia."""
        self.client.force_login(self.staff)
        r = self.client.get(reverse('ventas:calendario_seleccion') +
                            f'?reserva_id={self.venta.pk}')
        self.assertEqual(r.status_code, 200)

    def test_el_calendario_sigue_siendo_solo_staff(self):
        r = self.client.get(reverse('ventas:calendario_seleccion'))
        self.assertEqual(r.status_code, 302)


class ApiDelCalendario(TestCase):
    """La API agregar_servicio_a_reserva existía SIN ninguna prueba, y desde la
    fase 4 la tarjeta depende de ella. Estas pruebas cubren lo que la tarjeta
    necesita que siga siendo cierto: que agrega con precio congelado y total
    recalculado, y que los candados (bloqueo, cupo) siguen puestos.
    """

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='api_cal_test', email='ac@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Elena Osorno',
                                         telefono='+56977778888')
        cls.venta = VentaReserva.objects.create(cliente=cliente)
        cls.tina = Servicio.objects.create(
            nombre='Tina Osorno', precio_base=25000, duracion=120,
            tipo_servicio='tina', activo=True, max_servicios_simultaneos=2)
        cls.url = reverse('ventas:agregar_servicio_reserva')

    def _post(self, **datos):
        import json as _json

        self.client.force_login(self.staff)
        base = {'reserva_id': self.venta.pk, 'servicio_nombre': 'Tina Osorno',
                'fecha': '2026-09-10', 'hora': '19:00', 'cantidad': 1}
        base.update(datos)
        return self.client.post(self.url, _json.dumps(base),
                                content_type='application/json')

    def test_agrega_con_precio_congelado_y_total_recalculado(self):
        r = self._post()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])

        linea = self.venta.reservaservicios.get()
        self.assertEqual(int(linea.precio_unitario_venta), 25000)
        self.venta.refresh_from_db()
        self.assertEqual(int(self.venta.total),
                         25000 * linea.cantidad_personas)

    def test_un_slot_bloqueado_se_rechaza(self):
        """El candado del propio endpoint: cubre pestañas desactualizadas y
        llamadas directas, como dice su comentario. Que siga vivo."""
        from ventas.models import ServicioSlotBloqueo

        ServicioSlotBloqueo.objects.create(servicio=self.tina, activo=True,
                                           fecha='2026-09-10', hora_slot='19:00',
                                           motivo='mantención')
        r = self._post()
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.venta.reservaservicios.count(), 0)

    def test_sin_cupo_simultaneo_se_rechaza(self):
        self._post()
        self._post()          # llena los 2 cupos simultáneos
        r = self._post()
        self.assertEqual(r.status_code, 400)
        self.assertIn('espacio', r.json()['error'])
        self.assertEqual(self.venta.reservaservicios.count(), 2)

    def test_sin_login_no_agrega(self):
        import json as _json

        r = self.client.post(self.url, _json.dumps({'reserva_id': self.venta.pk}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.venta.reservaservicios.count(), 0)


class CrearReservaFase5(TestCase):
    """Fase 5: crear una reserva con lo mínimo — teléfono y nombre.

    Lo que más protege esta clase son los CLIENTES DUPLICADOS: el mismo
    teléfono escrito distinto («9 1234 5678» vs «+56912345678») ya obligó una
    vez a una limpieza masiva (normalize_and_merge_clients). Crear siempre
    pasa por el normalizador y busca antes de crear.
    """

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='crear_test', email='cr@test.cl', password='x')
        cls.url = reverse('ventas:nueva_reserva')

    def _post(self, **datos):
        self.client.force_login(self.staff)
        return self.client.post(self.url, datos)

    def test_telefono_nuevo_crea_cliente_normalizado_y_abre_la_tarjeta(self):
        r = self._post(telefono='912345678', nombre='Marta Llanquihue')
        cliente = Cliente.objects.get(nombre='Marta Llanquihue')
        self.assertEqual(cliente.telefono, '+56912345678',
                         'el teléfono no pasó por el normalizador')
        venta = VentaReserva.objects.get(cliente=cliente)
        self.assertIsNotNone(venta.fecha_reserva,
                             'sin fecha, la venta se esconde de los reportes')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('ventas:tarjeta_reserva', args=[venta.pk]))

    def test_el_mismo_telefono_escrito_distinto_NO_duplica_al_cliente(self):
        """El camino de la segunda vez, que es el que duele: el cliente ya
        existe con +56 y Deborah escribe el número a la chilena."""
        existente = Cliente.objects.create(nombre='Marta Llanquihue',
                                           telefono='+56912345678')
        r = self._post(telefono='9 1234 5678', nombre='Marta L.')
        self.assertEqual(Cliente.objects.count(), 1, 'creó un cliente duplicado')
        existente.refresh_from_db()
        self.assertEqual(existente.nombre, 'Marta Llanquihue',
                         'le pisó el nombre al cliente existente')
        venta = VentaReserva.objects.get()
        self.assertEqual(venta.cliente, existente)
        self.assertEqual(r.status_code, 302)

    def test_telefono_invalido_explica_y_no_crea_nada(self):
        r = self._post(telefono='123', nombre='Alguien')
        self.assertEqual(r.status_code, 200)
        self.assertIn('no se entiende', r.content.decode())
        self.assertEqual(Cliente.objects.count(), 0)
        self.assertEqual(VentaReserva.objects.count(), 0)

    def test_cliente_nuevo_sin_nombre_explica_y_no_crea_nada(self):
        r = self._post(telefono='987654321', nombre='')
        self.assertEqual(r.status_code, 200)
        self.assertIn('falta el nombre', r.content.decode())
        self.assertEqual(VentaReserva.objects.count(), 0)

    def test_solo_staff(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        r = self.client.post(self.url, {'telefono': '912345678', 'nombre': 'X'})
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)
        self.assertEqual(VentaReserva.objects.count(), 0)

    def test_la_agenda_y_la_tarjeta_ofrecen_la_entrada(self):
        """La lección de los tres menús: sin entrada visible, la pantalla
        existe pero nadie la usa."""
        self.client.force_login(self.staff)
        agenda = self.client.get(reverse('ventas:agenda_operativa')).content.decode()
        self.assertIn(self.url, agenda)

        cliente = Cliente.objects.create(nombre='Eva', telefono='+56900001111')
        venta = VentaReserva.objects.create(cliente=cliente)
        tarjeta = self.client.get(reverse('ventas:tarjeta_reserva',
                                          args=[venta.pk])).content.decode()
        self.assertIn(self.url, tarjeta)


class DatosComplementariosFase5(TestCase):
    """El bloque colapsado de datos complementarios: guarda SOLO lo suyo."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='datos_test', email='d@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Iván Frutillar',
                                         telefono='+56900002222')
        cls.venta = VentaReserva.objects.create(cliente=cliente)
        tina = Servicio.objects.create(nombre='Tina Petrohué', precio_base=30000,
                                       duracion=120, tipo_servicio='tina')
        ReservaServicio.objects.create(venta_reserva=cls.venta, servicio=tina,
                                       fecha_agendamiento='2026-09-12',
                                       hora_inicio='19:00', cantidad_personas=2)
        cls.venta.refresh_from_db()
        cls.url = reverse('ventas:tarjeta_editar_datos', args=[cls.venta.pk])

    def test_guarda_comentarios_y_documento_sin_tocar_la_plata(self):
        total_antes = int(self.venta.total or 0)
        self.client.force_login(self.staff)
        r = self.client.post(self.url, {'comentarios': 'Llega 30 min antes',
                                        'numero_documento_fiscal': 'BOL-778'})
        self.assertTrue(r.json()['ok'])
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.comentarios, 'Llega 30 min antes')
        self.assertEqual(self.venta.numero_documento_fiscal, 'BOL-778')
        self.assertEqual(int(self.venta.total), total_antes,
                         'guardar datos complementarios movió la plata')

    def test_la_tarjeta_trae_el_formulario_prellenado(self):
        self.venta.comentarios = '[Luna] Propuesta aprobada'
        self.venta.save(update_fields=['comentarios'])
        self.client.force_login(self.staff)
        html = self.client.get(reverse('ventas:tarjeta_reserva',
                                       args=[self.venta.pk])).content.decode()
        self.assertIn('Datos complementarios', html)
        self.assertIn('[Luna] Propuesta aprobada', html)

    def test_solo_staff_y_solo_POST(self):
        r = self.client.post(self.url, {'comentarios': 'x'})
        self.assertEqual(r.status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 405)


class CandadoFechasPasadas(TestCase):
    """El calendario dejó agendar para el 05/08 estando a 30/08 (lo cazó Jorge
    en su iPhone). Una reserva hacia atrás no aparece en la agenda del día:
    nadie la prepara y el cliente llega a una puerta cerrada.

    El candado vive en la API —no solo en lo que el calendario pinta— por la
    misma razón que el de los bloqueos: cubre pestañas desactualizadas.
    """

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='pasado_test', email='pa@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Laura Ancud',
                                         telefono='+56966667777')
        cls.venta = VentaReserva.objects.create(cliente=cliente)
        Servicio.objects.create(nombre='Tina Rupanco', precio_base=25000,
                                duracion=120, tipo_servicio='tina', activo=True,
                                max_servicios_simultaneos=3)
        cls.url = reverse('ventas:agregar_servicio_reserva')

    def _post(self, fecha):
        import json as _json

        self.client.force_login(self.staff)
        return self.client.post(self.url, _json.dumps({
            'reserva_id': self.venta.pk, 'servicio_nombre': 'Tina Rupanco',
            'fecha': fecha, 'hora': '19:00', 'cantidad': 1,
        }), content_type='application/json')

    def test_ayer_se_rechaza_explicando(self):
        from datetime import timedelta

        from django.utils import timezone as tz

        ayer = (tz.localdate() - timedelta(days=1)).isoformat()
        r = self._post(ayer)
        self.assertEqual(r.status_code, 400)
        self.assertIn('ya pasó', r.json()['error'])
        self.assertEqual(self.venta.reservaservicios.count(), 0)

    def test_HOY_se_permite(self):
        """El 29,6% de las reservas son para el mismo día: bloquear hoy sería
        matar la venta más común por proteger de la más rara."""
        from django.utils import timezone as tz

        r = self._post(tz.localdate().isoformat())
        self.assertTrue(r.json()['success'])
        self.assertEqual(self.venta.reservaservicios.count(), 1)


class EditarPersonasFase6(TestCase):
    """Fase 6: cambiar la cantidad de personas tocando la línea del servicio.

    La guarda es el contrato del admin: en una CABAÑA la cantidad son cabañas
    (siempre 1) y tocarla multiplica el precio completo — bloqueada. En tinas
    y masajes el valor unitario ES por persona — editables. La tina del
    escenario se llama a propósito como la REAL que Jorge tocó primero
    (Puyehue): está en TINAS_PRECIO_PLANO del checkout, y usar esa lista como
    vara la habría dejado no editable — la fase inútil en su primer uso.
    """

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='pers_test', email='pe@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Sofía Castro',
                                         telefono='+56988889999')
        cls.venta = VentaReserva.objects.create(cliente=cliente)
        cls.tina = Servicio.objects.create(
            nombre='Tina Hidromasaje Puyehue', precio_base=30000, duracion=120,
            tipo_servicio='tina', capacidad_minima=2, capacidad_maxima=6)
        cls.cabana = Servicio.objects.create(
            nombre='Cabaña Alerce', precio_base=90000, duracion=60,
            tipo_servicio='cabana', capacidad_maxima=4)
        cls.linea_tina = ReservaServicio.objects.create(
            venta_reserva=cls.venta, servicio=cls.tina,
            fecha_agendamiento='2026-09-14', hora_inicio='19:00',
            cantidad_personas=2)
        cls.linea_cabana = ReservaServicio.objects.create(
            venta_reserva=cls.venta, servicio=cls.cabana,
            fecha_agendamiento='2026-09-14', hora_inicio='16:00',
            cantidad_personas=2)
        cls.venta.refresh_from_db()
        cls.url = reverse('ventas:tarjeta_editar_servicio', args=[cls.venta.pk])


    def _post(self, **datos):
        self.client.force_login(self.staff)
        return self.client.post(self.url, datos)

    def test_cambia_las_personas_y_la_plata_sigue_al_grupo(self):
        r = self._post(linea_id=self.linea_tina.pk, cantidad='4')
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertEqual(d['linea'], {'personas': 4, 'subtotal': 120000})
        # 30.000×4 (tina) + 90.000×2 (cabaña intacta)
        self.assertEqual(d['total'], 120000 + 180000)
        self.linea_tina.refresh_from_db()
        self.assertEqual(self.linea_tina.cantidad_personas, 4)

    def test_la_cabaña_NO_se_toca_desde_la_tarjeta(self):
        """En una cabaña, cantidad × precio = precio de la cabaña multiplicado:
        editar «personas» ahí cobraría 2 o 4 cabañas."""
        r = self._post(linea_id=self.linea_cabana.pk, cantidad='4')
        self.assertEqual(r.status_code, 400)
        self.assertIn('cabaña', r.json()['mensaje'])
        self.linea_cabana.refresh_from_db()
        self.assertEqual(self.linea_cabana.cantidad_personas, 2)

    def test_la_tina_REAL_de_jorge_SI_es_editable(self):
        """Puyehue está en TINAS_PRECIO_PLANO (la lista de la vitrina web).
        Si alguien vuelve a usar esa lista como guarda, esta prueba cae: la
        primera tina que Jorge quiso editar quedaría bloqueada otra vez."""
        r = self._post(linea_id=self.linea_tina.pk, cantidad='3')
        self.assertTrue(r.json()['ok'])
        self.assertEqual(r.json()['linea']['personas'], 3)

    def test_no_se_pasa_de_la_capacidad(self):
        r = self._post(linea_id=self.linea_tina.pk, cantidad='7')
        self.assertEqual(r.status_code, 400)
        self.assertIn('hasta 6', r.json()['mensaje'])

    def test_tampoco_se_baja_del_minimo(self):
        """El piso importa tanto como el techo: una tina con mínimo 2 editada
        a 1 persona se cobraría bajo tarifa."""
        r = self._post(linea_id=self.linea_tina.pk, cantidad='1')
        self.assertEqual(r.status_code, 400)
        self.assertIn('mínimo 2', r.json()['mensaje'])
        self.linea_tina.refresh_from_db()
        self.assertEqual(self.linea_tina.cantidad_personas, 2)

    def test_una_linea_de_OTRA_reserva_no_se_alcanza(self):
        """IDOR: el id de línea viaja en el POST; sin este candado, cambiando
        el número se editaría la reserva de otro cliente."""
        otro = Cliente.objects.create(nombre='Otro', telefono='+56900003333')
        otra_venta = VentaReserva.objects.create(cliente=otro)
        linea_ajena = ReservaServicio.objects.create(
            venta_reserva=otra_venta, servicio=self.tina,
            fecha_agendamiento='2026-09-15', hora_inicio='19:00',
            cantidad_personas=2)
        r = self._post(linea_id=linea_ajena.pk, cantidad='6')
        self.assertEqual(r.status_code, 404)
        linea_ajena.refresh_from_db()
        self.assertEqual(linea_ajena.cantidad_personas, 2)

    def test_entradas_invalidas(self):
        for malo in ('0', 'abc', '', '-3'):
            r = self._post(linea_id=self.linea_tina.pk, cantidad=malo)
            self.assertEqual(r.status_code, 400, f'aceptó {malo!r}')
        self.linea_tina.refresh_from_db()
        self.assertEqual(self.linea_tina.cantidad_personas, 2)

    def test_solo_staff_y_solo_POST(self):
        r = self.client.post(self.url, {'linea_id': self.linea_tina.pk,
                                        'cantidad': '4'})
        self.assertEqual(r.status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_la_tarjeta_marca_solo_las_lineas_editables(self):
        self.client.force_login(self.staff)
        html = self.client.get(reverse('ventas:tarjeta_reserva',
                                       args=[self.venta.pk])).content.decode()
        self.assertIn(f'data-linea="{self.linea_tina.pk}"', html)
        self.assertNotIn(f'data-linea="{self.linea_cabana.pk}"', html,
                         'la cabaña de precio plano quedó tocable')


class LaAgendaAbreLaTarjetaNoElAdmin(TestCase):
    """Jorge (2026-08-30): al abrir una reserva desde la agenda en el celular
    se abría el admin antiguo. Ahora TODOS los enlaces de reserva de la agenda
    van a la tarjeta móvil; el camino al admin vive DENTRO de la tarjeta
    («Abrir en el admin»), a un toque para quien lo necesite.
    """

    @classmethod
    def setUpTestData(cls):
        from datetime import timedelta

        from django.utils import timezone as tz

        cls.staff = get_user_model().objects.create_superuser(
            username='agenda_tarjeta_test', email='at@test.cl', password='x')
        cliente = Cliente.objects.create(nombre='Norma Osorno',
                                         telefono='+56944445555')
        cls.venta = VentaReserva.objects.create(cliente=cliente)
        cabana = Servicio.objects.create(nombre='Cabaña Coihue', precio_base=90000,
                                         duracion=60, tipo_servicio='cabana',
                                         capacidad_maxima=2)
        # Estadía que terminó ayer: dibuja la tarjeta de check-out, el enlace
        # más usado de la agenda.
        ReservaServicio.objects.create(
            venta_reserva=cls.venta, servicio=cabana,
            fecha_agendamiento=tz.localdate() - timedelta(days=1),
            hora_inicio='16:00', cantidad_personas=2)

    def test_en_el_codigo_no_queda_NINGUN_enlace_al_admin_viejo(self):
        """Guarda de fuente, como la de los tres menús: si alguien reintroduce
        un enlace al admin en cualquiera de las cinco zonas de la agenda, esto
        cae sin depender de qué sección se dibujó en la prueba."""
        import os

        from django.conf import settings

        src = open(os.path.join(settings.BASE_DIR, 'ventas', 'templates',
                                'ventas', 'agenda_operativa.html'),
                   encoding='utf-8').read()
        self.assertNotIn('/admin/ventas/ventareserva/', src)

    def test_la_tarjeta_de_checkout_abre_la_tarjeta_movil(self):
        self.client.force_login(self.staff)
        html = self.client.get(reverse('ventas:agenda_operativa') +
                               '?filtro=checkout').content.decode()
        self.assertIn(f'/ventas/reserva/{self.venta.pk}/tarjeta/', html)
        self.assertNotIn(f'/admin/ventas/ventareserva/{self.venta.pk}/change/',
                         html)


class ListaMovilDeReservas(TestCase):
    """La lista para encontrar una reserva desde el celular (Jorge, 30-08):
    número, fecha y cliente — nada más — con UN buscador que entiende id,
    nombre, teléfono o fecha. Cada fila abre la tarjeta.
    """

    @classmethod
    def setUpTestData(cls):
        from datetime import timedelta

        from django.utils import timezone as tz

        cls.staff = get_user_model().objects.create_superuser(
            username='lista_test', email='li@test.cl', password='x')
        c1 = Cliente.objects.create(nombre='Liliana Oportus',
                                    telefono='+56966090345')
        c2 = Cliente.objects.create(nombre='Amy Prueba', telefono='+56954503703')
        cls.v1 = VentaReserva.objects.create(cliente=c1, fecha_reserva=tz.now())
        cls.v2 = VentaReserva.objects.create(
            cliente=c2, fecha_reserva=tz.now() - timedelta(days=3))
        cls.url = reverse('ventas:tarjetas_lista')

    def _html(self, q=''):
        self.client.force_login(self.staff)
        return self.client.get(self.url, {'q': q} if q else None).content.decode()

    def test_solo_staff(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)

    def test_muestra_lo_minimo_y_cada_fila_abre_la_tarjeta(self):
        html = self._html()
        self.assertIn('Liliana Oportus', html)
        self.assertIn(f'#{self.v1.pk}', html)
        self.assertIn(reverse('ventas:tarjeta_reserva', args=[self.v1.pk]), html)

    def test_busca_por_numero_de_reserva(self):
        html = self._html(str(self.v1.pk))
        self.assertIn('Liliana Oportus', html)
        self.assertNotIn('Amy Prueba', html)

    def test_busca_por_nombre_parcial(self):
        html = self._html('oport')
        self.assertIn('Liliana Oportus', html)
        self.assertNotIn('Amy Prueba', html)

    def test_busca_por_telefono_como_lo_escribe_deborah(self):
        """«66090345» sin el +569: tiene que encontrarla igual."""
        html = self._html('66090345')
        self.assertIn('Liliana Oportus', html)
        self.assertNotIn('Amy Prueba', html)

    def test_busca_por_fecha(self):
        from django.utils import timezone as tz

        html = self._html(tz.localdate().strftime('%d/%m/%Y'))
        self.assertIn('Liliana Oportus', html)
        self.assertNotIn('Amy Prueba', html)

    def test_sin_resultados_explica_en_vez_de_quedar_en_blanco(self):
        self.assertIn('Nada para', self._html('zzzz'))

    def test_las_entradas_existen(self):
        """La lección de los tres menús, otra vez: agenda, tarjeta y el
        listado del admin ofrecen el camino."""
        self.client.force_login(self.staff)
        agenda = self.client.get(reverse('ventas:agenda_operativa')).content.decode()
        self.assertIn(self.url, agenda)
        tarjeta = self.client.get(reverse('ventas:tarjeta_reserva',
                                          args=[self.v1.pk])).content.decode()
        self.assertIn(self.url, tarjeta)
        changelist = self.client.get(
            reverse('admin:ventas_ventareserva_changelist')).content.decode()
        self.assertIn(self.url, changelist)
