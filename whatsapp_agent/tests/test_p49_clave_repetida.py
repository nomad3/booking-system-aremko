"""P-49 (23-09-2026): una clave de idempotencia ya usada no termina en «error interno».

Las claves que arman las herramientas de Luna son estables por CLIENTE, no por
pedido (`carrito-<id>` es uno por cliente para siempre; `ritual-<tel>-<fecha>`
se puede volver a pedir; `gc-<tel>-<exp>-<n>` se puede volver a comprar), y
las herramientas sin clave guardaban la cadena vacía, que la unique deja
existir una sola vez. Con cualquiera de las dos, la base respondía «duplicate
key» y el cliente recibía un error. En producción: 4 fallas de carrito y 5 de
«agregar a mi reserva» en una semana; esta última no creó NUNCA una propuesta
desde que nació (la fila vacía es del 19-06-2026 y la función, del 03-07).

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_p49_clave_repetida
"""
from __future__ import annotations

import inspect
from datetime import timedelta
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from ventas.models import CategoriaServicio, Cliente, Servicio, VentaReserva
from whatsapp_agent import idempotencia
from whatsapp_agent.giftcards import preparar_giftcard
from whatsapp_agent.models import PropuestaReserva
from whatsapp_agent.reserva_service import preparar_adicion_a_reserva, preparar_reserva
from whatsapp_agent.tests.test_giftcards_luna import (CLIENTE, HISTORIAL,
                                                      _experiencia, _SinSenalesDeVenta)

TEL = '+56911111111'


def _fila_vacia_de_junio():
    """La fila que hay en producción desde el 19-06-2026 (id 7, expirada)."""
    return PropuestaReserva.objects.create(
        propuesta_id='legado-junio', idempotency_key='', canal='whatsapp',
        external_id='+56912345678', payload={}, cliente_data={}, servicios=[],
        total=60000, estado='expirada',
        expires_at=timezone.now() - timedelta(days=90))


class Base(_SinSenalesDeVenta, TestCase):
    @classmethod
    def setUpTestData(cls):
        tinas = CategoriaServicio.objects.create(nombre='Tinas')
        cls.tina = Servicio.objects.create(
            nombre='Tina Hornopiren', precio_base=25000, categoria=tinas,
            duracion=60, tipo_servicio='tina', activo=True)
        cls.otra_tina = Servicio.objects.create(
            nombre='Tina Calbuco', precio_base=25000, categoria=tinas,
            duracion=60, tipo_servicio='tina', activo=True)
        cls.cliente = Cliente.objects.create(nombre='María Prueba', telefono=TEL)

    def _payload(self, servicio=None, fecha='2026-10-10', hora='16:00'):
        return {'cliente': dict(CLIENTE),
                'servicios': [{'servicio_id': (servicio or self.tina).id, 'fecha': fecha,
                               'hora': hora, 'cantidad_personas': 2}]}

    def _preparar(self, payload=None, clave='carrito-7'):
        return preparar_reserva(canal='whatsapp', external_id=TEL,
                                payload=payload or self._payload(), idempotency_key=clave)

    def _convertir_en_reserva(self, propuesta_id, hace=timedelta(minutes=5)):
        """Lo que hace crear_reserva al aprobar, sin pasar por ella."""
        venta = VentaReserva.objects.create(cliente=self.cliente)
        PropuestaReserva.objects.filter(propuesta_id=propuesta_id).update(
            estado='creada', reserva_id=venta.id, creada_at=timezone.now() - hace)
        return venta


