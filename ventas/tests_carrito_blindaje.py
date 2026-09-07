"""El carrito de la web no se puede desarmar para pagar menos.

Caso real que lo motivó: reserva 6777, 07-09-2026. Un cliente comparó tres
paquetes en la web (Noche $160.000, Ritual $210.000, Refugio $290.000), armó
el Refugio, y después cambió la cabaña por una más cara, sacó una noche y las
dos tinas. El Refugio mete su descuento como una LÍNEA del carrito —$400.000
de servicios menos $110.000 son los $290.000 del paquete— y al sacar ítems el
total se recalculaba sumando subtotales: el descuento entero quedó aplicándose
sobre lo que quedaba.

Pagó $150.000 por servicios que valen $260.000. No hizo nada raro: el sistema
se lo permitió. Y nadie volvía a revisar el carrito antes de cobrar, porque el
blindaje del constructor solo corre al ARMAR el paquete.

Tres arreglos, tres grupos de pruebas:
  · sacar algo de un paquete cerrado lo deshace
  · nada se manda a pagar si el carrito no cuadra
  · al carrito solo entra lo que está publicado en la web

Ejecutar:
    python manage.py test ventas.tests_carrito_blindaje
"""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from ventas.models import CategoriaServicio, Servicio
from ventas.views.checkout_views import _carrito_no_cuadra, _deshacer_paquete


def _refugio():
    """Un carrito como el que arma el Refugio: $400.000 de servicios y una
    línea de −$110.000 que los deja en los $290.000 del paquete."""
    return {
        'servicios': [
            {'nombre': 'Cabaña Arrayan', 'cantidad_personas': 2, 'subtotal': 110000.0},
            {'nombre': 'Cabaña Arrayan', 'cantidad_personas': 2, 'subtotal': 110000.0},
            {'nombre': 'Tina Hornopiren', 'cantidad_personas': 2, 'subtotal': 50000.0},
            {'nombre': 'Tina Tronador', 'cantidad_personas': 2, 'subtotal': 50000.0},
            {'nombre': 'Masaje Relajación', 'cantidad_personas': 2, 'subtotal': 80000.0},
            {'nombre': 'Descuento_Servicios', 'cantidad_personas': 110000,
             'subtotal': -110000.0},
        ],
        'giftcards': [], 'productos': [],
        'total': 290000.0,
        'paquete_cerrado': 'refugio',
    }


class SacarAlgoDeshaceElPaquete(TestCase):
    def test_el_descuento_se_va_con_el_paquete(self):
        cart = _refugio()
        del cart['servicios'][1]          # se saca una noche
        self.assertTrue(_deshacer_paquete(cart))
        negativos = [i for i in cart['servicios'] if i['subtotal'] < 0]
        self.assertEqual(negativos, [], 'el descuento no puede sobrevivir')

    def test_deja_de_ser_paquete_cerrado(self):
        cart = _refugio()
        _deshacer_paquete(cart)
        self.assertNotIn('paquete_cerrado', cart)

    def test_lo_que_queda_se_cobra_a_precio_de_lista(self):
        # Es lo honesto: si desarma el combo, paga lo que pide.
        cart = _refugio()
        del cart['servicios'][1]
        _deshacer_paquete(cart)
        suma = sum(i['subtotal'] for i in cart['servicios'])
        self.assertEqual(suma, 290000.0)   # 400.000 − la noche de 110.000

    def test_un_carrito_normal_no_se_toca(self):
        cart = {'servicios': [{'nombre': 'Tina', 'subtotal': 60000.0}],
                'giftcards': [], 'total': 60000.0}
        self.assertFalse(_deshacer_paquete(cart))
        self.assertEqual(len(cart['servicios']), 1)


