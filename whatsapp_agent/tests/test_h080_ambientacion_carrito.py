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
from whatsapp_agent.agent import _es_ambientacion, _resolver_ambientacion


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
