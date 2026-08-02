"""Qué comandas ve cocina HOY en la Agenda Operativa.

Caso real (Jorge, 2026-08-02, reserva 6479): "generé la comanda para la reserva
6479 pero dos cosas: no aparece la comanda en los reportes y por lo mismo no
suena nada".

Los dos síntomas eran uno solo — la página y el aviso sonoro leen la MISMA
consulta, así que lo que no entra ahí ni se ve ni suena. El estado real en
producción era:

    SERVICIOS: []                         ← la reserva no tenía servicios
    #707 estado=pendiente | entrega=None
    #706 estado=pendiente | entrega=None

La regla vieja tenía dos casos:
    1. fecha_entrega_objetivo definida → debe caer HOY.
    2. Sin fecha objetivo → algún ReservaServicio de la reserva debe ser HOY.
Con la reserva sin servicios, el caso 2 no podía cumplirse JAMÁS: comandas
huérfanas, invisibles para siempre y no solo ese día. De ahí el caso 3.

Y de paso se cayó el filtro `creada_por_cliente=True`: dejaba invisibles las
comandas que el admin crea solo. El mismo día se perdieron así las #701, #702
y #705 — ninguna llegó a cocina.

Ejecutar:
    python manage.py test ventas.tests_comandas_cocina
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from control_gestion.signals import react_to_reserva_change

from .models import (Cliente, CategoriaServicio, Comanda, DetalleComanda,
                     Producto, Servicio, VentaReserva)
from .signals.main_signals import actualizar_tramo_y_premios_on_pago
from .views.agenda_operativa_view import comandas_fuera_de_hoy, comandas_para_cocina

# Las señales de CRM consultan `crm_service_history`, tabla que no existe en la
# BD de test (drift preexistente AR-033/AR-034). Sin desconectarlas, el primer
# create aborta la transacción y TODO lo que sigue falla por arrastre. Mismo
# patrón que tests_checkout_agenda.
_SENSORES = (actualizar_tramo_y_premios_on_pago, react_to_reserva_change)


def _hoy():
    return timezone.localtime(timezone.now()).date()


def _en(dia, hora=12):
    """Datetime aware en `dia` a las `hora`."""
    return timezone.make_aware(datetime.combine(dia, time(hora, 0)))


class _Base(TestCase):
    """Fixtures con IDs altos explícitos: insertar con PK explícita NO avanza la
    secuencia de Postgres, y otras suites reservan a mano IDs bajos (ver el
    `duplicate key id=22` de tests_martes_cerrado)."""

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
        cls.cat = CategoriaServicio.objects.create(id=9301, nombre='Alojamientos')
        cls.servicio = Servicio.objects.create(
            id=9311, nombre='Cabaña Torre', categoria=cls.cat, tipo_servicio='cabana',
            precio_base=Decimal('100000'), duracion=60, activo=True, slots_disponibles={})
        cls.producto = Producto.objects.create(
            id=9321, nombre='Facilitar copas de vino', precio_base=Decimal('3000'),
            cantidad_disponible=99)
        cls.cliente = Cliente.objects.create(
            id=9331, nombre='Cliente Prueba', telefono='+56900000001')

    def _reserva(self, fechas_servicio=()):
        venta = VentaReserva.objects.create(cliente=self.cliente)
        for f in fechas_servicio:
            venta.reservaservicios.create(
                servicio=self.servicio, fecha_agendamiento=f, hora_inicio='16:00', cantidad_personas=2)
        return venta

    def _comanda(self, venta, estado='pendiente', objetivo=None,
                 por_cliente=True, solicitada=None, con_item=True):
        c = Comanda.objects.create(
            venta_reserva=venta, estado=estado,
            fecha_entrega_objetivo=objetivo, creada_por_cliente=por_cliente)
        if con_item:
            DetalleComanda.objects.create(
                comanda=c, producto=self.producto, cantidad=1,
                precio_unitario=self.producto.precio_base)
        if solicitada is not None:
            # auto_now_add: solo se puede mover con un update() directo.
            Comanda.objects.filter(pk=c.pk).update(fecha_solicitud=solicitada)
            c.refresh_from_db()
        return c

    def _ids_de_hoy(self):
        return set(comandas_para_cocina(_hoy()).values_list('id', flat=True))


class ElCasoRealTest(_Base):
    """Reserva 6479: pedidos confirmados, sin servicios, sin fecha objetivo."""

    def test_comanda_huerfana_SI_aparece(self):
        venta = self._reserva(fechas_servicio=())   # ← sin servicios, como la 6479
        c = self._comanda(venta, objetivo=None)
        self.assertIn(c.id, self._ids_de_hoy())

    def test_dos_pedidos_del_mismo_cliente_aparecen_los_dos(self):
        venta = self._reserva(fechas_servicio=())
        c1 = self._comanda(venta, objetivo=None)
        c2 = self._comanda(venta, objetivo=None)
        self.assertEqual({c1.id, c2.id} & self._ids_de_hoy(), {c1.id, c2.id})

    def test_la_regla_VIEJA_efectivamente_no_la_encontraba(self):
        """Prueba de que el arreglo hace algo.

        Reconstruye la consulta anterior sobre el mismo dato: si no fallara
        acá, el fix sería decorativo. Es el mismo par comanda+reserva que en
        producción quedó invisible (la 706 y la 707 de la reserva 6479).
        """
        from django.db.models import Q
        venta = self._reserva(fechas_servicio=())
        c = self._comanda(venta, objetivo=None)

        regla_vieja = (
            Comanda.objects
            .filter(estado__in=('pendiente', 'procesando'), creada_por_cliente=True)
            .filter(Q(fecha_entrega_objetivo__date=_hoy())
                    | (Q(fecha_entrega_objetivo__isnull=True)
                       & Q(venta_reserva__reservaservicios__fecha_agendamiento=_hoy())))
            .distinct()
        )
        self.assertNotIn(c.id, set(regla_vieja.values_list('id', flat=True)))
        self.assertIn(c.id, self._ids_de_hoy())   # y con la nueva sí aparece

    def test_pero_NO_se_arrastra_para_siempre(self):
        """Sin servicios manda el día en que se pidió: el pedido de anteayer no
        puede seguir apareciendo hoy, o cocina acumula basura."""
        venta = self._reserva(fechas_servicio=())
        vieja = self._comanda(venta, objetivo=None,
                              solicitada=_en(_hoy() - timedelta(days=2)))
        self.assertNotIn(vieja.id, self._ids_de_hoy())


class ComandasDelAdminTest(_Base):
    """El bug encontrado de paso: #701, #702 y #705 del 2026-08-02."""

    def test_comanda_creada_por_el_admin_SI_aparece(self):
        # `_asegurar_comanda_de_productos` no marca creada_por_cliente — y hace
        # bien, porque NO la creó el cliente. El error era filtrar por eso.
        venta = self._reserva(fechas_servicio=(_hoy(),))
        c = self._comanda(venta, por_cliente=False, objetivo=_en(_hoy()))
        self.assertIn(c.id, self._ids_de_hoy())

    def test_a_cocina_le_da_igual_quien_la_tecleo(self):
        venta = self._reserva(fechas_servicio=(_hoy(),))
        del_cliente = self._comanda(venta, por_cliente=True)
        del_admin = self._comanda(venta, por_cliente=False)
        ids = self._ids_de_hoy()
        self.assertIn(del_cliente.id, ids)
        self.assertIn(del_admin.id, ids)


