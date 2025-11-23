# -*- coding: utf-8 -*-
"""
Vista mejorada para crear campañas de email desde segmentación de clientes
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.db import transaction
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from ventas.models import Cliente, EmailCampaign, EmailRecipient
import json


def es_administrador(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(es_administrador)
@require_http_methods(["POST"])
def create_email_campaign_from_segment(request):
    """
    Vista mejorada para crear una campaña de email desde clientes segmentados
    
    Flujo:
    1. Recibe IDs de clientes seleccionados
    2. Muestra modal para crear/seleccionar campaña
    3. Permite editar template
    4. Crea EmailCampaign y EmailRecipients
    5. Redirige a vista de confirmación
    """
    
    # Obtener IDs de clientes seleccionados
    selected_clients_string = request.POST.get('selected_clients', '')
    
    if not selected_clients_string:
        messages.error(request, _("No se seleccionaron clientes."))
        return HttpResponseRedirect(reverse('ventas:cliente_segmentation'))
    
    # Parsear IDs
    try:
        selected_client_ids = [
            int(client_id) 
            for client_id in selected_clients_string.split(',') 
            if client_id.isdigit()
        ]
    except ValueError:
        messages.error(request, _("IDs de clientes inválidos."))
        return HttpResponseRedirect(reverse('ventas:cliente_segmentation'))
    
    # Obtener clientes
    clientes = Cliente.objects.filter(id__in=selected_client_ids)
    
    if not clientes.exists():
        messages.error(request, _("No se encontraron clientes con los IDs proporcionados."))
        return HttpResponseRedirect(reverse('ventas:cliente_segmentation'))
    
    # Preparar datos de clientes para la vista
    clientes_data = []
    for cliente in clientes:
        gasto_total = cliente.ventareserva_set.aggregate(
            total=Sum('total')
        )['total'] or 0
        
        primer_nombre = cliente.nombre.split()[0] if cliente.nombre else 'Cliente'
        
        clientes_data.append({
            'id': cliente.id,
            'nombre_completo': cliente.nombre,
            'primer_nombre': primer_nombre,
            'email': cliente.email,
            'gasto_total': gasto_total,
            'visitas': cliente.ventareserva_set.count(),
            'ciudad': cliente.ciudad or 'N/A'
        })
    
    # Si es una petición AJAX para obtener datos de clientes
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'clientes': clientes_data,
            'total': len(clientes_data)
        })
    
    # Renderizar página de creación de campaña
    context = {
        'clientes': clientes_data,
        'clientes_json': json.dumps(clientes_data),
        'total_clientes': len(clientes_data),
        'selected_client_ids': selected_client_ids,
        'selected_clients_string': selected_clients_string,
    }
    
    return render(request, 'ventas/email_campaign_creator.html', context)


@login_required
@user_passes_test(es_administrador)
@require_http_methods(["POST"])
def save_email_campaign(request):
    """
    Guarda la campaña de email y crea los destinatarios
    """
    
    try:
        # Obtener datos del formulario
        campaign_name = request.POST.get('campaign_name', '').strip()
        email_subject = request.POST.get('email_subject', '').strip()
        email_body = request.POST.get('email_body', '').strip()
        selected_clients_string = request.POST.get('selected_clients', '')
        
        # Validaciones
        if not campaign_name:
            return JsonResponse({
                'success': False,
                'error': 'El nombre de la campaña es obligatorio'
            }, status=400)
        
        if not email_subject:
            return JsonResponse({
                'success': False,
                'error': 'El asunto del email es obligatorio'
            }, status=400)
        
        if not email_body:
            return JsonResponse({
                'success': False,
                'error': 'El cuerpo del email es obligatorio'
            }, status=400)
        
        if not selected_clients_string:
            return JsonResponse({
                'success': False,
                'error': 'No se seleccionaron clientes'
            }, status=400)
        
        # Parsear IDs de clientes
        selected_client_ids = [
            int(client_id) 
            for client_id in selected_clients_string.split(',') 
            if client_id.isdigit()
        ]
        
        # Obtener configuración de envío
        schedule_config = {
            "start_time": request.POST.get('start_time', '08:00'),
            "end_time": request.POST.get('end_time', '21:00'),
            "batch_size": int(request.POST.get('batch_size', 5)),
            "interval_minutes": int(request.POST.get('interval_minutes', 6)),
            "ai_enabled": request.POST.get('ai_enabled') == 'true'
        }
        
        with transaction.atomic():
            # Crear EmailCampaign
            campaign = EmailCampaign.objects.create(
                name=campaign_name,
                email_subject_template=email_subject,
                email_body_template=email_body,
                status='draft',
                schedule_config=schedule_config,
                ai_variation_enabled=schedule_config['ai_enabled'],
                created_by=request.user
            )
            
            # Crear EmailRecipients
            clientes = Cliente.objects.filter(id__in=selected_client_ids)
            recipients_created = 0
            
            for cliente in clientes:
                # Calcular datos del cliente
                gasto_total = cliente.ventareserva_set.aggregate(
                    total=Sum('total')
                )['total'] or 0
                
                # Extraer primer nombre
                primer_nombre = cliente.nombre.split()[0] if cliente.nombre else 'Cliente'
                
                # Personalizar contenido
                subject = email_subject.replace('{nombre_cliente}', primer_nombre)
                body = email_body.replace('{nombre_cliente}', primer_nombre)
                body = body.replace('{gasto_total}', f'{gasto_total:,.0f}')
                
                # Crear destinatario
                EmailRecipient.objects.create(
                    campaign=campaign,
                    client=cliente,
                    email=cliente.email,
                    name=primer_nombre,
                    personalized_subject=subject,
                    personalized_body=body,
                    client_total_spend=gasto_total,
                    client_visit_count=cliente.ventareserva_set.count(),
                    client_last_visit=cliente.ventareserva_set.order_by('-fecha_reserva').first().fecha_reserva if cliente.ventareserva_set.exists() else None,
                    client_city=cliente.ciudad or 'N/A',
                    status='pending',
                    send_enabled=True,
                    priority=1
                )
                recipients_created += 1
            
            # Actualizar total de destinatarios en la campaña
            campaign.total_recipients = recipients_created
            campaign.save()
        
        return JsonResponse({
            'success': True,
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'recipients_created': recipients_created,
            'redirect_url': reverse('ventas:email_campaign_preview', args=[campaign.id])
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(es_administrador)
def email_campaign_preview(request, campaign_id):
    """
    Vista de previa de la campaña antes de enviar
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
    except EmailCampaign.DoesNotExist:
        messages.error(request, _("Campaña no encontrada."))
        return HttpResponseRedirect(reverse('ventas:cliente_segmentation'))
    
    # Obtener destinatarios
    recipients = campaign.recipients.all()
    
    # Obtener un destinatario de ejemplo para vista previa
    sample_recipient = recipients.first()
    
    context = {
        'campaign': campaign,
        'recipients': recipients,
        'sample_recipient': sample_recipient,
        'total_recipients': recipients.count(),
    }
    
    return render(request, 'ventas/email_campaign_preview.html', context)


@login_required
@user_passes_test(es_administrador)
@require_http_methods(["POST"])
def send_email_campaign(request, campaign_id):
    """
    Inicia el envío de la campaña
    """
    try:
        campaign = EmailCampaign.objects.get(id=campaign_id)
    except EmailCampaign.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Campaña no encontrada'
        }, status=404)
    
    # Cambiar estado a ready
    campaign.status = 'ready'
    campaign.save()
    
    # Ejecutar comando de envío en background
    from django.core.management import call_command
    import threading
    
    def send_campaign():
        call_command('enviar_campana_email', campaign_id=campaign_id)
    
    thread = threading.Thread(target=send_campaign)
    thread.daemon = True
    thread.start()
    
    return JsonResponse({
        'success': True,
        'message': f'Campaña "{campaign.name}" iniciada. Los emails se enviarán en lotes.',
        'campaign_id': campaign.id
    })
