# -*- coding: utf-8 -*-
"""Pruebas de la vitrina de «Cabaña y spa por el día».

Una landing se rompe de dos maneras y ninguna avisa: por un error de plantilla
—que solo aparece al dibujarla— y por decir algo que no es cierto. Lo segundo
es peor: acá lo grave sería prometer alojamiento, porque el cliente lo
descubriría el día que llega, después de manejar hora y media.
"""
from django.test import TestCase
from django.urls import reverse


class LaPaginaSeDibuja(TestCase):

    def setUp(self):
        import re
        self.r = self.client.get(reverse('dia_landing'))
        self.html = self.r.content.decode()
        # El HTML parte las frases con saltos de línea e indentación; comparar
        # contra el crudo haría fallar la prueba por cómo quedó formateado el
        # archivo, no por lo que dice la página.
        self.texto = re.sub(r'\s+', ' ', self.html)

    def test_carga(self):
        self.assertEqual(self.r.status_code, 200)

    def test_no_se_filtra_sintaxis_de_plantilla(self):
        """Solo los marcadores inequívocos de Django. `{{` y `}}` quedan
        fuera a propósito: aparecen de verdad en el JavaScript y el CSS que
        hereda la página del sitio, y buscarlos daría un falso positivo
        permanente que terminaría haciendo que se ignore esta prueba."""
        for resto in ('{%', '%}', '{#', '#}'):
            self.assertNotIn(resto, self.html, f'quedó sin procesar: {resto}')

    def test_dice_el_nombre_y_el_precio(self):
        self.assertIn('Cabaña y spa por el día', self.texto)
        self.assertIn('200.000', self.texto)

    def test_dice_los_dias_que_se_vende(self):
        """Si no los dice, llegan consultas para sábado y se pierde la venta
        explicando por qué no."""
        for d in ('lunes', 'miércoles', 'jueves'):
            self.assertIn(d, self.texto)

    def test_deja_clarísimo_que_NO_se_duerme(self):
        """Lo más caro que puede hacer esta página es dejar creer que hay
        alojamiento. Se descubriría el día de la llegada."""
        self.assertIn('duermen en su cama', self.texto)
        self.assertIn('sin quedarse a dormir', self.texto.lower())

    def test_el_boton_lleva_a_whatsapp(self):
        self.assertIn('wa.me/56957902525', self.html)

    def test_mide_el_clic_como_conversion(self):
        """Sin esto la landing puede vender y nadie sabría que fue ella."""
        self.assertIn('dia_whatsapp_click', self.html)
        self.assertIn("fbq('track', 'Lead'", self.html)

    def test_es_indexable(self):
        """Es su razón de ser: responde a una búsqueda que hoy no tiene
        destino, y no depende de campaña paga."""
        self.assertIn('index, follow', self.html)


class EstaEnLaVitrina(TestCase):

    def test_aparece_en_el_menu_de_experiencias(self):
        """Sin esto la página existe pero nadie la encuentra desde el sitio."""
        html = self.client.get('/').content.decode()
        self.assertIn(reverse('dia_landing'), html)

    def test_esta_en_el_sitemap(self):
        xml = self.client.get('/sitemap.xml').content.decode()
        self.assertIn('cabana-y-spa-por-el-dia', xml)
