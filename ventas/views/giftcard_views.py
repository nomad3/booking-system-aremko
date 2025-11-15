# -*- coding: utf-8 -*-
"""
Vistas API para el sistema de GiftCards con personalización IA
"""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from decimal import Decimal
import json
import logging

from ..models import GiftCard, Cliente
from ..services.giftcard_ai_service import GiftCardAIService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def generar_mensajes_ai(request):
    """
    Endpoint para generar mensajes personalizados con IA

    POST /api/giftcard/generar-mensajes/

    Body JSON:
    {
        "tipo_mensaje": "romantico",  // romantico, cumpleanos, aniversario, etc.
        "nombre": "María",
        "relacion": "esposa",
        "detalle": "Celebrando 10 años juntos",  // Opcional
        "cantidad": 3  // Opcional, default 3
    }

    Response:
    {
        "success": true,
        "mensajes": [
            "Mensaje 1...",
            "Mensaje 2...",
            "Mensaje 3..."
        ]
    }
    """
    try:
        # Parsear body JSON
        data = json.loads(request.body)

        # Validar campos requeridos
        tipo_mensaje = data.get('tipo_mensaje')
        nombre = data.get('nombre')
        relacion = data.get('relacion')

        if not tipo_mensaje or not nombre or not relacion:
            return JsonResponse({
                'success': False,
                'error': 'Campos requeridos: tipo_mensaje, nombre, relacion'
            }, status=400)

        # Campos opcionales
        detalle = data.get('detalle', '')
        cantidad = int(data.get('cantidad', 3))

        # Validar cantidad
        if cantidad < 1 or cantidad > 5:
            return JsonResponse({
                'success': False,
                'error': 'La cantidad debe estar entre 1 y 5'
            }, status=400)

        # Generar mensajes con IA
        mensajes = GiftCardAIService.generar_mensajes(
            tipo_mensaje=tipo_mensaje,
            nombre=nombre,
            relacion=relacion,
            detalle=detalle,
            cantidad=cantidad
        )

        logger.info(f"Mensajes generados exitosamente para {nombre} (tipo: {tipo_mensaje})")

        return JsonResponse({
            'success': True,
            'mensajes': mensajes,
            'cantidad_generada': len(mensajes)
        })

    except ValueError as e:
        logger.warning(f"Error de validación en generar_mensajes_ai: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

    except Exception as e:
        logger.error(f"Error en generar_mensajes_ai: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Error al generar mensajes con IA. Intente nuevamente.'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def regenerar_mensaje_ai(request):
    """
    Endpoint para regenerar un mensaje diferente a los anteriores

    POST /api/giftcard/regenerar-mensaje/

    Body JSON:
    {
        "tipo_mensaje": "romantico",
        "nombre": "María",
        "relacion": "esposa",
        "detalle": "Celebrando 10 años juntos",  // Opcional
        "mensajes_previos": [  // Opcional, mensajes a evitar
            "Mensaje 1...",
            "Mensaje 2..."
        ]
    }

    Response:
    {
        "success": true,
        "mensaje": "Nuevo mensaje diferente..."
    }
    """
    try:
        # Parsear body JSON
        data = json.loads(request.body)

        # Validar campos requeridos
        tipo_mensaje = data.get('tipo_mensaje')
        nombre = data.get('nombre')
        relacion = data.get('relacion')

        if not tipo_mensaje or not nombre or not relacion:
            return JsonResponse({
                'success': False,
                'error': 'Campos requeridos: tipo_mensaje, nombre, relacion'
            }, status=400)

        # Campos opcionales
        detalle = data.get('detalle', '')
        mensajes_previos = data.get('mensajes_previos', [])

        # Regenerar mensaje único
        nuevo_mensaje = GiftCardAIService.regenerar_mensaje_unico(
            tipo_mensaje=tipo_mensaje,
            nombre=nombre,
            relacion=relacion,
            detalle=detalle,
            mensajes_previos=mensajes_previos
        )

        logger.info(f"Mensaje regenerado exitosamente para {nombre}")

        return JsonResponse({
            'success': True,
            'mensaje': nuevo_mensaje
        })

    except ValueError as e:
        logger.warning(f"Error de validación en regenerar_mensaje_ai: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

    except Exception as e:
        logger.error(f"Error en regenerar_mensaje_ai: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Error al regenerar mensaje. Intente nuevamente.'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def crear_giftcard(request):
    """
    Endpoint para crear una GiftCard personalizada con mensaje IA

    POST /api/giftcard/crear/

    Body JSON:
    {
        "monto_inicial": 50000,
        "dias_validez": 180,
        "comprador_nombre": "Juan Pérez",
        "comprador_email": "juan@example.com",
        "comprador_telefono": "+56912345678",
        "destinatario_nombre": "María",
        "destinatario_email": "maria@example.com",  // Opcional
        "destinatario_telefono": "+56987654321",  // Opcional
        "destinatario_relacion": "esposa",
        "detalle_especial": "Celebrando 10 años juntos",  // Opcional
        "tipo_mensaje": "aniversario",
        "mensaje_personalizado": "Mensaje seleccionado...",
        "mensaje_alternativas": ["Mensaje 1", "Mensaje 2", "Mensaje 3"],
        "servicio_asociado": "tinas"  // Opcional
    }

    Response:
    {
        "success": true,
        "giftcard_id": 123,
        "codigo": "GIFT-ABC123",
        "monto_inicial": 50000,
        "fecha_vencimiento": "2025-05-15",
        "estado": "por_cobrar"
    }
    """
    try:
        # Parsear body JSON
        data = json.loads(request.body)

        # Validar campos requeridos mínimos
        monto_inicial = data.get('monto_inicial')
        comprador_nombre = data.get('comprador_nombre')
        destinatario_nombre = data.get('destinatario_nombre')
        tipo_mensaje = data.get('tipo_mensaje')
        mensaje_personalizado = data.get('mensaje_personalizado')

        if not all([monto_inicial, comprador_nombre, destinatario_nombre, tipo_mensaje, mensaje_personalizado]):
            return JsonResponse({
                'success': False,
                'error': 'Campos requeridos: monto_inicial, comprador_nombre, destinatario_nombre, tipo_mensaje, mensaje_personalizado'
            }, status=400)

        # Validar monto
        try:
            monto_decimal = Decimal(str(monto_inicial))
            if monto_decimal <= 0:
                raise ValueError("El monto debe ser mayor a 0")
        except (ValueError, TypeError) as e:
            return JsonResponse({
                'success': False,
                'error': f'Monto inválido: {str(e)}'
            }, status=400)

        # Días de validez (default 180 días)
        dias_validez = int(data.get('dias_validez', 180))

        # Calcular fecha de vencimiento
        fecha_vencimiento = timezone.now().date() + timezone.timedelta(days=dias_validez)

        # Crear GiftCard
        giftcard = GiftCard.objects.create(
            monto_inicial=monto_decimal,
            monto_disponible=monto_decimal,
            fecha_emision=timezone.now().date(),
            fecha_vencimiento=fecha_vencimiento,
            estado='por_cobrar',  # Inicial, luego cambia a 'cobrado' tras pago

            # Datos del comprador
            comprador_nombre=comprador_nombre,
            comprador_email=data.get('comprador_email', ''),
            comprador_telefono=data.get('comprador_telefono', ''),

            # Datos del destinatario
            destinatario_nombre=destinatario_nombre,
            destinatario_email=data.get('destinatario_email', ''),
            destinatario_telefono=data.get('destinatario_telefono', ''),
            destinatario_relacion=data.get('destinatario_relacion', ''),
            detalle_especial=data.get('detalle_especial', ''),

            # Configuración de mensaje IA
            tipo_mensaje=tipo_mensaje,
            mensaje_personalizado=mensaje_personalizado,
            mensaje_alternativas=data.get('mensaje_alternativas', []),

            # Servicio asociado (opcional)
            servicio_asociado=data.get('servicio_asociado', '')
        )

        logger.info(f"GiftCard creada: {giftcard.codigo} - Monto: ${monto_decimal} - Comprador: {comprador_nombre}")

        return JsonResponse({
            'success': True,
            'giftcard_id': giftcard.id,
            'codigo': giftcard.codigo,
            'monto_inicial': float(giftcard.monto_inicial),
            'fecha_vencimiento': giftcard.fecha_vencimiento.isoformat(),
            'estado': giftcard.estado
        }, status=201)

    except Exception as e:
        logger.error(f"Error en crear_giftcard: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Error al crear GiftCard. Intente nuevamente.'
        }, status=500)


@require_http_methods(["GET"])
def consultar_giftcard(request, codigo):
    """
    Endpoint para consultar una GiftCard por código

    GET /api/giftcard/{codigo}/

    Response:
    {
        "success": true,
        "giftcard": {
            "codigo": "GIFT-ABC123",
            "monto_inicial": 50000,
            "monto_disponible": 50000,
            "estado": "activo",
            "fecha_vencimiento": "2025-05-15",
            "destinatario_nombre": "María",
            "mensaje_personalizado": "Mensaje...",
            "servicio_asociado": "tinas"
        }
    }
    """
    try:
        # Buscar GiftCard por código
        giftcard = GiftCard.objects.get(codigo=codigo.upper())

        return JsonResponse({
            'success': True,
            'giftcard': {
                'codigo': giftcard.codigo,
                'monto_inicial': float(giftcard.monto_inicial),
                'monto_disponible': float(giftcard.monto_disponible),
                'estado': giftcard.estado,
                'fecha_emision': giftcard.fecha_emision.isoformat(),
                'fecha_vencimiento': giftcard.fecha_vencimiento.isoformat(),
                'destinatario_nombre': giftcard.destinatario_nombre,
                'mensaje_personalizado': giftcard.mensaje_personalizado,
                'servicio_asociado': giftcard.servicio_asociado,
                'dias_restantes': (giftcard.fecha_vencimiento - timezone.now().date()).days
            }
        })

    except GiftCard.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'GiftCard no encontrada'
        }, status=404)

    except Exception as e:
        logger.error(f"Error en consultar_giftcard: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Error al consultar GiftCard'
        }, status=500)


