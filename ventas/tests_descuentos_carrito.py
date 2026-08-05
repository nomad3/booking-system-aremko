"""Los descuentos se pueden agregar al carrito desde el cajón de la bandeja.

Caso real (Jorge, 2026-08-05): "tengo que agregar un descuento al carrito y esos
servicios y productos que no son tales pero que sirven para crear descuento… y no
puedo".

Estaban bloqueados por DOS filtros a la vez, y ninguno los apuntaba a propósito:
  · su categoría ('Descuento') está en `CATEGORIAS_PRODUCTO_INTERNAS`, y
  · `precio_base > 1` —puesto para sacar cortesías en $0 y centinelas en $1— se
    llevaba por delante cualquier precio negativo.

⚠️ La otra mitad del asunto: un descuento **se factura pero NO se prepara**. El
camino que agrega productos a una cotización ya creada arma una Comanda de
cocina con cada producto; sin gate, agregar un descuento le manda a cocina un
pedido de "Descuento -1000". H-097 acababa de sacar 316 «Gift Cards» de las
comandas viejas por exactamente este tipo de fuga.

Ejecutar:
    python manage.py test ventas.tests_descuentos_carrito
"""
from decimal import Decimal

from django.test import TestCase, override_settings

from .models import CategoriaProducto, Producto

URL = '/api/luna/catalogo-agregables/'
KEY = 'clave-de-prueba-luna'


@override_settings(LUNA_API_KEY=KEY)
class PickerTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.cat_comida = CategoriaProducto.objects.create(id=9501, nombre='Comestibles')
        cls.cat_desc = CategoriaProducto.objects.create(id=9502, nombre='Descuento')
        cls.cat_insumos = CategoriaProducto.objects.create(id=9503, nombre='Insumos Masaje')

        cls.tabla = Producto.objects.create(
            id=9511, nombre='Tabla Quesos', precio_base=Decimal('20000'),
            cantidad_disponible=10, categoria=cls.cat_comida)
        cls.desc_1k = Producto.objects.create(
            id=9512, nombre='Descuento -1000', precio_base=Decimal('-1000'),
            cantidad_disponible=0, categoria=cls.cat_desc)
        cls.desc_10k = Producto.objects.create(
            id=9513, nombre='Descuento -10000', precio_base=Decimal('-10000'),
            cantidad_disponible=0, categoria=cls.cat_desc)
        cls.cortesia = Producto.objects.create(
            id=9514, nombre='Frutos Seco Cortesía', precio_base=Decimal('0'),
            cantidad_disponible=5, categoria=cls.cat_comida)
        cls.insumo = Producto.objects.create(
            id=9515, nombre='Aceite de masaje', precio_base=Decimal('8000'),
            cantidad_disponible=5, categoria=cls.cat_insumos)

    def _catalogo(self):
        r = self.client.get(URL, HTTP_X_API_KEY=KEY)
        self.assertEqual(r.status_code, 200)
        return r.json()

    def _nombres(self):
        return [p['nombre'] for p in self._catalogo()['productos']]

    def test_EL_CASO_REAL_los_descuentos_aparecen(self):
        nombres = self._nombres()
        self.assertIn('Descuento -1000', nombres)
        self.assertIn('Descuento -10000', nombres)

    def test_van_al_FINAL_y_no_entre_la_comida(self):
        """"Descuento" cae justo después de "Comestibles" si se ordena solo por
        categoría. Nadie debería toparse con un descuento buscando una tabla."""
        nombres = self._nombres()
        self.assertEqual(nombres[-2:], ['Descuento -10000', 'Descuento -1000'])
        self.assertLess(nombres.index('Tabla Quesos'), nombres.index('Descuento -1000'))

    def test_el_mas_grande_primero(self):
        """Para un descuento alto conviene tener arriba la denominación grande:
        menos unidades, menos margen de error."""
        nombres = self._nombres()
        self.assertLess(nombres.index('Descuento -10000'), nombres.index('Descuento -1000'))

    def test_el_precio_llega_NEGATIVO(self):
        d = next(p for p in self._catalogo()['productos'] if p['nombre'] == 'Descuento -1000')
        self.assertEqual(d['precio'], -1000)

    def test_la_excepcion_NO_abre_el_filtro_entero(self):
        """Lo que se pidió fue dejar pasar los descuentos, no las cortesías ni
        los insumos: esos siguen fuera."""
        nombres = self._nombres()
        self.assertNotIn('Frutos Seco Cortesía', nombres)   # $0
        self.assertNotIn('Aceite de masaje', nombres)       # categoría interna

    def test_sin_API_KEY_no_responde(self):
        self.assertNotEqual(self.client.get(URL).status_code, 200)


class NoSePreparaEnCocinaTest(TestCase):
    """Un descuento se FACTURA pero no se prepara. Los dos filtros conviven."""

    @classmethod
    def setUpTestData(cls):
        cls.cat_desc = CategoriaProducto.objects.create(id=9521, nombre='Descuento')
        cls.cat_comida = CategoriaProducto.objects.create(id=9522, nombre='Comestibles')

    def test_el_gate_de_cocina_sigue_rechazando_descuentos(self):
        from ventas.admin import _se_prepara_en_cocina
        desc = Producto.objects.create(
            id=9531, nombre='Descuento -1000', precio_base=Decimal('-1000'),
            cantidad_disponible=0, categoria=self.cat_desc)
        self.assertFalse(_se_prepara_en_cocina(desc))

    def test_pero_una_tabla_si_se_prepara(self):
        from ventas.admin import _se_prepara_en_cocina
        tabla = Producto.objects.create(
            id=9532, nombre='Tabla Quesos', precio_base=Decimal('20000'),
            cantidad_disponible=10, categoria=self.cat_comida)
        self.assertTrue(_se_prepara_en_cocina(tabla))

    def test_el_camino_de_la_cotizacion_APLICA_ese_gate(self):
        """Fijado por inspección del fuente: si alguien saca esta llamada, los
        descuentos vuelven a la cocina y nadie se entera hasta ver la agenda."""
        import inspect
        from ventas.views import luna_api_views
        fuente = inspect.getsource(luna_api_views)
        i_gate = fuente.find('_se_prepara_en_cocina(producto)')
        i_linea = fuente.find('DetalleComanda.objects.create')
        self.assertNotEqual(i_gate, -1, 'se perdió el gate de cocina')
        self.assertLess(i_gate, i_linea, 'el gate quedó DESPUÉS de crear la línea')

    def test_las_dos_listas_no_se_contradicen(self):
        """`CATEGORIAS_DESCUENTO` (lo que SÍ se vende) y el gate de cocina (lo
        que NO se prepara) tienen que hablar de lo mismo."""
        from ventas.views.luna_api_views import CATEGORIAS_DESCUENTO
        self.assertIn('Descuento', CATEGORIAS_DESCUENTO)
