"""Tests del endpoint /api/luna/catalogo-agregables/ (picker "+ Agregar ítem" del
cajón de cotización en la bandeja aremko-cli).

Reglas que se prueban:
- Requiere X-API-Key (LunaAPIKeyAuthentication).
- Ambientaciones: solo servicios de la categoría "Ambientaciones", activos y con
  precio real (>1) — quedan fuera cortesías en $0 y servicios de otras categorías.
- Productos: solo Comestibles/Bebestibles con precio real (>1) — quedan fuera las
  categorías internas (Sueldos, Insumos...) y los centinelas en $1.
"""

from django.test import TestCase, override_settings

from ventas.models import (
    CategoriaProducto,
    CategoriaServicio,
    Producto,
    Servicio,
)

API_KEY = 'test-key-catalogo-agregables'
URL = '/api/luna/catalogo-agregables/'


@override_settings(LUNA_API_KEY=API_KEY)
class CatalogoAgregablesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat_amb = CategoriaServicio.objects.create(nombre='Ambientaciones')
        cat_tinas = CategoriaServicio.objects.create(nombre='Tinas')

        def servicio(nombre, precio, categoria, activo=True):
            return Servicio.objects.create(
                nombre=nombre,
                precio_base=precio,
                duracion=60,
                categoria=categoria,
                activo=activo,
            )

        cls.amb_ok = servicio('Ambientación romántica R1', 32000, cat_amb)
        servicio('Ambientación Cortesia', 0, cat_amb)              # $0 → fuera
        servicio('Ambientación Mama vieja', 18000, cat_amb, activo=False)  # inactiva → fuera
        servicio('Tina Llaima', 30000, cat_tinas)                  # otra categoría → fuera

        cat_com = CategoriaProducto.objects.create(nombre='Comestibles')
        cat_beb = CategoriaProducto.objects.create(nombre='Bebestibles')
        cat_sueldos = CategoriaProducto.objects.create(nombre='Sueldos')

        def producto(nombre, precio, categoria):
            return Producto.objects.create(
                nombre=nombre,
                precio_base=precio,
                cantidad_disponible=10,
                categoria=categoria,
            )

        cls.prod_tabla = producto('Tabla Quesos', 20000, cat_com)
        cls.prod_jugo = producto('Jugo Natural de Piña', 3500, cat_beb)
        producto('Frutos Seco Tabla', 0, cat_com)   # $0 insumo → fuera
        producto('Fruta', 1, cat_com)               # centinela $1 → fuera
        producto('Sueldos', 1000000, cat_sueldos)   # categoría interna → fuera

    def test_requiere_api_key(self):
        resp = self.client.get(URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_api_key_invalida(self):
        resp = self.client.get(URL, HTTP_X_API_KEY='llave-mala')
        self.assertIn(resp.status_code, (401, 403))

    def test_catalogo_filtrado(self):
        resp = self.client.get(URL, HTTP_X_API_KEY=API_KEY)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        ambientaciones = data['ambientaciones']
        nombres_amb = [a['nombre'] for a in ambientaciones]
        self.assertEqual(nombres_amb, ['Ambientación romántica R1'])
        self.assertEqual(ambientaciones[0]['servicio_id'], self.amb_ok.id)
        self.assertEqual(ambientaciones[0]['precio'], 32000)

        productos = data['productos']
        nombres_prod = [p['nombre'] for p in productos]
        # Bebestibles ordena antes que Comestibles (orden por categoría, luego nombre).
        self.assertEqual(nombres_prod, ['Jugo Natural de Piña', 'Tabla Quesos'])
        por_nombre = {p['nombre']: p for p in productos}
        self.assertEqual(por_nombre['Tabla Quesos']['producto_id'], self.prod_tabla.id)
        self.assertEqual(por_nombre['Tabla Quesos']['categoria'], 'Comestibles')
        self.assertEqual(por_nombre['Jugo Natural de Piña']['precio'], 3500)
