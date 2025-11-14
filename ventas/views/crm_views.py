"""
Vistas CRM - Propuestas Personalizadas con IA
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from ventas.models import Cliente, ServiceHistory
from ventas.services.crm_service import CRMService
from ventas.services.ai_proposal_service import get_ai_service
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


# @login_required  # TEMPORALMENTE DESHABILITADO PARA TESTING
def crm_dashboard(request):
    """
    Dashboard principal del CRM con métricas generales
    """
    from django.http import HttpResponse
    import traceback

    try:
        # Debug: Verificar que la vista se ejecuta
        debug_info = ["=== CRM DEBUG ==="]

        # Intentar obtener stats
        try:
            stats = CRMService.get_dashboard_stats()
            debug_info.append(f"✅ Stats obtenidas: {stats}")
        except Exception as e:
            debug_info.append(f"❌ Error obteniendo stats: {str(e)}")
            debug_info.append(f"Traceback: {traceback.format_exc()}")
            stats = None

        # Si stats es None, devolver debug info
        if stats is None:
            return HttpResponse("<br>".join(debug_info), content_type="text/html")

        # Intentar renderizar template
        context = {
            'stats': stats,
            'page_title': 'CRM Dashboard',
        }
        return render(request, 'ventas/crm/dashboard.html', context)

    except Exception as e:
        logger.error(f"Error en CRM dashboard: {e}")
        error_trace = traceback.format_exc()
        return HttpResponse(f"<h1>Error 500</h1><pre>{error_trace}</pre>", content_type="text/html", status=500)


# @login_required  # TEMPORALMENTE DESHABILITADO PARA TESTING
def crm_buscar(request):
    """
    Búsqueda de clientes
    """
    query = request.GET.get('q', '')
    resultados = []

    if query and len(query) >= 3:
        try:
            resultados = CRMService.buscar_clientes(query)
        except Exception as e:
            logger.error(f"Error buscando clientes: {e}")
            messages.error(request, f"Error en búsqueda: {str(e)}")

    context = {
        'query': query,
        'resultados': resultados,
        'page_title': 'Buscar Cliente',
    }
    return render(request, 'ventas/crm/buscar.html', context)


# @login_required  # TEMPORALMENTE DESHABILITADO PARA TESTING
def cliente_detalle(request, cliente_id):
    """
    Vista 360° del cliente con historial completo y propuesta personalizada
    """
    try:
        # Obtener perfil 360
        perfil = CRMService.get_customer_360(cliente_id)

        context = {
            'perfil': perfil,
            'cliente': perfil['cliente'],
            'page_title': f"Cliente: {perfil['cliente']['nombre']}",
        }
        return render(request, 'ventas/crm/cliente_detalle.html', context)

    except ValueError as e:
        messages.error(request, str(e))
        return redirect('crm_buscar')
    except Exception as e:
        logger.error(f"Error obteniendo perfil de cliente {cliente_id}: {e}")
        messages.error(request, f"Error cargando cliente: {str(e)}")
        return redirect('crm_buscar')


# @login_required  # TEMPORALMENTE DESHABILITADO PARA TESTING
@csrf_exempt  # TEMPORALMENTE DESHABILITADO PARA TESTING
@require_http_methods(["POST"])
def generar_propuesta(request, cliente_id):
    """
    Genera propuesta personalizada usando IA (DeepSeek o fallback)
    Soporta dos estilos: 'formal' (default) y 'calido'
    """
    try:
        # Obtener estilo del request (formal por defecto)
        import json as json_lib
        try:
            body = json_lib.loads(request.body.decode('utf-8')) if request.body else {}
            estilo = body.get('estilo', 'formal')
        except:
            estilo = request.POST.get('estilo', 'formal')

        # Log para debugging
        logger.info(f"Generando propuesta para cliente {cliente_id} con estilo: {estilo}")

        # Usar servicio de IA local
        ai_service = get_ai_service()
        propuesta = ai_service.generar_propuesta(cliente_id, estilo=estilo)

        # Log de confirmación
        logger.info(f"Propuesta generada exitosamente con estilo: {estilo}")

        return JsonResponse({
            'success': True,
            'propuesta': propuesta,
            'estilo': estilo
        })

    except Exception as e:
        logger.error(f"Error generando propuesta para cliente {cliente_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# @login_required  # TEMPORALMENTE DESHABILITADO PARA TESTING
@csrf_exempt  # TEMPORALMENTE DESHABILITADO PARA TESTING
@require_http_methods(["POST"])
def enviar_propuesta(request, cliente_id):
    """
    Genera y envía propuesta por email con asunto dinámico
    """
    try:
        # Obtener estilo del request (formal por defecto)
        import json as json_lib
        try:
            body = json_lib.loads(request.body.decode('utf-8')) if request.body else {}
            estilo = body.get('estilo', 'formal')
        except:
            estilo = request.POST.get('estilo', 'formal')

        # Obtener perfil del cliente
        perfil = CRMService.get_customer_360(cliente_id)
        cliente = perfil['cliente']

        # Validar que el cliente tenga email
        if not cliente['email']:
            return JsonResponse({
                'success': False,
                'error': 'El cliente no tiene email registrado'
            }, status=400)

        # Generar propuesta con IA (con estilo)
        ai_service = get_ai_service()
        propuesta = ai_service.generar_propuesta(cliente_id, estilo=estilo)

        # Usar asunto dinámico de la propuesta (o fallback)
        subject = propuesta.get('email_subject', 'Propuesta Personalizada - Aremko')
        message = "Por favor visualiza este mensaje en un cliente que soporte HTML."
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [cliente['email']]

        # Enviar email HTML
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=propuesta['email_body'],
            fail_silently=False
        )

        logger.info(f"Propuesta enviada exitosamente a {cliente['email']} (Cliente ID: {cliente_id}) con asunto: {subject}")
        messages.success(request, f"Propuesta enviada exitosamente a {cliente['email']}")

        return JsonResponse({
            'success': True,
            'message': 'Propuesta enviada exitosamente',
            'email': cliente['email']
        })

    except Exception as e:
        logger.error(f"Error enviando propuesta a cliente {cliente_id}: {e}")
        messages.error(request, f"Error enviando propuesta: {str(e)}")

        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def propuesta_preview(request, cliente_id):
    """
    Preview de propuesta antes de enviar
    """
    try:
        # Generar propuesta con IA
        ai_service = get_ai_service()
        propuesta = ai_service.generar_propuesta(cliente_id)
        perfil = CRMService.get_customer_360(cliente_id)

        context = {
            'propuesta': propuesta,
            'cliente': perfil['cliente'],
            'email_html': propuesta.get('email_body', ''),
            'page_title': 'Preview de Propuesta',
        }
        return render(request, 'ventas/crm/propuesta_preview.html', context)

    except Exception as e:
        logger.error(f"Error generando preview para cliente {cliente_id}: {e}")
        messages.error(request, f"Error generando preview: {str(e)}")
        return redirect('cliente_detalle', cliente_id=cliente_id)


@login_required
def historial_servicios(request, cliente_id):
    """
    Historial completo de servicios de un cliente
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    historial = ServiceHistory.objects.filter(cliente=cliente).order_by('-service_date')

    # Paginación simple
    page_size = 50
    page = int(request.GET.get('page', 1))
    start = (page - 1) * page_size
    end = start + page_size

    historial_paginado = historial[start:end]
    has_next = historial.count() > end

    context = {
        'cliente': cliente,
        'historial': historial_paginado,
        'page': page,
        'has_next': has_next,
        'page_title': f'Historial: {cliente.nombre}',
    }
    return render(request, 'ventas/crm/historial.html', context)