class ConClave(Base):
    def test_reintento_con_la_propuesta_pendiente_devuelve_la_misma(self):
        a = self._preparar()
        b = self._preparar()
        self.assertEqual(a['propuesta_id'], b['propuesta_id'])
        self.assertTrue(b.get('duplicada'))
        self.assertEqual(PropuestaReserva.objects.count(), 1)

    def test_el_cliente_que_vuelve_con_otro_pedido_no_recibe_error(self):
        # El carrito es uno por cliente: su segunda compra llega con la MISMA clave.
        primera = self._preparar()
        self._convertir_en_reserva(primera['propuesta_id'], hace=timedelta(days=60))
        r = self._preparar(self._payload(fecha='2026-12-05'))
        self.assertTrue(r['success'], r)
        self.assertNotEqual(r['propuesta_id'], primera['propuesta_id'])
        nueva = PropuestaReserva.objects.get(propuesta_id=r['propuesta_id'])
        self.assertEqual(nueva.idempotency_key, 'carrito-7#2')
        self.assertEqual(nueva.estado, 'pendiente')

    def test_el_reintento_del_pedido_nuevo_no_crea_una_tercera(self):
        primera = self._preparar()
        self._convertir_en_reserva(primera['propuesta_id'], hace=timedelta(days=60))
        b = self._preparar(self._payload(fecha='2026-12-05'))
        c = self._preparar(self._payload(fecha='2026-12-05'))
        self.assertEqual(b['propuesta_id'], c['propuesta_id'])
        self.assertEqual(PropuestaReserva.objects.count(), 2)

    def test_el_mismo_pedido_ya_convertido_en_reserva_se_avisa_sin_cotizar_de_nuevo(self):
        primera = self._preparar()
        venta = self._convertir_en_reserva(primera['propuesta_id'])
        r = self._preparar()
        self.assertTrue(r['success'])
        self.assertTrue(r.get('ya_creada'))
        self.assertEqual(r['reserva_id'], venta.id)
        self.assertIn(f'RES-{venta.id}', r['mensaje'])
        self.assertIn('NO armes otra', r['instruccion'])
        self.assertEqual(PropuestaReserva.objects.count(), 1)

    def test_si_la_reserva_se_borro_el_mismo_pedido_se_cotiza_de_nuevo(self):
        # Cancelar hoy es borrar: decir «ya está creada» sería mentirle.
        primera = self._preparar()
        venta = self._convertir_en_reserva(primera['propuesta_id'])
        VentaReserva.objects.filter(pk=venta.pk).delete()
        r = self._preparar()
        self.assertTrue(r['success'])
        self.assertFalse(r.get('ya_creada'))
        self.assertEqual(PropuestaReserva.objects.count(), 2)

    def test_pasado_un_dia_el_mismo_pedido_es_una_compra_nueva(self):
        primera = self._preparar()
        self._convertir_en_reserva(primera['propuesta_id'], hace=timedelta(days=2))
        r = self._preparar()
        self.assertTrue(r['success'])
        self.assertFalse(r.get('ya_creada'))
        self.assertEqual(PropuestaReserva.objects.count(), 2)

    def test_una_propuesta_vencida_o_descartada_no_bloquea_el_pedido(self):
        for estado in ('expirada', 'descartada'):
            with self.subTest(estado=estado):
                PropuestaReserva.objects.all().delete()
                primera = self._preparar(clave=f'ritual-{TEL}-2026-10-10')
                PropuestaReserva.objects.filter(propuesta_id=primera['propuesta_id']).update(estado=estado)
                r = self._preparar(clave=f'ritual-{TEL}-2026-10-10')
                self.assertTrue(r['success'], r)
                self.assertEqual(PropuestaReserva.objects.get(propuesta_id=r['propuesta_id']).idempotency_key,
                                 f'ritual-{TEL}-2026-10-10#2')

    def test_una_pendiente_ya_vencida_tampoco(self):
        primera = self._preparar()
        PropuestaReserva.objects.filter(propuesta_id=primera['propuesta_id']).update(
            expires_at=timezone.now() - timedelta(hours=1))
        r = self._preparar()
        self.assertTrue(r['success'], r)
        self.assertNotEqual(r['propuesta_id'], primera['propuesta_id'])

    def test_una_clave_parecida_no_es_de_la_misma_familia(self):
        # 'carrito-7' no puede confundirse con 'carrito-71'.
        self._preparar(clave='carrito-71')
        r = self._preparar(self._payload(servicio=self.otra_tina), clave='carrito-7')
        self.assertFalse(r.get('duplicada'))
        self.assertEqual(PropuestaReserva.objects.get(propuesta_id=r['propuesta_id']).idempotency_key,
                         'carrito-7')


