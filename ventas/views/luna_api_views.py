"""
API Views para Luna (Agente AI de WhatsApp)

Este módulo proporciona endpoints REST para que Luna pueda:
- Validar disponibilidad de servicios
- Crear reservas completas
- Consultar regiones y comunas

Autor: Claude Code
Fecha: 2026-03-31
"""

from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
from django.db import transaction
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from ventas.models import (
    Servicio, Cliente, VentaReserva, ReservaServicio,
    ServicioBloqueo, ServicioSlotBloqueo, Region, Comuna
)
from ventas.services.cliente_service import ClienteService
from ventas.services.pack_descuento_service import PackDescuentoService


logger = logging.getLogger(__name__)


# ============================================================================
# AUTENTICACIÓN
# ============================================================================

class LunaAPIKeyAuthentication(BaseAuthentication):
    """
    Autenticación personalizada para Luna API usando API Key en header.

    Header esperado: X-Luna-API-Key
    """

    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_LUNA_API_KEY')

        if not api_key:
            raise AuthenticationFailed('API Key no proporcionada. Use header X-Luna-API-Key.')

        expected_key = getattr(settings, 'LUNA_API_KEY', None)

        if not expected_key:
            logger.error('LUNA_API_KEY no configurada en settings')
            raise AuthenticationFailed('API Key no configurada en el servidor.')

        if api_key != expected_key:
            logger.warning(f'Intento de acceso con API Key inválida: {api_key[:10]}...')
            raise AuthenticationFailed('API Key inválida.')

        # Autenticación exitosa - retornar None como user (Luna no es un usuario Django)
        return (None, None)


# ============================================================================
# ENDPOINT DE PRUEBA
# ============================================================================

@api_view(['GET'])
@authentication_classes([LunaAPIKeyAuthentication])
def test_connection(request):
    """
    Endpoint de prueba para verificar que la autenticación funciona.

    GET /api/luna/test

    Respuesta:
    {
        "success": true,
        "message": "Autenticación exitosa",
        "timestamp": "2026-03-31T10:30:00Z"
    }
    """
    return Response({
        'success': True,
        'message': 'Autenticación exitosa. Luna API funcionando correctamente.',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0'
    })


# ============================================================================
# LISTAR REGIONES Y COMUNAS
# ============================================================================

@api_view(['GET'])
@authentication_classes([LunaAPIKeyAuthentication])
def listar_regiones(request):
    """
    Lista todas las regiones de Chile con sus comunas.

    GET /api/luna/regiones

    Respuesta:
    {
        "success": true,
        "regiones": [
            {
                "id": 1,
                "nombre": "Región de Los Lagos",
                "comunas": [
                    {"id": 10, "nombre": "Puerto Varas"},
                    {"id": 11, "nombre": "Puerto Montt"}
                ]
            }
        ]
    }
    """
    try:
        regiones = Region.objects.all().order_by('nombre')

        regiones_data = []
        for region in regiones:
            comunas = region.comunas.all().order_by('nombre')

            regiones_data.append({
                'id': region.id,
                'nombre': region.nombre,
                'comunas': [
                    {'id': c.id, 'nombre': c.nombre}
                    for c in comunas
                ]
            })

        return Response({
            'success': True,
            'regiones': regiones_data
        })

    except Exception as e:
        logger.error(f'Error listando regiones: {str(e)}')
        return Response({
            'success': False,
            'error': 'internal_error',
            'mensaje': 'Error al obtener regiones'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# VALIDAR DISPONIBILIDAD (Pre-validación)
# ============================================================================

@api_view(['POST'])
@authentication_classes([LunaAPIKeyAuthentication])
def validar_disponibilidad(request):
    """
    Valida disponibilidad de servicios sin crear la reserva.

    POST /api/luna/reservas/validar

    Body:
    {
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2026-04-01",
                "hora": "14:30",
                "cantidad_personas": 2
            }
        ]
    }

    Respuesta:
    {
        "success": true,
        "disponibilidad": [
            {
                "servicio_id": 12,
                "servicio_nombre": "Tina Calbuco",
                "disponible": true,
                "capacidad_disponible": 8,
                "precio_unitario": 25000,
                "precio_estimado": 50000
            }
        ],
        "total_estimado": 50000,
        "descuentos_aplicables": [],
        "total_con_descuentos": 50000
    }
    """
    servicios_data = request.data.get('servicios', [])

    if not servicios_data:
        return Response({
            'success': False,
            'error': 'validation_error',
            'mensaje': 'Debe incluir al menos un servicio'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Por ahora, endpoint básico que responde OK
    # TODO: Implementar validación completa en Fase 2

    return Response({
        'success': True,
        'disponibilidad': [],
        'mensaje': 'Endpoint en desarrollo - Fase 2'
    })


# ============================================================================
# CREAR RESERVA (Endpoint principal)
# ============================================================================

@api_view(['POST'])
@authentication_classes([LunaAPIKeyAuthentication])
def crear_reserva(request):
    """
    Crea una reserva completa desde Luna.

    POST /api/luna/reservas/create

    Body:
    {
        "idempotency_key": "unique-id-from-luna",
        "cliente": {
            "nombre": "Juan Pérez",
            "email": "juan@example.com",
            "telefono": "+56912345678",
            "documento_identidad": "12345678-9",
            "region_id": 1,
            "comuna_id": 10
        },
        "servicios": [
            {
                "servicio_id": 12,
                "fecha": "2026-04-01",
                "hora": "14:30",
                "cantidad_personas": 2
            }
        ],
        "metodo_pago": "pendiente",
        "notas": "Cliente contactado via WhatsApp"
    }

    Respuesta:
    {
        "success": true,
        "reserva": {
            "id": 1234,
            "numero": "RES-2026-1234",
            "cliente": {...},
            "servicios": [...],
            "total": 50000,
            "estado_pago": "pendiente",
            "url_detalle": "https://aremko.cl/reserva/1234/",
            "instrucciones_pago": "..."
        }
    }
    """

    # Por ahora, endpoint básico que responde OK
    # TODO: Implementar creación completa en Fase 3

    logger.info(f'[Luna API] Solicitud de creación de reserva recibida')

    return Response({
        'success': True,
        'mensaje': 'Endpoint en desarrollo - Fase 3',
        'nota': 'La autenticación funciona correctamente'
    })


# ============================================================================
# HEALTH CHECK
# ============================================================================

@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint (sin autenticación) para monitoreo.

    GET /api/luna/health
    """
    return Response({
        'status': 'healthy',
        'service': 'luna-api',
        'timestamp': timezone.now().isoformat()
    })
