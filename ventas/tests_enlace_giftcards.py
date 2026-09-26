"""/giftcards/ lleva a la vitrina de GiftCards (Jorge, 26-09-2026).

La vitrina vive en /ventas/giftcards/ y /giftcards/ daba 404: ahí llevaban el correo de la
campaña de invierno 2026 y el botón «Volver al Inicio» de un código de GiftCard inválido.

Ejecutar:
    python manage.py test ventas.tests_enlace_giftcards
"""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse


class ElEnlaceCortoLlevaALaVitrina(TestCase):
    def test_redirige_a_la_vitrina(self):
        self.assertRedirects(self.client.get('/giftcards/'), reverse('ventas:giftcard_menu'),
                             status_code=301)

    def test_conserva_los_parametros_del_correo(self):
        r = self.client.get('/giftcards/?utm_source=email&utm_campaign=invierno')
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r['Location'],
                         reverse('ventas:giftcard_menu') + '?utm_source=email&utm_campaign=invierno')

    def test_el_boton_del_codigo_invalido_lleva_a_la_vitrina(self):
        r = self.client.get(reverse('ventas:giftcard_mobile_view', kwargs={'codigo': 'NOEXISTE1234'}))
        self.assertContains(r, f'href="{reverse("ventas:giftcard_menu")}" class="btn-home"',
                            status_code=404)
