"""El QR de El Pase y la llegada del huésped.

Idea de Jorge (2026-08-03), nacida de una escena real en recepción: llegaban
clientes, les preguntaba "¿ya vieron la ficha de su reserva?" y respondían "¿qué
es eso?". Cuando él se las abría en el mesón, decían "ah, qué bueno" — el
contenido servía, pero nadie los había obligado nunca a abrirlo.

Su solución: **el QR no controla el ingreso, es el pretexto para que miren El
Pase.** Deborah dice "acá está su pase, con el QR para entrar", el cliente abre
la pantalla, y con la pantalla abierta aparecen las claves de wifi, cómo llegar
y la comanda. Esa conversación capacita y vende a la vez.

Lo que estos tests fijan, y que es donde la idea se puede arruinar:

1. **Un QR que no hace nada se abandona.** El escaneo registra la llegada de
   verdad y le sirve a recepción (saldo en pantalla, servicios, alertas).
2. **El QR NUNCA es la única puerta.** Sin celular, sin batería o sin señal,
   recepción marca la llegada desde la agenda, como siempre.
3. **Un solo link para los dos que pueden escanear.** Recepción registra; el
   cliente que apunta la cámara a su propia pantalla cae en su Pase y no ve
   nada interno.

Ejecutar:
    python manage.py test ventas.tests_llegada_pase
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from control_gestion.signals import react_to_reserva_change

from .llegadas import (TIPO_LLEGADA, VIA_MANUAL, VIA_QR, hora_local,
                       llegadas_de, registrar_llegada, ya_llego)
from .models import (CategoriaServicio, Cliente, MovimientoCliente, Servicio,
                     VentaReserva)
from .signals.main_signals import actualizar_tramo_y_premios_on_pago
from .views.ficha_reserva_view import qr_svg, token_para_reserva, url_llegada

# Las señales de CRM pegan a una tabla ausente por el drift AR-033/AR-034.
_SENSORES = (actualizar_tramo_y_premios_on_pago, react_to_reserva_change)


class _Base(TestCase):
    """IDs altos explícitos: insertar con PK explícita no avanza la secuencia de
    Postgres, y otras suites reservan IDs bajos a mano."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for r in _SENSORES:
            post_save.disconnect(r, sender=VentaReserva)

    @classmethod
    def tearDownClass(cls):
        for r in _SENSORES:
            post_save.connect(r, sender=VentaReserva)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.cat = CategoriaServicio.objects.create(id=9401, nombre='Tinas')
        cls.tina = Servicio.objects.create(
            id=9411, nombre='Tina Hidromasaje Puyehue', categoria=cls.cat,
            tipo_servicio='tina', precio_base=Decimal('60000'), duracion=90,
            activo=True, slots_disponibles={})
        cls.cliente = Cliente.objects.create(
            id=9421, nombre='Huésped Prueba', telefono='+56900000042')

    def setUp(self):
        self.venta = VentaReserva.objects.create(cliente=self.cliente)
        self.venta.reservaservicios.create(
            servicio=self.tina, fecha_agendamiento=timezone.localdate(),
            hora_inicio='16:00', cantidad_personas=2,
            precio_unitario_venta=Decimal('30000'))
        self.token = token_para_reserva(self.venta.id)

    def _staff(self, username='recepcion9401'):
        User = get_user_model()
        u = User.objects.create_user(username, password='x', is_staff=True)
        self.client.login(username=username, password='x')
        return u

    def tearDown(self):
        # ThreadLocalMiddleware guarda el usuario en un thread-local que nadie
        # limpia: tras el rollback quedaría apuntando a un usuario borrado y la
        # suite siguiente revienta con "usuario_id no existe en auth_user".
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()


class RegistrarLlegadaTest(_Base):

    def test_marca_la_llegada(self):
        cuando, recien = registrar_llegada(self.venta, via=VIA_QR)
        self.assertTrue(recien)
        self.assertIsNotNone(cuando)
        self.assertEqual(ya_llego(self.venta.id), cuando)

    def test_escanear_DOS_VECES_no_duplica_ni_pisa_la_hora(self):
        """Pasa de verdad: el cliente muestra el QR otra vez, o vuelve al mesón.
        No es un error y no puede cambiar la hora real de llegada."""
        primera, _ = registrar_llegada(self.venta, via=VIA_QR)
        segunda, recien = registrar_llegada(self.venta, via=VIA_QR)
        self.assertFalse(recien)
        self.assertEqual(primera, segunda)
        self.assertEqual(
            MovimientoCliente.objects.filter(
                venta_reserva=self.venta, tipo_movimiento=TIPO_LLEGADA).count(), 1)

    def test_deja_registrado_por_donde_entro(self):
        registrar_llegada(self.venta, via=VIA_MANUAL)
        mov = MovimientoCliente.objects.get(
            venta_reserva=self.venta, tipo_movimiento=TIPO_LLEGADA)
        self.assertIn(VIA_MANUAL, mov.comentarios)

    def test_una_sola_consulta_para_muchas_reservas(self):
        otra = VentaReserva.objects.create(cliente=self.cliente)
        registrar_llegada(self.venta)
        with self.assertNumQueries(1):
            mapa = llegadas_de([self.venta.id, otra.id])
        self.assertIn(self.venta.id, mapa)
        self.assertNotIn(otra.id, mapa)

    def test_no_revienta_con_basura(self):
        self.assertEqual(llegadas_de([]), {})
        self.assertEqual(llegadas_de([None, '']), {})
        self.assertEqual(registrar_llegada(None), (None, False))
        self.assertEqual(hora_local(None), '')


