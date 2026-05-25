"""
Tests E2E para los 9 endpoints de Operación Vuelta a Casa — Etapa 4.

Cubre:
    - Auth: token funciona / sin token devuelve 401 / sin env var devuelve 503
    - GET siguiente: orden (respuestas pendientes → celebraciones → bandeja → fin)
    - POST marcar-enviado: revalidación 409, actualiza ultimo_contacto_outbound,
      pre-resuelve siguiente
    - POST marcar-omitido / marcar-no-aplica: side effects en Cliente
    - POST registrar-respuesta: opt_out actualiza Cliente.opt_out_whatsapp,
      mas_adelante setea proximo_contacto_no_antes_de = today + 60d
    - GET explicacion: stub devuelve string vacío
    - GET resumen-dia: stats correctas
    - GET movimientos: matriz correcta sobre data sintética
    - GET scripts-estadisticas: agregaciones correctas

Ejecutar:
    python manage.py test ventas.tests_bandeja_whatsapp_endpoints
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal

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


TEST_API_KEY = 'test-bandeja-api-key-456'


@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class BandejaWhatsappEndpointsTestCase(TestCase):
    """Base con setup compartido para todos los tests de endpoints."""

    def setUp(self):
        self.client_http = Client()
        self.auth_headers = {'HTTP_X_API_KEY': TEST_API_KEY}

        # Cliente típico Dormido
        self.cli = Cliente.objects.create(
            nombre='María González Espinoza',
            telefono='+56987654321',
        )
        self.tax = ClienteTaxonomia.objects.create(
            cliente=self.cli,
            eje_valor='Dormido',
            eje_estilo='Amante de las Tinas',
            eje_contexto='Visitante Pareja',
            dias_desde_ultima_visita=200,
            ultima_visita=date.today() - timedelta(days=200),
            total_visitas=5,
            gasto_total=300000,
        )
        # Script aplicable
        self.script = ScriptWhatsApp.objects.create(
            script_id='TEST.1', nombre='Test Dormido',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='',
            salva=1,
            plantilla_texto='Hola {nombre}, hace {dias_sin_venir} días.',
        )
        # ContactoWhatsApp pendiente para hoy
        self.contacto = ContactoWhatsApp.objects.create(
            cliente=self.cli, script=self.script,
            eje_valor_snapshot='Dormido',
            eje_estilo_snapshot='Amante de las Tinas',
            eje_contexto_snapshot='Visitante Pareja',
            dias_sin_venir_snapshot=200,
            gasto_historico_snapshot=300000,
            salva=1,
            mensaje_renderizado='Hola María, hace 200 días.',
            prioridad=3,
            fecha_sugerido=date.today(),
            estado='pendiente',
        )

    def _get(self, path, **extra):
        return self.client_http.get(path, **{**self.auth_headers, **extra})

    def _post(self, path, body=None, **extra):
        return self.client_http.post(
            path,
            data=json.dumps(body or {}),
            content_type='application/json',
            **{**self.auth_headers, **extra},
        )


# ============================================================================
# AUTH
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class AuthTests(BandejaWhatsappEndpointsTestCase):
    URL = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/siguiente/'

    def test_sin_token_devuelve_401(self):
        r = self.client_http.get(self.URL)
        self.assertEqual(r.status_code, 401)
        self.assertIn('Authentication required', r.json()['error'])

    def test_token_invalido_devuelve_401(self):
        r = self.client_http.get(self.URL, HTTP_X_API_KEY='token-invalido')
        self.assertEqual(r.status_code, 401)

    def test_token_valido_devuelve_200(self):
        r = self._get(self.URL)
        self.assertEqual(r.status_code, 200)

    @override_settings(AUTOMATION_API_KEY='')
    def test_sin_env_var_devuelve_503(self):
        # Si la env var no está configurada, el endpoint se cierra
        r = self._get(self.URL)
        self.assertEqual(r.status_code, 503)


# ============================================================================
# GET siguiente — orden de prioridad
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class SiguienteTests(BandejaWhatsappEndpointsTestCase):
    URL = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/siguiente/'

    def test_devuelve_nuevo_contacto_cuando_solo_hay_pendientes(self):
        r = self._get(self.URL)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['tipo'], 'nuevo_contacto')
        self.assertEqual(data['contacto']['id'], self.contacto.id)
        self.assertEqual(data['contacto']['cliente']['nombre'], 'María González Espinoza')

    def test_respuesta_pendiente_tiene_precedencia_sobre_nuevo_contacto(self):
        # Crear un enviado hace 5 días sin tipo_respuesta marcado
        otro_cli = Cliente.objects.create(nombre='Pedro Test', telefono='+56987654322')
        cinco_dias_atras = timezone.now() - timedelta(days=5)
        otro = ContactoWhatsApp.objects.create(
            cliente=otro_cli, script=self.script,
            eje_valor_snapshot='Dormido', eje_estilo_snapshot='', eje_contexto_snapshot='',
            dias_sin_venir_snapshot=100, salva=1, mensaje_renderizado='x',
            fecha_sugerido=cinco_dias_atras.date(),
            fecha_envio=cinco_dias_atras,
            estado='enviado', tipo_respuesta='',
        )
        r = self._get(self.URL)
        data = r.json()
        self.assertEqual(data['tipo'], 'respuesta_pendiente')
        self.assertEqual(data['contacto']['id'], otro.id)

    def test_celebracion_tiene_precedencia_sobre_nuevo_contacto(self):
        # Crear movimiento + celebración del día
        mov = TaxonomiaMovimiento.objects.create(
            cliente=self.cli, fecha=date.today(),
            eje_valor_antes='Dormido', eje_estilo_antes='Amante de las Tinas',
            eje_contexto_antes='Visitante Pareja',
            eje_valor_despues='En Prueba', eje_estilo_despues='Amante de las Tinas',
            eje_contexto_despues='Visitante Pareja',
            evento_origen='reserva',
        )
        celeb = EventoCelebracion.objects.create(
            cliente=self.cli, tipo='recuperado_dormido',
            fecha=date.today(), movimiento_relacionado=mov,
            mensaje_sugerido='¡Qué bueno tenerte de vuelta!',
        )
        r = self._get(self.URL)
        data = r.json()
        self.assertEqual(data['tipo'], 'celebracion')
        self.assertEqual(data['celebracion']['id'], celeb.id)

    def test_fin_del_dia_cuando_no_hay_nada(self):
        ContactoWhatsApp.objects.all().delete()
        r = self._get(self.URL)
        data = r.json()
        self.assertEqual(data['tipo'], 'fin_del_dia')
        self.assertIn('resumen_dia', data)


# ============================================================================
# POST marcar-enviado
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class MarcarEnviadoTests(BandejaWhatsappEndpointsTestCase):
    def _url(self, cid):
        return f'/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/{cid}/marcar-enviado/'

    def test_marca_enviado_y_actualiza_ultimo_outbound(self):
        r = self._post(self._url(self.contacto.id), {'operador': 'deborah'})
        self.assertEqual(r.status_code, 200)

        self.contacto.refresh_from_db()
        self.cli.refresh_from_db()
        self.assertEqual(self.contacto.estado, 'enviado')
        self.assertEqual(self.contacto.operador, 'deborah')
        self.assertIsNotNone(self.contacto.fecha_envio)
        self.assertEqual(self.cli.ultimo_contacto_outbound, date.today())

    def test_guarda_mensaje_editado(self):
        editado = 'Hola María, te escribo personalmente :)'
        self._post(self._url(self.contacto.id), {
            'operador': 'deborah',
            'mensaje_enviado_editado': editado,
        })
        self.contacto.refresh_from_db()
        self.assertEqual(self.contacto.mensaje_enviado_editado, editado)

    def test_409_si_cliente_cambio_estado(self):
        # Cliente pasó de Dormido a En Prueba (reservó entre madrugada y ahora)
        self.tax.eje_valor = 'En Prueba'
        self.tax.save()

        r = self._post(self._url(self.contacto.id), {'operador': 'deborah'})
        self.assertEqual(r.status_code, 409)
        data = r.json()
        self.assertEqual(data['error'], 'conflict')
        self.assertEqual(data['eje_valor_anterior'], 'Dormido')
        self.assertEqual(data['eje_valor_actual'], 'En Prueba')

        self.contacto.refresh_from_db()
        self.assertEqual(self.contacto.estado, 'descartado')

    def test_no_se_puede_marcar_enviado_si_no_pendiente(self):
        self.contacto.estado = 'enviado'
        self.contacto.save()
        r = self._post(self._url(self.contacto.id), {'operador': 'deborah'})
        self.assertEqual(r.status_code, 400)

    def test_404_si_contacto_no_existe(self):
        r = self._post(self._url(99999), {'operador': 'deborah'})
        self.assertEqual(r.status_code, 404)

    def test_pre_resuelve_siguiente(self):
        # Crear un segundo pendiente
        cli2 = Cliente.objects.create(nombre='Otro', telefono='+56987654333')
        ContactoWhatsApp.objects.create(
            cliente=cli2, script=self.script,
            eje_valor_snapshot='Dormido', eje_estilo_snapshot='', eje_contexto_snapshot='',
            dias_sin_venir_snapshot=100, salva=1, mensaje_renderizado='x',
            prioridad=4, fecha_sugerido=date.today(), estado='pendiente',
        )
        r = self._post(self._url(self.contacto.id), {'operador': 'deborah'})
        data = r.json()
        self.assertIn('siguiente', data)
        # Debe traer el segundo pendiente (el primero ya está enviado)
        self.assertEqual(data['siguiente']['tipo'], 'nuevo_contacto')


# ============================================================================
# POST marcar-omitido + marcar-no-aplica
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class MarcarOmitidoTests(BandejaWhatsappEndpointsTestCase):
    def test_marca_omitido(self):
        url = f'/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/{self.contacto.id}/marcar-omitido/'
        r = self._post(url, {'operador': 'deborah'})
        self.assertEqual(r.status_code, 200)
        self.contacto.refresh_from_db()
        self.assertEqual(self.contacto.estado, 'omitido')


@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class MarcarNoAplicaTests(BandejaWhatsappEndpointsTestCase):
    def test_marca_no_aplica_y_setea_gracia_90d(self):
        url = f'/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/{self.contacto.id}/marcar-no-aplica/'
        r = self._post(url, {'operador': 'deborah', 'razon': 'telefono invalido'})
        self.assertEqual(r.status_code, 200)

        self.contacto.refresh_from_db()
        self.cli.refresh_from_db()
        self.assertEqual(self.contacto.estado, 'no_aplica')
        self.assertEqual(self.contacto.nota_operador, 'telefono invalido')
        self.assertEqual(
            self.cli.proximo_contacto_no_antes_de,
            date.today() + timedelta(days=90),
        )


# ============================================================================
# POST registrar-respuesta
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class RegistrarRespuestaTests(BandejaWhatsappEndpointsTestCase):
    def setUp(self):
        super().setUp()
        # Para registrar respuesta el contacto debe estar enviado
        self.contacto.estado = 'enviado'
        self.contacto.fecha_envio = timezone.now()
        self.contacto.save()

    def _url(self):
        return f'/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/{self.contacto.id}/registrar-respuesta/'

    def test_registra_respuesta_basica(self):
        r = self._post(self._url(), {
            'respondio': True,
            'tipo_respuesta': 'interesado',
            'nota_operador': 'Quiere venir el viernes',
            'operador': 'deborah',
        })
        self.assertEqual(r.status_code, 200)
        self.contacto.refresh_from_db()
        self.assertTrue(self.contacto.respondio)
        self.assertEqual(self.contacto.tipo_respuesta, 'interesado')
        self.assertEqual(self.contacto.nota_operador, 'Quiere venir el viernes')

    def test_opt_out_actualiza_cliente(self):
        r = self._post(self._url(), {
            'respondio': True,
            'tipo_respuesta': 'opt_out',
            'operador': 'deborah',
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['cliente_actualizado'])

        self.cli.refresh_from_db()
        self.assertTrue(self.cli.opt_out_whatsapp)

    def test_mas_adelante_setea_60d(self):
        r = self._post(self._url(), {
            'respondio': True,
            'tipo_respuesta': 'mas_adelante',
            'operador': 'deborah',
        })
        self.assertEqual(r.status_code, 200)
        self.cli.refresh_from_db()
        self.assertEqual(
            self.cli.proximo_contacto_no_antes_de,
            date.today() + timedelta(days=60),
        )

    def test_tipo_respuesta_invalido_400(self):
        r = self._post(self._url(), {
            'respondio': True,
            'tipo_respuesta': 'NOT_A_VALID_VALUE',
            'operador': 'deborah',
        })
        self.assertEqual(r.status_code, 400)

    def test_no_se_puede_registrar_si_no_enviado(self):
        self.contacto.estado = 'pendiente'
        self.contacto.save()
        r = self._post(self._url(), {
            'respondio': True, 'tipo_respuesta': 'interesado', 'operador': 'd',
        })
        self.assertEqual(r.status_code, 400)


# ============================================================================
# GET explicacion (stub)
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class ExplicacionTests(BandejaWhatsappEndpointsTestCase):
    def test_stub_devuelve_string_vacio(self):
        url = f'/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/explicacion/{self.contacto.id}/'
        r = self._get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['explicacion'], '')
        self.assertEqual(data['fuente'], 'stub')

    def test_404_si_no_existe(self):
        r = self._get('/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/explicacion/99999/')
        self.assertEqual(r.status_code, 404)


# ============================================================================
# GET resumen-dia
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class ResumenDiaTests(BandejaWhatsappEndpointsTestCase):
    URL = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/resumen-dia/'

    def test_resumen_dia_sin_actividad(self):
        r = self._get(self.URL)
        data = r.json()
        self.assertEqual(data['enviados'], 0)
        self.assertEqual(data['omitidos'], 0)

    def test_cuenta_enviados_omitidos_no_aplica(self):
        # 1 enviado, 1 omitido, 1 no_aplica adicionales hoy
        for estado in ['enviado', 'omitido', 'no_aplica']:
            cli = Cliente.objects.create(
                nombre=f'C{estado}', telefono=f'+5698700{hash(estado) % 1000:03d}',
            )
            ContactoWhatsApp.objects.create(
                cliente=cli, script=self.script,
                eje_valor_snapshot='Dormido', eje_estilo_snapshot='', eje_contexto_snapshot='',
                dias_sin_venir_snapshot=100, salva=1, mensaje_renderizado='x',
                fecha_sugerido=date.today(),
                fecha_envio=timezone.now() if estado == 'enviado' else None,
                estado=estado,
            )
        r = self._get(self.URL)
        data = r.json()
        self.assertEqual(data['enviados'], 1)
        self.assertEqual(data['omitidos'], 1)
        self.assertEqual(data['no_aplica'], 1)


# ============================================================================
# GET movimientos
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class MovimientosTests(BandejaWhatsappEndpointsTestCase):
    URL = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/movimientos/'

    def test_matriz_clasifica_positivos_y_negativos(self):
        # 1 positivo: Dormido → En Prueba
        TaxonomiaMovimiento.objects.create(
            cliente=self.cli, fecha=date.today(),
            eje_valor_antes='Dormido', eje_estilo_antes='',
            eje_contexto_antes='',
            eje_valor_despues='En Prueba', eje_estilo_despues='',
            eje_contexto_despues='',
            evento_origen='reserva',
        )
        # 1 negativo: Regular → En Riesgo
        cli2 = Cliente.objects.create(nombre='X', telefono='+56987654777')
        TaxonomiaMovimiento.objects.create(
            cliente=cli2, fecha=date.today(),
            eje_valor_antes='Regular', eje_estilo_antes='',
            eje_contexto_antes='',
            eje_valor_despues='En Riesgo', eje_estilo_despues='',
            eje_contexto_despues='',
            evento_origen='paso_tiempo',
        )

        r = self._get(self.URL)
        data = r.json()
        self.assertEqual(data['totales']['positivos'], 1)
        self.assertEqual(data['totales']['negativos'], 1)
        self.assertEqual(data['totales']['saldo_neto'], 0)
        self.assertEqual(len(data['matriz_eje_valor']), 2)

    def test_atribuidos_whatsapp_se_cuentan(self):
        TaxonomiaMovimiento.objects.create(
            cliente=self.cli, fecha=date.today(),
            eje_valor_antes='Dormido', eje_estilo_antes='',
            eje_contexto_antes='',
            eje_valor_despues='En Prueba', eje_estilo_despues='',
            eje_contexto_despues='',
            evento_origen='reserva',
            contacto_whatsapp_atribuido=self.contacto,
        )
        r = self._get(self.URL)
        self.assertEqual(r.json()['totales']['atribuidos_whatsapp'], 1)


# ============================================================================
# GET scripts-estadisticas
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class ScriptsEstadisticasTests(BandejaWhatsappEndpointsTestCase):
    URL = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/scripts-estadisticas/'

    def test_solo_incluye_scripts_con_envios_en_periodo(self):
        # script_2 sin uso → no debe aparecer
        ScriptWhatsApp.objects.create(
            script_id='TEST.UNUSED', nombre='Sin uso',
            estado_valor_target='Dormido', cohorte_estilo='',
            cohorte_contexto='', salva=1, plantilla_texto='x',
        )
        # Marcar el contacto como enviado para que TEST.1 aparezca
        self.contacto.estado = 'enviado'
        self.contacto.fecha_envio = timezone.now()
        self.contacto.save()

        r = self._get(self.URL)
        data = r.json()
        script_ids = [s['script_id'] for s in data['scripts']]
        self.assertIn('TEST.1', script_ids)
        self.assertNotIn('TEST.UNUSED', script_ids)

    def test_calcula_tasas_correctamente(self):
        # 2 enviados, 1 respondió, 0 reservó
        self.contacto.estado = 'enviado'
        self.contacto.fecha_envio = timezone.now()
        self.contacto.tipo_respuesta = 'interesado'
        self.contacto.save()

        cli2 = Cliente.objects.create(nombre='Otro', telefono='+56987654888')
        ContactoWhatsApp.objects.create(
            cliente=cli2, script=self.script,
            eje_valor_snapshot='Dormido', eje_estilo_snapshot='', eje_contexto_snapshot='',
            dias_sin_venir_snapshot=100, salva=1, mensaje_renderizado='x',
            fecha_sugerido=date.today(),
            fecha_envio=timezone.now(),
            estado='enviado', tipo_respuesta='',  # sin respuesta
        )

        r = self._get(self.URL)
        data = r.json()
        s = next(s for s in data['scripts'] if s['script_id'] == 'TEST.1')
        self.assertEqual(s['enviados'], 2)
        self.assertEqual(s['respondieron'], 1)
        self.assertEqual(s['tasa_respuesta'], 0.5)
        self.assertEqual(s['reservaron'], 0)
        self.assertEqual(s['tasa_conversion'], 0.0)


# ============================================================================
# Etapa 5.5.2 — POST bloquear-cliente/
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class BloquearClienteTests(BandejaWhatsappEndpointsTestCase):
    def _url(self, cid):
        return f'/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/{cid}/bloquear-cliente/'

    # ---- Auth ----
    def test_sin_token_401(self):
        r = self.client_http.post(
            self._url(self.contacto.id),
            data=json.dumps({'operador': 'jorge'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 401)

    def test_token_invalido_401(self):
        r = self.client_http.post(
            self._url(self.contacto.id),
            data=json.dumps({'operador': 'jorge'}),
            content_type='application/json',
            HTTP_X_API_KEY='token-falso',
        )
        self.assertEqual(r.status_code, 401)

    # ---- 404 ----
    def test_404_si_contacto_no_existe(self):
        r = self._post(self._url(99999), {'operador': 'jorge'})
        self.assertEqual(r.status_code, 404)

    # ---- Bloqueo efectivo ----
    def test_200_bloquea_cliente_opt_out(self):
        r = self._post(self._url(self.contacto.id), {
            'operador': 'jorge', 'razon': 'cliente proxy - staff',
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['cliente_bloqueado'])
        self.assertEqual(data['cliente_id'], self.cli.id)

        self.cli.refresh_from_db()
        self.assertTrue(self.cli.opt_out_whatsapp)

    def test_200_tambien_marca_contacto_como_no_aplica(self):
        # Contacto está pendiente en setUp
        self._post(self._url(self.contacto.id), {
            'operador': 'jorge', 'razon': 'proxy',
        })
        self.contacto.refresh_from_db()
        self.assertEqual(self.contacto.estado, 'no_aplica')
        self.assertEqual(self.contacto.nota_operador, 'proxy')
        self.assertEqual(self.contacto.operador, 'jorge')

    def test_contacto_no_pendiente_no_se_toca_pero_cliente_si_se_bloquea(self):
        # Contacto ya enviado: bloquear cliente pero NO modificar el contacto
        self.contacto.estado = 'enviado'
        self.contacto.fecha_envio = timezone.now()
        self.contacto.save()

        r = self._post(self._url(self.contacto.id), {'operador': 'jorge'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['cliente_bloqueado'])
        self.assertFalse(data['contacto_actualizado'])

        self.cli.refresh_from_db()
        self.contacto.refresh_from_db()
        self.assertTrue(self.cli.opt_out_whatsapp)
        self.assertEqual(self.contacto.estado, 'enviado')  # no cambió

    # ---- Razón vacía es válida ----
    def test_razon_vacia_funciona(self):
        r = self._post(self._url(self.contacto.id), {'operador': 'jorge'})
        self.assertEqual(r.status_code, 200)
        self.cli.refresh_from_db()
        self.assertTrue(self.cli.opt_out_whatsapp)

    # ---- Idempotencia ----
    def test_bloquear_dos_veces_no_crashea(self):
        # Primera vez: bloquea
        r1 = self._post(self._url(self.contacto.id), {'operador': 'jorge'})
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()['cliente_bloqueado'])

        # Segunda vez: ya estaba bloqueado, no es error
        r2 = self._post(self._url(self.contacto.id), {'operador': 'jorge'})
        self.assertEqual(r2.status_code, 200)
        # cliente_bloqueado=False porque ya estaba bloqueado de antes
        self.assertFalse(r2.json()['cliente_bloqueado'])

        self.cli.refresh_from_db()
        self.assertTrue(self.cli.opt_out_whatsapp)


# ============================================================================
# Etapa 5.6 — GET del-dia/ (historial del día)
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class DelDiaTests(BandejaWhatsappEndpointsTestCase):
    URL = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/del-dia/'

    def _crear_contacto(self, cliente=None, estado='pendiente', operador='',
                         fecha_envio=None, prioridad=5, gasto=100000,
                         fecha_sugerido=None):
        """Helper para crear ContactoWhatsApp con campos variables."""
        cliente = cliente or self.cli
        return ContactoWhatsApp.objects.create(
            cliente=cliente, script=self.script,
            eje_valor_snapshot='Dormido',
            eje_estilo_snapshot='', eje_contexto_snapshot='',
            dias_sin_venir_snapshot=200, salva=1,
            gasto_historico_snapshot=gasto,
            mensaje_renderizado='Hola test',
            fecha_sugerido=fecha_sugerido or date.today(),
            estado=estado, operador=operador,
            fecha_envio=fecha_envio, prioridad=prioridad,
        )

    # ---- Auth ----
    def test_sin_token_401(self):
        r = self.client_http.get(self.URL)
        self.assertEqual(r.status_code, 401)

    def test_token_invalido_401(self):
        r = self.client_http.get(self.URL, HTTP_X_API_KEY='invalido')
        self.assertEqual(r.status_code, 401)

    # ---- Default fecha = hoy ----
    def test_default_fecha_es_hoy(self):
        r = self._get(self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['fecha'], date.today().isoformat())

    def test_fecha_explicita_se_respeta(self):
        r = self._get(self.URL + '?fecha=2026-05-01')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['fecha'], '2026-05-01')

    def test_fecha_invalida_400(self):
        r = self._get(self.URL + '?fecha=NO-VALIDA')
        self.assertEqual(r.status_code, 400)

    # ---- Inclusión de contactos ----
    def test_sin_filtro_operador_incluye_pendientes(self):
        # setUp ya creó self.contacto en estado='pendiente'
        r = self._get(self.URL)
        data = r.json()
        ids = [c['id'] for c in data['contactos']]
        self.assertIn(self.contacto.id, ids)
        self.assertEqual(data['stats']['pendientes'], 1)

    def test_filtro_operador_NO_incluye_pendientes(self):
        # Pendiente del setUp + 1 enviado por jorge
        self.contacto2 = self._crear_contacto(
            estado='enviado', operador='jorge',
            fecha_envio=timezone.now(),
        )
        r = self._get(self.URL + '?operador=jorge')
        data = r.json()
        ids = [c['id'] for c in data['contactos']]
        # Solo el enviado de jorge, no el pendiente (no tiene operador)
        self.assertIn(self.contacto2.id, ids)
        self.assertNotIn(self.contacto.id, ids)
        self.assertEqual(data['operador_filtro'], 'jorge')

    def test_filtro_operador_excluye_otros_operadores(self):
        c_jorge = self._crear_contacto(
            estado='enviado', operador='jorge', fecha_envio=timezone.now(),
        )
        c_deborah = self._crear_contacto(
            estado='enviado', operador='deborah', fecha_envio=timezone.now(),
        )
        r = self._get(self.URL + '?operador=jorge')
        ids = [c['id'] for c in r.json()['contactos']]
        self.assertIn(c_jorge.id, ids)
        self.assertNotIn(c_deborah.id, ids)

    # ---- Orden ----
    def test_orden_procesados_primero_pendientes_despues(self):
        # Borrar el pendiente del setUp y crear: 2 enviados (en distintas horas) + 1 pendiente
        self.contacto.delete()
        ahora = timezone.now()
        c_pend = self._crear_contacto(estado='pendiente', prioridad=1)
        c_viejo = self._crear_contacto(
            estado='enviado', operador='x',
            fecha_envio=ahora - timedelta(hours=2),
        )
        c_reciente = self._crear_contacto(
            estado='enviado', operador='x',
            fecha_envio=ahora,
        )
        r = self._get(self.URL)
        ids = [c['id'] for c in r.json()['contactos']]
        # Reciente primero, después viejo, después pendiente
        self.assertEqual(ids, [c_reciente.id, c_viejo.id, c_pend.id])

    # ---- Stats ----
    def test_stats_cuenta_por_estado(self):
        # Borrar el pendiente del setUp
        self.contacto.delete()
        ahora = timezone.now()
        self._crear_contacto(estado='enviado', operador='x', fecha_envio=ahora)
        self._crear_contacto(estado='enviado', operador='x', fecha_envio=ahora)
        self._crear_contacto(estado='omitido', operador='x', fecha_envio=ahora)
        self._crear_contacto(estado='no_aplica', operador='x', fecha_envio=ahora)
        self._crear_contacto(estado='pendiente')

        r = self._get(self.URL)
        stats = r.json()['stats']
        self.assertEqual(stats['enviados'], 2)
        self.assertEqual(stats['omitidos'], 1)
        self.assertEqual(stats['no_aplica'], 1)
        self.assertEqual(stats['pendientes'], 1)
        self.assertEqual(r.json()['total'], 5)

    # ---- Limit ----
    def test_limit_default_100(self):
        # Default es 100, no validamos contenido, solo que la key venga
        r = self._get(self.URL)
        self.assertEqual(r.json()['limit_aplicado'], 100)

    def test_limit_explicito_se_respeta(self):
        r = self._get(self.URL + '?limit=50')
        self.assertEqual(r.json()['limit_aplicado'], 50)

    def test_limit_cap_max_500(self):
        r = self._get(self.URL + '?limit=9999')
        self.assertEqual(r.json()['limit_aplicado'], 500)

    def test_limit_minimo_1(self):
        r = self._get(self.URL + '?limit=0')
        self.assertEqual(r.json()['limit_aplicado'], 1)

    def test_limit_invalido_usa_default(self):
        r = self._get(self.URL + '?limit=abc')
        self.assertEqual(r.json()['limit_aplicado'], 100)

    # ---- cliente_opt_out_actual ----
    def test_cliente_opt_out_actual_refleja_estado_actual(self):
        # Inicialmente cliente NO bloqueado
        r = self._get(self.URL)
        c = next(c for c in r.json()['contactos'] if c['id'] == self.contacto.id)
        self.assertFalse(c['cliente_opt_out_actual'])

        # Bloqueamos cliente y volvemos a consultar
        self.cli.opt_out_whatsapp = True
        self.cli.save()
        r2 = self._get(self.URL)
        c2 = next(c for c in r2.json()['contactos'] if c['id'] == self.contacto.id)
        self.assertTrue(c2['cliente_opt_out_actual'])

    # ---- Campos extra del serializador historial ----
    def test_response_incluye_campos_de_respuesta(self):
        # Marcar el contacto como enviado + con respuesta
        self.contacto.estado = 'enviado'
        self.contacto.fecha_envio = timezone.now()
        self.contacto.operador = 'jorge'
        self.contacto.respondio = True
        self.contacto.tipo_respuesta = 'interesado'
        self.contacto.nota_operador = 'quiere viernes'
        self.contacto.mensaje_enviado_editado = 'edited text'
        self.contacto.save()

        r = self._get(self.URL)
        c = next(c for c in r.json()['contactos'] if c['id'] == self.contacto.id)
        self.assertEqual(c['operador'], 'jorge')
        self.assertEqual(c['respondio'], True)
        self.assertEqual(c['tipo_respuesta'], 'interesado')
        self.assertEqual(c['nota_operador'], 'quiere viernes')
        self.assertEqual(c['mensaje_enviado_editado'], 'edited text')
        self.assertIsNotNone(c['fecha_envio'])


# ============================================================================
# Commit puente Geo — campos region_geografica + ciudad_canonica en responses
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class CommitPuenteGeoTests(BandejaWhatsappEndpointsTestCase):
    """Verifica que los 3 endpoints exponen region_geografica + ciudad_canonica."""

    def test_siguiente_incluye_campos_geo_basico(self):
        # Sin ciudad_normalizada ni region asignada (default sin_clasificar)
        url = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/siguiente/'
        r = self._get(url)
        data = r.json()
        cliente_obj = data['contacto']['cliente']
        self.assertIn('region_geografica', cliente_obj)
        self.assertIn('ciudad_canonica', cliente_obj)
        # Default: sin clasificar, sin ciudad
        self.assertEqual(cliente_obj['region_geografica'], 'sin_clasificar')
        self.assertIsNone(cliente_obj['ciudad_canonica'])

    def test_siguiente_con_cliente_clasificado(self):
        # Crear Ciudad y asignarla
        from ventas.models import Ciudad
        c_pv = Ciudad.objects.create(
            nombre_canonico='Puerto Varas', aliases='puerto varas',
            region_geografica='sur',
        )
        self.cli.ciudad_normalizada = c_pv
        self.cli.region_geografica = 'sur'
        self.cli.save()

        url = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/siguiente/'
        r = self._get(url)
        cliente_obj = r.json()['contacto']['cliente']
        self.assertEqual(cliente_obj['region_geografica'], 'sur')
        self.assertEqual(cliente_obj['ciudad_canonica'], 'Puerto Varas')

    def test_del_dia_incluye_campos_geo(self):
        from ventas.models import Ciudad
        c_stgo = Ciudad.objects.create(
            nombre_canonico='Santiago', aliases='santiago',
            region_geografica='nacional',
        )
        self.cli.ciudad_normalizada = c_stgo
        self.cli.region_geografica = 'nacional'
        self.cli.save()

        url = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/del-dia/'
        r = self._get(url)
        c = r.json()['contactos'][0]
        self.assertEqual(c['cliente']['region_geografica'], 'nacional')
        self.assertEqual(c['cliente']['ciudad_canonica'], 'Santiago')

    def _placeholder_for_geo4_block(self):
        pass


# ============================================================================
# Etapa Geo.4 — POST clientes/<id>/actualizar-ubicacion/
# ============================================================================

@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class ActualizarUbicacionTests(BandejaWhatsappEndpointsTestCase):
    """Tests E2E del endpoint Geo.4 para captura inline de ubicación."""

    @classmethod
    def setUpTestData(cls):
        from ventas.models import Ciudad
        # Catálogo mínimo para los tests
        cls.c_pv = Ciudad.objects.create(
            nombre_canonico='Puerto Varas',
            aliases='puerto varas|pto varas|pto. varas|p. varas',
            region_geografica='sur',
        )
        cls.c_stgo = Ciudad.objects.create(
            nombre_canonico='Santiago',
            aliases='santiago|stgo',
            region_geografica='nacional',
        )
        cls.c_extra = Ciudad.objects.create(
            nombre_canonico='_otros_extranjero_',
            aliases='',
            region_geografica='extranjero',
        )

    def _url(self, cid):
        return f'/ventas/api/aremko-cli/operacion-vuelta-a-casa/clientes/{cid}/actualizar-ubicacion/'

    # ---- Auth ----
    def test_sin_token_401(self):
        r = self.client_http.post(
            self._url(self.cli.id),
            data=json.dumps({'ciudad': 'pto varas'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 401)

    def test_token_invalido_401(self):
        r = self.client_http.post(
            self._url(self.cli.id),
            data=json.dumps({'ciudad': 'pto varas'}),
            content_type='application/json',
            HTTP_X_API_KEY='invalido',
        )
        self.assertEqual(r.status_code, 401)

    # ---- Validaciones ----
    def test_404_cliente_no_existe(self):
        r = self._post(self._url(999999), {'ciudad': 'pto varas'})
        self.assertEqual(r.status_code, 404)

    def test_400_ciudad_vacia(self):
        r = self._post(self._url(self.cli.id), {'ciudad': ''})
        self.assertEqual(r.status_code, 400)

    def test_400_ciudad_un_solo_char(self):
        r = self._post(self._url(self.cli.id), {'ciudad': 'a'})
        self.assertEqual(r.status_code, 400)

    def test_400_body_no_json(self):
        r = self.client_http.post(
            self._url(self.cli.id),
            data='no es json',
            content_type='application/json',
            **self.auth_headers,
        )
        self.assertEqual(r.status_code, 400)

    def test_ciudad_solo_espacios_es_400(self):
        r = self._post(self._url(self.cli.id), {'ciudad': '   '})
        self.assertEqual(r.status_code, 400)

    # ---- Match canónico ----
    def test_match_canonico(self):
        r = self._post(self._url(self.cli.id), {
            'ciudad': 'Puerto Varas', 'operador': 'jorge',
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['ciudad_input'], 'Puerto Varas')
        self.assertEqual(data['ciudad_canonica'], 'Puerto Varas')
        self.assertEqual(data['region_geografica'], 'sur')
        self.assertEqual(data['match_method'], 'canonico')
        self.assertIsNone(data['match_score'])

        # Verifica persistencia
        self.cli.refresh_from_db()
        self.assertEqual(self.cli.ciudad, 'Puerto Varas')
        self.assertEqual(self.cli.ciudad_normalizada_id, self.c_pv.id)
        self.assertEqual(self.cli.region_geografica, 'sur')
        self.assertTrue(self.cli.ciudad_normalizada_manual)

    def test_match_canonico_case_insensitive(self):
        r = self._post(self._url(self.cli.id), {'ciudad': 'puerto varas'})
        data = r.json()
        self.assertEqual(data['match_method'], 'canonico')
        self.assertEqual(data['ciudad_canonica'], 'Puerto Varas')

    # ---- Match alias ----
    def test_match_alias_pto_varas(self):
        r = self._post(self._url(self.cli.id), {'ciudad': 'pto varas'})
        data = r.json()
        self.assertEqual(data['match_method'], 'alias')
        self.assertEqual(data['ciudad_canonica'], 'Puerto Varas')
        self.assertEqual(data['region_geografica'], 'sur')

    def test_match_alias_con_punto(self):
        r = self._post(self._url(self.cli.id), {'ciudad': 'pto. varas'})
        data = r.json()
        self.assertEqual(data['match_method'], 'alias')

    # ---- Extranjero por texto ----
    def test_match_extranjero_buenos_aires(self):
        r = self._post(self._url(self.cli.id), {'ciudad': 'Buenos Aires'})
        data = r.json()
        self.assertEqual(data['region_geografica'], 'extranjero')
        self.assertEqual(data['match_method'], 'extranjero_texto')

        self.cli.refresh_from_db()
        self.assertEqual(self.cli.region_geografica, 'extranjero')

    def test_match_extranjero_argentina_en_texto(self):
        r = self._post(self._url(self.cli.id), {'ciudad': 'Mendoza, Argentina'})
        data = r.json()
        self.assertEqual(data['region_geografica'], 'extranjero')

    # ---- No match ----
    def test_no_match_texto_random(self):
        r = self._post(self._url(self.cli.id), {
            'ciudad': 'asdkjhaskdjh', 'operador': 'jorge',
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['match_method'], 'no_match')
        self.assertEqual(data['region_geografica'], 'sin_clasificar')
        self.assertIsNone(data['ciudad_canonica'])

        # IMPORTANTE: el texto literal sí queda en Cliente.ciudad para revisión admin
        self.cli.refresh_from_db()
        self.assertEqual(self.cli.ciudad, 'asdkjhaskdjh')
        self.assertIsNone(self.cli.ciudad_normalizada)
        self.assertEqual(self.cli.region_geografica, 'sin_clasificar')
        # Flag manual SÍ se setea aunque sea no_match (operador hizo decisión)
        self.assertTrue(self.cli.ciudad_normalizada_manual)

    # ---- Flag manual ----
    def test_flag_manual_se_setea_en_match(self):
        r = self._post(self._url(self.cli.id), {'ciudad': 'Santiago'})
        self.cli.refresh_from_db()
        self.assertTrue(self.cli.ciudad_normalizada_manual)

    def test_sobrescribe_clasificacion_previa(self):
        # Cliente ya tenía sur asignado por el cron
        self.cli.ciudad_normalizada = self.c_pv
        self.cli.region_geografica = 'sur'
        self.cli.ciudad_normalizada_manual = False  # no manual aún
        self.cli.save()

        # Operador detecta que en realidad es de Santiago
        r = self._post(self._url(self.cli.id), {'ciudad': 'Santiago', 'operador': 'jorge'})
        self.assertEqual(r.status_code, 200)

        self.cli.refresh_from_db()
        self.assertEqual(self.cli.ciudad_normalizada_id, self.c_stgo.id)
        self.assertEqual(self.cli.region_geografica, 'nacional')
        self.assertTrue(self.cli.ciudad_normalizada_manual)

    def test_sobrescribe_aunque_ya_fuera_manual(self):
        # Cliente ya tenía manual=True, operador cambia de idea
        self.cli.ciudad_normalizada = self.c_pv
        self.cli.region_geografica = 'sur'
        self.cli.ciudad_normalizada_manual = True
        self.cli.save()

        r = self._post(self._url(self.cli.id), {'ciudad': 'Santiago'})
        self.cli.refresh_from_db()
        # Sobrescribió igual
        self.assertEqual(self.cli.ciudad_normalizada_id, self.c_stgo.id)
        self.assertEqual(self.cli.region_geografica, 'nacional')

    # ---- Bypass del Cliente.save() override ----
    def test_funciona_con_telefono_formato_no_estandar(self):
        """Garantiza que el endpoint NO falla por validación de teléfono.

        Cliente.save() override valida teléfono, pero usamos
        .filter().update() que va directo a SQL.
        """
        # Crear cliente con teléfono raro saltándonos la validación
        cli_usa = Cliente(
            nombre='USA Test', telefono='+19999999999',
            ciudad='', region_geografica='sin_clasificar',
        )
        # Bypass save() validation usando objects.bulk_create()
        Cliente.objects.bulk_create([cli_usa])
        cli_usa = Cliente.objects.get(nombre='USA Test')

        # Llamar al endpoint NO debe crashear con ValidationError de teléfono
        r = self._post(self._url(cli_usa.id), {'ciudad': 'Santiago'})
        self.assertEqual(r.status_code, 200)
        cli_usa.refresh_from_db()
        self.assertEqual(cli_usa.region_geografica, 'nacional')


@override_settings(AUTOMATION_API_KEY=TEST_API_KEY)
class CommitPuenteGeoTests2(BandejaWhatsappEndpointsTestCase):
    """(placeholder, real CommitPuenteGeoTests above remains active)"""

    def _placeholder(self):
        pass

    # Re-include only the test_marcar_enviado_siguiente_pre_resuelto_incluye_geo
    # below — moved out of CommitPuenteGeoTests for ordering reasons.

    def test_marcar_enviado_siguiente_pre_resuelto_incluye_geo(self):
        # Crear segundo contacto pendiente con ciudad asignada
        from ventas.models import Ciudad
        c_pv = Ciudad.objects.create(
            nombre_canonico='Puerto Varas', aliases='puerto varas',
            region_geografica='sur',
        )
        cli2 = Cliente.objects.create(
            nombre='Otro', telefono='+56987650200',
            ciudad_normalizada=c_pv, region_geografica='sur',
        )
        ContactoWhatsApp.objects.create(
            cliente=cli2, script=self.script,
            eje_valor_snapshot='Dormido', eje_estilo_snapshot='',
            eje_contexto_snapshot='',
            dias_sin_venir_snapshot=100, salva=1, mensaje_renderizado='x',
            prioridad=3, fecha_sugerido=date.today(), estado='pendiente',
        )
        # Marcar el primero como enviado
        url = f'/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/{self.contacto.id}/marcar-enviado/'
        r = self._post(url, {'operador': 'test'})
        data = r.json()
        siguiente = data['siguiente']
        self.assertEqual(siguiente['tipo'], 'nuevo_contacto')
        # El siguiente cliente (con ciudad asignada) trae los campos geo
        self.assertEqual(siguiente['contacto']['cliente']['region_geografica'], 'sur')
        self.assertEqual(siguiente['contacto']['cliente']['ciudad_canonica'], 'Puerto Varas')
