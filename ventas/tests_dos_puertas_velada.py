"""Las DOS puertas del configurador de veladas (2026-07-30).

Una sola landing mezclaba románticas (de a dos, con invitación secreta) con
celebraciones de grupo (despedida de soltera/o): el menú decía "Experiencia
Romántica" y abajo había un botón de despedida. Se separó en dos vitrinas con UN
solo motor.

Lo que se prueba acá es justamente lo que la separación debe garantizar:
  · cada puerta ofrece SOLO sus ocasiones;
  · un error de validación devuelve al cliente a SU puerta, no a la otra.

Ejecutar:
    python manage.py test ventas.tests_dos_puertas_velada
"""
from __future__ import annotations

from decimal import Decimal
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from ventas.models import CategoriaServicio, Servicio
from ventas.views.experiencia_romantica_view import (
    MODO_CELEBRACIONES, MODO_ROMANTICA, OCASIONES_POR_MODO,
    _ocasiones_visibles, modo_de_ocasion, url_de_ocasion,
)


class ModoDeOcasionTest(SimpleTestCase):
    """El ruteo ocasión → puerta. Sin BD, inmune al drift AR-034."""

    def test_romantica_va_a_su_puerta(self):
        self.assertEqual(modo_de_ocasion('romantica'), MODO_ROMANTICA)
        self.assertEqual(url_de_ocasion('romantica'), 'experiencia_romantica')

    def test_las_tres_celebraciones_van_a_celebraciones(self):
        for ocasion in ('cumpleanos', 'grupo', 'despedida'):
            self.assertEqual(modo_de_ocasion(ocasion), MODO_CELEBRACIONES, ocasion)
            self.assertEqual(url_de_ocasion(ocasion), 'celebraciones', ocasion)

    def test_ocasion_desconocida_cae_a_la_romantica(self):
        # Un POST manipulado no debe reventar: cae a la puerta por defecto.
        for basura in ('', 'otra_cosa', None):
            self.assertEqual(modo_de_ocasion(basura), MODO_ROMANTICA, repr(basura))

    def test_ninguna_ocasion_vive_en_las_dos_puertas(self):
        romanticas = set(OCASIONES_POR_MODO[MODO_ROMANTICA])
        celebraciones = set(OCASIONES_POR_MODO[MODO_CELEBRACIONES])
        self.assertEqual(romanticas & celebraciones, set())


class OcasionesVisiblesTest(SimpleTestCase):
    """Qué botones dibuja cada puerta."""

    def test_romantica_no_dibuja_selector(self):
        # Una sola ocasión → sin paso "elige tu ocasión" (un paso menos en el embudo).
        self.assertEqual(_ocasiones_visibles(MODO_ROMANTICA, True), [])
        self.assertEqual(_ocasiones_visibles(MODO_ROMANTICA, False), [])

    def test_celebraciones_con_tinas_grupales_ofrece_las_tres(self):
        claves = [o['clave'] for o in _ocasiones_visibles(MODO_CELEBRACIONES, True)]
        self.assertEqual(claves, ['cumpleanos', 'grupo', 'despedida'])

    def test_celebraciones_sin_tinas_grupales_solo_cumpleanos(self):
        # Sin tinas grupales publicadas, grupo y despedida no se pueden cumplir.
        claves = [o['clave'] for o in _ocasiones_visibles(MODO_CELEBRACIONES, False)]
        self.assertEqual(claves, ['cumpleanos'])

    def test_cada_boton_trae_lo_que_el_template_necesita(self):
        for oc in _ocasiones_visibles(MODO_CELEBRACIONES, True):
            for campo in ('clave', 'css_id', 'titulo', 'sub'):
                self.assertIn(campo, oc)
                self.assertTrue(oc[campo], f"{campo} vacío en {oc}")