class EscaneoDelQRTest(_Base):
    """La MISMA URL para los dos que pueden escanear."""

    def _url(self):
        return reverse('ventas:ficha_llegada', kwargs={'token': self.token})

    def test_recepcion_registra_la_llegada_y_ve_el_saldo(self):
        self._staff()
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ya_llego(self.venta.id))
        cuerpo = r.content.decode()
        self.assertIn('Llegada registrada', cuerpo)
        self.assertIn(self.cliente.nombre, cuerpo)
        self.assertIn('Tina Hidromasaje Puyehue', cuerpo)

    def test_el_saldo_sale_a_la_vista_porque_ese_es_el_momento_de_cobrar(self):
        self._staff()
        cuerpo = self.client.get(self._url()).content.decode()
        self.assertIn('Saldo por cobrar', cuerpo)
        self.assertIn('60.000', cuerpo)   # 2 personas × $30.000

    def test_el_CLIENTE_que_escanea_su_pantalla_NO_registra_nada(self):
        """Sin sesión de personal: cae en su Pase, no marca llegada, no ve datos
        internos. Un solo link evita usar el equivocado en el mesón."""
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 302)
        self.assertIn(self.token, r['Location'])
        self.assertIsNone(ya_llego(self.venta.id))

    def test_un_usuario_logueado_pero_NO_staff_tampoco_registra(self):
        User = get_user_model()
        User.objects.create_user('cliente9401', password='x', is_staff=False)
        self.client.login(username='cliente9401', password='x')
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(ya_llego(self.venta.id))

    def test_escanear_de_nuevo_avisa_sin_alarmar(self):
        self._staff()
        self.client.get(self._url())
        cuerpo = self.client.get(self._url()).content.decode()
        self.assertIn('Ya estaba registrado', cuerpo)

    def test_token_invalido_es_404_no_un_error_feo(self):
        self._staff()
        r = self.client.get(reverse('ventas:ficha_llegada',
                                    kwargs={'token': 'basura-inventada'}))
        self.assertEqual(r.status_code, 404)


class ElPaseTest(_Base):
    """Qué ve el huésped antes y después de llegar."""

    def _pase(self):
        return self.client.get(reverse('ventas:ficha_reserva_cliente',
                                       kwargs={'token': self.token})).content.decode()

    def test_antes_de_llegar_muestra_el_QR(self):
        cuerpo = self._pase()
        self.assertIn('Tu código de ingreso', cuerpo)
        self.assertIn('Muéstralo en recepción', cuerpo)
        self.assertIn('<svg', cuerpo)

    def test_despues_de_llegar_el_QR_da_paso_a_la_comanda(self):
        """El QR ya cumplió. Lo que sirve estando adentro es pedir algo — y que
        la pantalla cambie sola es lo que le demuestra al cliente que sirvió."""
        registrar_llegada(self.venta, via=VIA_QR)
        cuerpo = self._pase()
        self.assertIn('Bienvenido', cuerpo)
        self.assertIn('Pedir a mi tina', cuerpo)
        self.assertNotIn('Tu código de ingreso', cuerpo)

    def test_el_QR_apunta_a_la_URL_de_llegada_de_ESTA_reserva(self):
        url = url_llegada(self.token)
        self.assertIn('/llegada/', url)
        self.assertIn(self.token, url)
        self.assertTrue(url.startswith('http'))  # la cámara la abre en frío


class GeneradorQRTest(TestCase):

    def test_genera_un_svg(self):
        svg = qr_svg('https://www.aremko.cl/ventas/reserva/abc/llegada/')
        self.assertIn('<svg', svg)
        self.assertIn('</svg>', svg)

    def test_nunca_tumba_El_Pase(self):
        """Un QR ausente afea la pantalla; una excepción la deja en blanco. El
        Pase tiene que abrir SIEMPRE."""
        self.assertEqual(qr_svg(None), '')


class PlanBSinQRTest(_Base):
    """"Siempre vamos a poder seguir como estamos ahora" — Jorge, 2026-08-03."""

    def _marcar(self):
        return self.client.post(
            reverse('ventas:marcar_llegada_api'),
            data='{"reserva_id": %d}' % self.venta.id,
            content_type='application/json')

    def test_recepcion_marca_llegada_desde_la_agenda(self):
        self._staff()
        r = self._marcar()
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertTrue(datos['success'])
        self.assertTrue(datos['recien'])
        self.assertTrue(ya_llego(self.venta.id))

    def test_marcar_dos_veces_responde_OK_igual(self):
        # Si respondiera error, recepción vería una alerta roja por algo que no
        # es un problema.
        self._staff()
        self._marcar()
        datos = self._marcar().json()
        self.assertTrue(datos['success'])
        self.assertFalse(datos['recien'])

    def test_reserva_inexistente_da_404_claro(self):
        self._staff()
        r = self.client.post(reverse('ventas:marcar_llegada_api'),
                             data='{"reserva_id": 99999999}',
                             content_type='application/json')
        self.assertEqual(r.status_code, 404)

    def test_sin_sesion_de_personal_no_se_puede_marcar(self):
        r = self._marcar()
        self.assertIn(r.status_code, (302, 403))
        self.assertIsNone(ya_llego(self.venta.id))


