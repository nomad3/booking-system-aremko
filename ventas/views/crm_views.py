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
    Genera y envía propuesta por email
    """
    try:
        # Obtener perfil del cliente
        perfil = CRMService.get_customer_360(cliente_id)
        cliente = perfil['cliente']

        # Validar que el cliente tenga email
        if not cliente['email']:
            return JsonResponse({
                'success': False,
                'error': 'El cliente no tiene email registrado'
            }, status=400)

        # Generar propuesta con IA
        ai_service = get_ai_service()
        propuesta = ai_service.generar_propuesta(cliente_id)

        # Enviar email
        subject = f"Propuesta Personalizada - Aremko"
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

        logger.info(f"Propuesta enviada exitosamente a {cliente['email']} (Cliente ID: {cliente_id})")
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
