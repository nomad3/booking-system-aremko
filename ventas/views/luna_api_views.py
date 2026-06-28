"""
API Views para Luna (Agente AI de WhatsApp)

Este módulo proporciona endpoints REST para que Luna pueda:
- Validar disponibilidad de servicios
- Crear reservas completas
- Consultar regiones, comunas y clientes
- Obtener resumen de reservas

Rutas: GET/POST /api/luna/* (auth: X-API-Key)

Autor: Claude Code
Fecha: 2026-03-31, actualizado 2026-06-18 (H-028)
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
    ServicioBloqueo, ServicioSlotBloqueo, Region, Comuna,
    Producto, ReservaProducto, Comanda, DetalleComanda
)
from whatsapp_agent.models import PropuestaReserva
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

    # Tolerar RUT sin guión (ej. "76048924" o "76048924K", como suele pasarlo el LLM):
    # insertar el guión antes del dígito verificador.
    if '-' not in rut_limpio and re.match(r'^\d{7,8}[0-9K]$', rut_limpio):
        rut_limpio = rut_limpio[:-1] + '-' + rut_limpio[-1]

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

    # RUT: validar según contexto (se pasa cliente_es_nuevo en contexto externo)
    # Por ahora: si viene, debe ser válido. Obligatoriedad se valida en crear_reserva()
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

    Header esperado: X-API-Key (estandarizado con otros endpoints)
    """

    def authenticate(self, request):
        # request.headers es case-insensitive; respaldo vía META
        api_key = request.headers.get('X-API-Key') or request.META.get('HTTP_X_API_KEY')

        if not api_key:
            raise AuthenticationFailed('API Key no proporcionada. Use header X-API-Key.')

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

        # Calcular descuentos. Carrito vía construir_cart (masajes por persona) para que el motor
        # detecte el pack tina+masaje (cuenta masajes por ítem, exige >=2).
        cart_items = PackDescuentoService.construir_cart(disponibilidad_items)

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
    Crea una reserva completa desde Luna (H-028: soporta propuesta_id o payload directo).

    POST /api/luna/reservas/create/
    Header: X-API-Key

    Flujo 1 — CON PROPUESTA (aprobación de Deborah):
    Body: { "propuesta_id": "uuid-string" }
    - Consume payload guardado en PropuestaReserva
    - Re-verifica disponibilidad
    - Marcar propuesta como estado='creada' + guardar reserva_id
    - Idempotente: si propuesta ya está creada, devuelve reserva existente

    Flujo 2 — PAYLOAD DIRECTO (backward compat, Luna sin propuesta):
    Body: {
        "idempotency_key": "unique-id-from-luna",  # opcional
        "cliente": {...},
        "servicios": [...],
        "metodo_pago": "pendiente"  # opcional
    }

    Respuesta:
    {
        "success": true,
        "reserva": {
            "id": 1234,
            "numero": "RES-1234",
            "total": 180000,
            "estado_pago": "pendiente"
        }
    }

    Para obtener el resumen completo con datos de pago:
    GET /api/v1/resumen-reserva/{id}/ → resumen_texto
    """
    try:
        from whatsapp_agent.models import PropuestaReserva
        from whatsapp_agent.reserva_service import obtener_propuesta

        # Detectar flujo: propuesta_id o payload directo
        propuesta_id = request.data.get('propuesta_id', '').strip()

        if propuesta_id:
            # Flujo 1: CON PROPUESTA
            propuesta = obtener_propuesta(propuesta_id)
            if not propuesta:
                return Response({
                    'success': False,
                    'error': 'propuesta_not_found',
                    'mensaje': f'Propuesta {propuesta_id[:8]}... no existe o expiró'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Si propuesta ya fue creada, devolver la reserva existente (idempotencia)
            if propuesta.estado == 'creada' and propuesta.reserva_id:
                try:
                    reserva_existente = VentaReserva.objects.get(id=propuesta.reserva_id)
                    return Response({
                        'success': True,
                        'reserva': {
                            'id': reserva_existente.id,
                            'numero': f'RES-{reserva_existente.id}',
                            'total': int(reserva_existente.total),
                            'estado_pago': reserva_existente.estado_pago,
                            'duplicada': True
                        },
                        'mensaje': f'Reserva ya fue creada desde propuesta {propuesta_id[:8]}'
                    })
                except VentaReserva.DoesNotExist:
                    pass  # Propuesta dice creada pero reserva desapareció → proceder a crear

            # Extraer datos del payload guardado en la propuesta
            payload = propuesta.payload or {}
            cliente_data = payload.get('cliente', {})
            servicios_data = payload.get('servicios', [])
            productos_data = payload.get('productos', [])  # tablas, jugos, etc.
            metodo_pago = payload.get('metodo_pago', 'pendiente')
            notas = f'[Propuesta {propuesta_id[:8]}] Aprobada por Deborah'
            idempotency_key = propuesta.idempotency_key or f'propuesta_{propuesta_id}'
        else:
            # Flujo 2: PAYLOAD DIRECTO
            idempotency_key = request.data.get('idempotency_key')
            cliente_data = request.data.get('cliente', {})
            servicios_data = request.data.get('servicios', [])
            productos_data = request.data.get('productos', [])
            metodo_pago = request.data.get('metodo_pago', 'pendiente')
            notas = request.data.get('notas', '')

        # Validar campos requeridos
        if not idempotency_key:
            return Response({
                'success': False,
                'error': 'validation_error',
                'mensaje': 'idempotency_key es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not cliente_data:
            return Response({
                'success': False,
                'error': 'validation_error',
                'mensaje': 'Datos de cliente son requeridos'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not servicios_data:
            return Response({
                'success': False,
                'error': 'validation_error',
                'mensaje': 'Debe incluir al menos un servicio'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Verificar idempotencia (evitar duplicados)
        cache_key = f'luna_reserva_{idempotency_key}'
        cached_reserva = cache.get(cache_key)

        if cached_reserva:
            logger.info(f'[Luna API] Reserva duplicada detectada: {idempotency_key}')
            return Response({
                'success': True,
                'reserva': cached_reserva,
                'duplicada': True,
                'mensaje': 'Reserva ya fue creada previamente'
            })

        # Validar datos del cliente
        es_valido, errores = validar_datos_cliente(cliente_data)
        if not es_valido:
            return Response({
                'success': False,
                'error': 'validation_error',
                'errores': errores,
                'mensaje': 'Datos de cliente inválidos'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validar disponibilidad de servicios (reutilizar lógica de validar_disponibilidad)
        # Crear request interno para validación
        validacion_response = validar_disponibilidad_interna(servicios_data)

        if not validacion_response['success']:
            return Response({
                'success': False,
                'error': 'availability_error',
                'errores': validacion_response.get('errores', []),
                'mensaje': 'Uno o más servicios no están disponibles'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Iniciar transacción atómica
        with transaction.atomic():
            # 1. Buscar o crear cliente
            telefono_normalizado = validar_telefono_chileno(cliente_data.get('telefono', ''))[2]

            cliente, created = Cliente.objects.get_or_create(
                telefono=telefono_normalizado,
                defaults={
                    'nombre': cliente_data.get('nombre', ''),
                    'email': cliente_data.get('email', ''),
                    'documento_identidad': cliente_data.get('documento_identidad', ''),
                    'region_id': cliente_data.get('region_id'),
                    'comuna_id': cliente_data.get('comuna_id'),
                }
            )

            # Para cliente NUEVO, RUT es obligatorio (H-028)
            if created:
                rut = cliente_data.get('documento_identidad', '').strip()
                if not rut:
                    return Response({
                        'success': False,
                        'error': 'validation_error',
                        'mensaje': 'RUT es requerido para cliente nuevo',
                        'errores': [{'campo': 'documento_identidad', 'mensaje': 'RUT es obligatorio'}]
                    }, status=status.HTTP_400_BAD_REQUEST)
                # Si viene, ya fue validado en validar_datos_cliente()
                cliente.documento_identidad = rut
                cliente.save()

            # Actualizar datos si el cliente ya existía
            if not created:
                cliente.nombre = cliente_data.get('nombre', cliente.nombre)
                cliente.email = cliente_data.get('email', cliente.email) or cliente.email
                if cliente_data.get('documento_identidad'):
                    cliente.documento_identidad = cliente_data.get('documento_identidad')
                if cliente_data.get('region_id'):
                    cliente.region_id = cliente_data.get('region_id')
                if cliente_data.get('comuna_id'):
                    cliente.comuna_id = cliente_data.get('comuna_id')
                cliente.save()

            logger.info(f'[Luna API] Cliente {"creado" if created else "actualizado"}: {cliente.nombre} ({cliente.telefono})')

            # 2. Crear VentaReserva
            venta_reserva = VentaReserva.objects.create(
                cliente=cliente,
                estado_pago=metodo_pago,
                comentarios=f"[Luna WhatsApp] {notas}" if notas else "[Luna WhatsApp]",
                total=0  # Se calculará después
            )

            logger.info(f'[Luna API] VentaReserva creada: ID {venta_reserva.id}')

            # 3. Crear ReservaServicio para cada servicio
            servicios_creados = []
            total_estimado = 0

            for servicio_data in servicios_data:
                servicio = Servicio.objects.get(id=servicio_data['servicio_id'])

                fecha = datetime.strptime(servicio_data['fecha'], '%Y-%m-%d').date()
                hora = servicio_data['hora']
                cantidad_personas = servicio_data['cantidad_personas']

                # Calcular precio
                if servicio.tipo_servicio == 'cabana':
                    precio_unitario = servicio.precio_base
                else:
                    precio_unitario = servicio.precio_base

                reserva_servicio = ReservaServicio.objects.create(
                    venta_reserva=venta_reserva,
                    servicio=servicio,
                    fecha_agendamiento=fecha,
                    hora_inicio=hora,
                    cantidad_personas=cantidad_personas,
                    precio_unitario_venta=precio_unitario
                )

                # Calcular subtotal
                subtotal = reserva_servicio.calcular_precio()
                total_estimado += subtotal

                servicios_creados.append({
                    'id': reserva_servicio.id,
                    'servicio_id': servicio.id,
                    'servicio_nombre': servicio.nombre,
                    'fecha': servicio_data['fecha'],
                    'hora': hora,
                    'cantidad_personas': cantidad_personas,
                    'precio_unitario': float(precio_unitario),
                    'subtotal': float(subtotal)
                })

            # 3b. Productos (tablas, jugos, etc.): NO se descuenta inventario al crear.
            # Se crea una Comanda con fecha_entrega_objetivo = fecha del PRIMER servicio, y
            # ReservaProducto SIN fecha_entrega (NULL). El inventario se descuenta recién en
            # esa fecha vía comanda.entregar_inventario() (cron `procesar_entregas_comandas_vencidas`
            # o entrega manual). Así una reserva de hoy para dentro de 30 días descuenta en 30 días.
            if productos_data:
                # Fecha objetivo = primer servicio (por fecha, luego hora).
                serv_orden = sorted(
                    servicios_data, key=lambda s: (s['fecha'], s.get('hora') or '00:00'))
                primero = serv_orden[0]
                try:
                    naive_obj = datetime.strptime(
                        f"{primero['fecha']} {primero.get('hora') or '12:00'}", '%Y-%m-%d %H:%M')
                except (ValueError, KeyError):
                    naive_obj = datetime.strptime(f"{primero['fecha']} 12:00", '%Y-%m-%d %H:%M')
                fecha_entrega_objetivo = timezone.make_aware(naive_obj)

                comanda = Comanda.objects.create(
                    venta_reserva=venta_reserva,
                    estado='pendiente',
                    creada_por_cliente=True,
                    fecha_entrega_objetivo=fecha_entrega_objetivo,
                    notas_generales='[Luna WhatsApp] Productos agregados en la reserva',
                )
                for prod_data in productos_data:
                    try:
                        producto = Producto.objects.get(id=prod_data['producto_id'])
                    except Producto.DoesNotExist:
                        continue  # un producto inexistente no debe tumbar la reserva
                    cant = int(prod_data.get('cantidad', 1) or 1)
                    # Línea de cocina (comanda) + línea de facturación (ReservaProducto sin fecha).
                    DetalleComanda.objects.create(
                        comanda=comanda, producto=producto, cantidad=cant,
                        precio_unitario=producto.precio_base)
                    ReservaProducto.objects.create(
                        venta_reserva=venta_reserva, producto=producto, cantidad=cant,
                        precio_unitario_venta=producto.precio_base)  # fecha_entrega = NULL
                    # precio_base es Decimal y total_estimado es Decimal: NO mezclar con float.
                    total_estimado += producto.precio_base * cant

            # 4. Aplicar descuentos. Fuente ÚNICA: PackDescuentoService.descuento_para_servicios,
            # que arma el carrito como espera el motor (masajes divididos por persona). Antes este
            # camino armaba 1 masaje × N personas y el motor (que cuenta masajes por ÍTEM, exige >=2)
            # NO detectaba el pack tina+masaje → la reserva se creaba a precio completo.
            # PERO si los servicios YA traen una línea "Descuento de servicios" (precio negativo,
            # como el Ritual/Refugio o el pack del carrito), NO se vuelve a restar: la línea ya
            # descuenta y es DURABLE (calcular_total la suma; restar acá daría doble descuento, y
            # un total seteado a mano lo borra cualquier signal que recalcule).
            ya_tiene_linea_descuento = any(
                'descuento' in (s.get('servicio_nombre') or '').lower() for s in servicios_creados)
            total_descuentos = 0 if ya_tiene_linea_descuento else \
                PackDescuentoService.descuento_para_servicios(servicios_data)

            # 5. Actualizar total de VentaReserva
            venta_reserva.total = total_estimado - total_descuentos
            venta_reserva.saldo_pendiente = venta_reserva.total - venta_reserva.pagado
            venta_reserva.save()

            logger.info(f'[Luna API] Reserva completada: Total ${venta_reserva.total} (descuentos: ${total_descuentos})')

            # 6. Si vino propuesta_id, marcar como creada + guardar reserva_id (H-028)
            if propuesta_id:
                try:
                    propuesta = PropuestaReserva.objects.get(propuesta_id=propuesta_id)
                    propuesta.estado = 'creada'
                    propuesta.reserva_id = venta_reserva.id
                    propuesta.creada_at = timezone.now()
                    propuesta.save(update_fields=['estado', 'reserva_id', 'creada_at'])
                    logger.info(f'[Luna API] Propuesta {propuesta_id[:8]} marcada como creada (reserva {venta_reserva.id})')
                    # Vaciar el carrito de esa conversación: ya se convirtió en reserva. Si no, el
                    # carrito queda "zombie" (marcar_como_creado no se llama en ningún lado) y
                    # reaparece en la próxima conversación del mismo cliente / en el estado inyectado.
                    try:
                        from carrito_reservas.services import CarritoService
                        CarritoService.vaciar_carrito(propuesta.canal, propuesta.external_id)
                    except Exception:  # noqa: BLE001 — no romper la creación por limpiar el carrito
                        logger.exception('[Luna API] no se pudo vaciar el carrito tras crear la reserva')
                except PropuestaReserva.DoesNotExist:
                    pass  # propuesta_id fue validado antes, no debería pasar

            # 7. Preparar respuesta minimalista (H-028: fuente de verdad = /api/v1/resumen-reserva/{id}/)
            reserva_data = {
                'id': venta_reserva.id,
                'numero': f'RES-{venta_reserva.id}',
                'total': int(venta_reserva.total),
                'estado_pago': venta_reserva.estado_pago,
                # Luna consulta GET /api/v1/resumen-reserva/{id}/ para el texto completo con datos de pago
            }

            # Guardar en cache por 24 horas (idempotencia)
            cache.set(cache_key, reserva_data, 60 * 60 * 24)

            return Response({
                'success': True,
                'reserva': reserva_data,
                'mensaje': f'Reserva creada exitosamente: {venta_reserva.id}. Consulta GET /api/v1/resumen-reserva/{venta_reserva.id}/ para el resumen completo.'
            }, status=status.HTTP_201_CREATED)

    except Servicio.DoesNotExist as e:
        logger.error(f'[Luna API] Servicio no encontrado: {str(e)}')
        return Response({
            'success': False,
            'error': 'service_not_found',
            'mensaje': 'Uno o más servicios no existen'
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f'[Luna API] Error creando reserva: {str(e)}', exc_info=True)
        return Response({
            'success': False,
            'error': 'internal_error',
            'mensaje': 'Error interno al crear reserva'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([LunaAPIKeyAuthentication])
def agregar_servicios_reserva(request, reserva_id):
    """
    Agrega servicios adicionales a una reserva existente.

    POST /api/luna/reservas/{reserva_id}/servicios/

    Body:
    {
        "servicios": [
            {
                "servicio_id": 9,
                "fecha": "2026-04-30",
                "hora": "16:00",
                "cantidad_personas": 2
            }
        ]
    }

    Respuesta:
    {
        "success": true,
        "reserva_id": 5434,
        "numero": "RES-5434",
        "servicios_agregados": [...],
        "nuevo_total": 150000.0,
        "saldo_pendiente": 150000.0
    }
    """
    try:
        # Buscar la reserva existente
        try:
            venta_reserva = VentaReserva.objects.get(id=reserva_id)
        except VentaReserva.DoesNotExist:
            return Response({
                'success': False,
                'error': 'reserva_not_found',
                'mensaje': f'Reserva con ID {reserva_id} no existe'
            }, status=status.HTTP_404_NOT_FOUND)

        servicios_data = request.data.get('servicios', [])

        if not servicios_data:
            return Response({
                'success': False,
                'error': 'validation_error',
                'mensaje': 'Debe incluir al menos un servicio'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validar disponibilidad de los nuevos servicios
        validacion_response = validar_disponibilidad_interna(servicios_data)

        if not validacion_response['success']:
            return Response({
                'success': False,
                'error': 'availability_error',
                'errores': validacion_response.get('errores', []),
                'mensaje': 'Uno o más servicios no están disponibles'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Iniciar transacción atómica
        with transaction.atomic():
            servicios_agregados = []
            total_nuevos_servicios = 0

            # Crear ReservaServicio para cada servicio nuevo
            for servicio_data in servicios_data:
                servicio = Servicio.objects.get(id=servicio_data['servicio_id'])

                fecha = datetime.strptime(servicio_data['fecha'], '%Y-%m-%d').date()
                hora = servicio_data['hora']
                cantidad_personas = servicio_data['cantidad_personas']

                # Calcular precio
                if servicio.tipo_servicio == 'cabana':
                    precio_unitario = servicio.precio_base
                else:
                    precio_unitario = servicio.precio_base

                reserva_servicio = ReservaServicio.objects.create(
                    venta_reserva=venta_reserva,
                    servicio=servicio,
                    fecha_agendamiento=fecha,
                    hora_inicio=hora,
                    cantidad_personas=cantidad_personas,
                    precio_unitario_venta=precio_unitario
                )

                # Calcular subtotal
                subtotal = reserva_servicio.calcular_precio()
                total_nuevos_servicios += subtotal

                servicios_agregados.append({
                    'id': reserva_servicio.id,
                    'servicio_id': servicio.id,
                    'servicio_nombre': servicio.nombre,
                    'fecha': servicio_data['fecha'],
                    'hora': hora,
                    'cantidad_personas': cantidad_personas,
                    'precio_unitario': float(precio_unitario),
                    'subtotal': float(subtotal)
                })

            # Recalcular descuentos con TODOS los servicios (antiguos + nuevos)
            todos_servicios = []
            for rs in venta_reserva.reservaservicios.all():
                todos_servicios.append({
                    'id': rs.servicio.id,
                    'nombre': rs.servicio.nombre,
                    'precio': float(rs.servicio.precio_base),
                    'fecha': rs.fecha_agendamiento.strftime('%Y-%m-%d'),
                    'hora': rs.hora_inicio,
                    'cantidad_personas': rs.cantidad_personas,
                    'tipo_servicio': rs.servicio.tipo_servicio,
                    'subtotal': float(rs.calcular_precio())
                })

            # Calcular nuevo total con descuentos. El descuento se detecta con el carrito armado
            # por construir_cart (masajes por persona); el subtotal usa los precios congelados.
            packs_aplicables = PackDescuentoService.detectar_packs_aplicables(
                PackDescuentoService.construir_cart(todos_servicios))
            total_descuentos = sum(pack_info['descuento'] for pack_info in packs_aplicables)

            # Calcular subtotal de todos los servicios
            subtotal_total = sum(item['subtotal'] for item in todos_servicios)

            # Actualizar total de VentaReserva
            venta_reserva.total = subtotal_total - total_descuentos
            venta_reserva.saldo_pendiente = venta_reserva.total - venta_reserva.pagado
            venta_reserva.save()

            logger.info(f'[Luna API] Servicios agregados a reserva {reserva_id}: {len(servicios_agregados)} servicio(s)')

            # Preparar respuesta
            return Response({
                'success': True,
                'reserva_id': venta_reserva.id,
                'numero': f'RES-{venta_reserva.id}',
                'servicios_agregados': servicios_agregados,
                'descuentos_aplicados': [
                    {
                        'pack_nombre': pack_info['pack'].nombre,
                        'descuento': float(pack_info['descuento'])
                    }
                    for pack_info in packs_aplicables
                ],
                'total_descuentos': float(total_descuentos),
                'nuevo_total': float(venta_reserva.total),
                'saldo_pendiente': float(venta_reserva.saldo_pendiente),
                'mensaje': f'{len(servicios_agregados)} servicio(s) agregado(s) exitosamente'
            }, status=status.HTTP_200_OK)

    except Servicio.DoesNotExist as e:
        logger.error(f'[Luna API] Servicio no encontrado: {str(e)}')
        return Response({
            'success': False,
            'error': 'service_not_found',
            'mensaje': 'Uno o más servicios no existen'
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f'[Luna API] Error agregando servicios: {str(e)}', exc_info=True)
        return Response({
            'success': False,
            'error': 'internal_error',
            'mensaje': 'Error interno al agregar servicios'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def validar_disponibilidad_interna(servicios_data):
    """
    Función auxiliar para validar disponibilidad sin HTTP request.
    Reutiliza la lógica de validar_disponibilidad.
    """
    try:
        disponibilidad_items = []
        errores_validacion = []

        for idx, servicio_data in enumerate(servicios_data):
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

            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'invalid_date',
                    'mensaje': f'Fecha {fecha_str} inválida'
                })
                continue

            if fecha < timezone.now().date():
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'past_date',
                    'mensaje': f'No se puede reservar en fecha pasada'
                })
                continue

            if cantidad_personas < servicio.capacidad_minima or cantidad_personas > servicio.capacidad_maxima:
                errores_validacion.append({
                    'servicio_index': idx,
                    'servicio_id': servicio_id,
                    'error': 'capacity_error',
                    'mensaje': f'Capacidad debe estar entre {servicio.capacidad_minima} y {servicio.capacidad_maxima}'
                })
                continue

        if errores_validacion:
            return {
                'success': False,
                'errores': errores_validacion
            }

        return {
            'success': True,
            'disponibilidad': disponibilidad_items
        }

    except Exception as e:
        logger.error(f'Error en validación interna: {str(e)}')
        return {
            'success': False,
            'errores': [{'error': 'internal_error', 'mensaje': str(e)}]
        }


# ============================================================================
# LOOKUP CLIENTE (H-028)
# ============================================================================

@api_view(['GET'])
@authentication_classes([LunaAPIKeyAuthentication])
def lookup_cliente(request):
    """
    Busca cliente por teléfono y devuelve datos + campos faltantes (H-028).

    GET /api/luna/cliente/?telefono=+56912345678
    Header: X-API-Key

    Respuesta:
    {
        "existe": true,
        "cliente_id": 123,
        "nombre": "Juan Pérez",
        "email": "juan@example.com",
        "documento_identidad": "12345678-9",
        "region": "Los Lagos",
        "faltan": []  # campos vacíos que Luna debería pedir
    }

    Si no existe:
    {
        "existe": false,
        "faltan": ["nombre", "email", "documento_identidad", "region"]
    }
    """
    try:
        telefono = request.query_params.get('telefono', '').strip()
        if not telefono:
            return Response({
                'error': 'validation_error',
                'mensaje': 'Parámetro telefono es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Normalizar teléfono
        es_valido, mensaje, telefono_normalizado = validar_telefono_chileno(telefono)
        if not es_valido:
            return Response({
                'error': 'validation_error',
                'mensaje': f'Teléfono inválido: {mensaje}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Buscar cliente
        try:
            cliente = Cliente.objects.get(telefono=telefono_normalizado)
            # Cliente existe: devolver datos + campos faltantes
            faltan = []
            if not cliente.nombre or len(cliente.nombre.strip()) < 3:
                faltan.append('nombre')
            if not cliente.email:
                faltan.append('email')
            if not cliente.documento_identidad:
                faltan.append('documento_identidad')
            if not cliente.region_id:
                faltan.append('region')

            return Response({
                'existe': True,
                'cliente_id': cliente.id,
                'nombre': cliente.nombre,
                'email': cliente.email,
                'documento_identidad': cliente.documento_identidad,
                'region': cliente.region.nombre if cliente.region else None,
                'comuna': cliente.comuna.nombre if cliente.comuna else None,
                'faltan': faltan
            })
        except Cliente.DoesNotExist:
            # Cliente no existe: devolver lista de campos requeridos para nuevo
            return Response({
                'existe': False,
                'faltan': ['nombre', 'email', 'documento_identidad', 'region']
            })

    except Exception as e:
        logger.error(f'[Luna API] Error en lookup_cliente: {str(e)}', exc_info=True)
        return Response({
            'error': 'internal_error',
            'mensaje': 'Error al buscar cliente'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# PREPARAR RESERVA (H-028: Gate de Deborah)
# ============================================================================

@api_view(['POST'])
@authentication_classes([LunaAPIKeyAuthentication])
def preparar_reserva_endpoint(request):
    """
    Prepara una propuesta de reserva pendiente de aprobación de Deborah (H-028).

    POST /api/luna/reservas/preparar/
    Header: X-API-Key

    Body:
    {
        "idempotency_key": "luna-msg-uuid",  # opcional, para idempotencia
        "canal": "whatsapp",
        "external_id": "+56912345678",  # teléfono normalizado
        "payload": {
            "cliente": {
                "nombre": "Juan Pérez",
                "email": "juan@example.com",
                "documento_identidad": "12345678-9",
                "region_id": 1,
                "comuna_id": 10
            },
            "servicios": [
                {
                    "servicio_id": 12,
                    "fecha": "2026-06-20",
                    "hora": "14:00",
                    "cantidad_personas": 2
                }
            ],
            "metodo_pago": "pendiente"
        }
    }

    Respuesta exitosa:
    {
        "success": true,
        "propuesta_id": "uuid-string",
        "resumen_texto": "2x Tina Hidromasaje (20-06-2026 14:00) = $180,000",
        "total": 180000,
        "cliente": "Juan Pérez",
        "servicios_count": 1
    }

    Si es idempotente (Luna reenvía la misma propuesta):
    {
        "success": true,
        "propuesta_id": "uuid-string",  # mismo que antes
        "resumen_texto": "...",
        "total": 180000,
        "duplicada": true
    }
    """
    try:
        from whatsapp_agent.reserva_service import preparar_reserva as servicio_preparar_reserva

        idempotency_key = request.data.get('idempotency_key', '').strip()
        canal = request.data.get('canal', 'whatsapp').strip()
        external_id = request.data.get('external_id', '').strip()
        payload = request.data.get('payload', {})

        # Validar datos requeridos
        if not external_id:
            return Response({
                'success': False,
                'error': 'validation_error',
                'mensaje': 'external_id requerido (teléfono normalizado)'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not payload:
            return Response({
                'success': False,
                'error': 'validation_error',
                'mensaje': 'payload requerido'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Llamar servicio
        resultado = servicio_preparar_reserva(
            canal=canal,
            external_id=external_id,
            payload=payload,
            idempotency_key=idempotency_key if idempotency_key else None
        )

        if resultado['success']:
            return Response(resultado, status=status.HTTP_201_CREATED)
        else:
            return Response(resultado, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f'[Luna API] Error en preparar_reserva_endpoint: {str(e)}', exc_info=True)
        return Response({
            'success': False,
            'error': 'internal_error',
            'mensaje': 'Error al preparar reserva'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# ADMIN: LIMPIAR CONVERSACIÓN
# ============================================================================

@api_view(['POST'])
@authentication_classes([LunaAPIKeyAuthentication])
def limpiar_conversacion_endpoint(request):
    """
    Limpia el historial de una conversación (testing/debug).

    POST /api/luna/admin/limpiar-conversacion
    Header: X-API-Key
    Body: {
        "phone": "+56958655810",  # default
        "force": false
    }

    Returns: {success, mensaje, borrados}
    """
    try:
        phone = (request.data.get('phone') or '+56958655810').strip()
        force = request.data.get('force', False)

        from ventas.models import WhatsAppMessage
        from carrito_reservas.models import CarritoReserva
        from whatsapp_agent.models import PropuestaReserva

        msg_count = WhatsAppMessage.objects.filter(phone=phone).count()
        carrito_count = CarritoReserva.objects.filter(
            canal='whatsapp',
            external_id=phone
        ).count()
        # PropuestaReserva alimenta el banner "Crear reserva"; si no se borra, el banner
        # (incluso uno con error) persiste tras limpiar la conversación.
        propuesta_count = PropuestaReserva.objects.filter(
            canal='whatsapp',
            external_id=phone
        ).count()

        if msg_count == 0 and carrito_count == 0 and propuesta_count == 0:
            return Response({
                'success': False,
                'error': 'nada_para_borrar',
                'mensaje': f'No hay conversación para {phone}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Borrar
        WhatsAppMessage.objects.filter(phone=phone).delete()
        CarritoReserva.objects.filter(canal='whatsapp', external_id=phone).delete()
        PropuestaReserva.objects.filter(canal='whatsapp', external_id=phone).delete()

        logger.info(f'[Admin] Limpiada conversación {phone}: {msg_count} msgs + '
                    f'{carrito_count} carritos + {propuesta_count} propuestas')

        return Response({
            'success': True,
            'mensaje': f'Conversación {phone} limpia',
            'borrados': {
                'mensajes': msg_count,
                'carritos': carrito_count,
                'propuestas': propuesta_count
            }
        })

    except Exception as e:
        logger.error(f'[Luna API] Error en limpiar_conversacion: {str(e)}', exc_info=True)
        return Response({
            'success': False,
            'error': 'internal_error',
            'mensaje': f'Error: {str(e)[:100]}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
