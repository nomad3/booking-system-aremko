"""Tests H-080: Luna agrega ambientaciones al carrito cuando el cliente confirma.

Contrato:
- `_resolver_ambientacion(nombre)` resuelve por nombre (icontains) SOLO si matchea
  UNA ambientación activa con precio real (>1); 0 o 2+ matches → None (sin adivinar).
- `_es_ambientacion(servicio_id)` detecta la categoría para forzar cantidad=1 en el
  handler (el precio de servicio es base × cantidad_personas: con 2 se duplicaría).

NOTA: la suite local sigue bloqueada por el drift AR-033/AR-034; estos tests quedan
para CI / cuando eso se resuelva.
"""
from django.test import TestCase

from ventas.models import CategoriaServicio, Servicio
from whatsapp_agent.agent import (
    _cliente_confirmo_ambientacion,
    _cliente_eligio_producto,
    _es_ambientacion,
    _resolver_ambientacion,
)


class ResolverAmbientacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat_amb = CategoriaServicio.objects.create(nombre='Ambientaciones')
        cat_tinas = CategoriaServicio.objects.create(nombre='Tinas')

        def servicio(nombre, precio, categoria, activo=True):
            return Servicio.objects.create(
                nombre=nombre, precio_base=precio, duracion=60,
                categoria=categoria, activo=activo)

        cls.r1 = servicio('Ambientación romántica R1', 32000, cat_amb)
        cls.r2 = servicio('Ambientación romántica R2', 68000, cat_amb)
        servicio('Ambientación Cortesia', 0, cat_amb)                # $0 → fuera
        servicio('Ambientación Vieja', 30000, cat_amb, activo=False)  # inactiva → fuera
        cls.tina = servicio('Tina Llaima', 30000, cat_tinas)

    def test_resuelve_nombre_exacto_y_parcial_unico(self):
        self.assertEqual(_resolver_ambientacion('Ambientación romántica R1'), self.r1.id)
        # "la R1 de 32.000" → el modelo puede pasar solo "R1": sigue siendo único.
        self.assertEqual(_resolver_ambientacion('R1'), self.r1.id)

    def test_ambiguo_no_adivina(self):
        self.assertIsNone(_resolver_ambientacion('romántica'))  # matchea R1 y R2

    def test_inactivas_y_cortesias_no_resuelven(self):
        self.assertIsNone(_resolver_ambientacion('Vieja'))
        self.assertIsNone(_resolver_ambientacion('Cortesia'))
        self.assertIsNone(_resolver_ambientacion(''))
        self.assertIsNone(_resolver_ambientacion(None))

    def test_es_ambientacion(self):
        self.assertTrue(_es_ambientacion(self.r1.id))
        self.assertFalse(_es_ambientacion(self.tina.id))
        self.assertFalse(_es_ambientacion(9999999))


class ClienteConfirmoAmbientacionTests(TestCase):
    """H-083: gate anti agregado prematuro (función PURA, sin DB).

    Caso real 2026-07-30: "¿Tienes ambientaciones?" → el modelo agregó la R1 al
    carrito de inmediato. Este gate lo hace imposible en código."""

    R1 = 'Ambientación romántica R1'

    def test_pregunta_generica_no_confirma(self):
        self.assertFalse(_cliente_confirmo_ambientacion('Tienes ambientaciones ?', self.R1))
        self.assertFalse(_cliente_confirmo_ambientacion('y que ambientaciones tienes', self.R1))
        self.assertFalse(_cliente_confirmo_ambientacion(
            'quisiera saber qué incluye la decoración', self.R1))

    def test_nombrarla_confirma(self):
        self.assertTrue(_cliente_confirmo_ambientacion('reservame la R1 de 32.000', self.R1))
        self.assertTrue(_cliente_confirmo_ambientacion('quiero la romántica', self.R1))
        self.assertTrue(_cliente_confirmo_ambientacion(
            'el azul porfa', 'Decoración Simple · Azul'))

    def test_asentimiento_confirma(self):
        self.assertTrue(_cliente_confirmo_ambientacion('sí', self.R1))
        self.assertTrue(_cliente_confirmo_ambientacion('dale, agrégala', self.R1))
        self.assertTrue(_cliente_confirmo_ambientacion('esa misma', self.R1))

    def test_negacion_nunca_confirma(self):
        self.assertFalse(_cliente_confirmo_ambientacion('no, esa no', self.R1))
        self.assertFalse(_cliente_confirmo_ambientacion('todavía no', self.R1))
        self.assertFalse(_cliente_confirmo_ambientacion('no quiero ambientación', self.R1))

    def test_vacio_no_confirma(self):
        self.assertFalse(_cliente_confirmo_ambientacion('', self.R1))
        self.assertFalse(_cliente_confirmo_ambientacion(None, self.R1))


class ClienteEligioProductoTests(TestCase):
    """H-084: gate anti "variante elegida por el modelo" (función PURA, candidatos
    inyectados — sin DB). Caso real 2026-07-30: "Si un jugo" → el modelo agregó
    Frambuesa al carrito Y preguntó el sabor en el mismo turno."""

    CAT = [
        (107, 'Jugo Natural Arandanos'), (108, 'Jugo Natural de Frambuesa'),
        (109, 'Jugo Natural de Melon'), (9, 'Jugos Naturales'),
        (3, 'Tabla Quesos'), (123, 'Tabla Mixta de Quesos y Jamones'),
        (111, 'Cafe Marley Americano Mediano'), (112, 'Cafe Marley Americano Grande'),
    ]
    H_MELON = '[Aremko]: ¿Te agrego el jugo natural de melón para acompañar?'
    H_DOBLE = '[Aremko]: ¿Te gustaría sumar una tabla de quesos o un jugo natural?'

    def _ok(self, mensaje, historial, target):
        return _cliente_eligio_producto(mensaje, historial, target, candidatos=self.CAT)[0]

    def test_generico_bloquea(self):
        self.assertFalse(self._ok('Si un jugo', self.H_DOBLE, 108))  # el bug real
        self.assertFalse(self._ok('un cafe americano', '', 112))     # ¿mediano o grande?

    def test_variante_nombrada_pasa(self):
        self.assertTrue(self._ok('quiero jugo de frambuesa', '', 108))
        self.assertTrue(self._ok('cafe americano grande', '', 112))
        # cobertura: "tabla de quesos" es la Tabla Quesos, no la Mixta
        self.assertTrue(self._ok('una tabla de quesos porfa', '', 3))

    def test_asentimiento_a_oferta_especifica_pasa(self):
        self.assertTrue(self._ok('sí', self.H_MELON, 109))

    def test_asentimiento_a_oferta_doble_bloquea(self):
        self.assertFalse(self._ok('sí', self.H_DOBLE, 3))

    def test_producto_distinto_al_pedido_bloquea(self):
        # Cliente pidió melón; el modelo intenta agregar frambuesa → bloqueado.
        self.assertFalse(self._ok('jugo de melon', '', 108))
