"""
Tests para Operación Vuelta a Casa, Etapa 7.

Cobertura:
    1. Endpoints cron HTTP (2):
       - GET sin token → 403
       - GET con token inválido → 403
       - GET con token válido → 200, ejecuta el comando, responde resumen
       - Verificar side effects en BD (bandeja generada / atribución realizada)

    2. Admin Django (cobertura mínima):
       - Los 4 modelos nuevos están registrados
       - Cada changelist renderiza sin crashear
       - Cada formulario de edición/visualización carga sin crashear
       - readonly_fields se aplican (ContactoWhatsApp no permite add/delete)

Ejecutar:
    python manage.py test ventas.tests_etapa7_admin_y_crons
"""

from __future__ import annotations

from datetime import date, timedelta
from io import StringIO

from django.contrib.admin.sites import site as default_admin_site
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ventas.models import (
    Cliente,
    ClienteTaxonomia,
    ContactoWhatsApp,
    EventoCelebracion,
    ScriptWhatsApp,
    TaxonomiaMovimiento,
    VentaReserva,
)


TEST_CRON_TOKEN = 'test-cron-token-789'


# ============================================================================
# Endpoints cron HTTP
# ============================================================================

@override_settings(AUTOMATION_API_KEY='dummy')  # evita warnings del otro auth
class CronGenerarBandejaEndpointTests(TestCase):
    URL = '/ventas/api/cron/generar-bandeja-whatsapp-diaria/'

    def setUp(self):
        self.client_http = Client()
        # Setup mínimo para que el comando tenga algo que hacer
        self.cli = Cliente.objects.create(nombre='Test', telefono='+56987651500')
        ClienteTaxonomia.objects.create(
            cliente=self.cli,
            eje_valor='Dormido',
            eje_estilo='Amante de las Tinas',
            eje_contexto='Visitante Pareja',
            dias_desde_ultima_visita=200,
            ultima_visita=date.today() - timedelta(days=200),
            gasto_total=300000,
        )
        ScriptWhatsApp.objects.create(
            script_id='TEST.CRON.1', nombre='Test',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            plantilla_texto='Hola {nombre}',
        )

    @override_settings(CRON_TOKEN='', AUTOMATION_API_KEY='dummy')
    def _patch_env(self, monkeypatch=None):
        pass

    def test_sin_token_403(self):
        import os
        os.environ['CRON_TOKEN'] = TEST_CRON_TOKEN
        try:
            r = self.client_http.get(self.URL)
            self.assertEqual(r.status_code, 403)
        finally:
            del os.environ['CRON_TOKEN']

    def test_token_invalido_403(self):
        import os
        os.environ['CRON_TOKEN'] = TEST_CRON_TOKEN
        try:
            r = self.client_http.get(self.URL + '?token=invalido')
            self.assertEqual(r.status_code, 403)
        finally:
            del os.environ['CRON_TOKEN']

    def test_token_valido_200_ejecuta_comando(self):
        import os
        os.environ['CRON_TOKEN'] = TEST_CRON_TOKEN
        try:
            r = self.client_http.get(self.URL + f'?token={TEST_CRON_TOKEN}')
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertTrue(data['ok'])
            self.assertEqual(data['command'], 'generar_bandeja_whatsapp_diaria')
            self.assertIn('duracion_segundos', data)
            self.assertIn('output', data)

            # Side effect: debe haber creado al menos 1 ContactoWhatsApp
            self.assertGreater(ContactoWhatsApp.objects.count(), 0)
        finally:
            del os.environ['CRON_TOKEN']

    def test_sin_cron_token_env_no_valida(self):
        """Si CRON_TOKEN no está seteada en env, el endpoint NO valida y deja pasar.
        Esto es el comportamiento heredado del patrón existente (cron_procesar_premios_bienvenida).
        Es intencional para entornos de desarrollo locales sin CRON_TOKEN."""
        import os
        os.environ.pop('CRON_TOKEN', None)  # asegurar no seteada
        r = self.client_http.get(self.URL)
        # Sin la env var, deja pasar (igual que el patrón histórico)
        self.assertEqual(r.status_code, 200)


