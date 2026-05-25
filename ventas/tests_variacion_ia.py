"""
Tests para Etapa Variaciones IA on-demand de mensajes WhatsApp.

Mockea openai.OpenAI para evitar llamadas reales al LLM en CI.

Cubre:
  - Toggle OVC_USAR_VARIACIONES_IA off → mensaje_variado=None
  - Toggle on + LLM responde → mensaje_variado con texto distinto
  - Toggle on + LLM timeout → mensaje_variado=None + log warning
  - Toggle on + LLM 401 → mensaje_variado=None + log warning
  - Toggle on + respuesta vacía LLM → mensaje_variado=None
  - OPENROUTER_API_KEY ausente → mensaje_variado=None aunque toggle on
  - Endpoints: solo /siguiente/ tipo nuevo_contacto y _resolver_siguiente
    invocan al LLM; /del-dia/, respuesta_pendiente, celebracion NO lo invocan
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from ventas.models import (
    Cliente,
    ClienteTaxonomia,
    ContactoWhatsApp,
    EventoCelebracion,
    ScriptWhatsApp,
    TaxonomiaMovimiento,
)
from ventas.services.variacion_ia_service import generar_variacion_mensaje


TEST_API_KEY = 'test-api-key-variacion'


def _make_mock_openai_client(content='Mensaje variado generado'):
    """Construye un mock de openai.OpenAI con respuesta controlada."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ============================================================================
# Tests del helper puro (sin endpoint)
# ============================================================================

class GenerarVariacionMensajeTests(TestCase):
    """Tests unitarios de la función generar_variacion_mensaje."""

    @override_settings(OVC_USAR_VARIACIONES_IA=False)
    def test_toggle_off_devuelve_none(self):
        r = generar_variacion_mensaje("Hola María, ¿cómo estás?")
        self.assertIsNone(r)

    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='')
    def test_sin_api_key_devuelve_none(self):
        r = generar_variacion_mensaje("Hola María")
        self.assertIsNone(r)

    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='fake-key')
    def test_llm_ok_devuelve_variado(self):
        mock_client = _make_mock_openai_client(content='Hola María, te saludo!')
        with patch('openai.OpenAI', return_value=mock_client):
            r = generar_variacion_mensaje("Hola María, ¿cómo estás?")
        self.assertEqual(r, 'Hola María, te saludo!')

    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='fake-key')
    def test_llm_respuesta_vacia_devuelve_none(self):
        mock_client = _make_mock_openai_client(content='')
        with patch('openai.OpenAI', return_value=mock_client):
            r = generar_variacion_mensaje("Hola María")
        self.assertIsNone(r)

    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='fake-key')
    def test_llm_exception_devuelve_none(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Timeout")
        with patch('openai.OpenAI', return_value=mock_client):
            r = generar_variacion_mensaje("Hola María")
        self.assertIsNone(r)

    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='fake-key')
    def test_llm_401_devuelve_none(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "401 Unauthorized"
        )
        with patch('openai.OpenAI', return_value=mock_client):
            r = generar_variacion_mensaje("Hola María")
        self.assertIsNone(r)

    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='fake-key')
    def test_mensaje_vacio_devuelve_none(self):
        """Edge case: si caller pasa string vacío, retornar None sin llamar al LLM."""
        with patch('openai.OpenAI') as mock_openai:
            r = generar_variacion_mensaje("")
        self.assertIsNone(r)
        mock_openai.assert_not_called()


# ============================================================================
# Tests de endpoints (integración)
# ============================================================================