class ReglaDeFechaTest(_Base):

    def test_fecha_objetivo_hoy_aparece(self):
        venta = self._reserva(fechas_servicio=(_hoy() + timedelta(days=5),))
        c = self._comanda(venta, objetivo=_en(_hoy(), 20))
        self.assertIn(c.id, self._ids_de_hoy())

    def test_fecha_objetivo_manana_NO_aparece(self):
        venta = self._reserva(fechas_servicio=(_hoy(),))
        c = self._comanda(venta, objetivo=_en(_hoy() + timedelta(days=1)))
        self.assertNotIn(c.id, self._ids_de_hoy())

    def test_sin_objetivo_pero_con_servicio_hoy_aparece(self):
        venta = self._reserva(fechas_servicio=(_hoy(),))
        c = self._comanda(venta, objetivo=None)
        self.assertIn(c.id, self._ids_de_hoy())

    def test_sin_objetivo_y_servicio_a_futuro_NO_aparece(self):
        """Cocina no prepara hoy el pedido de una estadía del próximo sábado."""
        venta = self._reserva(fechas_servicio=(_hoy() + timedelta(days=4),))
        c = self._comanda(venta, objetivo=None)
        self.assertNotIn(c.id, self._ids_de_hoy())


class EstadoTest(_Base):

    def test_borrador_NO_aparece(self):
        """Un borrador es el carrito del cliente, no un pedido confirmado."""
        venta = self._reserva(fechas_servicio=(_hoy(),))
        c = self._comanda(venta, estado='borrador')
        self.assertNotIn(c.id, self._ids_de_hoy())

    def test_procesando_SI_aparece(self):
        venta = self._reserva(fechas_servicio=(_hoy(),))
        c = self._comanda(venta, estado='procesando')
        self.assertIn(c.id, self._ids_de_hoy())

    def test_entregada_y_cancelada_NO_aparecen(self):
        venta = self._reserva(fechas_servicio=(_hoy(),))
        for estado in ('entregada', 'cancelada', 'pendiente_pago', 'pago_fallido'):
            c = self._comanda(venta, estado=estado)
            self.assertNotIn(c.id, self._ids_de_hoy(), estado)