@override_settings(AUTOMATION_API_KEY='dummy')
class CronCruzarReservasEndpointTests(TestCase):
    URL = '/ventas/api/cron/cruzar-reservas-contactos-whatsapp/'

    def setUp(self):
        self.client_http = Client()
        self.cli = Cliente.objects.create(nombre='Test2', telefono='+56987651600')

    def test_sin_token_403(self):
        import os
        os.environ['CRON_TOKEN'] = TEST_CRON_TOKEN
        try:
            r = self.client_http.get(self.URL)
            self.assertEqual(r.status_code, 403)
        finally:
            del os.environ['CRON_TOKEN']

    def test_token_valido_200_ejecuta_sin_crashear(self):
        """Con base vacía de contactos/reservas, debe correr OK y devolver 0 atribuciones."""
        import os
        os.environ['CRON_TOKEN'] = TEST_CRON_TOKEN
        try:
            r = self.client_http.get(self.URL + f'?token={TEST_CRON_TOKEN}')
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertTrue(data['ok'])
            self.assertEqual(data['command'], 'cruzar_reservas_contactos_whatsapp')
            self.assertIn('duracion_segundos', data)
        finally:
            del os.environ['CRON_TOKEN']

    def test_atribuye_conversion_end_to_end(self):
        """Test E2E completo: contacto enviado + reserva del día → atribuye."""
        import os
        os.environ['CRON_TOKEN'] = TEST_CRON_TOKEN
        try:
            # Crear contacto enviado hace 3 días
            script = ScriptWhatsApp.objects.create(
                script_id='TEST.CRON.2', nombre='Test', estado_valor_target='Dormido',
                cohorte_estilo='', cohorte_contexto='', salva=1, plantilla_texto='x',
            )
            ahora = timezone.now()
            contacto = ContactoWhatsApp.objects.create(
                cliente=self.cli, script=script,
                eje_valor_snapshot='Dormido',
                eje_estilo_snapshot='', eje_contexto_snapshot='',
                dias_sin_venir_snapshot=200, salva=1, mensaje_renderizado='x',
                fecha_sugerido=ahora.date() - timedelta(days=3),
                fecha_envio=ahora - timedelta(days=3),
                estado='enviado',
            )
            # Crear reserva hoy
            VentaReserva.objects.create(
                cliente=self.cli, total=120000, estado_pago='pagado',
            )

            r = self.client_http.get(self.URL + f'?token={TEST_CRON_TOKEN}')
            self.assertEqual(r.status_code, 200)

            # Verificar atribución
            contacto.refresh_from_db()
            self.assertTrue(contacto.convirtio)
            self.assertIsNotNone(contacto.reserva_atribuida)
        finally:
            del os.environ['CRON_TOKEN']


# ============================================================================
# Admin Django — cobertura mínima de renderizado
# ============================================================================

class AdminRegistroTests(TestCase):
    """Los 4 modelos nuevos están registrados en el admin."""

    def test_scriptwhatsapp_registrado(self):
        self.assertIn(ScriptWhatsApp, default_admin_site._registry)

    def test_contactowhatsapp_registrado(self):
        self.assertIn(ContactoWhatsApp, default_admin_site._registry)

    def test_taxonomiamovimiento_registrado(self):
        self.assertIn(TaxonomiaMovimiento, default_admin_site._registry)

    def test_eventocelebracion_registrado(self):
        self.assertIn(EventoCelebracion, default_admin_site._registry)


