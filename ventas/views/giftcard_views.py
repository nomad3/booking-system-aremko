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

from ..models import GiftCard, Cliente, GiftCardExperiencia
from ..services.giftcard_ai_service import GiftCardAIService
from ..services.cliente_service import ClienteService

logger = logging.getLogger(__name__)


def _card_optim(url):
    """Transformación Cloudinary para las cards (vitrina Y wizard): recorte 4:3
    (más VERTICAL que 16:9 — así no se pierde la altura de los domos/cabañas,
    Jorge 2026-07-06), encuadre inteligente + formato/calidad auto. Las fotos
    originales pesan 2-4MB; así se sirven en ~100-200KB (mismo criterio
    anti-bandwidth de `optimizada`)."""
    if not url or '/upload/' not in url:
        return url
    return url.replace('/upload/', '/upload/c_fill,ar_4:3,g_auto,w_800,f_auto,q_auto/', 1)


@require_http_methods(["GET"])
def giftcard_menu(request):
    """
    Vitrina de GiftCards: las 4 experiencias insignia con carrusel de fotos.
    El botón "Regalar esta experiencia" manda al wizard con ?exp=...&skip_step1=true.
    """
    # DECISIÓN RADICAL (Jorge 2026-07-05): solo se regalan EXPERIENCIAS — las 4
    # insignia, nada más. Ni tinas sueltas, ni masajes sueltos, ni monto libre
    # (cargar_experiencias_giftcard desactiva el resto).
    # Fallback de emergencia: ?classic=1 → template anterior (tabs por categoría).
    experiencias_db = GiftCardExperiencia.objects.filter(activo=True).order_by('orden', 'nombre')
    experiencias = [exp.to_dict() for exp in experiencias_db]

    def _clp(v):
        return '$' + f'{int(v):,}'.replace(',', '.')

    for exp in experiencias:
        exp['precio_str'] = _clp(exp['monto_fijo']) if exp.get('monto_fijo') else ''
        exp['montos_sugeridos_str'] = [_clp(m) for m in (exp.get('montos_sugeridos') or [])]
        exp['imagen'] = _card_optim(exp.get('imagen') or '')
        # Galería del carrusel (1-3 fotos), todas optimizadas/recortadas a 4:3
        exp['imagenes'] = [_card_optim(u) for u in (exp.get('imagenes') or []) if u]

    if request.GET.get('classic') == '1':
        experiencias_por_categoria = {
            cat: [e for e in experiencias if e['categoria'] == cat]
            for cat in ('tinas', 'masajes', 'faciales', 'packs', 'valor')
        }
        return render(request, 'ventas/giftcard_menu_classic.html', {
            'experiencias': experiencias,
            'experiencias_por_categoria': experiencias_por_categoria,
        })

    # Las 4 insignia en orden fijo de escalera (ascendente de precio). Se identifican
    # por id_experiencia (creadas por cargar_experiencias_giftcard). Jorge (2026-07-05):
    # la GiftCard de monto libre TAMPOCO va — solo las 4 experiencias, nada más.
    IDS_INSIGNIA = ['pausa_junto_al_rio', 'noche_aguas_calientes', 'ritual_del_rio', 'refugio_aremko']
    por_id = {exp['id']: exp for exp in experiencias}
    experiencias_insignia = [por_id[i] for i in IDS_INSIGNIA if i in por_id]

    context = {
        'experiencias': experiencias,
        'experiencias_insignia': experiencias_insignia,
    }

    return render(request, 'ventas/giftcard_menu.html', context)


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


