"""El carrito abandonado se vacía cuando el cliente vuelve (Jorge, 26-09-2026).

Un cliente armó un carrito en junio y no aprobó la cotización. El carrito solo se vacía al
crearse la reserva, así que siguió ahí: en septiembre Luna le sumó esos ítems a la cotización
nueva y le dio totales equivocados. Luna ya no lo veía en su estado (lo oculta pasadas 24
horas), pero sus herramientas sí lo usaban. Ahora, un carrito con más de 24 horas sin cambios
(lo mismo que dura una cotización) se vacía en cuanto el cliente vuelve.

Ejecutar:
    python manage.py test whatsapp_agent.tests.test_carrito_abandonado
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from carrito_reservas.models import CarritoReserva
from carrito_reservas.services import CarritoService
from destino_puerto_varas.services.llm.openrouter_provider import LLMResult
from ventas.models import CategoriaServicio, Servicio
from whatsapp_agent import agent

PROVIDER = ('destino_puerto_varas.services.llm.openrouter_provider.'
            'OpenRouterProvider.generate_with_tools')
CANAL, PHONE = 'whatsapp', '+56900000626'
DE_JUNIO = {'tipo': 'servicio', 'servicio_id': 999, 'nombre': 'Tina de junio',
            'fecha': '2026-06-14', 'hora': '19:00', 'cantidad_personas': 2,
            'precio_unitario': 25000.0, 'subtotal': 50000.0}
CLIENTE = {'nombre': 'Ana Soto', 'email': 'a@correo.cl', 'documento_identidad': '12.345.678-5',
           'comuna': 'Puerto Varas'}


def _carrito(hace):
    """El carrito de junio, sin cambios desde `hace`."""
    c = CarritoReserva.objects.create(canal=CANAL, external_id=PHONE, items=[DE_JUNIO],
                                      subtotal_servicios=Decimal('50000'), total=Decimal('50000'))
    CarritoReserva.objects.filter(pk=c.pk).update(updated_at=timezone.now() - hace)
    c.refresh_from_db()
    return c


def _turno(herramienta, args, texto='Listo', envoltorio=True):
    """Un turno de Luna en que el modelo llama a `herramienta` y responde `texto`."""
    visto = {}

    def generate_with_tools(self, messages, tools, tool_executor, **kwargs):
        visto['resultado'] = tool_executor(herramienta, args)
        return LLMResult(texto, 'google/gemini-2.5-flash', 10, 5, 100)

    producir = agent._producir_borrador if envoltorio else agent._producir_borrador_inner
    with mock.patch(PROVIDER, generate_with_tools):
        producir(agent.get_config(), 'hola, ¿me confirmas?', '', phone=PHONE, canal=CANAL)
    return visto['resultado']


class ElCarritoAbandonado(TestCase):
    @classmethod
    def setUpTestData(cls):
        tinas = CategoriaServicio.objects.create(nombre='Tinas')
        cls.tina = Servicio.objects.create(
            nombre='Tina Tronador', categoria=tinas, tipo_servicio='tina',
            precio_base=Decimal('30000'), duracion=120, activo=True, publicado_web=True,
            slots_disponibles={}, capacidad_minima=1, capacidad_maxima=4)

    def test_al_volver_se_vacia_y_conserva_el_id(self):
        viejo = _carrito(timedelta(days=100))
        carrito = CarritoReserva.obtener_o_crear(CANAL, PHONE)
        self.assertEqual(carrito.pk, viejo.pk)
        self.assertEqual(carrito.items, [])
        self.assertEqual(carrito.total, 0)
        self.assertEqual(carrito.estado, 'activo')

    def test_uno_de_hoy_se_conserva(self):
        _carrito(timedelta(hours=3))
        self.assertEqual(CarritoReserva.obtener_o_crear(CANAL, PHONE).items, [DE_JUNIO])

    def test_el_pedido_nuevo_no_arrastra_lo_de_junio(self):
        # El caso real: Luna agrega lo nuevo y el total salía con lo de junio sumado.
        _carrito(timedelta(days=100))
        r = CarritoService.agregar_servicio(CANAL, PHONE, self.tina.id, '2026-09-27', '14:30', 2)
        self.assertTrue(r['success'], r)
        carrito = CarritoReserva.objects.get(canal=CANAL, external_id=PHONE)
        self.assertEqual([it['nombre'] for it in carrito.items], ['Tina Tronador'])
        self.assertEqual(int(carrito.total), 60000)

    def test_luna_no_lo_ve_ni_lo_cuenta(self):
        _carrito(timedelta(days=100))
        self.assertNotIn('Tina de junio', agent._estado_estructurado(CANAL, PHONE))
        self.assertEqual(agent._estado_cotizacion_carrito(CANAL, PHONE), (False, False))

    def test_la_bandeja_muestra_solo_uno_de_hoy(self):
        from inbox_omnicanal.views import _carrito_en_curso
        _carrito(timedelta(hours=3))
        self.assertEqual(_carrito_en_curso(CANAL, PHONE)['servicios'][0]['servicio_nombre'],
                         'Tina de junio')
        CarritoReserva.objects.update(updated_at=timezone.now() - timedelta(days=100))
        self.assertIsNone(_carrito_en_curso(CANAL, PHONE))

    def test_la_ambientacion_no_hereda_la_fecha_de_junio(self):
        # La ambientación toma la fecha de la primera línea con fecha del carrito.
        ambientaciones = CategoriaServicio.objects.create(nombre='Ambientaciones')
        r1 = Servicio.objects.create(
            nombre='Ambientación R1', categoria=ambientaciones, tipo_servicio='otro',
            precio_base=Decimal('32000'), duracion=60, activo=True, publicado_web=False,
            slots_disponibles={}, capacidad_minima=1, capacidad_maxima=1)
        _carrito(timedelta(days=100))
        agent._agregar_ambientacion_al_carrito(CANAL, PHONE, r1.id)
        carrito = CarritoReserva.objects.get(canal=CANAL, external_id=PHONE)
        self.assertEqual([(it['nombre'], it['fecha']) for it in carrito.items],
                         [('Ambientación R1', None)])

    def test_confirmar_no_cotiza_lo_de_junio(self):
        # La herramienta se cuida sola: sin el vaciado del inicio del turno y sin el paso del
        # upgrade de ambientación, que también lee el carrito antes que ella.
        _carrito(timedelta(days=100))
        with mock.patch.object(agent, 'aplicar_upgrade_si_acepto', return_value=''):
            r = _turno('confirmar_reserva_carrito', CLIENTE, envoltorio=False)
        self.assertEqual(r.get('error'), 'carrito_vacio', r)

    def test_un_turno_escalado_no_lo_resucita(self):
        # El rollback de un turno escalado devuelve el carrito a la foto del inicio: si la
        # foto tuviera lo de junio, volvería con fecha de hoy y Luna lo vería de nuevo.
        _carrito(timedelta(days=100))
        _turno('ver_carrito', {}, texto='[ESCALAR: prueba]')
        carrito = CarritoReserva.objects.get(canal=CANAL, external_id=PHONE)
        self.assertEqual(carrito.items, [])
        self.assertNotIn('Tina de junio', agent._estado_estructurado(CANAL, PHONE))