class SinClave(Base):
    def setUp(self):
        super().setUp()
        _fila_vacia_de_junio()

    def test_con_la_fila_vacia_de_junio_se_puede_crear_igual(self):
        a = self._preparar(clave=None)
        b = self._preparar(self._payload(servicio=self.otra_tina), clave=None)
        self.assertTrue(a['success'], a)
        self.assertTrue(b['success'], b)
        self.assertNotEqual(a['propuesta_id'], b['propuesta_id'])

    def test_el_reintento_del_mismo_pedido_devuelve_el_mismo(self):
        a = self._preparar(clave=None)
        b = self._preparar(clave=None)
        self.assertEqual(a['propuesta_id'], b['propuesta_id'])
        self.assertTrue(b.get('duplicada'))

    def test_ya_no_se_guarda_la_clave_vacia(self):
        a = self._preparar(clave=None)
        clave = PropuestaReserva.objects.get(propuesta_id=a['propuesta_id']).idempotency_key
        self.assertTrue(clave.startswith('auto-'))


class AgregarAUnaReservaExistente(Base):
    """«Agregar a mi reserva» desde WhatsApp: nunca había creado una propuesta."""

    def setUp(self):
        super().setUp()
        _fila_vacia_de_junio()
        self.venta = VentaReserva.objects.create(cliente=self.cliente)

    def _agregar(self, servicio=None, hora='18:00'):
        return preparar_adicion_a_reserva(
            canal='whatsapp', external_id=TEL, reserva_id=self.venta.id,
            servicios_data=[{'servicio_id': (servicio or self.tina).id, 'fecha': '2026-10-10',
                             'hora': hora, 'cantidad_personas': 2}])

    def test_crea_la_propuesta_de_adicion(self):
        r = self._agregar()
        self.assertTrue(r['success'], r)
        p = PropuestaReserva.objects.get(propuesta_id=r['propuesta_id'])
        self.assertEqual(p.reserva_existente_id, self.venta.id)
        self.assertEqual(p.estado, 'pendiente')

    def test_el_reintento_no_la_duplica(self):
        a = self._agregar()
        b = self._agregar()
        self.assertEqual(a['propuesta_id'], b['propuesta_id'])
        self.assertTrue(b.get('duplicada'))

    def test_otro_pedido_para_la_misma_reserva_es_otra_propuesta(self):
        a = self._agregar()
        b = self._agregar(servicio=self.otra_tina)
        self.assertNotEqual(a['propuesta_id'], b['propuesta_id'])

    def test_no_se_confunde_con_una_propuesta_de_reserva_nueva(self):
        # Mismo servicio y hora, pero una es «reserva nueva» y la otra «agregar».
        nueva = self._preparar(self._payload(hora='18:00'), clave=None)
        r = self._agregar()
        self.assertNotEqual(nueva['propuesta_id'], r['propuesta_id'])


class GiftCards(_SinSenalesDeVenta, TestCase):
    def setUp(self):
        super().setUp()
        self.exp = _experiencia()
        self.cliente = Cliente.objects.create(nombre='María Prueba', telefono=TEL)

    def _comprar(self, destinatario='Los papás de María'):
        # H-094: el destinatario tiene que haberlo dicho el cliente.
        historial = HISTORIAL + f'[Cliente]: quiero otra igual, para {destinatario}\n'
        return preparar_giftcard(
            canal='whatsapp', external_id=TEL, cliente_data=dict(CLIENTE),
            historial=historial, sin_datos_regalo=True,
            giftcards_data=[{'experiencia_id': 'masaje_relajacion', 'cantidad': 2,
                             'destinatario_nombre': destinatario}],
            idempotency_key=f'gc-{TEL}-masaje_relajacion-2')

    def test_la_misma_compra_ya_hecha_se_avisa(self):
        a = self._comprar()
        venta = VentaReserva.objects.create(cliente=self.cliente)
        PropuestaReserva.objects.filter(propuesta_id=a['propuesta_id']).update(
            estado='creada', reserva_id=venta.id, creada_at=timezone.now())
        r = self._comprar()
        self.assertTrue(r.get('ya_creada'), r)
        self.assertIn('ya quedó registrada', r['mensaje'])

    def test_otra_gift_card_igual_para_otra_persona_es_una_compra_nueva(self):
        a = self._comprar()
        venta = VentaReserva.objects.create(cliente=self.cliente)
        PropuestaReserva.objects.filter(propuesta_id=a['propuesta_id']).update(
            estado='creada', reserva_id=venta.id, creada_at=timezone.now())
        r = self._comprar(destinatario='Mi hermana')
        self.assertTrue(r['success'], r)
        self.assertFalse(r.get('ya_creada'))
        self.assertEqual(PropuestaReserva.objects.get(propuesta_id=r['propuesta_id']).idempotency_key,
                         f'gc-{TEL}-masaje_relajacion-2#2')