class _BasePuertas(TestCase):
    """Catálogo mínimo: una tina de pareja, una grupal y las dos ambientaciones."""

    @classmethod
    def setUpTestData(cls):
        cls.cat_amb = CategoriaServicio.objects.create(nombre='Ambientaciones')
        cls.cat_tinas = CategoriaServicio.objects.create(nombre='Tinas')
        # Tina de pareja: sirve para románticas, NO para cumpleaños ni grupo.
        cls.tina_pareja = Servicio.objects.create(
            nombre='Tina Tronador', categoria=cls.cat_tinas, tipo_servicio='tina',
            precio_base=Decimal('60000'), duracion=60, activo=True,
            publicado_web=True, capacidad_maxima=2)
        # Osorno: admite cumpleaños Y grupo.
        cls.tina_osorno = Servicio.objects.create(
            nombre='Tina Osorno', categoria=cls.cat_tinas, tipo_servicio='tina',
            precio_base=Decimal('25000'), duracion=60, activo=True,
            publicado_web=True, capacidad_maxima=6)
        Servicio.objects.create(
            id=22, nombre='Ambientación romántica R1', categoria=cls.cat_amb,
            tipo_servicio='otro', precio_base=Decimal('32000'), duracion=60, activo=True)
        Servicio.objects.create(
            id=66, nombre='Decoración Simple · Rosado', categoria=cls.cat_amb,
            tipo_servicio='otro', precio_base=Decimal('38000'), duracion=60, activo=True)
        cls.fecha = (timezone.now().date() + timedelta(days=10)).isoformat()