class AgendaMuestraLlegadasTest(_Base):

    def test_el_filtro_traduce_el_id_a_la_hora(self):
        from ventas.templatetags.ventas_extras import hora_llegada
        self.assertEqual(hora_llegada({7: '15:04'}, 7), '15:04')
        self.assertEqual(hora_llegada({7: '15:04'}, '7'), '15:04')   # llega como texto
        self.assertEqual(hora_llegada({7: '15:04'}, 8), '')
        self.assertEqual(hora_llegada(None, 7), '')
        self.assertEqual(hora_llegada({}, 'x'), '')

    def test_la_agenda_pinta_quien_llego_y_ofrece_marcar_al_resto(self):
        self._staff()
        cuerpo = self.client.get(reverse('ventas:agenda_operativa')).content.decode()
        self.assertIn('Marcar llegada', cuerpo)   # todavía no llega

        registrar_llegada(self.venta, via=VIA_QR)
        cuerpo = self.client.get(reverse('ventas:agenda_operativa')).content.decode()
        self.assertIn('Llegó', cuerpo)


class GuionEnElAdminTest(_Base):
    """El guion vive donde Deborah copia el link, y no en un manual.

    Un sábado con seis llegadas, lo que no está delante de los ojos no pasa. Es
    la misma lección que ya costó un bug esta semana: los guardias van en el
    camino principal, no en una rama que a veces se ejecuta.
    """

    def _guion(self, venta=None):
        from ventas.admin import VentaReservaAdmin
        from django.contrib import admin as dj_admin
        adm = VentaReservaAdmin(VentaReserva, dj_admin.site)
        return adm.pase_guion_display(venta or self.venta)

    def test_trae_el_link_del_Pase_listo_para_pegar(self):
        html = self._guion()
        self.assertIn('/ventas/reserva/', html)
        self.assertIn('Copiar mensaje', html)

    def test_el_mensaje_le_da_un_TRABAJO_no_describe_un_documento(self):
        """El mensaje viejo decía 'ahí está el link de su ficha y encontrará los
        detalles'. Nadie abre eso. El nuevo pide guardarlo y anuncia el QR."""
        html = self._guion()
        self.assertIn('QR', html)
        self.assertIn('Guárdalo', html)
        self.assertNotIn('encontrará los detalles', html)

    def test_los_cuatro_pasos_estan_y_en_orden(self):
        html = self._guion()
        pasos = ['Mándale el Pase', 'Claves de wifi', 'Cómo llegar', 'Comanda digital']
        posiciones = [html.find(p) for p in pasos]
        self.assertNotIn(-1, posiciones, 'falta un paso del guion')
        self.assertEqual(posiciones, sorted(posiciones), 'el guion quedó desordenado')

    def test_el_paso_del_masaje_NO_aparece_si_no_hay_masaje(self):
        """Un guion con pasos que no aplican se empieza a saltar entero."""
        self.assertNotIn('acompañante', self._guion())

    def test_el_paso_del_masaje_SI_aparece_cuando_hay_masaje(self):
        masaje = Servicio.objects.create(
            id=9431, nombre='Masaje de relajación', categoria=self.cat,
            tipo_servicio='masaje', precio_base=Decimal('45000'), duracion=60,
            activo=True, slots_disponibles={})
        self.venta.reservaservicios.create(
            servicio=masaje, fecha_agendamiento=timezone.localdate(),
            hora_inicio='18:00', cantidad_personas=1)
        html = self._guion()
        self.assertIn('acompañante', html)
        self.assertIn('antes de venir', html)

    def test_una_reserva_sin_guardar_no_revienta(self):
        self.assertIn('Guarda la reserva', self._guion(VentaReserva()))

    def test_un_cliente_SIN_NOMBRE_no_produce_un_saludo_roto(self):
        """Pasa de verdad: desde H-067 se guarda nombre vacío cuando el pushname
        de WhatsApp es basura ("L@mirn@dri@@🥰"). El saludo no puede quedar
        "Hola , " ni con el emoji adentro."""
        anonimo = Cliente.objects.create(id=9441, nombre='', telefono='+56900000043')
        venta = VentaReserva.objects.create(cliente=anonimo)
        html = self._guion(venta)
        self.assertIn('Hola, acá está tu Pase', html)

    def test_arma_el_boton_de_WhatsApp_con_el_telefono_del_cliente(self):
        html = self._guion()
        self.assertIn('wa.me/56900000042', html)
