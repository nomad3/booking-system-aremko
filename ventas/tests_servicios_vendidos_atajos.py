"""El listado de servicios vendidos tiene atajos de Ayer, Hoy y Mañana.

Pedido de Jorge (01-09-2026): el listado abre en HOY, y lo que se mira a diario
es el día anterior —para cerrar— y el siguiente —para preparar—. Sin atajos hay
que escribir dos fechas en dos calendarios, que en el celular es lento.

Los atajos son ENLACES, no JavaScript: así el resultado se puede compartir y
funciona igual desde el teléfono.

Ejecutar:
    python manage.py test ventas.tests_servicios_vendidos_atajos
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone


class AtajosDeFechaEnServiciosVendidos(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='sv_atajos', email='s@test.cl', password='x')

    def setUp(self):
        self.client.force_login(self.staff)
        self.url = reverse('ventas:servicios_vendidos')
        self.hoy = timezone.localdate()

    def test_ofrece_ayer_hoy_y_manana(self):
        html = self.client.get(self.url).content.decode()
        for nombre in ('Ayer', 'Hoy', 'Mañana'):
            self.assertIn(f'>{nombre}</a>', html)

    def test_los_atajos_apuntan_a_las_fechas_correctas(self):
        html = self.client.get(self.url).content.decode()
        ayer = (self.hoy - timedelta(days=1)).strftime('%Y-%m-%d')
        manana = (self.hoy + timedelta(days=1)).strftime('%Y-%m-%d')
        # Un solo día: la misma fecha de inicio y de fin.
        self.assertIn(f'fecha_inicio={ayer}&amp;fecha_fin={ayer}', html)
        self.assertIn(f'fecha_inicio={manana}&amp;fecha_fin={manana}', html)

    def test_al_abrir_sin_filtros_el_marcado_es_hoy(self):
        r = self.client.get(self.url)
        activos = [a['nombre'] for a in r.context['atajos'] if a['activo']]
        self.assertEqual(activos, ['Hoy'])

    def test_al_pedir_manana_el_marcado_se_mueve(self):
        manana = (self.hoy + timedelta(days=1)).strftime('%Y-%m-%d')
        r = self.client.get(self.url, {'fecha_inicio': manana, 'fecha_fin': manana})
        activos = [a['nombre'] for a in r.context['atajos'] if a['activo']]
        self.assertEqual(activos, ['Mañana'])

    def test_un_rango_de_varios_dias_no_marca_ningun_atajo(self):
        # Marcar «Hoy» en un rango de una semana que empieza hoy sería mentir.
        r = self.client.get(self.url, {
            'fecha_inicio': self.hoy.strftime('%Y-%m-%d'),
            'fecha_fin': (self.hoy + timedelta(days=7)).strftime('%Y-%m-%d')})
        self.assertEqual([a['nombre'] for a in r.context['atajos'] if a['activo']], [])

    def test_el_atajo_conserva_los_otros_filtros(self):
        # Si alguien filtró por reserva y luego toca «Ayer», perder el filtro
        # lo obliga a escribirlo de nuevo.
        html = self.client.get(self.url, {'venta_reserva_id': '6702'}).content.decode()
        self.assertIn('venta_reserva_id=6702', html)
