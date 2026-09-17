"""El Pase: la hora adicional no es una noche, y se puede pedir desde ahí.

Dos cosas, las dos de Jorge el 17-09-2026:

1. **La etiqueta.** «Hora Adicional Cabaña · late check-out» es de tipo cabaña.
   El Pase contaba cada línea de ese tipo como una noche: un Ritual del Río con
   late check-out se mostraba como «Refugio Aremko» y una Noche de Aguas
   Calientes quedaba sin nombre.
2. **El bloque.** El Pase ofrece el late check-out y abre WhatsApp; confirma
   recepción. Solo desde el día anterior a la salida y hasta las 11:00, solo si
   duerme en una cabaña de verdad, solo si todavía no la pidió, y con el precio
   leído del catálogo.

Ejecutar:
    python manage.py test ventas.tests_pase_late_checkout
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from urllib.parse import unquote

from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from control_gestion.signals import react_to_reserva_change

from .models import CategoriaServicio, Cliente, Servicio, VentaReserva
from .signals.main_signals import actualizar_tramo_y_premios_on_pago
from .views.ficha_reserva_view import (_late_checkout_para, _tipos_desde_payload,
                                       token_para_reserva)

# Las señales de CRM pegan a una tabla ausente por el drift AR-033/AR-034.
_SENSORES = (actualizar_tramo_y_premios_on_pago, react_to_reserva_change)


def _a_las(fecha, hora, minuto=0):
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(hora, minuto)))


class _Base(TestCase):
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
        cab = CategoriaServicio.objects.create(id=9503, nombre='Cabañas')
        otras = CategoriaServicio.objects.create(id=9501, nombre='Tinas y masajes')

        def servicio(pk, nombre, tipo, precio, cat, cap=2):
            return Servicio.objects.create(
                id=pk, nombre=nombre, categoria=cat, tipo_servicio=tipo,
                precio_base=Decimal(precio), duracion=60, activo=True,
                slots_disponibles={}, capacidad_minima=1, capacidad_maxima=cap)

        cls.torre = servicio(9511, 'Cabaña Torre', 'cabana', '60000', cab)
        cls.hora_extra = servicio(9544, 'Hora Adicional Cabaña · late check-out', 'cabana',
                                  '20000', cab, cap=1)
        cls.tina = servicio(9521, 'Tina Hornopirén', 'tina', '25000', otras, cap=4)
        cls.masaje = servicio(9531, 'Masaje Relajación', 'masaje', '40000', otras)
        cls.cliente = Cliente.objects.create(id=9521, nombre='Camila Rojas',
                                             telefono='+56900000095')
        cls.hoy = timezone.localdate()

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def _venta(self, *lineas):
        """lineas = (servicio, fecha, hora). Se crean EN ESE ORDEN (importa el id)."""
        v = VentaReserva.objects.create(cliente=self.cliente)
        for s, fecha, hora in lineas:
            v.reservaservicios.create(servicio=s, fecha_agendamiento=fecha, hora_inicio=hora,
                                      cantidad_personas=1, precio_unitario_venta=s.precio_base)
        return v

    def _pase(self, venta):
        return self.client.get(reverse('ventas:ficha_reserva_cliente',
                                       kwargs={'token': token_para_reserva(venta.id)}))


class LaHoraAdicionalNoEsUnaNoche(_Base):
    def _nombre(self, venta):
        return self._pase(venta).context['experiencia_nombre']

    def test_ritual_con_late_checkout_sigue_siendo_ritual(self):
        manana = self.hoy + datetime.timedelta(days=1)
        v = self._venta((self.torre, self.hoy, '16:00'), (self.tina, self.hoy, '19:00'),
                        (self.masaje, self.hoy, '17:30'), (self.hora_extra, manana, '11:00'))
        self.assertEqual(self._nombre(v), 'Ritual del Río')

    def test_noche_de_aguas_calientes_con_late_checkout_conserva_su_nombre(self):
        manana = self.hoy + datetime.timedelta(days=1)
        v = self._venta((self.torre, self.hoy, '16:00'), (self.tina, self.hoy, '19:00'),
                        (self.hora_extra, manana, '11:00'))
        self.assertEqual(self._nombre(v), 'Noche de Aguas Calientes')

    def test_dos_noches_de_verdad_siguen_siendo_refugio(self):
        manana = self.hoy + datetime.timedelta(days=1)
        v = self._venta((self.torre, self.hoy, '16:00'), (self.torre, manana, '16:00'),
                        (self.tina, self.hoy, '19:00'), (self.masaje, self.hoy, '17:30'))
        self.assertEqual(self._nombre(v), 'Refugio Aremko')

    def test_la_hora_de_la_cabana_no_se_toma_de_la_hora_adicional(self):
        # «Cabaña y spa por el día» se reconoce porque la cabaña entra a las 10:00. Si
        # la hora adicional se creó primero, su 11:00 no puede tapar ese 10:00.
        v = self._venta((self.hora_extra, self.hoy, '11:00'), (self.torre, self.hoy, '10:00'),
                        (self.tina, self.hoy, '12:00'), (self.masaje, self.hoy, '13:00'))
        self.assertEqual(self._nombre(v), 'Cabaña y spa por el día')

    def test_la_cotizacion_mira_con_los_mismos_ojos(self):
        tipos = _tipos_desde_payload([{'servicio_id': self.torre.id}, {'servicio_id': self.tina.id},
                                      {'servicio_id': self.masaje.id},
                                      {'servicio_id': self.hora_extra.id}])
        self.assertEqual(tipos.count('cabana'), 1)


class ElBloqueDelPase(_Base):
    def _estadia(self, ultima_noche):
        return self._venta((self.torre, ultima_noche, '16:00'), (self.tina, ultima_noche, '19:00'))

    def test_el_dia_de_llegada_de_una_noche_ya_lo_ofrece(self):
        v = self._estadia(self.hoy)
        b = _late_checkout_para(v, _a_las(self.hoy, 18))
        self.assertIsNotNone(b)
        self.assertEqual(b['precio'], '$20.000')
        self.assertEqual(b['salida'], self.hoy + datetime.timedelta(days=1))
        self.assertTrue(b['url'].startswith('https://wa.me/56957902525?text='))
        texto = unquote(b['url'].split('?text=')[1])
        self.assertIn(f'reserva #{v.id}', texto)
        self.assertIn('Camila', texto)
        self.assertIn('late check-out', texto)

    def test_tres_dias_antes_todavia_es_ruido(self):
        v = self._estadia(self.hoy + datetime.timedelta(days=3))
        self.assertIsNone(_late_checkout_para(v, _a_las(self.hoy, 12)))

    def test_el_dia_de_salida_hasta_las_11_y_ni_un_minuto_mas(self):
        ayer = self.hoy - datetime.timedelta(days=1)
        v = self._estadia(ayer)                       # sale HOY
        self.assertIsNotNone(_late_checkout_para(v, _a_las(self.hoy, 10, 59)))
        self.assertIsNone(_late_checkout_para(v, _a_las(self.hoy, 11, 0)))

    def test_sin_cabana_de_verdad_no_se_ofrece(self):
        v = self._venta((self.tina, self.hoy, '19:00'), (self.masaje, self.hoy, '17:30'))
        self.assertIsNone(_late_checkout_para(v, _a_las(self.hoy, 18)))

    def test_si_ya_la_pidio_no_se_vuelve_a_ofrecer(self):
        manana = self.hoy + datetime.timedelta(days=1)
        v = self._venta((self.torre, self.hoy, '16:00'), (self.hora_extra, manana, '11:00'))
        self.assertIsNone(_late_checkout_para(v, _a_las(self.hoy, 18)))

    def test_el_precio_sale_del_catalogo(self):
        Servicio.objects.filter(pk=self.hora_extra.pk).update(precio_base=Decimal('25000'))
        b = _late_checkout_para(self._estadia(self.hoy), _a_las(self.hoy, 18))
        self.assertEqual(b['precio'], '$25.000')

    def test_sin_el_servicio_en_el_catalogo_no_se_inventa_un_precio(self):
        Servicio.objects.filter(pk=self.hora_extra.pk).update(activo=False)
        self.assertIsNone(_late_checkout_para(self._estadia(self.hoy), _a_las(self.hoy, 18)))

    def test_una_reserva_cancelada_no_ofrece_nada(self):
        v = self._estadia(self.hoy)
        VentaReserva.objects.filter(pk=v.pk).update(estado_reserva='cancelada')
        v.refresh_from_db()
        self.assertIsNone(_late_checkout_para(v, _a_las(self.hoy, 18)))


class LoQueVeElHuesped(_Base):
    def test_en_ventana_el_pase_muestra_el_bloque_con_hora_o_fraccion(self):
        v = self._venta((self.torre, self.hoy, '16:00'), (self.tina, self.hoy, '19:00'))
        html = self._pase(v).content.decode()
        self.assertIn('¿Quieres quedarte un poco más?', html)
        self.assertIn('$20.000 la hora adicional o fracción', html)
        self.assertIn('Pedir late check-out por WhatsApp', html)

    def test_fuera_de_ventana_el_pase_no_lo_menciona(self):
        lejos = self.hoy + datetime.timedelta(days=10)
        v = self._venta((self.torre, lejos, '16:00'), (self.tina, lejos, '19:00'))
        self.assertNotIn('¿Quieres quedarte un poco más?', self._pase(v).content.decode())