class SiDosLlamadasChocan(Base):
    """La última red: la clave se ocupa entre la decisión y la creación."""

    def test_devuelve_la_que_gano_en_vez_de_reventar(self):
        ganadora = self._preparar(clave='carrito-9')
        real = idempotencia.resolver
        llamadas = []

        def resolver_con_carrera(*a, **kw):
            llamadas.append(1)
            if len(llamadas) == 1:
                # Vio la clave libre... y otra llamada la tomó justo después.
                return idempotencia.Decision('nueva', clave='carrito-9')
            return real(*a, **kw)

        with mock.patch.object(idempotencia, 'resolver', side_effect=resolver_con_carrera):
            r = self._preparar(clave='carrito-9')
        self.assertTrue(r['success'], r)
        self.assertEqual(r['propuesta_id'], ganadora['propuesta_id'])
        self.assertEqual(PropuestaReserva.objects.count(), 1)

    def test_si_no_encuentra_a_la_ganadora_no_muestra_un_error_tecnico(self):
        self._preparar(clave='carrito-9')
        with mock.patch.object(idempotencia, 'resolver',
                               return_value=idempotencia.Decision('nueva', clave='carrito-9')):
            r = self._preparar(self._payload(servicio=self.otra_tina), clave='carrito-9')
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'propuesta_en_curso')
        self.assertNotIn('duplicate', r['mensaje'])


class LasHerramientasPasanElAviso(SimpleTestCase):
    """El despacho vive dentro de una función anidada del agente: se revisa la
    fuente (mismo recurso que test_dia.ElBloqueoQuedaCableado)."""

    def _rama(self, tool, largo=9000):
        from whatsapp_agent import agent
        fuente = inspect.getsource(agent)
        i = fuente.index(f"if name == '{tool}':")
        return fuente[i:i + largo]

    def test_cada_confirmacion_devuelve_el_aviso_antes_de_seguir(self):
        # (herramienta, la llamada que crea, lo primero que hace cuando creó)
        casos = (
            ('confirmar_reserva_carrito', 'servicio_preparar_reserva(',
             "[confirmar_reserva_carrito] propuesta %s creada"),
            ('confirmar_ritual', 'servicio_preparar_reserva(', "[confirmar_ritual] propuesta %s creada"),
            ('confirmar_dia', 'servicio_preparar_reserva(', 'bloquear_noche_previa('),
            ('confirmar_refugio', 'servicio_preparar_reserva(', "[confirmar_refugio] propuesta %s creada"),
            ('preparar_giftcard', '_preparar_gc(', '¡Qué lindo regalo!'),
        )
        for tool, llamada, exito in casos:
            with self.subTest(tool=tool):
                rama = self._rama(tool)
                aviso = rama.index("resultado.get('ya_creada')")
                self.assertLess(rama.index(llamada), aviso)
                self.assertLess(aviso, rama.index(exito, rama.index(llamada)))

    def test_la_noche_previa_no_se_vuelve_a_bloquear(self):
        rama = self._rama('confirmar_dia')
        self.assertLess(rama.index("resultado.get('ya_creada')"),
                        rama.index('bloquear_noche_previa('))
