# -*- coding: utf-8 -*-
"""/accounts/login/ devolvía 500: `django.contrib.auth.urls` renderiza
`registration/login.html` y este proyecto no la tiene. El equipo entra por
/admin/, así que la ruta redirige ahí conservando el `?next=`.
"""
from django.test import TestCase
from django.urls import reverse


class LoginNoRevientaTest(TestCase):

    def test_accounts_login_redirige_al_admin(self):
        r = self.client.get('/accounts/login/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/admin/login/')

    def test_conserva_el_next(self):
        """@login_required manda ?next=… y el usuario debe aterrizar ahí."""
        r = self.client.get('/accounts/login/?next=/ventas/agenda/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/admin/login/?next=/ventas/agenda/')

    def test_el_nombre_login_sigue_resolviendo(self):
        """El botón «Salir» de la web pública y @login_required lo reversan."""
        self.assertEqual(reverse('login'), '/accounts/login/')

    def test_logout_y_password_reset_siguen_en_pie(self):
        """Solo se desvía login: el resto de auth funciona (el admin trae esas
        plantillas) y no hay que tocarlo."""
        self.assertEqual(reverse('logout'), '/accounts/logout/')
        self.assertEqual(self.client.get('/accounts/password_reset/').status_code, 200)