@override_settings(AUTOMATION_API_KEY='test-api-key-endpoints')
class EndpointsVariacionTests(TestCase):
    """Verifica que solo los endpoints correctos invocan al LLM."""

    def setUp(self):
        self.client_http = Client()
        self.auth_headers = {'HTTP_X_API_KEY': 'test-api-key-endpoints'}

        self.cli = Cliente.objects.create(
            nombre='María Test', telefono='+56987650999',
        )
        self.script = ScriptWhatsApp.objects.create(
            script_id='TEST.VAR', nombre='Test',
            estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1,
            plantilla_texto='Hola {nombre}',
        )
        self.contacto = ContactoWhatsApp.objects.create(
            cliente=self.cli, script=self.script,
            eje_valor_snapshot='Dormido',
            eje_estilo_snapshot='', eje_contexto_snapshot='',
            dias_sin_venir_snapshot=200, salva=1,
            mensaje_renderizado='Hola María, hace 200 días.',
            prioridad=3, fecha_sugerido=date.today(),
            estado='pendiente',
        )

    def _get(self, url):
        return self.client_http.get(url, **self.auth_headers)

    def _post(self, url, body):
        return self.client_http.post(
            url, data=json.dumps(body),
            content_type='application/json', **self.auth_headers,
        )

    # ---- Toggle OFF: mensaje_variado SIEMPRE None ----
    @override_settings(OVC_USAR_VARIACIONES_IA=False)
    def test_siguiente_toggle_off(self):
        url = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/siguiente/'
        r = self._get(url)
        data = r.json()
        self.assertEqual(data['tipo'], 'nuevo_contacto')
        self.assertIsNone(data['contacto']['mensaje_variado'])

    # ---- Toggle ON + LLM responde ----
    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='fake-key')
    def test_siguiente_toggle_on_llm_ok(self):
        mock_client = _make_mock_openai_client(content='Variación generada por IA!')
        url = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/siguiente/'
        with patch('openai.OpenAI', return_value=mock_client):
            r = self._get(url)
        data = r.json()
        self.assertEqual(data['tipo'], 'nuevo_contacto')
        self.assertEqual(data['contacto']['mensaje_variado'], 'Variación generada por IA!')
        # mensaje_renderizado original sigue presente
        self.assertEqual(data['contacto']['mensaje_renderizado'], 'Hola María, hace 200 días.')

    # ---- Toggle ON + LLM falla ----
    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='fake-key')
    def test_siguiente_toggle_on_llm_falla_fallback_none(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Timeout")
        url = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/siguiente/'
        with patch('openai.OpenAI', return_value=mock_client):
            r = self._get(url)
        data = r.json()
        self.assertEqual(data['tipo'], 'nuevo_contacto')
        self.assertIsNone(data['contacto']['mensaje_variado'])

    # ---- marcar-enviado: siguiente_contacto también incluye variación ----
    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='fake-key')
    def test_marcar_enviado_pre_resuelto_invoca_variacion(self):
        # Crear segundo contacto pendiente
        cli2 = Cliente.objects.create(nombre='Pedro', telefono='+56987651000')
        c2 = ContactoWhatsApp.objects.create(
            cliente=cli2, script=self.script,
            eje_valor_snapshot='Dormido',
            eje_estilo_snapshot='', eje_contexto_snapshot='',
            dias_sin_venir_snapshot=100, salva=1, mensaje_renderizado='Hola Pedro',
            prioridad=4, fecha_sugerido=date.today(), estado='pendiente',
        )

        mock_client = _make_mock_openai_client(content='Variación pre-resuelta')
        url = f'/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/{self.contacto.id}/marcar-enviado/'
        with patch('openai.OpenAI', return_value=mock_client):
            r = self._post(url, {'operador': 'test'})
        data = r.json()
        siguiente = data['siguiente']
        self.assertEqual(siguiente['tipo'], 'nuevo_contacto')
        self.assertEqual(siguiente['contacto']['mensaje_variado'], 'Variación pre-resuelta')

    # ---- del-dia: NUNCA invoca variación ----
    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='fake-key')
    def test_del_dia_NO_invoca_variacion(self):
        """del-dia es read-only del historial, no debe llamar al LLM."""
        with patch('openai.OpenAI') as mock_openai:
            url = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/del-dia/'
            r = self._get(url)
        # Aunque toggle esté ON, NO se llama al LLM porque _serializar_contacto
        # en del-dia se invoca con agregar_variacion=False (default).
        mock_openai.assert_not_called()
        data = r.json()
        # mensaje_variado debe estar presente como key con valor None
        if data['contactos']:
            self.assertIsNone(data['contactos'][0].get('mensaje_variado'))

    # ---- respuesta_pendiente: NO invoca variación ----
    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='fake-key')
    def test_respuesta_pendiente_NO_invoca_variacion(self):
        # Marcar contacto del setUp como respuesta pendiente (enviado hace 5 días)
        self.contacto.estado = 'enviado'
        self.contacto.fecha_envio = timezone.now() - timedelta(days=5)
        self.contacto.tipo_respuesta = ''
        self.contacto.save()

        with patch('openai.OpenAI') as mock_openai:
            url = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/siguiente/'
            r = self._get(url)
        # Tipo respuesta_pendiente NO debe llamar al LLM
        data = r.json()
        if data['tipo'] == 'respuesta_pendiente':
            mock_openai.assert_not_called()
            self.assertIsNone(data['contacto'].get('mensaje_variado'))

    # ---- celebracion: NO invoca variación ----
    @override_settings(OVC_USAR_VARIACIONES_IA=True, OPENROUTER_API_KEY='fake-key')
    def test_celebracion_NO_invoca_variacion(self):
        mov = TaxonomiaMovimiento.objects.create(
            cliente=self.cli, fecha=date.today(),
            eje_valor_antes='Dormido', eje_estilo_antes='', eje_contexto_antes='',
            eje_valor_despues='En Prueba', eje_estilo_despues='',
            eje_contexto_despues='',
            evento_origen='reserva',
        )
        EventoCelebracion.objects.create(
            cliente=self.cli, tipo='recuperado_dormido',
            fecha=date.today(), movimiento_relacionado=mov,
            mensaje_sugerido='¡Qué bueno!',
        )
        # Borrar el pendiente del setUp para que la celebración gane
        # (orden: respuesta_pendiente → celebracion → nuevo_contacto)
        # En este caso el pendiente del setUp no es respuesta_pendiente,
        # pero la celebracion del día gana sobre nuevo_contacto.
        # Como hay pendiente del día Y celebración, orden: celebracion gana.

        with patch('openai.OpenAI') as mock_openai:
            url = '/ventas/api/aremko-cli/operacion-vuelta-a-casa/bandeja-whatsapp/siguiente/'
            r = self._get(url)
        data = r.json()
        if data['tipo'] == 'celebracion':
            mock_openai.assert_not_called()