# ============================================================================
# VISTAS DE INTERFAZ WEB (Frontend)
# ============================================================================

@require_http_methods(["GET"])
def giftcard_wizard(request):
    """
    Página principal del wizard de compra de GiftCards

    GET /giftcards/

    Wizard de 6 pasos:
    1. Seleccionar experiencia/monto
    2. Datos del destinatario
    3. Tipo de mensaje
    4. Generar y elegir mensaje IA
    5. Preview de giftcard
    6. Checkout
    """

    # Opciones de experiencias/servicios
    experiencias = [
        {
            'id': 'tinas',
            'nombre': 'Tinas Calientes',
            'descripcion': 'Experiencia de tinas calientes junto al río Pescado',
            'imagen': 'images/tinas.jpg',  # Ajustar ruta según tus imágenes
            'montos_sugeridos': [30000, 50000, 75000, 100000]
        },
        {
            'id': 'masajes',
            'nombre': 'Masajes Relajantes',
            'descripcion': 'Sesión de masajes profesionales',
            'imagen': 'images/masajes.jpg',
            'montos_sugeridos': [40000, 60000, 80000]
        },
        {
            'id': 'cabanas',
            'nombre': 'Alojamiento en Cabaña',
            'descripcion': 'Estadía completa en nuestras cabañas',
            'imagen': 'images/cabanas.jpg',
            'montos_sugeridos': [80000, 120000, 150000]
        },
        {
            'id': 'ritual_rio',
            'nombre': 'Ritual del Río',
            'descripcion': 'Experiencia completa Ritual del Río',
            'imagen': 'images/ritual.jpg',
            'montos_sugeridos': [100000, 150000, 200000]
        },
        {
            'id': 'celebracion',
            'nombre': 'Celebración Especial',
            'descripcion': 'Paquete personalizado para celebraciones',
            'imagen': 'images/celebracion.jpg',
            'montos_sugeridos': [120000, 180000, 250000]
        },
        {
            'id': 'monto_libre',
            'nombre': 'Monto Libre',
            'descripcion': 'El destinatario elige la experiencia',
            'imagen': 'images/gift_generic.jpg',
            'montos_sugeridos': [50000, 100000, 150000, 200000]
        }
    ]

    # Tipos de mensaje disponibles
    tipos_mensaje = [
        {
            'id': 'romantico',
            'nombre': 'Romántico',
            'descripcion': 'Mensaje íntimo y apasionado para parejas',
            'icono': 'fa-heart'
        },
        {
            'id': 'cumpleanos',
            'nombre': 'Cumpleaños',
            'descripcion': 'Celebrativo y alegre para cumpleaños',
            'icono': 'fa-birthday-cake'
        },
        {
            'id': 'aniversario',
            'nombre': 'Aniversario',
            'descripcion': 'Nostálgico y especial para aniversarios',
            'icono': 'fa-ring'
        },
        {
            'id': 'celebracion',
            'nombre': 'Celebración',
            'descripcion': 'Festivo para cualquier celebración',
            'icono': 'fa-champagne-glasses'
        },
        {
            'id': 'relajacion',
            'nombre': 'Relajación',
            'descripcion': 'Tranquilo y sereno para descanso',
            'icono': 'fa-spa'
        },
        {
            'id': 'parejas',
            'nombre': 'Parejas',
            'descripcion': 'Romántico y cómplice para dos',
            'icono': 'fa-heart-circle'
        },
        {
            'id': 'agradecimiento',
            'nombre': 'Agradecimiento',
            'descripcion': 'Cálido y sincero para agradecer',
            'icono': 'fa-hands-holding-heart'
        },
        {
            'id': 'amistad',
            'nombre': 'Amistad',
            'descripcion': 'Fraternal y cariñoso para amigos',
            'icono': 'fa-user-friends'
        }
    ]

    context = {
        'experiencias': experiencias,
        'tipos_mensaje': tipos_mensaje,
        'paso_actual': 1,
        'total_pasos': 6
    }

    return render(request, 'ventas/giftcard_wizard.html', context)
