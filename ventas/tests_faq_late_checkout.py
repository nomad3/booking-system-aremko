"""La pregunta «¿Debo pagar por late check-out?» cabe y sale al final.

Jorge (17-09-2026): alojamientos tenía los 6 espacios de preguntas ocupados.
SEOContent ahora tiene 8. La misma lista alimenta lo que se ve en la página y
los datos que lee Google (FAQPage), así que basta un lugar para las dos cosas.

Ejecutar:
    python manage.py test ventas.tests_faq_late_checkout
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ventas.models import FAQ_ESPACIOS, CategoriaServicio, SEOContent

RAIZ = Path(__file__).resolve().parent.parent
PREGUNTA = '¿Debo pagar por late check-out?'
RESPUESTA = ('Sí. El check-out es hasta las 11:00 hrs. Si quieres quedarte más tiempo, cada '
             'hora adicional o fracción tiene un valor de $20.000 por cabaña y está sujeta a '
             'disponibilidad. Coordínalo con recepción o por WhatsApp antes de tu salida.')


def _seo_de_alojamientos(con_la_nueva=True):
    cat = CategoriaServicio.objects.create(id=3, nombre='Cabañas')
    datos = {f'faq_{i}_pregunta': f'¿Pregunta {i}?' for i in range(1, 7)}
    datos.update({f'faq_{i}_respuesta': f'Respuesta {i}.' for i in range(1, 7)})
    if con_la_nueva:
        datos.update(faq_7_pregunta=PREGUNTA, faq_7_respuesta=RESPUESTA)
    return SEOContent.objects.create(
        categoria=cat, meta_title='Cabañas en Puerto Varas', meta_description='Alojamiento',
        contenido_principal='Texto', subtitulo_principal='Sub', **datos)


class LosOchoEspacios(TestCase):
    def test_hay_ocho_espacios(self):
        self.assertEqual(FAQ_ESPACIOS, 8)
        for i in range(1, 9):
            SEOContent._meta.get_field(f'faq_{i}_pregunta')
            SEOContent._meta.get_field(f'faq_{i}_respuesta')

    def test_la_septima_sale_y_sale_al_final(self):
        faqs = _seo_de_alojamientos().get_faqs()
        self.assertEqual(len(faqs), 7)
        self.assertEqual(faqs[-1], {'pregunta': PREGUNTA, 'respuesta': RESPUESTA})

    def test_un_espacio_vacio_no_se_muestra(self):
        self.assertEqual(len(_seo_de_alojamientos(con_la_nueva=False).get_faqs()), 6)


class LaPaginaDeAlojamientos(TestCase):
    def setUp(self):
        _seo_de_alojamientos()
        self.html = self.client.get(reverse('alojamientos')).content.decode()

    def test_se_ve_en_la_pagina_y_es_la_ultima(self):
        self.assertIn(PREGUNTA, self.html)
        self.assertIn('$20.000 por cabaña', self.html)
        self.assertGreater(self.html.rindex(PREGUNTA), self.html.rindex('¿Pregunta 6?'))

    def test_google_la_lee_en_los_datos_estructurados(self):
        preguntas = []
        for bloque in re.findall(r'<script type="application/ld\+json">(.*?)</script>',
                                 self.html, re.S):
            try:
                datos = json.loads(bloque)
            except ValueError:
                continue
            nodos = datos.get('@graph', [datos]) if isinstance(datos, dict) else datos
            for n in nodos:
                if isinstance(n, dict) and n.get('@type') == 'FAQPage':
                    preguntas = [(q['name'], q['acceptedAnswer']['text'])
                                 for q in n['mainEntity']]
        self.assertEqual(len(preguntas), 7)
        self.assertEqual(preguntas[-1], (PREGUNTA, RESPUESTA))


class SePuedeEditarEnElAdmin(TestCase):
    def test_el_formulario_trae_los_espacios_7_y_8(self):
        seo = _seo_de_alojamientos()
        jefe = get_user_model().objects.create_superuser('jorge_t', 'j@test.cl', 'x')
        self.client.force_login(jefe)
        r = self.client.get(reverse('admin:ventas_seocontent_change', args=[seo.pk]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for campo in ('faq_7_pregunta', 'faq_7_respuesta', 'faq_8_pregunta', 'faq_8_respuesta'):
            self.assertIn(f'name="{campo}"', html)
        # Y el formulario se puede GUARDAR sin perder nada (método duplicado, 08-09).
        self.assertIn('name="faq_1_pregunta"', html)
        self.assertIn('name="meta_title"', html)


class LaSemilla(TestCase):
    def test_un_re_run_deja_la_pregunta_nueva(self):
        texto = (RAIZ / 'populate_seo_content.py').read_text(encoding='utf-8')
        self.assertIn(f"'faq_7_pregunta': '{PREGUNTA}'", texto)
        self.assertIn(RESPUESTA, texto)