# ====================================================================================
# ENVÍO MASIVO DE EMAILS CON IA
# ====================================================================================

@login_required
def bulk_email_sender_view(request):
    """
    Vista principal para envío masivo de emails con IA
    Segmentación SIMPLIFICADA - Solo por gasto (sin contar visitas)
    """
    from django.db.models import Count, Sum
    from django.db.models.functions import Coalesce
    from django.db import models as django_models

    # Thresholds de gasto
    SPEND_THRESHOLD_MEDIUM = 50000
    SPEND_THRESHOLD_HIGH = 150000

    segments = {
        'low_spend': {'label': 'Bajo Gasto (< $50,000)', 'count': 0},
        'medium_spend': {'label': 'Gasto Medio ($50,000 - $150,000)', 'count': 0},
        'high_spend': {'label': 'Alto Gasto (> $150,000)', 'count': 0},
        'zero_spend': {'label': 'Sin Gasto Registrado', 'count': 0},
    }

    # Calcular conteos de clientes por segmento
    clientes = Cliente.objects.annotate(
        total_spend=Coalesce(Sum('ventareserva__total'), 0, output_field=django_models.DecimalField())
    )

    for cliente in clientes:
        spend = float(cliente.total_spend)

        if spend == 0:
            segments['zero_spend']['count'] += 1
        elif spend < SPEND_THRESHOLD_MEDIUM:
            segments['low_spend']['count'] += 1
        elif spend < SPEND_THRESHOLD_HIGH:
            segments['medium_spend']['count'] += 1
        else:
            segments['high_spend']['count'] += 1

    context = {
        'segments': segments,
        'total_clients': clientes.count(),
        'page_title': 'Envío Masivo de Emails con IA',
    }

    return render(request, 'ventas/crm/bulk_email_sender.html', context)