# Vista legacy `crear_giftcard` ELIMINADA 2026-07-06: era del flujo viejo pre-carrito,
# no estaba ruteada en urls.py y nadie la llamaba. La GiftCard real se crea tras el
# pago (signal sobre Pago) a partir de agregar_giftcard_al_carrito + checkout.


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
    Wizard de creación de GiftCards — 4 ESTACIONES (5 pantallas internas):

    1. Experiencia   — pantalla 1 (se salta con ?exp=...&skip_step1=true desde la vitrina)
    2. Destinatario  — pantalla 2
    3. Mensaje       — pantallas 3 (tipo) y 4 (elegir el generado por IA; con
                       "Escribir Mi Mensaje" la 4 se salta)
    4. Confirmar     — pantalla 5 (vista previa) → botón "Agregar al Carrito"

    Después del wizard: checkout (datos del comprador + pago) → el pago dispara el
    signal que crea la GiftCard real + PDF + email. Ver ESTACION_POR_PANTALLA en el
    template (giftcard_wizard.html).

    GET /ventas/giftcards/wizard/
    GET /ventas/giftcards/wizard/?exp=ritual_del_rio&skip_step1=true  (desde la vitrina)
    """

    # ============================================================
    # EXPERIENCIAS DESDE BASE DE DATOS
    # ============================================================
    # Las experiencias ahora se leen desde la tabla GiftCardExperiencia
    # en lugar de estar hardcodeadas en el código.
    # Esto permite editar precios, imágenes y contenido desde el admin.

    experiencias_db = GiftCardExperiencia.objects.filter(activo=True).order_by('categoria', 'orden', 'nombre')

    # Convertir QuerySet a lista de diccionarios compatible con el template
    # (mismo formato que el array hardcodeado original)
    experiencias = []
    for exp in experiencias_db:
        exp_dict = exp.to_dict()
        # Asegurar que monto_fijo se maneje correctamente
        if exp_dict.get('monto_fijo') is not None:
            # Convertir a float explícitamente para JavaScript
            exp_dict['monto_fijo'] = float(exp_dict['monto_fijo'])
        else:
            # Mantener None que se convertirá a null en JavaScript
            exp_dict['monto_fijo'] = None
        # Card liviana: mismo recorte 4:3 optimizado que la vitrina
        exp_dict['imagen'] = _card_optim(exp_dict.get('imagen') or '')
        experiencias.append(exp_dict)

    # Si no hay experiencias en BD, fallback a array vacío
    # (evitamos mostrar wizard sin productos)
    if not experiencias:
        logger.warning("⚠️ No hay experiencias GiftCard activas en la base de datos")
        # Podrías redirigir a página de error o mostrar mensaje
        experiencias = []

    # ============================================================
    # MANEJAR PARÁMETRO ?exp= PARA PRE-SELECCIÓN
    # ============================================================
    # Si viene ?exp=alojamiento_semana en la URL, pre-seleccionamos esa experiencia
    experiencia_preseleccionada = None
    exp_id = request.GET.get('exp')

    if exp_id:
        logger.info(f"🔍 Parámetro ?exp={exp_id} detectado, buscando experiencia...")
        # Buscar si existe una experiencia con ese ID (buscar por id_experiencia O por nombre)
        experiencia_obj = experiencias_db.filter(id_experiencia=exp_id).first()

        # Si no se encuentra por id_experiencia, intentar buscar por nombre
        if not experiencia_obj:
            experiencia_obj = experiencias_db.filter(nombre=exp_id).first()
            if experiencia_obj:
                logger.info(f"🔍 Experiencia encontrada por nombre, usando id_experiencia: {experiencia_obj.id_experiencia}")

        if experiencia_obj:
            # IMPORTANTE: Usar el id_experiencia del objeto encontrado, no el parámetro exp_id
            experiencia_preseleccionada = experiencia_obj.id_experiencia
            logger.info(f"✅ Experiencia '{experiencia_obj.nombre}' encontrada y pre-seleccionada (ID: {experiencia_preseleccionada})")
        else:
            logger.warning(f"⚠️ Experiencia con id_experiencia='{exp_id}' no encontrada o inactiva")
            # No redirigir ni mostrar error, simplemente ignorar y mostrar todas las experiencias

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

    # Serializar experiencias a JSON para evitar problemas con None/null
    import json
    experiencias_json = json.dumps(experiencias)

    context = {
        'experiencias': experiencias,
        'experiencias_json': experiencias_json,  # Versión JSON serializada
        'tipos_mensaje': tipos_mensaje,
        'experiencia_preseleccionada': experiencia_preseleccionada,  # Nuevo: para pre-selección
        'paso_actual': 1,
        'total_pasos': 4  # 4 ESTACIONES: Experiencia, Destinatario, Mensaje, Confirmar (ver docstring)
    }

    # Renderizar respuesta con headers anti-caché para Cloudflare
    response = render(request, 'ventas/giftcard_wizard.html', context)

    # Headers para prevenir caché por Cloudflare y navegadores
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    return response


# Vista `buscar_cliente_por_telefono` ELIMINADA 2026-07-06: servía a la pantalla
# "Tus Datos" (step6) del wizard, muerta desde que el comprador se pide en el
# checkout. Nadie la llamaba y exponía datos de clientes sin autenticación.
# (ClienteService.buscar_cliente_por_telefono —el método de servicio— sigue vivo.)


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


@require_http_methods(["GET"])
def giftcard_mobile_view(request, codigo):
    """
    Vista web optimizada para móvil de una GiftCard
    Permite visualizar la GiftCard directamente en el navegador
    sin necesidad de descargar el PDF

    GET /giftcard/<codigo>/view/

    Retorna una página HTML responsive optimizada para móvil
    con el diseño de 5.5 x 9.8 pulgadas
    """
    try:
        # Buscar la GiftCard por código
        giftcard = GiftCard.objects.select_related(
            'cliente_comprador',
            'cliente_destinatario',
            'venta_reserva'
        ).get(codigo=codigo)

        # Verificar si la GiftCard está activa y válida
        hoy = timezone.now().date()

        # Calcular días restantes
        dias_restantes = (giftcard.fecha_vencimiento - hoy).days if giftcard.fecha_vencimiento else 0
        esta_vencida = dias_restantes < 0

        # Obtener información de la experiencia si existe
        experiencia_info = None
        if giftcard.servicio_asociado:
            try:
                experiencia = GiftCardExperiencia.objects.get(
                    id_experiencia=giftcard.servicio_asociado,
                    activo=True
                )
                experiencia_info = {
                    'nombre': experiencia.nombre,
                    'descripcion': experiencia.descripcion_giftcard,
                    'imagen_url': experiencia.imagen.url if experiencia.imagen else None
                }
            except GiftCardExperiencia.DoesNotExist:
                # Usar nombre guardado en GiftCard si no se encuentra la experiencia
                experiencia_info = {
                    'nombre': giftcard.servicio_asociado.replace('_', ' ').title(),
                    'descripcion': None,
                    'imagen_url': None
                }

        # Determinar si es móvil desde el user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        is_mobile = any(device in user_agent for device in ['mobile', 'android', 'iphone', 'ipad'])

        # Formatear fechas de manera robusta sin depender del locale
        meses_es = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }

        fecha_emision_formateada = f"{giftcard.fecha_emision.day} de {meses_es[giftcard.fecha_emision.month]} de {giftcard.fecha_emision.year}"
        fecha_vencimiento_formateada = f"{giftcard.fecha_vencimiento.day} de {meses_es[giftcard.fecha_vencimiento.month]} de {giftcard.fecha_vencimiento.year}"

        # Formatear datos para el template
        context = {
            'giftcard': giftcard,
            'experiencia': experiencia_info,
            'dias_restantes': dias_restantes,
            'esta_vencida': esta_vencida,
            'is_mobile': is_mobile,
            'monto_formateado': f"${giftcard.monto_inicial:,.0f}".replace(',', '.'),
            'monto_disponible_formateado': f"${giftcard.monto_disponible:,.0f}".replace(',', '.'),
            'fecha_emision_formateada': fecha_emision_formateada,
            'fecha_vencimiento_formateada': fecha_vencimiento_formateada,
            'whatsapp_url': f"https://wa.me/56957902525?text=Hola!%20Quiero%20reservar%20con%20mi%20GiftCard%20{giftcard.codigo}",
            'puede_descargar_pdf': True,  # Siempre permitir descarga del PDF
            'show_wallet_button': False,  # Por ahora desactivado, activar cuando se implemente Apple/Google Wallet
        }

        # Renderizar template móvil
        return render(request, 'ventas/giftcard_mobile_view.html', context)

    except GiftCard.DoesNotExist:
        # Si no existe la GiftCard, mostrar página de error
        context = {
            'error': True,
            'mensaje': 'La GiftCard que buscas no existe o el código es incorrecto.',
            'codigo_invalido': codigo
        }
        return render(request, 'ventas/giftcard_mobile_view.html', context, status=404)

    except Exception as e:
        logger.error(f"Error en giftcard_mobile_view para código {codigo}: {str(e)}", exc_info=True)
        context = {
            'error': True,
            'mensaje': 'Ocurrió un error al cargar la GiftCard. Por favor intenta nuevamente.',
        }
        return render(request, 'ventas/giftcard_mobile_view.html', context, status=500)


@require_http_methods(["GET"])
def giftcard_download_pdf(request, codigo):
    """
    Descarga el PDF de una GiftCard en formato móvil (5.5 x 9.8 pulgadas)

    GET /giftcard/<codigo>/download/

    Retorna el archivo PDF para descargar
    """
    try:
        from django.http import HttpResponse
        from ..services.giftcard_pdf_service import GiftCardPDFService

        # Buscar la GiftCard
        giftcard = GiftCard.objects.get(codigo=codigo)

        # Obtener información de la experiencia
        experiencia_imagen_url = None
        experiencia_nombre = giftcard.servicio_asociado.replace('_', ' ').title() if giftcard.servicio_asociado else 'Experiencia Aremko'
        experiencia_descripcion = None

        if giftcard.servicio_asociado:
            try:
                experiencia = GiftCardExperiencia.objects.get(id_experiencia=giftcard.servicio_asociado)
                if experiencia.imagen:
                    experiencia_imagen_url = request.build_absolute_uri(experiencia.imagen.url)
                experiencia_nombre = experiencia.nombre
                experiencia_descripcion = experiencia.descripcion
            except GiftCardExperiencia.DoesNotExist:
                pass

        # Preparar datos para el PDF
        giftcard_data = {
            'codigo': giftcard.codigo,
            'experiencia_nombre': experiencia_nombre,
            'experiencia_descripcion': experiencia_descripcion,
            'experiencia_imagen_url': experiencia_imagen_url,
            'destinatario_nombre': giftcard.destinatario_nombre or 'Invitado Especial',
            'mensaje_seleccionado': giftcard.mensaje_personalizado or f"Te regalo esta experiencia única en Aremko Spa para que disfrutes de un momento de relajación y bienestar en medio de la naturaleza de Puerto Varas.",
            'precio': giftcard.monto_inicial,
            'fecha_emision': giftcard.fecha_emision,
            'fecha_vencimiento': giftcard.fecha_vencimiento,
        }

        # Generar PDF en formato móvil
        pdf_bytes = GiftCardPDFService.generar_pdf_giftcard(giftcard_data, formato='mobile')

        if not pdf_bytes:
            raise Exception("No se pudo generar el PDF")

        # Preparar respuesta HTTP con el PDF
        response = HttpResponse(pdf_bytes, content_type='application/pdf')

        # Nombre del archivo para descarga
        filename = f"GiftCard_Aremko_{codigo}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except GiftCard.DoesNotExist:
        return JsonResponse({
            'error': 'GiftCard no encontrada'
        }, status=404)

    except Exception as e:
        logger.error(f"Error generando PDF para GiftCard {codigo}: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': 'Error al generar el PDF'
        }, status=500)
