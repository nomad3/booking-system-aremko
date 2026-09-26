"""La política de cancelación en todas las preguntas frecuentes (Jorge, 26-09-2026).

La página de Tinas arma sus preguntas desde el admin (contenido SEO) y no traía la de
cancelación; Masajes, Garantía y Gift cards tampoco. Todas la leen ahora del mismo lugar que
la cotización y el Pase: admin → Configuración Resumen (etiqueta `politica_cancelacion`).

Ejecutar:
    python manage.py test ventas.tests_faq_cancelacion
"""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from ventas.models import CategoriaServicio, ConfiguracionResumen, SEOContent

POLITICA = ('Si nos avisas con 48 horas o más de anticipación, te devolvemos el 100% o cambiamos '
            'la fecha sin costo. Con menos de 48 horas, la reserva se pierde.')
PREGUNTA = '¿Cuál es la política de cancelación?'


class LaPoliticaEnLasPreguntasFrecuentes(TestCase):
    @classmethod
    def setUpTestData(cls):
        config = ConfiguracionResumen.get_solo()
        config.politica_alojamiento = POLITICA
        config.politica_tinas_masajes = POLITICA
        config.save()
        cls.tinas = CategoriaServicio.objects.create(nombre='Tinas Calientes')
        SEOContent.objects.create(categoria=cls.tinas, meta_title='Tinas', meta_description='Tinas',
                                  faq_1_pregunta='¿Cuánto dura una sesión?',
                                  faq_1_respuesta='Dos horas de uso exclusivo.')
        cls.ambientaciones = CategoriaServicio.objects.create(nombre='Ambientaciones')

    def _html(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, url)
        return r.content.decode()

    def test_la_categoria_con_preguntas_del_admin_la_suma(self):
        html = self._html(reverse('ventas:categoria_detail', kwargs={'categoria_id': self.tinas.id}))
        self.assertIn('¿Cuánto dura una sesión?', html)
        # En la sección visible (no basta con que esté en los datos para Google).
        self.assertIn(f'<span>{PREGUNTA}</span>', html)
        self.assertIn(f'<p>{POLITICA}</p>', html)
        # Google la lee en los datos estructurados de la página.
        self.assertIn(f'"name": "{PREGUNTA}"', html)

    def test_la_categoria_sin_preguntas_del_admin_tambien(self):
        html = self._html(reverse('ventas:categoria_detail',
                                  kwargs={'categoria_id': self.ambientaciones.id}))
        self.assertIn(PREGUNTA, html)
        self.assertIn(POLITICA, html)

    def test_masajes_garantia_y_empresas(self):
        for nombre in ('masajes', 'garantia', 'empresas'):
            self.assertIn(POLITICA, self._html(reverse(nombre)), nombre)

    def test_giftcards_solo_cambio_de_fecha(self):
        # Jorge, 26-09-2026: quien usa la GiftCard puede cambiar la fecha con el mismo aviso,
        # pero no pedir la devolución del dinero.
        for url in (reverse('ventas:giftcard_menu'), reverse('ventas:giftcard_menu') + '?classic=1'):
            html = self._html(url)
            self.assertIn(ConfiguracionResumen.POLITICA_GIFTCARD, html, url)
            self.assertNotIn('te devolvemos el 100%', html, url)

    def test_si_cambia_en_el_admin_cambia_en_la_web(self):
        config = ConfiguracionResumen.get_solo()
        config.politica_tinas_masajes = 'Política nueva de prueba: 72 horas.'
        config.save()
        self.assertIn('Política nueva de prueba: 72 horas.', self._html(reverse('garantia')))