class ContadorFueraDeHoyTest(_Base):
    """Nada desaparece en silencio."""

    def test_cuenta_las_que_quedan_para_otro_dia(self):
        venta = self._reserva(fechas_servicio=(_hoy(),))
        self._comanda(venta, objetivo=_en(_hoy()))                       # entra hoy
        self._comanda(venta, objetivo=_en(_hoy() + timedelta(days=1)))   # mañana
        self._comanda(venta, objetivo=_en(_hoy() + timedelta(days=3)))   # en 3 días
        self.assertEqual(comandas_fuera_de_hoy(_hoy()), 2)

    def test_no_cuenta_borradores_ni_entregadas(self):
        venta = self._reserva(fechas_servicio=(_hoy(),))
        self._comanda(venta, estado='borrador', objetivo=_en(_hoy() + timedelta(days=1)))
        self._comanda(venta, estado='entregada', objetivo=_en(_hoy() + timedelta(days=1)))
        self.assertEqual(comandas_fuera_de_hoy(_hoy()), 0)


class FechaObjetivoAlConfirmarTest(_Base):
    """Que la comanda nazca anclada, en vez de depender de un rescate."""

    def test_con_servicios_usa_el_primero(self):
        from ventas.views_comandas_cliente import _fecha_objetivo_de
        sabado = _hoy() + timedelta(days=4)
        venta = self._reserva(fechas_servicio=(sabado, sabado + timedelta(days=1)))
        self.assertEqual(timezone.localtime(_fecha_objetivo_de(venta)).date(), sabado)

    def test_sin_servicios_usa_HOY(self):
        from ventas.views_comandas_cliente import _fecha_objetivo_de
        venta = self._reserva(fechas_servicio=())
        self.assertEqual(timezone.localtime(_fecha_objetivo_de(venta)).date(), _hoy())

    def test_sin_reserva_no_revienta(self):
        from ventas.views_comandas_cliente import _fecha_objetivo_de
        self.assertEqual(timezone.localtime(_fecha_objetivo_de(None)).date(), _hoy())


class UnaSolaConsultaTest(_Base):
    """La página y el sonido tienen que leer LO MISMO.

    Antes era la misma consulta copiada en dos lugares (líneas 807 y 904), que
    es exactamente cómo un arreglo se aplica a medias: se corrige una y la otra
    queda muda. Si alguien vuelve a duplicarla, esto falla.
    """

    def tearDown(self):
        """Limpia el usuario que dejó el login en el thread-local.

        `ThreadLocalMiddleware` guarda el usuario del request en un thread-local
        que NADIE limpia al terminar. Cuando este test hace login y termina, la
        BD hace rollback y ese usuario deja de existir — pero el thread-local
        sigue apuntándolo. La suite siguiente crea un Pago, un signal llama a
        `get_current_user()` y revienta con "usuario_id=1 is not present in
        auth_user". Los tests pasaban solos y fallaban en conjunto.
        """
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def test_el_endpoint_del_sonido_devuelve_el_caso_real(self):
        from django.contrib.auth import get_user_model
        venta = self._reserva(fechas_servicio=())
        c = self._comanda(venta, objetivo=None)

        User = get_user_model()
        User.objects.create_user('staff9301', password='x', is_staff=True)
        self.client.login(username='staff9301', password='x')

        r = self.client.get(reverse('ventas:comandas_pendientes_api'))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertTrue(datos['success'])
        self.assertIn(c.id, [x['id'] for x in datos['comandas']])

    def test_el_codigo_NO_vuelve_a_duplicar_la_consulta(self):
        import io
        import os
        from django.conf import settings
        ruta = os.path.join(settings.BASE_DIR, 'ventas', 'views', 'agenda_operativa_view.py')
        lineas = io.open(ruta, encoding='utf-8').read().splitlines()
        # Los comentarios explican POR QUÉ se sacó el filtro y nombran el campo:
        # sin descartarlos, este test se dispara con su propia documentación.
        codigo = '\n'.join(l for l in lineas if not l.lstrip().startswith('#'))

        # Una sola definición del filtro, y ambos consumidores la llaman.
        self.assertEqual(codigo.count('def comandas_para_cocina'), 1)
        self.assertGreaterEqual(codigo.count('comandas_para_cocina(hoy)'), 2)
        # El filtro que dejaba comandas invisibles no puede volver.
        self.assertNotIn('creada_por_cliente=True', codigo)
