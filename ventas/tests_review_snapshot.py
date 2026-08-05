"""El admin de ReviewSnapshot daba 500 al registrar el SEGUNDO snapshot.

Caso real (Jorge, 2026-08-05): "revisa por qué no funciona la captura de
opiniones externas" — `/admin/ventas/reviewsnapshot/` respondía Server Error.

Causa: las columnas Δ usaban `format_html('{:+.2f}★', rd)`. **`format_html` pasa
cada argumento por `conditional_escape`**, así que el número llega convertido en
`SafeString` y el especificador numérico revienta con «Unknown format code 'f'
for object of type 'SafeString'».

Por qué apareció recién: con UN solo snapshot, `deltas()` devuelve None y la
columna muestra "—" sin tocar esa línea. Reventó al registrar el segundo. **Un
camino que solo se recorre la segunda vez no lo tocan las pruebas del primer
día** — de ahí que el test de abajo cree DOS.

Ejecutar:
    python manage.py test ventas.tests_review_snapshot
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from ventas.admin import _delta_reviews
from ventas.models import ReviewSnapshot

URL = '/admin/ventas/reviewsnapshot/'


class FormatoDeltaTest(TestCase):
    """El helper puro — donde estaba el error."""

    def test_sube_muestra_flecha_arriba_y_signo(self):
        self.assertIn('🔺', _delta_reviews(0.1, 5))
        self.assertIn('+0.10★', _delta_reviews(0.1, 5))
        self.assertIn('+5', _delta_reviews(0.1, 5))

    def test_baja_muestra_flecha_abajo(self):
        salida = _delta_reviews(-0.2, -3)
        self.assertIn('🔻', salida)
        self.assertIn('-0.20★', salida)

    def test_sin_cambio_muestra_flecha_lateral(self):
        self.assertIn('→', _delta_reviews(0, 0))

    def test_acepta_Decimal_sin_reventar(self):
        """Los ratings vienen como Decimal desde la BD, no como float."""
        self.assertIn('+0.30★', _delta_reviews(Decimal('0.3'), Decimal('7')))

    def test_acepta_None(self):
        self.assertIn('→', _delta_reviews(None, None))


class ElCasoRealTest(TestCase):
    """La página con DOS snapshots — exactamente lo que daba 500."""

    def setUp(self):
        hoy = timezone.localdate()
        ReviewSnapshot.objects.create(
            fecha=hoy - timedelta(days=7),
            google_rating=Decimal('4.7'), google_total=310,
            tripadvisor_rating=Decimal('4.5'), tripadvisor_total=120)
        ReviewSnapshot.objects.create(
            fecha=hoy,
            google_rating=Decimal('4.8'), google_total=315,
            tripadvisor_rating=Decimal('4.4'), tripadvisor_total=123)
        User = get_user_model()
        User.objects.create_superuser('admin_rs', 'a@test.cl', 'x')
        self.client.login(username='admin_rs', password='x')

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()

    def test_el_listado_ABRE(self):
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200)

    def test_y_muestra_los_deltas_calculados(self):
        cuerpo = self.client.get(URL).content.decode()
        self.assertIn('+0.10★', cuerpo)   # Google subió de 4.7 a 4.8
        self.assertIn('-0.10★', cuerpo)   # TripAdvisor bajó de 4.5 a 4.4

    def test_con_UN_SOLO_snapshot_tambien_abre(self):
        """El caso que sí funcionaba antes: no romperlo al arreglar el otro."""
        ReviewSnapshot.objects.all().delete()
        ReviewSnapshot.objects.create(
            fecha=timezone.localdate(),
            google_rating=Decimal('4.7'), google_total=310)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertIn('—', r.content.decode())


class SinEspecificadoresNumericosTest(TestCase):
    """Que el error no vuelva por otra puerta del mismo archivo."""

    def test_ningun_format_html_del_admin_usa_specs_numericos(self):
        import io
        import os
        import re
        from django.conf import settings
        ruta = os.path.join(settings.BASE_DIR, 'ventas', 'admin.py')
        fuente = io.open(ruta, encoding='utf-8').read()
        # `format_html('... {:.2f} ...')` — el patrón que revienta.
        malos = re.findall(r"format_html\(\s*['\"][^'\"]*\{:[^}]*[fdeg%][^}]*\}", fuente)
        self.assertEqual(malos, [], f'format_html con formato numérico: {malos}')
