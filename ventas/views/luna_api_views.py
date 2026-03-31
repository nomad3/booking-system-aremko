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
from django.db.models import Sum
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
# FUNCIONES AUXILIARES
# ============================================================================

def validar_email(email: str) -> tuple:
    """
    Valida formato de email.

    Returns:
        (es_valido: bool, mensaje_error: str)
    """
    if not email:
        return False, "Email es requerido"

    import re
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(email_regex, email):
        return False, "Email tiene formato inválido"

    return True, ""


def validar_telefono_chileno(telefono: str) -> tuple:
    """
    Valida teléfono chileno. Acepta:
    - +56912345678
    - 56912345678
    - 912345678

    Returns:
        (es_valido: bool, mensaje_error: str, telefono_normalizado: str)
    """
    if not telefono:
        return False, "Teléfono es requerido", ""

    import re
    # Remover espacios, guiones, paréntesis
    telefono_limpio = re.sub(r'[\s\-\(\)]', '', telefono)

    # Si empieza con +56, remover el +
    if telefono_limpio.startswith('+56'):
        telefono_limpio = telefono_limpio[3:]

    # Si empieza con 56, remover el 56
    if telefono_limpio.startswith('56') and len(telefono_limpio) == 11:
        telefono_limpio = telefono_limpio[2:]

    # Debe quedar 9XXXXXXXX (9 dígitos empezando con 9)
    if not re.match(r'^9\d{8}$', telefono_limpio):
        return False, "Teléfono debe ser formato chileno (9XXXXXXXX)", ""

    # Normalizar con +56
    telefono_normalizado = f"+56{telefono_limpio}"

    return True, "", telefono_normalizado


def validar_rut_chileno(rut: str) -> tuple:
    """
    Valida RUT chileno con dígito verificador.
    Acepta formatos: 12345678-9, 12.345.678-9, 12345678-K

    Returns:
        (es_valido: bool, mensaje_error: str, rut_normalizado: str)
    """
    if not rut:
        return False, "RUT es requerido", ""

    import re
    # Remover puntos y espacios
    rut_limpio = re.sub(r'[.\s]', '', rut).upper()

    # Debe tener formato 12345678-9 o 12345678-K
    if not re.match(r'^\d{7,8}-[0-9K]$', rut_limpio):
        return False, "RUT debe tener formato 12345678-9", ""

    # Separar número y dígito verificador
    partes = rut_limpio.split('-')
    numero = partes[0]
    dv = partes[1]

    # Calcular dígito verificador
    suma = 0
    multiplicador = 2

    for digito in reversed(numero):
        suma += int(digito) * multiplicador
        multiplicador += 1
        if multiplicador > 7:
            multiplicador = 2

    resto = suma % 11
    dv_calculado = 11 - resto

    if dv_calculado == 11:
        dv_esperado = '0'
    elif dv_calculado == 10:
        dv_esperado = 'K'
    else:
        dv_esperado = str(dv_calculado)

    if dv != dv_esperado:
        return False, f"RUT inválido. Dígito verificador incorrecto", ""

    return True, "", rut_limpio


