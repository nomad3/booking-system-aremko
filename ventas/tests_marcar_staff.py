"""
Tests para el endpoint marcar_staff (solicitado aremko-cli 2026-05-27 PM).

Cubre:
    - Auth X-API-KEY (401 sin / mal key)
    - Cliente inexistente → 404
    - Marca correctamente es_staff_proxy=True + razon
    - Descarta TODOS los pendientes del cliente (no solo el del día)
    - Idempotencia: re-marcar ya-staff retorna already_marked sin tocar BD
    - Filtro del cron excluye clientes es_staff_proxy=True

Ejecutar:
    python manage.py test ventas.tests_marcar_staff
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from ventas.models import (
    Cliente,
    ClienteTaxonomia,
    ContactoWhatsApp,
    ScriptWhatsApp,
)


HOY = date.today()
URL = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/clientes/{}/marcar-staff/'


@override_settings(AUTOMATION_API_KEY='test-key-staff')
class MarcarStaffEndpointTests(TestCase):

    def setUp(self):
        self.cli = Cliente.objects.create(
            nombre='Jorge Aguilera',
            telefono='+56958655810',
        )
        self.script = ScriptWhatsApp.objects.create(
            script_id='TEST.1', nombre='Test',
            estado_valor_target='Campeón',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            plantilla_texto='Hola {nombre}',
        )
        self.http = Client(HTTP_HOST='testserver')

    def _post(self, cliente_id, body, api_key='test-key-staff'):
        return self.http.post(
            URL.format(cliente_id),
            data=json.dumps(body),
            content_type='application/json',
            HTTP_X_API_KEY=api_key,
        )

    # ---- Auth ----
    def test_sin_api_key_401(self):
        resp = self.http.post(
            URL.format(self.cli.id),
            data='{}', content_type='application/json',
        )
        self.assertEqual(resp.status_code, 401)

    def test_api_key_invalida_401(self):
        resp = self._post(self.cli.id, {}, api_key='wrong')
        self.assertEqual(resp.status_code, 401)

    # ---- 404 cliente inexistente ----
    def test_cliente_inexistente_404(self):
        resp = self._post(99999, {'razon': 'test'})
        self.assertEqual(resp.status_code, 404)

    # ---- Body no JSON ----
    def test_body_no_json_400(self):
        resp = self.http.post(
            URL.format(self.cli.id),
            data='no es json',
            content_type='application/json',
            HTTP_X_API_KEY='test-key-staff',
        )
        self.assertEqual(resp.status_code, 400)

    # ---- Caso feliz ----
    def test_marca_cliente_y_responde_ok(self):
        resp = self._post(self.cli.id, {
            'razon': 'Jorge Aguilera, dueño del spa',
            'operador': 'deborah',
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['cliente_id'], self.cli.id)
        self.assertEqual(data['nombre_cliente'], 'Jorge Aguilera')
        self.assertEqual(data['razon'], 'Jorge Aguilera, dueño del spa')
        self.assertFalse(data['already_marked'])

        # BD actualizada
        self.cli.refresh_from_db()
        self.assertTrue(self.cli.es_staff_proxy)
        self.assertEqual(self.cli.es_staff_proxy_razon, 'Jorge Aguilera, dueño del spa')

    def test_descarta_contactos_pendientes(self):
        # Crear 3 contactos pendientes en distintos días
        for dias_atras in [0, 1, 5]:
            ContactoWhatsApp.objects.create(
                cliente=self.cli, script=self.script,
                eje_valor_snapshot='Campeón',
                eje_estilo_snapshot='', eje_contexto_snapshot='',
                dias_sin_venir_snapshot=200, salva=1,
                mensaje_renderizado='msg', prioridad=0,
                fecha_sugerido=HOY - timedelta(days=dias_atras),
                estado='pendiente',
            )
        # Y uno enviado (no debe descartarse)
        ContactoWhatsApp.objects.create(
            cliente=self.cli, script=self.script,
            eje_valor_snapshot='Campeón',
            eje_estilo_snapshot='', eje_contexto_snapshot='',
            dias_sin_venir_snapshot=200, salva=1,
            mensaje_renderizado='msg', prioridad=0,
            fecha_sugerido=HOY - timedelta(days=10),
            estado='enviado',
        )

        resp = self._post(self.cli.id, {'razon': 'staff'})
        data = json.loads(resp.content)
        self.assertEqual(data['contactos_descartados'], 3)

        self.assertEqual(
            ContactoWhatsApp.objects.filter(cliente=self.cli, estado='descartado').count(),
            3,
        )
        self.assertEqual(
            ContactoWhatsApp.objects.filter(cliente=self.cli, estado='enviado').count(),
            1,
            "El enviado NO debe descartarse",
        )

    def test_idempotente_ya_marcado(self):
        Cliente.objects.filter(id=self.cli.id).update(
            es_staff_proxy=True, es_staff_proxy_razon='razón previa'
        )
        resp = self._post(self.cli.id, {'razon': 'intento doble'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['already_marked'])
        self.assertEqual(data['contactos_descartados'], 0)

        # La razón previa NO se sobrescribe
        self.cli.refresh_from_db()
        self.assertEqual(self.cli.es_staff_proxy_razon, 'razón previa')

    def test_razon_truncada_max_length(self):
        razon_larga = 'x' * 500
        resp = self._post(self.cli.id, {'razon': razon_larga})
        self.assertEqual(resp.status_code, 200)
        self.cli.refresh_from_db()
        self.assertEqual(len(self.cli.es_staff_proxy_razon), 200)


@override_settings(AUTOMATION_API_KEY='test-key-staff')
class CronFiltraStaffProxyTests(TestCase):
    """El cron generar_bandeja_whatsapp_diaria debe excluir clientes con
    es_staff_proxy=True antes de evaluar candidatos."""

    def setUp(self):
        ScriptWhatsApp.objects.all().delete()
        self.script = ScriptWhatsApp.objects.create(
            script_id='B.1', nombre='Dormido genérico',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            plantilla_texto='Hola {nombre}, hace {dias_sin_venir} días',
        )

    def _make_cliente_dormido(self, nombre, telefono, es_staff=False):
        cli = Cliente.objects.create(
            nombre=nombre, telefono=telefono, es_staff_proxy=es_staff,
        )
        ClienteTaxonomia.objects.create(
            cliente=cli, eje_valor='Dormido',
            eje_estilo='Amante de las Tinas',
            eje_contexto='Visitante Pareja',
            dias_desde_ultima_visita=200,
            gasto_total=100000,
            ultima_visita=HOY - timedelta(days=200),
        )
        return cli

    def test_cron_excluye_es_staff_proxy(self):
        cli_normal = self._make_cliente_dormido('Cliente Normal', '+56911100001')
        cli_staff = self._make_cliente_dormido('Jorge Aguilera', '+56911100002', es_staff=True)

        out = StringIO()
        call_command('generar_bandeja_whatsapp_diaria', stdout=out)

        contactos = ContactoWhatsApp.objects.all()
        self.assertEqual(contactos.count(), 1, "Solo el cliente normal entra")
        self.assertEqual(contactos.first().cliente_id, cli_normal.id)