@login_required
@require_http_methods(["POST"])
def bulk_email_send_view(request):
    """
    Vista AJAX para enviar emails masivos con IA
    Genera propuestas automáticamente y envía en lote
    Segmentación SIMPLIFICADA - Solo por gasto (sin contar visitas)
    """
    import json
    from django.db.models import Count, Sum
    from django.db.models.functions import Coalesce
    from django.db import models as django_models

    try:
        data = json.loads(request.body)
        segment = data.get('segment')
        estilo = data.get('estilo', 'calido')
        limit = int(data.get('limit', 50))  # Límite de envíos por batch

        if not segment:
            return JsonResponse({'success': False, 'error': 'Segmento no especificado'})

        # Thresholds de gasto
        SPEND_THRESHOLD_MEDIUM = 50000
        SPEND_THRESHOLD_HIGH = 150000

        # Filtrar clientes según segmento
        clientes = Cliente.objects.annotate(
            total_spend=Coalesce(Sum('ventareserva__total'), 0, output_field=django_models.DecimalField())
        ).filter(email__isnull=False).exclude(email='')

        # Aplicar filtro de segmento (SOLO POR GASTO)
        filtered_clients = []
        for cliente in clientes:
            spend = float(cliente.total_spend)

            include = False

            if segment == 'low_spend':
                include = 0 < spend < SPEND_THRESHOLD_MEDIUM
            elif segment == 'medium_spend':
                include = SPEND_THRESHOLD_MEDIUM <= spend < SPEND_THRESHOLD_HIGH
            elif segment == 'high_spend':
                include = spend >= SPEND_THRESHOLD_HIGH
            elif segment == 'zero_spend':
                include = spend == 0

            if include:
                filtered_clients.append(cliente)
                if len(filtered_clients) >= limit:
                    break

        # Enviar emails
        success_count = 0
        error_count = 0
        errors = []

        ai_service = get_ai_service()

        for cliente in filtered_clients:
            try:
                # Generar propuesta con IA
                propuesta = ai_service.generar_propuesta(cliente.id, estilo=estilo)

                # Enviar email
                send_mail(
                    subject=propuesta['email_subject'],
                    message='',  # No se usa en HTML
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[cliente.email],
                    html_message=propuesta['email_body'],
                    fail_silently=False,
                )

                success_count += 1
                logger.info(f"Email enviado a {cliente.email} ({estilo})")

            except Exception as e:
                error_count += 1
                error_msg = f"{cliente.email}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Error enviando email a {cliente.email}: {e}")

        return JsonResponse({
            'success': True,
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors[:10],  # Máximo 10 errores para mostrar
            'total_sent': success_count,
        })

    except Exception as e:
        logger.error(f"Error en bulk_email_send_view: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@require_http_methods(["POST"])
def whatsapp_propuesta(request, cliente_id):
    """
    Genera un mensaje de WhatsApp basado en la propuesta personalizada
    """
    import json
    from bs4 import BeautifulSoup
    import re

    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        data = json.loads(request.body)
        estilo = data.get('estilo', 'formal')
        propuesta = data.get('propuesta', {})

        # Extraer el contenido del email HTML
        email_body = propuesta.get('email_body', '')

        # Parsear el HTML con BeautifulSoup
        soup = BeautifulSoup(email_body, 'html.parser')

        # Iniciar mensaje
        nombre_cliente = cliente.nombre.split()[0] if estilo == 'calido' else cliente.nombre

        if estilo == 'calido':
            mensaje = f"Hola {nombre_cliente} 👋\n\n"
        else:
            mensaje = f"Estimado/a {cliente.nombre},\n\n"

        # Variables para almacenar partes del mensaje
        narrativa_servicios = ""
        consecuencia_texto = ""
        oferta_completa = ""
        validez_texto = ""
        familia_aremko_texto = ""

        # Extraer cada parte específica del email
        parrafos = soup.find_all('p')

        for p in parrafos:
            texto = p.get_text().strip()

            # Buscar narrativa de servicios
            if 'recordar' in texto and any(s in texto for s in ['tinajas', 'cabañas', 'momentos']):
                narrativa_servicios = texto

            # Buscar "En consecuencia"
            elif texto.startswith('En consecuencia') or 'consecuencia' in texto:
                consecuencia_texto = texto

            # Buscar párrafo de validez
            elif 'beneficios son válidos' in texto or 'válidos durante' in texto:
                validez_texto = texto

            # Buscar párrafo "no eres un cliente más"
            elif 'no eres un cliente más' in texto or 'familia Aremko' in texto:
                familia_aremko_texto = texto

        # Buscar la oferta en el div destacado
        for div in soup.find_all('div', style=lambda value: value and ('background-color' in value or 'border' in value)):
            texto_div = div.get_text().strip()
            if 'Invitación exclusiva' in texto_div or 'descuento' in texto_div.lower():
                # Limpiar espacios múltiples
                oferta_completa = re.sub(r'\s+', ' ', texto_div)
                break

        # Construir el mensaje en el orden correcto
        if narrativa_servicios:
            mensaje += f"{narrativa_servicios}\n\n"

        if consecuencia_texto:
            mensaje += f"{consecuencia_texto}\n\n"

        if oferta_completa:
            mensaje += f"🎁 *OFERTA ESPECIAL:*\n{oferta_completa}\n\n"

        if validez_texto:
            mensaje += f"{validez_texto}\n\n"

        if familia_aremko_texto:
            mensaje += f"{familia_aremko_texto}\n\n"

        # Call to action
        if estilo == 'calido':
            mensaje += "¿Te gustaría reservar? ¡Estamos aquí para consentirte! 💆‍♀️\n\n"
        else:
            mensaje += "Para realizar su reserva o consultas, estamos a su disposición.\n\n"

        # Firma
        mensaje += "📱 Reservas: +56 9 5790 2525\n"
        mensaje += "🌐 www.aremko.cl"

        # Limpiar teléfono
        telefono = cliente.telefono
        if telefono:
            telefono = ''.join(filter(str.isdigit, str(telefono)))
            if telefono.startswith('569'):
                telefono = telefono[2:]
            elif telefono.startswith('56'):
                telefono = telefono[2:]
            elif telefono.startswith('9'):
                telefono = telefono

        return JsonResponse({
            'success': True,
            'mensaje': mensaje,
            'telefono': telefono,
            'cliente_nombre': cliente.nombre
        })

    except Exception as e:
        logger.error(f"Error generando mensaje WhatsApp: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# SISTEMA DE MENSAJES WHATSAPP PERSONALIZADOS CON IA (GPT-4o)
# ============================================================================

@login_required
@require_http_methods(["POST"])
def generar_mensaje_whatsapp_ia(request, cliente_id):
    """
    Genera mensaje personalizado de WhatsApp usando IA GPT-4o
    Analiza perfil 360° del cliente y genera mensaje contextualizado
    """
    try:
        from ventas.services.whatsapp_message_service import WhatsAppMessageService

        # Generar mensaje con IA
        resultado = WhatsAppMessageService.generar_mensaje_whatsapp(cliente_id)

        if resultado['success']:
            logger.info(f"Mensaje WhatsApp IA generado para cliente {cliente_id} - Perfil: {resultado['perfil']}")
            return JsonResponse(resultado)
        else:
            return JsonResponse(resultado, status=500)

    except Exception as e:
        logger.error(f"Error generando mensaje WhatsApp IA para cliente {cliente_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f"Error generando mensaje: {str(e)}"
        }, status=500)


@login_required
def preview_mensaje_whatsapp(request, cliente_id):
    """
    Vista para mostrar preview del mensaje WhatsApp generado con IA
    Muestra modal con el mensaje, perfil detectado y opciones para copiar/enviar
    """
    try:
        from ventas.services.whatsapp_message_service import WhatsAppMessageService
        from ventas.services.crm_service import CRMService

        # Obtener datos del cliente
        datos_360 = CRMService.get_customer_360(cliente_id)
        cliente = datos_360['cliente']

        # Generar mensaje
        resultado = WhatsAppMessageService.generar_mensaje_whatsapp(cliente_id)

        if not resultado['success']:
            messages.error(request, f"Error generando mensaje: {resultado.get('error', 'Error desconocido')}")
            return redirect('ventas:cliente_detalle', cliente_id=cliente_id)

        return render(request, 'ventas/crm/whatsapp_preview.html', {
            'cliente': cliente,
            'mensaje': resultado['mensaje'],
            'perfil': resultado['perfil'],
            'perfil_nombre': resultado['perfil_nombre'],
            'telefono': resultado['telefono'],
            'telefono_limpio': resultado['telefono_limpio'],
            'whatsapp_url': resultado['whatsapp_url'],
            'datos_360': datos_360
        })

    except Exception as e:
        logger.error(f"Error en preview mensaje WhatsApp: {e}", exc_info=True)
        messages.error(request, f"Error: {str(e)}")
        return redirect('ventas:cliente_detalle', cliente_id=cliente_id)


@login_required
def clientes_historicos_inactivos(request):
    """
    Vista de listado de clientes históricos que no han comprado recientemente
    Incluye filtro por cantidad de meses sin visita
    """
    try:
        # Obtener parámetro de filtro (default: 12 meses)
        meses_sin_visita = int(request.GET.get('meses', 12))

        # Validar rango (mínimo 1 mes, máximo 60 meses)
        if meses_sin_visita < 1:
            meses_sin_visita = 1
        elif meses_sin_visita > 60:
            meses_sin_visita = 60

        # Obtener clientes inactivos
        clientes_inactivos = CRMService.get_clientes_historicos_inactivos(meses_sin_visita)

        context = {
            'clientes_inactivos': clientes_inactivos,
            'meses_filtro': meses_sin_visita,
            'total_clientes': len(clientes_inactivos),
            'page_title': 'Clientes Históricos Inactivos'
        }

        return render(request, 'ventas/crm/clientes_inactivos.html', context)

    except Exception as e:
        logger.error(f"Error en listado de clientes inactivos: {e}", exc_info=True)
        messages.error(request, f"Error cargando listado: {str(e)}")
        return redirect('ventas:crm_dashboard')