def validar_datos_cliente(cliente_data: dict) -> tuple:
    """
    Valida todos los datos del cliente.

    Returns:
        (es_valido: bool, errores: list)
    """
    errores = []

    # Validar nombre
    nombre = cliente_data.get('nombre', '').strip()
    if not nombre or len(nombre) < 3:
        errores.append({
            'campo': 'nombre',
            'mensaje': 'Nombre debe tener al menos 3 caracteres'
        })

    # Validar email
    email = cliente_data.get('email', '').strip()
    es_valido, mensaje = validar_email(email)
    if not es_valido:
        errores.append({
            'campo': 'email',
            'mensaje': mensaje
        })

    # Validar teléfono
    telefono = cliente_data.get('telefono', '').strip()
    es_valido, mensaje, telefono_norm = validar_telefono_chileno(telefono)
    if not es_valido:
        errores.append({
            'campo': 'telefono',
            'mensaje': mensaje
        })

    # Validar RUT (opcional pero si viene debe ser válido)
    rut = cliente_data.get('documento_identidad', '').strip()
    if rut:
        es_valido, mensaje, rut_norm = validar_rut_chileno(rut)
        if not es_valido:
            errores.append({
                'campo': 'documento_identidad',
                'mensaje': mensaje
            })

    # Validar región
    region_id = cliente_data.get('region_id')
    if region_id:
        try:
            region = Region.objects.get(id=region_id)
        except Region.DoesNotExist:
            errores.append({
                'campo': 'region_id',
                'mensaje': f'Región con ID {region_id} no existe'
            })

    # Validar comuna
    comuna_id = cliente_data.get('comuna_id')
    if comuna_id:
        try:
            comuna = Comuna.objects.get(id=comuna_id)
            # Verificar que la comuna pertenece a la región
            if region_id and comuna.region_id != region_id:
                errores.append({
                    'campo': 'comuna_id',
                    'mensaje': f'Comuna no pertenece a la región seleccionada'
                })
        except Comuna.DoesNotExist:
            errores.append({
                'campo': 'comuna_id',
                'mensaje': f'Comuna con ID {comuna_id} no existe'
            })

    return len(errores) == 0, errores


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

    try:
        disponibilidad_items = []
        total_estimado = 0
        errores_validacion = []

        for idx, servicio_data in enumerate(servicios_data):
            # Validar campos requeridos
            servicio_id = servicio_data.get('servicio_id')
            fecha_str = servicio_data.get('fecha')
            hora_str = servicio_data.get('hora')
            cantidad_personas = servicio_data.get('cantidad_personas', 1)

            if not all([servicio_id, fecha_str, hora_str]):
                errores_validacion.append({
                    'servicio_index': idx,
                    'error': 'missing_fields',
                    'mensaje': 'servicio_id, fecha y hora son requeridos'
                })
                continue

            # Validar que el servicio existe y está activo
            try:
                servicio = Servicio.objects.get(id=servicio_id, activo=True)
            except Servicio.DoesNotExist:
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'service_not_found',
                    'mensaje': f'Servicio con ID {servicio_id} no existe o no está activo'
                })
                continue

            # Validar formato de fecha
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'invalid_date',
                    'mensaje': f'Fecha {fecha_str} inválida. Use formato YYYY-MM-DD'
                })
                continue

            # Validar que la fecha no sea pasada
            if fecha < timezone.now().date():
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'past_date',
                    'mensaje': f'No se puede reservar en fecha pasada: {fecha_str}'
                })
                continue

            # Validar formato de hora
            try:
                hora = datetime.strptime(hora_str, '%H:%M').time()
            except ValueError:
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'invalid_time',
                    'mensaje': f'Hora {hora_str} inválida. Use formato HH:MM'
                })
                continue

            # Validar capacidad
            if cantidad_personas < servicio.capacidad_minima:
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'below_min_capacity',
                    'mensaje': f'{servicio.nombre} requiere mínimo {servicio.capacidad_minima} personas'
                })
                continue

            if cantidad_personas > servicio.capacidad_maxima:
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'above_max_capacity',
                    'mensaje': f'{servicio.nombre} permite máximo {servicio.capacidad_maxima} personas'
                })
                continue

            # Verificar bloqueos del servicio
            bloqueos = ServicioBloqueo.objects.filter(
                servicio=servicio,
                fecha_inicio__lte=fecha,
                fecha_fin__gte=fecha
            )
            if bloqueos.exists():
                bloqueo = bloqueos.first()
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'service_blocked',
                    'mensaje': f'{servicio.nombre} no disponible: {bloqueo.motivo}'
                })
                continue

            # Verificar bloqueos de slot específico
            bloqueos_slot = ServicioSlotBloqueo.objects.filter(
                servicio=servicio,
                fecha=fecha,
                hora_slot=hora_str
            )
            if bloqueos_slot.exists():
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'slot_blocked',
                    'mensaje': f'{servicio.nombre} no disponible en ese horario'
                })
                continue

            # Calcular capacidad ocupada en ese slot
            reservas_existentes = ReservaServicio.objects.filter(
                servicio=servicio,
                fecha_agendamiento=fecha,
                hora_inicio=hora_str,
                venta_reserva__estado_pago__in=['pendiente', 'pagado', 'parcial']
            )

            # Calcular cuántas veces se ha reservado el servicio en ese slot
            slots_ocupados = reservas_existentes.count()
            capacidad_disponible_slots = servicio.max_servicios_simultaneos - slots_ocupados

            if capacidad_disponible_slots <= 0:
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'no_availability',
                    'mensaje': f'{servicio.nombre} no tiene disponibilidad en ese horario'
                })
                continue

            # Calcular personas ocupadas (para tinas/servicios con capacidad compartida)
            personas_ocupadas = reservas_existentes.aggregate(
                total=Sum('cantidad_personas')
            )['total'] or 0

            capacidad_personas_disponible = (servicio.capacidad_maxima * servicio.max_servicios_simultaneos) - personas_ocupadas

            if cantidad_personas > capacidad_personas_disponible:
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'insufficient_capacity',
                    'mensaje': f'{servicio.nombre} solo tiene capacidad para {capacidad_personas_disponible} personas en ese horario'
                })
                continue

            # Calcular precio
            if servicio.tipo_servicio == 'cabana':
                precio_estimado = servicio.precio_base  # Precio fijo para cabañas
            else:
                precio_estimado = servicio.precio_base * cantidad_personas

            total_estimado += precio_estimado

            # Agregar a disponibilidad
            disponibilidad_items.append({
                'servicio_id': servicio.id,
                'servicio_nombre': servicio.nombre,
                'servicio_tipo': servicio.tipo_servicio,
                'disponible': True,
                'fecha': fecha_str,
                'hora': hora_str,
                'cantidad_personas': cantidad_personas,
                'capacidad_disponible': int(capacidad_personas_disponible),
                'precio_unitario': float(servicio.precio_base),
                'precio_estimado': float(precio_estimado)
            })

        # Si hubo errores de validación, retornarlos
        if errores_validacion:
            return Response({
                'success': False,
                'error': 'validation_errors',
                'errores': errores_validacion,
                'mensaje': f'{len(errores_validacion)} servicio(s) con errores de validación'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Calcular descuentos aplicables usando PackDescuentoService
        cart_items = []
        for item in disponibilidad_items:
            cart_items.append({
                'id': item['servicio_id'],
                'nombre': item['servicio_nombre'],
                'precio': item['precio_estimado'],
                'fecha': item['fecha'],
                'hora': item['hora'],
                'cantidad_personas': item['cantidad_personas'],
                'tipo_servicio': item['servicio_tipo'],
                'subtotal': item['precio_estimado']
            })

        # Calcular descuentos
        packs_aplicables = []
        total_descuentos = 0

        if cart_items:
            packs_info = PackDescuentoService.detectar_packs_aplicables(cart_items)

            for pack_info in packs_info:
                packs_aplicables.append({
                    'pack_nombre': pack_info['pack'].nombre,
                    'descuento': float(pack_info['descuento']),
                    'descripcion': pack_info['descripcion_aplicacion']
                })
                total_descuentos += float(pack_info['descuento'])

        total_con_descuentos = total_estimado - total_descuentos

        return Response({
            'success': True,
            'disponibilidad': disponibilidad_items,
            'total_estimado': float(total_estimado),
            'descuentos_aplicables': packs_aplicables,
            'total_descuentos': float(total_descuentos),
            'total_con_descuentos': float(total_con_descuentos),
            'mensaje': f'{len(disponibilidad_items)} servicio(s) disponible(s)'
        })

    except Exception as e:
        logger.error(f'[Luna API] Error validando disponibilidad: {str(e)}', exc_info=True)
        return Response({
            'success': False,
            'error': 'internal_error',
            'mensaje': 'Error interno al validar disponibilidad'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
