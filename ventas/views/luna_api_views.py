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
from whatsapp_agent.prompt import nombre_presentable
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
    Valida y normaliza un teléfono para Luna. Acepta:
    - Chileno: +56912345678 / 56912345678 / 912345678
    - Internacional (turista extranjero): con + y código de país, ej. Brasil
      +5511987654321, Argentina +5491112345678.

    2026-07-22: delega en PhoneService.normalize_phone (fuente única, la misma
    que usa el admin y el resto del sistema) en vez de una lógica chilena-only
    duplicada — antes un turista extranjero era rechazado en el flujo de Luna.
    (El nombre se mantiene por compatibilidad con los 3 llamadores.)

    Returns:
        (es_valido: bool, mensaje_error: str, telefono_normalizado: str)
    """
    if not telefono:
        return False, "Teléfono es requerido", ""

    from ..services.phone_service import PhoneService
    telefono_normalizado = PhoneService.normalize_phone(telefono)
    if not telefono_normalizado:
        return False, (
            "Teléfono inválido. Usa formato chileno (9XXXXXXXX) o, para un "
            "número extranjero, inclúyelo con el + y el código de país "
            "(ej. Brasil: +55 11 98765-4321)."
        ), ""

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

            # Calcular precio: precio_base × personas para TODOS los tipos,
            # incluidas cabañas (precio_base de cabaña es POR PERSONA; son para 2).
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

            # H-060: propuesta de ADICIÓN a una reserva YA EXISTENTE — camino
            # completamente distinto (no valida cliente_data/servicios "de reserva
            # nueva", no crea una VentaReserva nueva). Se resuelve antes de seguir con
            # el flujo de reserva nueva de abajo.
            if propuesta.reserva_existente_id:
                return _aprobar_adicion_a_reserva_existente(propuesta_id, propuesta)

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
            # 0. Guard de CONCURRENCIA (doble click en el botón "Aprobar" del link al cliente):
            # bloqueamos la fila de la propuesta y re-chequeamos BAJO LOCK. El check de arriba
            # (línea ~683) es check-then-act y no resiste dos requests casi simultáneas: ambas
            # lo pasan antes de que la primera marque estado='creada' → se crean 2 reservas
            # (caso 6169/6170). Con el lock, la 2ª request espera a que la 1ª haga commit y,
            # al ver estado='creada', devuelve la reserva existente en vez de duplicar.
            if propuesta_id:
                propuesta = PropuestaReserva.objects.select_for_update().get(propuesta_id=propuesta_id)
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
                                'duplicada': True,
                            },
                            'mensaje': f'Reserva ya fue creada desde propuesta {propuesta_id[:8]}',
                        })
                    except VentaReserva.DoesNotExist:
                        pass  # propuesta dice creada pero la reserva no está → proceder a crear

            # 1. Buscar o crear cliente
            telefono_normalizado = validar_telefono_chileno(cliente_data.get('telefono', ''))[2]

            cliente, created = Cliente.objects.get_or_create(
                telefono=telefono_normalizado,
                defaults={
                    # Gate H-067: un pushname con basura no se guarda como nombre
                    # ('' para que el lápiz de la bandeja lo corrija a mano).
                    'nombre': nombre_presentable(cliente_data.get('nombre', '')),
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
                # Gate H-067: solo pisar el nombre si el nuevo es presentable —
                # nunca guardar un pushname con basura sobre lo existente.
                nombre_nuevo = nombre_presentable(cliente_data.get('nombre', ''))
                if nombre_nuevo:
                    cliente.nombre = nombre_nuevo
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
            # H-046 (2026-07-22): faltaba fecha_reserva — quedaba en blanco ("-" en el listado
            # del admin) para TODA reserva creada por este camino (aprobar cotización de Luna,
            # el mismo que usa Deborah). Las otras rutas de creación (checkout web en
            # reservation_service.py, api_views.py) sí la seteaban con timezone.now().
            venta_reserva = VentaReserva.objects.create(
                cliente=cliente,
                estado_pago=metodo_pago,
                comentarios=f"[Luna WhatsApp] {notas}" if notas else "[Luna WhatsApp]",
                total=0,  # Se calculará después
                fecha_reserva=timezone.now(),
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

                # precio_unitario_venta = precio POR PERSONA (precio_base). El total
                # se calcula como precio_unitario × cantidad_personas en calcular_total()
                # — para cabañas cantidad_personas=2, dando el precio total correcto.
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


def _aprobar_adicion_a_reserva_existente(propuesta_id, propuesta):
    """Aprueba una PropuestaReserva de ADICIÓN (H-060): en vez de crear una VentaReserva
    nueva, agrega sus servicios/productos a la reserva #reserva_existente_id que YA es
    real (posiblemente ya pagada). Llamada desde crear_reserva() cuando detecta
    propuesta.reserva_existente_id — comparte su try/except (Servicio.DoesNotExist /
    Exception genérica), así que no necesita uno propio.

    Mismo criterio de concurrencia que la reserva nueva (ver comentario en crear_reserva,
    caso 6169/6170): select_for_update() + re-chequeo de idempotencia BAJO LOCK, para que
    un doble-click en "Aprobar" no duplique la adición.
    """
    from ventas.services.reserva_addition_service import agregar_items_a_reserva

    with transaction.atomic():
        # Re-leer la propuesta BAJO LOCK (la llamada anterior, obtener_propuesta, no bloquea).
        propuesta = PropuestaReserva.objects.select_for_update().get(propuesta_id=propuesta_id)

        if propuesta.estado == 'creada':
            # Ya se aplicó (esta misma llamada re-entrando, o un click duplicado) — idempotente.
            try:
                venta_reserva = VentaReserva.objects.get(id=propuesta.reserva_id)
                return Response({
                    'success': True,
                    'reserva': {
                        'id': venta_reserva.id,
                        'numero': f'RES-{venta_reserva.id}',
                        'total': int(venta_reserva.total),
                        'estado_pago': venta_reserva.estado_pago,
                        'duplicada': True,
                    },
                    'agregado': True,
                    'mensaje': f'Ya se había agregado desde la propuesta {propuesta_id[:8]}',
                })
            except VentaReserva.DoesNotExist:
                return Response({
                    'success': False, 'error': 'reserva_not_found',
                    'mensaje': 'La reserva a la que se agregó ya no existe',
                }, status=status.HTTP_404_NOT_FOUND)

        try:
            venta_reserva = VentaReserva.objects.select_for_update().get(
                id=propuesta.reserva_existente_id)
        except VentaReserva.DoesNotExist:
            return Response({
                'success': False, 'error': 'reserva_not_found',
                'mensaje': f'La reserva {propuesta.reserva_existente_id} ya no existe',
            }, status=status.HTTP_404_NOT_FOUND)

        payload = propuesta.payload or {}
        servicios_data = payload.get('servicios', [])
        productos_data = payload.get('productos', [])

        # Revalidar disponibilidad de los servicios nuevos (pudieron ocuparse desde que se
        # propuso) — mismo criterio que agregar_servicios_reserva/crear_reserva.
        if servicios_data:
            validacion = validar_disponibilidad_interna(servicios_data)
            if not validacion['success']:
                return Response({
                    'success': False, 'error': 'availability_error',
                    'errores': validacion.get('errores', []),
                    'mensaje': 'Uno o más servicios ya no están disponibles',
                }, status=status.HTTP_400_BAD_REQUEST)

        resultado = agregar_items_a_reserva(venta_reserva, servicios_data, productos_data)

        propuesta.estado = 'creada'
        # Punto delicado de idempotencia: reserva_id queda IGUAL a reserva_existente_id (no
        # null) para que el chequeo de arriba ("if propuesta.estado == 'creada'") funcione
        # en el próximo click sin tocar ese código — dejarlo null duplicaría la adición.
        propuesta.reserva_id = propuesta.reserva_existente_id
        propuesta.creada_at = timezone.now()
        propuesta.save(update_fields=['estado', 'reserva_id', 'creada_at'])

        logger.info(f'[Luna API] Adición aprobada: propuesta {propuesta_id[:8]} → reserva {venta_reserva.id}')

        return Response({
            'success': True,
            'reserva': {
                'id': venta_reserva.id,
                'numero': f'RES-{venta_reserva.id}',
                'total': int(resultado['nuevo_total']),
                'estado_pago': resultado['estado_pago'],
            },
            'agregado': True,
            'servicios_agregados': resultado['servicios_agregados'],
            'productos_agregados': resultado['productos_agregados'],
            'mensaje': f'Se agregó a la Reserva RES-{venta_reserva.id}',
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([LunaAPIKeyAuthentication])
def agregar_servicios_reserva(request, reserva_id):
    """
    Agrega servicios y/o productos adicionales a una reserva existente. Delega el
    trabajo a ventas.services.reserva_addition_service.agregar_items_a_reserva
    (H-060) — misma función que usa la aprobación de una adición vía PropuestaReserva,
    para no duplicar el recálculo de pack ni el fix del bug de actualizar_saldo.

    POST /api/luna/reservas/{reserva_id}/servicios/

    Body:
    {
        "servicios": [
            {"servicio_id": 9, "fecha": "2026-04-30", "hora": "16:00", "cantidad_personas": 2}
        ],
        "productos": [
            {"producto_id": 3, "cantidad": 2}
        ]
    }
    (servicios y productos son ambos opcionales, pero se requiere al menos uno de los dos)

    Respuesta:
    {
        "success": true,
        "reserva_id": 5434,
        "numero": "RES-5434",
        "servicios_agregados": [...],
        "productos_agregados": [...],
        "nuevo_total": 150000.0,
        "saldo_pendiente": 150000.0,
        "estado_pago": "parcial"
    }
    """
    from ventas.services.reserva_addition_service import agregar_items_a_reserva

    try:
        try:
            venta_reserva = VentaReserva.objects.get(id=reserva_id)
        except VentaReserva.DoesNotExist:
            return Response({
                'success': False,
                'error': 'reserva_not_found',
                'mensaje': f'Reserva con ID {reserva_id} no existe'
            }, status=status.HTTP_404_NOT_FOUND)

        servicios_data = request.data.get('servicios', [])
        productos_data = request.data.get('productos', [])

        if not servicios_data and not productos_data:
            return Response({
                'success': False,
                'error': 'validation_error',
                'mensaje': 'Debe incluir al menos un servicio o producto'
            }, status=status.HTTP_400_BAD_REQUEST)

        if servicios_data:
            validacion_response = validar_disponibilidad_interna(servicios_data)
            if not validacion_response['success']:
                return Response({
                    'success': False,
                    'error': 'availability_error',
                    'errores': validacion_response.get('errores', []),
                    'mensaje': 'Uno o más servicios no están disponibles'
                }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            resultado = agregar_items_a_reserva(venta_reserva, servicios_data, productos_data)

            n_serv = len(resultado['servicios_agregados'])
            n_prod = len(resultado['productos_agregados'])
            partes = []
            if n_serv:
                partes.append(f'{n_serv} servicio(s)')
            if n_prod:
                partes.append(f'{n_prod} producto(s)')
            logger.info(f'[Luna API] Agregado a reserva {reserva_id}: {", ".join(partes)}')

            return Response({
                'success': True,
                'reserva_id': venta_reserva.id,
                'numero': f'RES-{venta_reserva.id}',
                'servicios_agregados': resultado['servicios_agregados'],
                'productos_agregados': resultado['productos_agregados'],
                'descuentos_aplicados': resultado['descuentos_aplicados'],
                'total_descuentos': resultado['total_descuentos'],
                'nuevo_total': resultado['nuevo_total'],
                'saldo_pendiente': resultado['saldo_pendiente'],
                'estado_pago': resultado['estado_pago'],
                'mensaje': f'{" y ".join(partes)} agregado(s) exitosamente',
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


@api_view(['GET'])
@authentication_classes([LunaAPIKeyAuthentication])
def buscar_reservas_cliente(request):
    """
    Lista las reservas ELEGIBLES de un cliente por teléfono — para que Luna identifique
    a cuál reserva agregar un servicio/producto (H-060). Solo lectura, no crea nada.

    GET /api/luna/reservas/buscar/?telefono=+56912345678

    Elegibilidad (whatsapp_agent/reservas_existentes.py, funciones puras testeadas en
    whatsapp_agent/tests/test_logic.py): no cancelada, y con al menos un servicio con
    fecha vigente (hoy o después, con 1 día de gracia) o sin servicios con fecha en
    absoluto (ej. reserva solo de productos).

    Respuesta 200 (siempre — sin cliente o sin reservas es un estado normal, no un error):
    {
        "success": true,
        "reservas": [
            {"reserva_id": 6037, "numero": "RES-6037", "fecha_principal": "2026-07-04",
             "resumen_corto": "Tina Llaima + Masaje Relajación (04-07-2026)",
             "estado_pago": "parcial", "total": 180000}
        ]
    }
    400 si falta el parámetro telefono.
    """
    from whatsapp_agent.reserva_service import buscar_reservas_elegibles

    telefono = (request.GET.get('telefono') or '').strip()
    if not telefono:
        return Response({'success': False, 'error': 'validation_error',
                         'mensaje': 'telefono es obligatorio'}, status=status.HTTP_400_BAD_REQUEST)

    elegibles = buscar_reservas_elegibles(telefono)
    reservas_out = [{
        'reserva_id': r['reserva_id'],
        'numero': r['numero'],
        'fecha_principal': r['fecha_principal'].isoformat() if r['fecha_principal'] else None,
        'resumen_corto': r['resumen_corto'],
        'estado_pago': r['estado_pago'],
        'total': r['total'],
    } for r in elegibles]

    return Response({'success': True, 'reservas': reservas_out})


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


@api_view(['POST'])
@authentication_classes([LunaAPIKeyAuthentication])
def editar_propuesta_endpoint(request):
    """Corrige una propuesta PENDIENTE antes de enviarla (Deborah ajusta cantidades / quita
    líneas en el cajón de cotización). Reemplaza COMPLETAMENTE servicios + productos.

    POST /api/luna/reservas/editar/
    Header: X-API-Key
    Body:
    {
        "propuesta_id": "uuid-string",
        "servicios": [{"servicio_id": 12, "fecha": "2026-06-20", "hora": "14:00", "cantidad_personas": 2}, ...],
        "productos": [{"producto_id": 5, "cantidad": 1}, ...]   # opcional
    }
    Respuesta: { "success": true, "propuesta_id": "...", "resumen_texto": "...", "total": 118000, ... }
    """
    try:
        from whatsapp_agent.reserva_service import editar_propuesta

        propuesta_id = (request.data.get('propuesta_id') or '').strip()
        if not propuesta_id:
            return Response({'success': False, 'error': 'validation_error',
                             'mensaje': 'propuesta_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        servicios = request.data.get('servicios', None)
        if servicios is None:
            return Response({'success': False, 'error': 'validation_error',
                             'mensaje': 'servicios requerido (lista COMPLETA final tras la edición)'},
                            status=status.HTTP_400_BAD_REQUEST)
        productos = request.data.get('productos', []) or []

        resultado = editar_propuesta(propuesta_id, servicios, productos)
        ok = resultado.get('success')
        return Response(resultado, status=status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f'[Luna API] Error en editar_propuesta_endpoint: {str(e)}', exc_info=True)
        return Response({'success': False, 'error': 'internal_error',
                         'mensaje': 'Error al editar la propuesta'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([LunaAPIKeyAuthentication])
def descartar_propuesta_endpoint(request):
    """Descarta/cierra una propuesta PENDIENTE (botón 'Cerrar' del cajón de cotización). Cambia
    estado a 'descartada' → desaparece del cajón y la conversación sigue.

    POST /api/luna/reservas/descartar/
    Header: X-API-Key
    Body: { "propuesta_id": "uuid-string" }
    Respuesta: { "success": true, "propuesta_id": "...", "estado": "descartada" }
    """
    try:
        from whatsapp_agent.reserva_service import cancelar_propuesta

        propuesta_id = (request.data.get('propuesta_id') or '').strip()
        if not propuesta_id:
            return Response({'success': False, 'error': 'validation_error',
                             'mensaje': 'propuesta_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        if cancelar_propuesta(propuesta_id):
            return Response({'success': True, 'propuesta_id': propuesta_id, 'estado': 'descartada'})
        return Response({'success': False, 'error': 'no_descartable',
                         'mensaje': 'La propuesta no existe o no está pendiente'},
                        status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f'[Luna API] Error en descartar_propuesta_endpoint: {str(e)}', exc_info=True)
        return Response({'success': False, 'error': 'internal_error',
                         'mensaje': 'Error al descartar la propuesta'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# CATÁLOGO AGREGABLE (picker "+ Agregar ítem" del cajón de cotización)
# ============================================================================

@api_view(['GET'])
@authentication_classes([LunaAPIKeyAuthentication])
def catalogo_agregables(request):
    """Catálogo de ítems que se pueden AGREGAR a una cotización desde el cajón de la
    bandeja (aremko-cli): ambientaciones (servicios de la categoría Ambientaciones)
    + productos vendibles (Comestibles / Bebestibles: tablas, jugos, café, torta...).

    GET /api/luna/catalogo-agregables/
    Header: X-API-Key

    Solo activos y con precio real (>1: excluye cortesías/insumos en $0 y los
    centinelas en $1 tipo "Fruta"). Los precios de aquí son referencia para elegir;
    al guardar, editar_propuesta re-lee el catálogo (fuente única de precios).

    Respuesta:
    {
        "success": true,
        "ambientaciones": [{"servicio_id": 22, "nombre": "Ambientación romántica R1", "precio": 32000}],
        "productos": [{"producto_id": 3, "nombre": "Tabla Quesos", "precio": 20000, "categoria": "Comestibles"}]
    }
    """
    try:
        ambientaciones = [
            {'servicio_id': s.id, 'nombre': s.nombre, 'precio': int(s.precio_base)}
            for s in Servicio.objects.filter(
                categoria__nombre__iexact='Ambientaciones',
                activo=True,
                precio_base__gt=1,
            ).order_by('nombre')
        ]
        productos = [
            {
                'producto_id': p.id,
                'nombre': p.nombre,
                'precio': int(p.precio_base),
                'categoria': p.categoria.nombre if p.categoria else '',
            }
            for p in Producto.objects.select_related('categoria').filter(
                categoria__nombre__in=['Comestibles', 'Bebestibles'],
                precio_base__gt=1,
            ).order_by('categoria__nombre', 'nombre')
        ]
        return Response({'success': True, 'ambientaciones': ambientaciones, 'productos': productos})
    except Exception as e:
        logger.error(f'[Luna API] Error en catalogo_agregables: {str(e)}', exc_info=True)
        return Response({'success': False, 'error': 'internal_error',
                         'mensaje': 'Error al leer el catálogo agregable'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([LunaAPIKeyAuthentication])
def editar_carrito_endpoint(request):
    """H-079 (H-046 Fase 2): edita el CARRITO EN CURSO desde la bandeja, ANTES de que
    exista cotización. Mismo contrato que editar_propuesta: REEMPLAZO TOTAL de
    servicios + productos; los precios se re-leen del catálogo (nunca del input).

    POST /api/luna/carrito/editar/
    Header: X-API-Key
    Body:
    {
        "canal": "whatsapp",              # whatsapp | instagram | messenger
        "external_id": "+56912345678",    # phone (WA) / IGSID (IG) / PSID (Msgr)
        "servicios": [{"servicio_id": 9, "fecha": "2026-08-05", "hora": "14:30", "cantidad_personas": 2}, ...],
        "productos": [{"producto_id": 3, "cantidad": 1}, ...]   # opcional
    }
    Ambas listas vacías → se ELIMINA el carrito (queda como si no se hubiera armado).
    Respuesta: {success, items_count, total} | {success, vacio: true}
    """
    try:
        from carrito_reservas.models import CarritoReserva
        from carrito_reservas.services import CarritoService

        canal = (request.data.get('canal') or 'whatsapp').strip()
        external_id = (request.data.get('external_id') or '').strip()
        if not external_id:
            return Response({'success': False, 'error': 'validation_error',
                             'mensaje': 'external_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
        servicios = request.data.get('servicios', None)
        if servicios is None:
            return Response({'success': False, 'error': 'validation_error',
                             'mensaje': 'servicios requerido (lista COMPLETA final; puede ser vacía)'},
                            status=status.HTTP_400_BAD_REQUEST)
        productos = request.data.get('productos', []) or []

        carrito = CarritoReserva.objects.filter(canal=canal, external_id=external_id).first()
        if carrito is None:
            return Response({'success': False, 'error': 'carrito_not_found',
                             'mensaje': 'No hay carrito en curso para esta conversación'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Rearmar items releyendo el catálogo (fuente única de precios).
        items = []
        for s in servicios:
            servicio = Servicio.objects.filter(id=s.get('servicio_id')).first()
            if servicio is None:
                return Response({'success': False, 'error': 'service_not_found',
                                 'mensaje': f"Servicio {s.get('servicio_id')} no existe"},
                                status=status.HTTP_400_BAD_REQUEST)
            personas = max(1, int(s.get('cantidad_personas') or 1))
            precio = float(servicio.precio_base)
            items.append({
                'tipo': 'servicio', 'servicio_id': servicio.id, 'nombre': servicio.nombre,
                'fecha': s.get('fecha'), 'hora': s.get('hora'),
                'cantidad_personas': personas,
                'precio_unitario': precio, 'subtotal': precio * personas,
            })
        for p in productos:
            producto = Producto.objects.filter(id=p.get('producto_id')).first()
            if producto is None:
                return Response({'success': False, 'error': 'product_not_found',
                                 'mensaje': f"Producto {p.get('producto_id')} no existe"},
                                status=status.HTTP_400_BAD_REQUEST)
            cantidad = max(1, int(p.get('cantidad') or 1))
            items.append({
                'tipo': 'producto', 'producto_id': producto.id, 'nombre': producto.nombre,
                'cantidad': cantidad,
                'precio_unitario': float(producto.precio_base),
                'subtotal': float(producto.precio_base) * cantidad,
            })

        if not items:
            carrito.delete()
            logger.info(f'[Bandeja] carrito {canal}:{external_id} VACIADO por edición (H-079)')
            return Response({'success': True, 'vacio': True, 'mensaje': 'Carrito vaciado'})

        carrito.items = items
        carrito.save(update_fields=['items', 'updated_at'])
        # Recalcula subtotales + descuento de pack con la fuente única del carrito.
        CarritoService._recalcular_totales(carrito)
        carrito.refresh_from_db()
        logger.info(
            f'[Bandeja] carrito {canal}:{external_id} EDITADO (H-079): '
            f'{len(items)} items → total ${int(carrito.total or 0):,}')
        return Response({'success': True, 'items_count': len(items),
                         'total': int(carrito.total or 0)})

    except Exception as e:
        logger.error(f'[Luna API] Error en editar_carrito_endpoint: {str(e)}', exc_info=True)
        return Response({'success': False, 'error': 'internal_error',
                         'mensaje': 'Error al editar el carrito'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
# ALTERNATIVAS DE HORARIO — PAUSA (TINA+MASAJE) — H-059
# ============================================================================

@api_view(['GET'])
@authentication_classes([LunaAPIKeyAuthentication])
def pausa_alternativas(request):
    """
    Todas las alternativas de horario válidas del pack Pausa (tina+masaje) para una fecha
    dada — para el botón "buscar otro horario" de la bandeja (H-059): cada alternativa ya
    trae un texto listo para pegar en el borrador, ordenadas de más temprano a más tardío.

    Antes, la tool que usa Luna solo mostraba 2 opciones (la más temprana de cada tipo de
    tina) — si el cliente pedía "más tarde", no había forma de ofrecer otra sin adivinar.
    Este endpoint expone TODAS las combinaciones posibles ese día (reusa
    `disponibilidad_pack_tina_masaje(..., todas=True)`, mismas reglas de negocio: buffer de
    45min para cliente sin alojamiento, sin solapar horarios, packs de descuento si aplican)
    para que el staff navegue con un clic, sin depender de que el LLM interprete "más tarde".

    GET /api/luna/pausa/alternativas/?fecha=YYYY-MM-DD&personas=N (personas default 2)

    Respuesta 200:
    {
      "fecha": "2026-07-05", "personas": 2,
      "alternativas": [
        {"etiqueta": "con hidromasaje", "tina": "Tina Hidromasaje Llaima",
         "hora_tina": "11:30", "hora_masaje": "14:15",
         "precio_total": 140000, "precio_con_descuento": 110000, "hay_descuento": true,
         "texto_sugerido": "Tina Hidromasaje Llaima a las 11:30 hrs y Masaje de Relajación o Descontracturante a las 14:15 hrs, por un total de $110.000 (con descuento de pack; precio normal $140.000)."},
        ...
      ]
    }
    `alternativas` viene vacía (200, no error) si ese día no hay ninguna combinación posible
    — mismo criterio que la tool de Luna (no es un error, es información real).
    400 si falta `fecha` o los parámetros son inválidos.
    """
    fecha = request.GET.get('fecha')
    personas_raw = request.GET.get('personas', '2')

    if not fecha:
        return Response(
            {'error': 'fecha es obligatoria (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        personas = int(personas_raw)
    except (TypeError, ValueError):
        return Response(
            {'error': 'personas debe ser un número entero'}, status=status.HTTP_400_BAD_REQUEST)
    if personas < 1:
        return Response(
            {'error': 'personas debe ser >= 1'}, status=status.HTTP_400_BAD_REQUEST)

    from whatsapp_agent import packs
    from whatsapp_agent.grounding import formatear_precio

    try:
        resultado = packs.disponibilidad_pack_tina_masaje(fecha, personas=personas, todas=True)
    except Exception as e:  # noqa: BLE001 — no romper el endpoint por un error inesperado
        logger.error(f'[Luna API] Error en pausa_alternativas: {str(e)}', exc_info=True)
        return Response({'error': f'error interno: {str(e)[:200]}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if resultado.get('error'):
        return Response({'error': resultado['error']}, status=status.HTTP_400_BAD_REQUEST)

    alternativas = []
    for alt in resultado.get('alternativas', []):
        tina, masaje = alt['tina'], alt['masaje']
        if alt['hay_descuento']:
            precio_txt = (
                f"por un total de {formatear_precio(alt['precio_con_descuento'])} "
                f"(con descuento de pack; precio normal {formatear_precio(alt['precio_total'])})"
            )
        else:
            precio_txt = f"por un total de {formatear_precio(alt['precio_total'])}"
        texto_sugerido = (
            f"{tina['nombre']} a las {tina['hora']} hrs y "
            f"{masaje['nombre']} a las {masaje['hora']} hrs, {precio_txt}."
        )
        alternativas.append({
            'etiqueta': alt['etiqueta'],
            'tina': tina['nombre'],
            'hora_tina': tina['hora'],
            'hora_masaje': masaje['hora'],
            'precio_total': alt['precio_total'],
            'precio_con_descuento': alt['precio_con_descuento'],
            'hay_descuento': alt['hay_descuento'],
            'texto_sugerido': texto_sugerido,
        })

    return Response({
        'fecha': resultado['fecha'],
        'personas': resultado['personas'],
        'alternativas': alternativas,
    })


@api_view(['GET'])
@authentication_classes([LunaAPIKeyAuthentication])
def experiencias_alternativas(request):
    """Alternativas de horario de CUALQUIER experiencia (H-061) — generaliza el
    botón de la bandeja de Pausa (H-059) a los demás casos.

    GET /api/luna/experiencias/alternativas/?tipo=<tipo>&fecha=YYYY-MM-DD&personas=N

      tipo (obligatorio): pausa | tina_sola | masaje_solo | noche_aguas_calientes
                          | ritual | refugio
      fecha (obligatorio, YYYY-MM-DD; también acepta expresiones NL)
      personas (opcional, default 2, entero ≥ 1). Para masaje: N personas = N masajes.
                Ritual/Refugio/Noche son siempre para 2 (se ignora personas).

    Respuesta 200 (shape unificado, mismo espíritu que Pausa):
    {
      "tipo": "tina_sola", "fecha": "2026-07-14", "personas": 2,
      "nombre_experiencia": "Tina",
      "alternativas": [
        {"titulo": "Tina Hidromasaje Llaima · 18:00",
         "precio_total": 60000, "precio_con_descuento": 60000, "hay_descuento": false,
         "texto_sugerido": "Tina ... a las 18:00 hrs para 2 personas, $60.000.",
         "itinerario": [{"servicio": "Tina ...", "hora": "18:00"}]}
      ]
    }
    `alternativas` vacía (200, no error) si ese día no hay nada. 400 si falta tipo/fecha,
    tipo inválido o de Fase 2, o parámetros mal formados.
    """
    tipo = request.GET.get('tipo')
    fecha = request.GET.get('fecha')
    personas_raw = request.GET.get('personas', '2')

    if not tipo:
        return Response(
            {'error': 'tipo es obligatorio (pausa|tina_sola|masaje_solo|noche_aguas_calientes)'},
            status=status.HTTP_400_BAD_REQUEST)
    if not fecha:
        return Response(
            {'error': 'fecha es obligatoria (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        personas = int(personas_raw)
    except (TypeError, ValueError):
        return Response(
            {'error': 'personas debe ser un número entero'}, status=status.HTTP_400_BAD_REQUEST)
    if personas < 1:
        return Response(
            {'error': 'personas debe ser >= 1'}, status=status.HTTP_400_BAD_REQUEST)

    from whatsapp_agent import alternativas as alt_mod

    try:
        resultado = alt_mod.construir_alternativas(tipo, fecha, personas)
    except Exception as e:  # noqa: BLE001 — no romper el endpoint por un error inesperado
        logger.error(f'[Luna API] Error en experiencias_alternativas: {str(e)}', exc_info=True)
        return Response({'error': f'error interno: {str(e)[:200]}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if resultado.get('error'):
        return Response({'error': resultado['error']}, status=status.HTTP_400_BAD_REQUEST)

    return Response(resultado)


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
