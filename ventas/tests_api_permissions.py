"""
Regresión de seguridad (2026-07-22): los ViewSets DRF de datos sensibles
(pagos, clientes, reservas, productos, proveedores, categorías) NO deben ser
accesibles sin autenticación.

Contexto: heredaban el default global DEFAULT_PERMISSION_CLASSES=[AllowAny] y
quedaban públicos con lectura Y escritura/borrado. Confirmado en prod:
/ventas/api/pagos/ devolvía 932 KB sin token; /ventas/api/clientes/ exponía
RUT/email/teléfono. Se cerraron a IsAuthenticated (ver ventas/views/api_views.py).

Este test es barato y no toca la BD: el chequeo de permiso de DRF ocurre en
initial(), ANTES de get_queryset(), así que un GET anónimo devuelve 403 sin
consultar ninguna tabla — por eso es inmune al drift AR-034 del snapshot local
y no necesita crear fixtures.

Ejecutar:
    python manage.py test ventas.tests_api_permissions
"""
from __future__ import annotations

from django.test import Client, TestCase


class ApiViewSetsRequierenAutenticacionTest(TestCase):
    # Endpoints registrados en el router (ventas/urls.py) que exponen datos de
    # negocio o PII. NO incluye regiones/comunas: esos son públicos a propósito
    # (los usa el checkout) y de solo lectura.
    ENDPOINTS_SENSIBLES = [
        '/ventas/api/pagos/',
        '/ventas/api/clientes/',
        '/ventas/api/ventasreservas/',
        '/ventas/api/productos/',
        '/ventas/api/proveedores/',
        '/ventas/api/categorias/',
    ]

    # Métodos de escritura que un anónimo tampoco debe poder ejecutar.
    METODOS_ESCRITURA = ('post', 'put', 'patch', 'delete')

    def setUp(self):
        self.anon = Client()

    def test_get_anonimo_es_rechazado(self):
        """Sin credenciales, cada endpoint sensible responde 401/403 — nunca 200."""
        for url in self.ENDPOINTS_SENSIBLES:
            with self.subTest(url=url, metodo='GET'):
                resp = self.anon.get(url)
                self.assertIn(
                    resp.status_code, (401, 403),
                    f'{url} GET anónimo devolvió {resp.status_code}; se esperaba 401/403',
                )

    def test_escritura_anonima_es_rechazada(self):
        """Sin credenciales, POST/PUT/PATCH/DELETE se rechazan (no crean/borran datos)."""
        for url in self.ENDPOINTS_SENSIBLES:
            for metodo in self.METODOS_ESCRITURA:
                with self.subTest(url=url, metodo=metodo.upper()):
                    resp = getattr(self.anon, metodo)(url, data={}, content_type='application/json')
                    self.assertIn(
                        resp.status_code, (401, 403),
                        f'{url} {metodo.upper()} anónimo devolvió {resp.status_code}; se esperaba 401/403',
                    )
