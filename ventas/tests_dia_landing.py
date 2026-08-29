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

    def test_el_titulo_nombra_la_ciudad(self):
        """El título es lo que Google muestra en sus resultados. Las otras
        páginas del sitio dicen «Puerto Varas» ahí («Tinas Calientes Puerto
        Varas…»); esta nació sin la ciudad y competía en desventaja por
        búsquedas como «spa por el día puerto varas», que es exactamente
        para lo que existe."""
        titulo = self.html.split('<title>')[1].split('</title>')[0]
        self.assertIn('Puerto Varas', titulo)

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


class LaFotoDelDesayuno(TestCase):
    """El desayuno es el único acto de esta landing que el Ritual no tiene por
    separado, así que necesita su propia foto. Sin ella la tarjeta queda como
    un hueco en la grilla — lo vio Jorge en la página publicada."""

    def test_el_campo_existe_y_es_opcional(self):
        from ventas.models import RitualRioLandingConfig
        campo = RitualRioLandingConfig._meta.get_field('foto_acto4')
        self.assertTrue(campo.blank)
        self.assertTrue(campo.null)

    def test_se_puede_subir_desde_el_admin(self):
        """Los campos del admin están listados uno por uno: si no está ahí, el
        campo existe en la base pero no hay dónde subir la foto."""
        from ventas.admin import RitualRioLandingConfigAdmin
        campos = [c for _, opts in RitualRioLandingConfigAdmin.fieldsets
                  for c in opts['fields']]
        self.assertIn('foto_acto4', campos)

    def test_sin_foto_la_pagina_igual_carga(self):
        """Mientras no haya foto subida, la landing no puede romperse."""
        r = self.client.get(reverse('dia_landing'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('Desayuno sureño al llegar', r.content.decode())


class SeEncuentraDesdeTODO_EL_SITIO(TestCase):
    """El menú vive en DOS plantillas: la home lo sobreescribe y el resto del
    sitio usa la base. Se había agregado solo en la home, así que quien llegaba
    por una landing, el blog o las tinas no tenía cómo encontrarlo."""

    def test_esta_en_el_menu_de_la_home(self):
        html = self.client.get('/').content.decode()
        self.assertIn(reverse('dia_landing'), html)

    def test_esta_en_el_menu_del_RESTO_del_sitio(self):
        """Se prueba sobre la propia landing porque hereda de la plantilla
        base sin sobreescribir el menú — o sea, muestra exactamente el mismo
        menú que ven todas las páginas que NO son la home, que era donde
        faltaba. Otras páginas del sitio dependen de datos y devuelven 404 en
        pruebas, así que servirían de poco."""
        html = self.client.get(reverse('dia_landing')).content.decode()
        self.assertIn('Refugio Aremko', html)                # el menú se dibujó
        self.assertIn(reverse('dia_landing'), html)

    def test_esta_en_el_pie_de_pagina(self):
        """El pie lista los servicios populares y lo ve Google en cada página."""
        html = self.client.get(reverse('dia_landing')).content.decode()
        pie = html[html.index('Servicios Populares'):]
        self.assertIn(reverse('dia_landing'), pie)


class NingunMenuSeQuedaAtras(TestCase):
    """El menú está copiado en TRES plantillas y se descubrió de a una: primero
    la home, después la base, después las páginas de categoría. Cada vez que
    faltaba, un grupo entero de visitantes no podía encontrar la experiencia.

    Esta prueba mira el código fuente en vez de una página concreta: si mañana
    alguien crea una cuarta plantilla con su propio menú y la olvida, esto
    falla. Es la única forma de no volver a descubrirlo por casualidad."""

    def test_todos_los_menus_ofrecen_la_experiencia(self):
        import glob
        import os

        from django.conf import settings

        raiz = os.path.join(settings.BASE_DIR, 'ventas', 'templates')
        con_menu, sin_enlace = [], []
        for ruta in glob.glob(os.path.join(raiz, '**', '*.html'), recursive=True):
            with open(ruta, encoding='utf-8') as f:
                contenido = f.read()
            if '{% block nav_items %}' not in contenido:
                continue
            con_menu.append(os.path.basename(ruta))
            # Un menú que ofrece el Refugio es un menú de experiencias; si no
            # lo ofrece, es otra cosa y no aplica.
            if "'refugio_landing'" in contenido and "'dia_landing'" not in contenido:
                sin_enlace.append(os.path.basename(ruta))

        self.assertGreaterEqual(len(con_menu), 3,
                                'se esperaban al menos 3 plantillas con menú')
        self.assertEqual(sin_enlace, [],
                         f'menús de experiencias sin «Cabaña y spa por el día»: {sin_enlace}')