class LandingsOfrecenSoloLoSuyoTest(_BasePuertas):
    """Cada vitrina muestra su propia mercadería."""

    def test_romantica_no_ofrece_ninguna_celebracion(self):
        resp = self.client.get(reverse('experiencia_romantica'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['ocasiones'], [])
        self.assertEqual(resp.context['ocasion_default'], 'romantica')
        cuerpo = resp.content.decode()
        for ocasion in ('cumpleanos', 'grupo', 'despedida'):
            self.assertNotIn(f'data-oc="{ocasion}"', cuerpo, ocasion)

    def test_celebraciones_no_ofrece_la_romantica(self):
        resp = self.client.get(reverse('celebraciones'))
        self.assertEqual(resp.status_code, 200)
        claves = [o['clave'] for o in resp.context['ocasiones']]
        self.assertEqual(claves, ['cumpleanos', 'grupo', 'despedida'])
        self.assertEqual(resp.context['ocasion_default'], 'cumpleanos')
        self.assertNotIn('data-oc="romantica"', resp.content.decode())

    def test_cada_puerta_lleva_su_propio_titulo(self):
        romantica = self.client.get(reverse('experiencia_romantica')).content.decode()
        celebra = self.client.get(reverse('celebraciones')).content.decode()
        self.assertIn('Experiencia Romántica', romantica)
        self.assertIn('Cumpleaños y celebraciones', celebra)
        # El hero de una nunca aparece en la otra (era justo la contradicción vieja).
        self.assertNotIn('Cumplir años aquí', romantica)
        self.assertNotIn('Regálale una velada', celebra)

    def test_el_html_inicial_ya_muestra_el_panel_correcto(self):
        """Sin depender del JS: si el servidor mandara el panel equivocado, la página
        mostraría por un instante las opciones de la OTRA ocasión."""
        romantica = self.client.get(reverse('experiencia_romantica'))
        self.assertFalse(romantica.context['default_lleva_color'])
        self.assertIn('<div id="panelCum" style="display:none;">',
                      romantica.content.decode())

        celebra = self.client.get(reverse('celebraciones'))
        self.assertTrue(celebra.context['default_lleva_color'])
        self.assertIn('<div id="panelRom" style="display:none;">',
                      celebra.content.decode())

    def test_numeracion_de_pasos_sin_selector_corre_un_paso_arriba(self):
        romantica = self.client.get(reverse('experiencia_romantica'))
        self.assertEqual(romantica.context['paso_tina'], 2)   # 1 incluye · 2 tina · 3 extras
        self.assertEqual(romantica.context['paso_choco'], 3)

        celebra = self.client.get(reverse('celebraciones'))
        self.assertEqual(celebra.context['paso_tina'], 4)     # 1 ocasión · 2 color · 3 torta · 4 tina
        self.assertEqual(celebra.context['paso_choco'], 5)

    def test_cada_puerta_enlaza_a_la_otra(self):
        romantica = self.client.get(reverse('experiencia_romantica')).content.decode()
        celebra = self.client.get(reverse('celebraciones')).content.decode()
        self.assertIn(reverse('celebraciones'), romantica)
        self.assertIn(reverse('experiencia_romantica'), celebra)


class ErrorVuelveASuPuertaTest(_BasePuertas):
    """El bug que la separación podía introducir: mandar al cliente a la otra puerta."""

    def _post(self, **extra):
        datos = {'fecha': self.fecha, 'hora': '16:00'}
        datos.update(extra)
        return self.client.post(reverse('experiencia_romantica_continuar'), datos)

    def test_error_de_romantica_vuelve_a_romantica(self):
        resp = self._post(ocasion='romantica', nivel='r1')  # sin tina_id
        self.assertRedirects(resp, reverse('experiencia_romantica'),
                             fetch_redirect_response=False)

    def test_error_de_cumpleanos_vuelve_a_celebraciones(self):
        # Tronador no admite ambientación de cumpleaños → error.
        resp = self._post(ocasion='cumpleanos', color='rosado', torta='sin_torta',
                          tina_id=self.tina_pareja.id)
        self.assertRedirects(resp, reverse('celebraciones'),
                             fetch_redirect_response=False)

    def test_error_de_grupo_vuelve_a_celebraciones(self):
        # Tina no grupal para una celebración de grupo → error.
        resp = self._post(ocasion='grupo', color='rosado', torta='sin_torta',
                          tina_id=self.tina_pareja.id, personas=4)
        self.assertRedirects(resp, reverse('celebraciones'),
                             fetch_redirect_response=False)

    def test_error_de_despedida_vuelve_a_celebraciones(self):
        # Osorno sí es grupal, pero 9 personas excede su capacidad (6) → error.
        resp = self._post(ocasion='despedida', color='rosado', torta='sin_torta',
                          tina_id=self.tina_osorno.id, personas=9)
        self.assertRedirects(resp, reverse('celebraciones'),
                             fetch_redirect_response=False)

    def test_falta_de_datos_en_celebraciones_no_manda_a_la_romantica(self):
        resp = self.client.post(reverse('experiencia_romantica_continuar'),
                                {'ocasion': 'cumpleanos'})  # sin tina/fecha/hora
        self.assertRedirects(resp, reverse('celebraciones'),
                             fetch_redirect_response=False)

    def test_el_motor_sigue_armando_el_carrito_igual(self):
        # La separación es de vitrina: el carrito no cambió.
        resp = self._post(ocasion='romantica', nivel='r1', tina_id=self.tina_pareja.id)
        self.assertEqual(resp.status_code, 302)
        cart = self.client.session['cart']
        self.assertEqual([s['id'] for s in cart['servicios']], [self.tina_pareja.id, 22])
        self.assertEqual(cart['total'], 60000 * 2 + 32000)  # tina ×2 + ambientación


class SitemapTest(_BasePuertas):
    """Las dos puertas entran al sitemap.

    Se prueba RENDERIZANDO, no con `check`: `items()` solo se ejecuta al renderizar,
    así que un queryset roto pasa el check y revienta en prod.
    """

    def test_sitemap_lista_las_dos_puertas(self):
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        xml = resp.content.decode()
        self.assertIn(reverse('experiencia_romantica'), xml)
        self.assertIn(reverse('celebraciones'), xml)


class ElPieRescataAlQueNoReservo(TestCase):
    """Las dos puertas son páginas de embudo: no tienen menú, a propósito, para
    no darle al visitante una puerta de salida antes de reservar. El precio de
    eso es que quien llega desde un anuncio, baja entera la página y NO reserva
    quedaba sin ningún lado adonde ir salvo la otra puerta.

    Desde el 2026-08-28 el pie ofrece además «Cabaña y spa por el día», que es
    de a dos igual que la velada pero de día y más barato. Va al final, después
    del configurador: rescata al que no convirtió, no compite con el que sí.
    """

    def _pie(self, nombre_url):
        html = self.client.get(reverse(nombre_url)).content.decode()
        # El cruce vive al final; basta con el HTML completo para verificarlo.
        return html

    def test_romantica_ofrece_las_dos_salidas(self):
        html = self._pie('experiencia_romantica')
        self.assertIn(reverse('celebraciones'), html)
        self.assertIn(reverse('dia_landing'), html)

    def test_celebraciones_ofrece_las_dos_salidas(self):
        html = self._pie('celebraciones')
        self.assertIn(reverse('experiencia_romantica'), html)
        self.assertIn(reverse('dia_landing'), html)

    def test_el_cruce_viejo_no_fue_reemplazado(self):
        """Agregar una salida no debe costar la que ya existía: el cruce entre
        las dos puertas es el que más convierte, porque ambas son veladas."""
        from ventas.views.experiencia_romantica_view import (
            COPY, MODO_CELEBRACIONES, MODO_ROMANTICA,
        )
        for modo, esperado in ((MODO_ROMANTICA, 'celebraciones'),
                               (MODO_CELEBRACIONES, 'experiencia_romantica')):
            urls = [c['url'] for c in COPY[modo]['cruces']]
            self.assertIn(esperado, urls)
            self.assertIn('dia_landing', urls)
            self.assertEqual(urls[0], esperado,
                             'la salida hermana debe ir primero: convierte más')
