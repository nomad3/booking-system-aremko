"""
Tests para la landing "Refugio Aremko" (campaña 15-jun-2026).

Cubre los 6 escenarios del brief:
    1. GET /refugio/ → 200 con HTML correcto cuando la campaña está activa
    2. GET /refugio/ → 404 cuando la campaña está desactivada
    3. POST /refugio/submit/ válido → 200 JSON + RefugioLead creado + email
    4. POST /refugio/submit/ sin campos requeridos → 400 JSON
    5. POST con UTM en GET previo + hidden inputs → UTM persistidos en el lead
    6. JSON-LD Product/Offer presente en el HTML para SEO/rich results

Ejecutar:
    python manage.py test ventas.tests_refugio_landing
"""

from __future__ import annotations

from django.core import mail
from django.test import TestCase, Client
from django.urls import reverse

from ventas.models import RefugioConfig, RefugioImagen, RefugioLead


class RefugioLandingTests(TestCase):
    """Suite de la landing pública /refugio/ y el endpoint /refugio/submit/."""

    def setUp(self):
        # Singleton: get_solo crea con defaults la primera vez.
        self.config = RefugioConfig.get_solo()
        self.config.activo = True
        self.config.precio_clp = 270000
        self.config.save()
        self.client = Client()

    # ──────────────────────────────────────────────────────────────────
    # Test 1: GET landing activa renderiza 200 + textos del config
    # ──────────────────────────────────────────────────────────────────
    def test_get_landing_activa_renderiza_ok(self):
        url = reverse('refugio_landing')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Texto del config visible
        self.assertContains(resp, self.config.hero_title)
        # Form con CSRF presente
        self.assertContains(resp, 'csrfmiddlewaretoken')
        # Precio renderizado (puede venir con separador de miles, validamos cifra base)
        self.assertContains(resp, '270')

    # ──────────────────────────────────────────────────────────────────
    # Test 2: GET landing desactivada → 404
    # ──────────────────────────────────────────────────────────────────
    def test_get_landing_inactiva_devuelve_404(self):
        self.config.activo = False
        self.config.save()
        resp = self.client.get(reverse('refugio_landing'))
        self.assertEqual(resp.status_code, 404)

    # ──────────────────────────────────────────────────────────────────
    # Test 3: POST submit válido crea RefugioLead + envía emails
    # ──────────────────────────────────────────────────────────────────
    def test_post_submit_valido_crea_lead_y_envia_emails(self):
        url = reverse('refugio_submit')
        payload = {
            'nombre': 'Jorge Aguilera',
            'email': 'jorge@example.com',
            'telefono': '+56912345678',
            'fecha_tentativa': '2026-06-20',
            'num_personas': '2',
            'mensaje': 'Para nuestro aniversario',
        }
        resp = self.client.post(url, payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('lead_id', data)

        # Lead persistido con todos los datos
        lead = RefugioLead.objects.get(id=data['lead_id'])
        self.assertEqual(lead.nombre, 'Jorge Aguilera')
        self.assertEqual(lead.email, 'jorge@example.com')
        self.assertEqual(lead.num_personas, 2)
        self.assertEqual(lead.status, 'nuevo')
        self.assertIsNotNone(lead.fecha_tentativa)

        # Emails enviados: 1 al equipo + 1 al cliente
        self.assertEqual(len(mail.outbox), 2)
        emails_to = {addr for m in mail.outbox for addr in m.to}
        self.assertIn('jorge@example.com', emails_to)
        self.assertIn('comunicaciones@aremko.cl', emails_to)
        self.assertIn('aremkospa@gmail.com', emails_to)

    # ──────────────────────────────────────────────────────────────────
    # Test 4: POST sin campos requeridos → 400
    # ──────────────────────────────────────────────────────────────────
    def test_post_sin_nombre_devuelve_400(self):
        url = reverse('refugio_submit')
        resp = self.client.post(url, {'email': 'sin-nombre@example.com'})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn('obligatorios', data['error'].lower())
        # Y no se creó nada en BD
        self.assertEqual(RefugioLead.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    # ──────────────────────────────────────────────────────────────────
    # Test 5: UTM tracking — desde hidden inputs del POST se persisten
    # ──────────────────────────────────────────────────────────────────
    def test_utm_se_persisten_en_el_lead(self):
        url = reverse('refugio_submit')
        payload = {
            'nombre': 'Test UTM',
            'email': 'utm@example.com',
            'num_personas': '2',
            'utm_source': 'meta_ads',
            'utm_medium': 'cpc',
            'utm_campaign': 'refugio_lanzamiento',
            'utm_content': 'video_15s',
            'utm_term': 'spa puerto varas',
        }
        resp = self.client.post(url, payload)
        self.assertEqual(resp.status_code, 200)

        lead = RefugioLead.objects.get(email='utm@example.com')
        self.assertEqual(lead.utm_source, 'meta_ads')
        self.assertEqual(lead.utm_medium, 'cpc')
        self.assertEqual(lead.utm_campaign, 'refugio_lanzamiento')
        self.assertEqual(lead.utm_content, 'video_15s')
        self.assertEqual(lead.utm_term, 'spa puerto varas')

    # ──────────────────────────────────────────────────────────────────
    # Test 6: JSON-LD Product/Offer presente para SEO
    # ──────────────────────────────────────────────────────────────────
    def test_jsonld_product_offer_presente(self):
        url = reverse('refugio_landing')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('application/ld+json', html)
        self.assertIn('"@type": "Product"', html)
        self.assertIn('"@type": "Offer"', html)
        self.assertIn('"priceCurrency": "CLP"', html)
        self.assertIn('"price": "270000"', html)
