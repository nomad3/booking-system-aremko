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
import string
import random

from ..models import GiftCard, Cliente
from ..services.giftcard_ai_service import GiftCardAIService
from ..services.cliente_service import ClienteService

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def giftcard_menu(request):
    """
    Página de inicio de GiftCards con 3 opciones:
    1. Comprar y Personalizar 1 GiftCard (activo)
    2. Comprar Varias GiftCards (próximamente)
    3. GiftCards para Empresas (próximamente)
    """
    return render(request, 'ventas/giftcard_menu.html')


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

    # Opciones de experiencias/servicios organizadas por categorías
    experiencias = [
        # ========== GRUPO TINAS ==========
        {
            'id': 'tinas',
            'categoria': 'tinas',
            'nombre': 'Tina para 2',
            'descripcion': 'Tinas calientes para dos personas',
            'descripcion_giftcard': 'Tinas calientes para dos personas en tinas con o sin hidromasaje junto al Río Pescado',
            'imagen': 'images/tinas.jpg',
            'monto_fijo': 50000,
            'montos_sugeridos': []
        },
        {
            'id': 'tinas_masajes_semana',
            'categoria': 'tinas',
            'nombre': 'Tina + Masajes (Dom-Jue)',
            'descripcion': 'Tina con masajes para dos de domingo a jueves',
            'descripcion_giftcard': 'Tinas calientes + masajes relajantes para dos personas de domingo a jueves',
            'imagen': 'images/tinas_masajes.jpg',
            'monto_fijo': 95000,
            'montos_sugeridos': []
        },
        {
            'id': 'tinas_masajes_finde',
            'categoria': 'tinas',
            'nombre': 'Tina + Masajes (Vie-Sáb)',
            'descripcion': 'Tina con masajes para dos viernes o sábado',
            'descripcion_giftcard': 'Tinas calientes + masajes relajantes para dos personas viernes o sábado',
            'imagen': 'images/tinas_masajes.jpg',
            'monto_fijo': 130000,
            'montos_sugeridos': []
        },
        {
            'id': 'pack_4_personas',
            'categoria': 'tinas',
            'nombre': 'Pack 4 Personas',
            'descripcion': '4 horas de tinas + masaje para 4 personas',
            'descripcion_giftcard': 'Pack completo para 4 personas: 4 horas de tinas calientes + masajes relajantes',
            'imagen': 'images/tinas_masajes.jpg',
            'monto_fijo': 190000,
            'montos_sugeridos': []
        },
        {
            'id': 'pack_6_personas',
            'categoria': 'tinas',
            'nombre': 'Pack 6 Personas',
            'descripcion': '4 horas de tinas + masaje para 6 personas',
            'descripcion_giftcard': 'Pack completo para 6 personas: 4 horas de tinas calientes + masajes relajantes',
            'imagen': 'images/tinas_masajes.jpg',
            'monto_fijo': 285000,
            'montos_sugeridos': []
        },

        # ========== GRUPO SOLO MASAJES ==========
        {
            'id': 'masaje_piedras',
            'categoria': 'masajes',
            'nombre': 'Masaje Piedras Calientes',
            'descripcion': 'Masaje con piedras calientes para 1 persona',
            'descripcion_giftcard': 'Masaje con piedras calientes volcánicas para una persona en domos de bienestar',
            'imagen': 'images/masaje_piedras.jpg',
            'monto_fijo': 45000,
            'montos_sugeridos': []
        },
        {
            'id': 'masaje_deportivo',
            'categoria': 'masajes',
            'nombre': 'Masaje Deportivo',
            'descripcion': 'Masaje deportivo profesional para 1 persona',
            'descripcion_giftcard': 'Masaje deportivo profesional para una persona, ideal para recuperación muscular',
            'imagen': 'images/masaje_deportivo.jpg',
            'monto_fijo': 45000,
            'montos_sugeridos': []
        },
        {
            'id': 'drenaje_linfatico',
            'categoria': 'masajes',
            'nombre': 'Drenaje Linfático',
            'descripcion': 'Drenaje linfático para 1 persona',
            'descripcion_giftcard': 'Sesión de drenaje linfático profesional para una persona',
            'imagen': 'images/drenaje_linfatico.jpg',
            'monto_fijo': 45000,
            'montos_sugeridos': []
        },
        {
            'id': 'masaje_pareja',
            'categoria': 'masajes',
            'nombre': 'Masaje para Dos',
            'descripcion': 'Masaje relajante o descontracturante para dos personas',
            'descripcion_giftcard': 'Masaje relajante o descontracturante para dos personas en nuestros domos de bienestar',
            'imagen': 'images/masaje_pareja.jpg',
            'monto_fijo': 80000,
            'montos_sugeridos': []
        },

        # ========== GRUPO ALOJAMIENTOS ==========
        {
            'id': 'alojamiento_semana',
            'categoria': 'alojamientos',
            'nombre': 'Alojamiento + Tinas (Dom-Jue)',
            'descripcion': 'Alojamiento para dos con tinas de domingo a jueves',
            'descripcion_giftcard': 'Alojamiento para dos en cabaña + tinas calientes de domingo a jueves',
            'imagen': 'images/alojamiento_tinas.jpg',
            'monto_fijo': 95000,
            'montos_sugeridos': []
        },
        {
            'id': 'alojamiento_finde',
            'categoria': 'alojamientos',
            'nombre': 'Alojamiento + Tinas (Vie-Sáb)',
            'descripcion': 'Alojamiento para dos con tinas viernes o sábado',
            'descripcion_giftcard': 'Alojamiento para dos en cabaña + tinas calientes viernes o sábado',
            'imagen': 'images/alojamiento_tinas.jpg',
            'monto_fijo': 140000,
            'montos_sugeridos': []
        },
        {
            'id': 'alojamiento_romantico',
            'categoria': 'alojamientos',
            'nombre': 'Paquete Romántico Completo',
            'descripcion': 'Alojamiento + Tinas + Desayuno + Decoración romántica',
            'descripcion_giftcard': 'Alojamiento + Tinas calientes + Desayuno + Decoración romántica en tinas cualquier día de la semana',
            'imagen': 'images/alojamiento_romantico.jpg',
            'monto_fijo': 150000,
            'montos_sugeridos': []
        },

        # ========== GRUPO CELEBRACIONES ==========
        {
            'id': 'tina_cumpleanos',
            'categoria': 'celebraciones',
            'nombre': 'Tina + Ambientación Cumpleaños',
            'descripcion': 'Tina más ambientación de cumpleaños para dos',
            'descripcion_giftcard': 'Tinas calientes + ambientación especial de cumpleaños para dos personas',
            'imagen': 'images/tina_cumpleanos.jpg',
            'monto_fijo': 88000,
            'montos_sugeridos': []
        },
        {
            'id': 'tina_celebracion',
            'categoria': 'celebraciones',
            'nombre': 'Tina + Celebración Especial',
            'descripcion': 'Tina más celebración especial para dos',
            'descripcion_giftcard': 'Tinas calientes + ambientación para celebración especial para dos personas',
            'imagen': 'images/tina_celebracion.jpg',
            'monto_fijo': 82000,
            'montos_sugeridos': []
        },

        # ========== MONTO LIBRE ==========
        {
            'id': 'monto_libre',
            'categoria': 'libre',
            'nombre': 'Monto Libre',
            'descripcion': 'El destinatario elige la experiencia',
            'descripcion_giftcard': 'Vale por el monto indicado para usar en cualquier experiencia de Aremko Spa',
            'imagen': 'images/gift_generic.jpg',
            'monto_fijo': 0,  # 0 indica que NO tiene monto fijo (evitamos None que causa error en JS)
            'montos_sugeridos': [30000, 50000, 75000, 100000, 150000, 200000]
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
        },
        {
            'id': 'personalizado',
            'nombre': 'Escribir Mi Mensaje',
            'descripcion': 'Escribe tu propio mensaje personalizado',
            'icono': 'fa-pen-fancy'
        }
    ]

    context = {
        'experiencias': experiencias,
        'tipos_mensaje': tipos_mensaje,
        'paso_actual': 1,
        'total_pasos': 5  # 1:Experiencia, 2:Destinatario, 3:Tipo, 4:Mensaje, 5:Preview (Comprador ahora en checkout)
    }

    return render(request, 'ventas/giftcard_wizard.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def buscar_cliente_por_telefono(request):
    """
    Busca un cliente por teléfono para autocompletar datos en el wizard
    Usa búsqueda robusta con múltiples variantes de formato

    POST /ventas/api/giftcard/buscar-cliente/

    Body JSON:
    {
        "telefono": "+56912345678"
    }

    Response:
    {
        "success": true,
        "encontrado": true,
        "cliente": {
            "nombre": "Juan Pérez",
            "email": "juan@example.com",
            "telefono": "+56912345678",
            "telefono_display": "+56 9 1234 5678",
            "documento_identidad": "12345678-9",
            "region_id": 10,
            "region_nombre": "Los Lagos",
            "comuna_id": 101,
            "comuna_nombre": "Puerto Varas",
            "pais": "Chile",
            "numero_visitas": 3,
            "gasto_total": 150000.0,
            "datos_completos": true
        }
    }
    """
    try:
        data = json.loads(request.body)
        telefono_input = data.get('telefono', '').strip()

        if not telefono_input:
            return JsonResponse({
                'success': False,
                'error': 'Teléfono requerido'
            }, status=400)

        logger.info(f"🔍 Búsqueda robusta de cliente con teléfono: {telefono_input}")

        # Usar servicio robusto de búsqueda
        cliente, telefono_normalizado = ClienteService.buscar_cliente_por_telefono(telefono_input)

        if cliente:
            # Obtener datos completos del cliente con relaciones
            datos_cliente = ClienteService.obtener_datos_completos_cliente(cliente)

            logger.info(f"✅ Cliente encontrado: {cliente.nombre} ({cliente.email}) - Teléfono normalizado: {telefono_normalizado}")

            return JsonResponse({
                'success': True,
                'encontrado': True,
                'telefono_normalizado': telefono_normalizado,
                'cliente': datos_cliente['cliente']
            })
        else:
            logger.info(f"ℹ️ Cliente no encontrado con teléfono: {telefono_input}")
            return JsonResponse({
                'success': True,
                'encontrado': False,
                'telefono_normalizado': telefono_normalizado
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)

    except Exception as e:
        logger.error(f"Error en buscar_cliente_por_telefono: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Error al buscar cliente'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def agregar_giftcard_al_carrito(request):
    """
    Agrega una GiftCard personalizada al carrito de compras

    POST /ventas/api/giftcard/agregar-al-carrito/

    Body JSON:
    {
        "experiencia_id": 1,
        "experiencia_nombre": "Tinas Calientes",
        "precio": 50000,
        "destinatario_nombre": "Alda",
        "destinatario_email": "alda@example.com",
        "destinatario_telefono": "+56912345678",
        "tipo_mensaje": "aniversario",
        "mensaje_seleccionado": "Alda, que estas aguas..."
    }

    Response:
    {
        "success": true,
        "cart_count": 1,
        "redirect_url": "/ventas/cart/"
    }
    """
    try:
        # Parsear body JSON
        data = json.loads(request.body)
        logger.info(f"📥 Datos recibidos en agregar_giftcard_al_carrito: {data}")

        # Validar campos requeridos
        required_fields = [
            'experiencia_id', 'experiencia_nombre', 'precio',
            'destinatario_nombre', 'destinatario_email',
            'tipo_mensaje', 'mensaje_seleccionado'
        ]

        for field in required_fields:
            if not data.get(field):
                logger.warning(f"❌ Campo requerido faltante: {field}")
                return JsonResponse({
                    'success': False,
                    'error': f'Campo requerido: {field}'
                }, status=400)

        # Inicializar carrito en sesión si no existe
        if 'cart' not in request.session:
            logger.info("🛒 Creando nuevo carrito en sesión")
            request.session['cart'] = {
                'servicios': [],
                'giftcards': []
            }

        # Asegurar que existe el array de giftcards
        if 'giftcards' not in request.session['cart']:
            logger.info("🎁 Inicializando array de giftcards en carrito")
            request.session['cart']['giftcards'] = []

        # Generar código único para la GiftCard
        codigo_unico = 'GC-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        logger.info(f"🔑 Código generado: {codigo_unico}")

        # Crear item de GiftCard para el carrito
        giftcard_item = {
            'tipo': 'giftcard',
            'codigo_temporal': codigo_unico,
            'experiencia_id': data['experiencia_id'],  # Keep as string (tinas, masajes, etc)
            'experiencia_nombre': data['experiencia_nombre'],
            'precio': float(data['precio']),
            'destinatario_nombre': data['destinatario_nombre'],
            'destinatario_email': data['destinatario_email'],
            'destinatario_telefono': data.get('destinatario_telefono', ''),
            'tipo_mensaje': data['tipo_mensaje'],
            'mensaje_seleccionado': data['mensaje_seleccionado']
        }
        logger.info(f"📦 GiftCard creada: {giftcard_item}")

        # Agregar al carrito
        request.session['cart']['giftcards'].append(giftcard_item)
        request.session.modified = True
        logger.info(f"✅ GiftCard agregada al carrito. Total giftcards: {len(request.session['cart']['giftcards'])}")

        # Calcular total de items en carrito
        cart_count = len(request.session['cart']['servicios']) + len(request.session['cart']['giftcards'])

        logger.info(f"🎉 GiftCard {codigo_unico} agregada exitosamente para {data['destinatario_nombre']}")

        return JsonResponse({
            'success': True,
            'cart_count': cart_count,
            'redirect_url': '/ventas/cart/',
            'codigo': codigo_unico
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)

    except Exception as e:
        logger.error(f"Error en agregar_giftcard_al_carrito: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Error al agregar GiftCard al carrito'
        }, status=500)
