"""La tarjeta «Celular» del panel lleva a la Sala de control, y desde ahí se vuelve.

Pedido de Jorge (2026-08-31): la sala de control es parte de lo que mira desde
el teléfono, así que va en esa tarjeta como las demás. Y su regla para esta
tarjeta, dicha en su momento: «Todas deben tener un botón de volver al menú».

Ejecutar:
    python manage.py test ventas.tests_card_celular_sala
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class LaTarjetaCelularLlevaALaSala(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='panel_sala', email='p@test.cl', password='x')

    def setUp(self):
        self.client.force_login(self.staff)

    def test_el_panel_ofrece_la_sala_de_control(self):
        html = self.client.get('/admin/').content.decode()
        self.assertIn('Sala de control', html)
        self.assertIn(reverse('sala_control:sala'), html)

    def test_la_sala_tiene_como_volver_al_menu(self):
        # Sin salida, el usuario queda atrapado en una página sin navegación:
        # es la razón por la que Jorge pidió el botón en todas las opciones.
        html = self.client.get(reverse('sala_control:sala')).content.decode()
        self.assertIn('Volver al menú', html)
        self.assertIn('/admin/', html)

    def test_la_sala_sigue_siendo_solo_para_el_personal(self):
        self.client.logout()
        r = self.client.get(reverse('sala_control:sala'))
        self.assertIn(r.status_code, (302, 403))