class AdminRenderingTests(TestCase):
    """Cada changelist/changeform renderiza sin crashear."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin_user = User.objects.create_superuser(
            username='admin_test', email='admin@test.com', password='pwd'
        )
        # Datos mínimos para que las listas tengan filas
        cls.cli = Cliente.objects.create(nombre='Admin Test Cli', telefono='+56987652000')
        cls.script = ScriptWhatsApp.objects.create(
            script_id='TEST.ADMIN.1', nombre='Test',
            estado_valor_target='Dormido', cohorte_estilo='', cohorte_contexto='',
            salva=1, plantilla_texto='x',
        )
        cls.contacto = ContactoWhatsApp.objects.create(
            cliente=cls.cli, script=cls.script,
            eje_valor_snapshot='Dormido', eje_estilo_snapshot='',
            eje_contexto_snapshot='',
            dias_sin_venir_snapshot=100, salva=1, mensaje_renderizado='x',
            fecha_sugerido=date.today(), estado='pendiente',
        )
        cls.mov = TaxonomiaMovimiento.objects.create(
            cliente=cls.cli, fecha=date.today(),
            eje_valor_antes='Dormido', eje_estilo_antes='', eje_contexto_antes='',
            eje_valor_despues='En Prueba', eje_estilo_despues='',
            eje_contexto_despues='',
            evento_origen='recalculo_features',
        )
        cls.celeb = EventoCelebracion.objects.create(
            cliente=cls.cli, tipo='recuperado_dormido',
            fecha=date.today(), movimiento_relacionado=cls.mov,
            mensaje_sugerido='¡Qué bueno!',
        )

    def setUp(self):
        self.client_http = Client()
        self.client_http.force_login(self.admin_user)

    # ---- ScriptWhatsApp ----
    def test_scriptwhatsapp_changelist_renderiza(self):
        r = self.client_http.get('/admin/ventas/scriptwhatsapp/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'TEST.ADMIN.1')

    def test_scriptwhatsapp_change_renderiza(self):
        r = self.client_http.get(f'/admin/ventas/scriptwhatsapp/{self.script.id}/change/')
        self.assertEqual(r.status_code, 200)

    def test_scriptwhatsapp_add_renderiza(self):
        """ScriptWhatsApp SÍ permite agregar nuevos (Jorge puede crear plantillas desde admin)."""
        r = self.client_http.get('/admin/ventas/scriptwhatsapp/add/')
        self.assertEqual(r.status_code, 200)

    # ---- ContactoWhatsApp ----
    def test_contactowhatsapp_changelist_renderiza(self):
        r = self.client_http.get('/admin/ventas/contactowhatsapp/')
        self.assertEqual(r.status_code, 200)

    def test_contactowhatsapp_change_renderiza(self):
        r = self.client_http.get(f'/admin/ventas/contactowhatsapp/{self.contacto.id}/change/')
        self.assertEqual(r.status_code, 200)

    def test_contactowhatsapp_no_permite_add(self):
        """ContactoWhatsApp solo se crea desde el cron, no manualmente."""
        r = self.client_http.get('/admin/ventas/contactowhatsapp/add/')
        # Django devuelve 403 cuando has_add_permission=False
        self.assertEqual(r.status_code, 403)

    # ---- TaxonomiaMovimiento ----
    def test_taxonomiamovimiento_changelist_renderiza(self):
        r = self.client_http.get('/admin/ventas/taxonomiamovimiento/')
        self.assertEqual(r.status_code, 200)

    def test_taxonomiamovimiento_change_renderiza(self):
        r = self.client_http.get(f'/admin/ventas/taxonomiamovimiento/{self.mov.id}/change/')
        self.assertEqual(r.status_code, 200)

    def test_taxonomiamovimiento_no_permite_add(self):
        r = self.client_http.get('/admin/ventas/taxonomiamovimiento/add/')
        self.assertEqual(r.status_code, 403)

    # ---- EventoCelebracion ----
    def test_eventocelebracion_changelist_renderiza(self):
        r = self.client_http.get('/admin/ventas/eventocelebracion/')
        self.assertEqual(r.status_code, 200)

    def test_eventocelebracion_change_renderiza(self):
        r = self.client_http.get(f'/admin/ventas/eventocelebracion/{self.celeb.id}/change/')
        self.assertEqual(r.status_code, 200)

    def test_eventocelebracion_no_permite_add(self):
        r = self.client_http.get('/admin/ventas/eventocelebracion/add/')
        self.assertEqual(r.status_code, 403)

    # ---- Cliente: nuevos campos visibles ----
    def test_cliente_change_muestra_fieldset_operacion(self):
        """El fieldset 'Operación Vuelta a Casa' debe aparecer en el form de Cliente."""
        r = self.client_http.get(f'/admin/ventas/cliente/{self.cli.id}/change/')
        self.assertEqual(r.status_code, 200)
        # El fieldset es collapse, pero el HTML lo incluye igual
        self.assertContains(r, 'Operación Vuelta a Casa')
        self.assertContains(r, 'opt_out_whatsapp')