class ElCarritoSeRevisaAntesDeCobrar(TestCase):
    def test_un_refugio_intacto_pasa(self):
        self.assertIsNone(_carrito_no_cuadra(_refugio()))

    def test_el_caso_6777_se_rechaza(self):
        # El carrito exacto que se mandó a FLOW aquel día.
        cart = {
            'servicios': [
                {'nombre': 'Descuento_Servicios', 'cantidad_personas': 110000,
                 'subtotal': -110000.0},
                {'nombre': 'Tina Hidromasaje Llaima', 'subtotal': 60000.0},
                {'nombre': 'Masaje Relajación', 'subtotal': 80000.0},
                {'nombre': 'Cabaña Torre', 'subtotal': 120000.0},
            ],
            'giftcards': [], 'total': 150000.0,
        }
        motivo = _carrito_no_cuadra(cart)
        self.assertIsNotNone(motivo, 'esto tenía que rebotar')
        self.assertIn('descuento sin paquete', motivo)

    def test_rechaza_si_el_total_no_es_la_suma(self):
        cart = {'servicios': [{'nombre': 'Tina', 'subtotal': 60000.0}],
                'giftcards': [], 'total': 10000.0}
        self.assertIn('no es la suma', _carrito_no_cuadra(cart))

    def test_rechaza_un_total_de_cero_o_menos(self):
        cart = {'servicios': [{'nombre': 'X', 'subtotal': 0.0}],
                'giftcards': [], 'total': 0.0}
        self.assertIn('el total es', _carrito_no_cuadra(cart))

    def test_una_giftcard_sola_pasa(self):
        cart = {'servicios': [], 'giftcards': [{'precio': 110000.0}],
                'total': 110000.0}
        self.assertIsNone(_carrito_no_cuadra(cart))


class AlCarritoSoloEntraLoPublicado(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = CategoriaServicio.objects.create(nombre='Tinas')
        cls.publicado = Servicio.objects.create(
            nombre='Tina Hidromasaje Llaima', precio_base=30000, categoria=cat,
            duracion=120, tipo_servicio='tina', activo=True, publicado_web=True,
            capacidad_minima=1, capacidad_maxima=2,
            slots_disponibles={d: ['19:00'] for d in
                               ('monday','tuesday','wednesday','thursday',
                                'friday','saturday','sunday')})
        cls.descuento = Servicio.objects.create(
            nombre='Descuento_Servicios', precio_base=-1,
            categoria=CategoriaServicio.objects.create(nombre='Descuento_Servicio'),
            duracion=0, tipo_servicio='otro', activo=True, publicado_web=False,
            capacidad_minima=1, capacidad_maxima=1000000)
        horario = {d: ['19:00'] for d in
                   ('monday','tuesday','wednesday','thursday',
                    'friday','saturday','sunday')}
        cls.interno = Servicio.objects.create(
            nombre='Preparar Cortesia', precio_base=0, categoria=cat,
            duracion=0, tipo_servicio='otro', activo=True, publicado_web=False,
            capacidad_minima=1, capacidad_maxima=10, slots_disponibles=horario)

    def _agregar(self, servicio, cantidad=2):
        return self.client.post(
            reverse('ventas:add_to_cart'),
            {'servicio_id': servicio.pk, 'fecha': '2026-09-16',
             'hora': '19:00', 'cantidad_personas': str(cantidad)})

    def _carrito(self):
        return self.client.session.get('cart', {}).get('servicios', [])

    def test_el_descuento_NO_entra(self):
        # Era un millón de pesos de rebaja a un POST de distancia.
        self._agregar(self.descuento, cantidad=110000)
        self.assertEqual(self._carrito(), [])

    def test_un_servicio_interno_NO_entra(self):
        # Cantidad 1: si se pide más, lo rechaza el control de capacidad y no
        # se estaría probando el filtro sino otra cosa.
        self._agregar(self.interno, cantidad=1)
        self.assertEqual(self._carrito(), [])

    def test_lo_publicado_sigue_entrando(self):
        self._agregar(self.publicado)
        self.assertEqual(len(self._carrito()), 1)

    def test_el_desayuno_generico_sigue_entrando(self):
        # No está publicado a propósito —no se vende suelto— pero este mismo
        # endpoint lo traduce al desayuno de la cabaña. Filtrarlo lo rompería.
        d = Servicio.objects.create(
            nombre='Desayuno', precio_base=20000,
            categoria=CategoriaServicio.objects.create(nombre='Otros'),
            duracion=0, tipo_servicio='otro', activo=True, publicado_web=False,
            capacidad_minima=1, capacidad_maxima=10)
        r = self._agregar(d, cantidad=1)
        # Sin cabaña en el carrito rebota con su propio mensaje, no con el del
        # filtro: lo que importa es que el filtro no lo atajó antes.
        self.assertEqual(r.status_code, 302)
        from ventas.views.checkout_views import DESAYUNO_GENERICO_NOMBRE
        self.assertEqual(DESAYUNO_GENERICO_NOMBRE.lower(), d.nombre.lower())
