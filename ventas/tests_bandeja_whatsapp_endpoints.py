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
