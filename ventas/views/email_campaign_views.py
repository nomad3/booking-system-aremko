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
from django.core.serializers.json import DjangoJSONEncoder

from ventas.models import Cliente, EmailCampaign, EmailRecipient, CampaignEmailTemplate
import json
import logging

# Configurar logger
logger = logging.getLogger(__name__)


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

    try:
        logger.info("=== Iniciando create_email_campaign_from_segment ===")

        # Obtener IDs de clientes seleccionados
        selected_clients_string = request.POST.get('selected_clients', '')
        logger.info(f"Selected clients string: {selected_clients_string}")

        if not selected_clients_string:
            logger.warning("No se seleccionaron clientes")
            messages.error(request, _("No se seleccionaron clientes."))
            return HttpResponseRedirect(reverse('ventas:cliente_segmentation'))

        # Parsear IDs
        try:
            selected_client_ids = [
                int(client_id)
                for client_id in selected_clients_string.split(',')
                if client_id.isdigit()
            ]
            logger.info(f"Parsed {len(selected_client_ids)} client IDs")
        except ValueError as e:
            logger.error(f"Error parseando IDs: {str(e)}")
            messages.error(request, _("IDs de clientes inválidos."))
            return HttpResponseRedirect(reverse('ventas:cliente_segmentation'))

        # Obtener clientes
        logger.info(f"Buscando {len(selected_client_ids)} clientes en la base de datos")
        clientes = Cliente.objects.filter(id__in=selected_client_ids)
        logger.info(f"Encontrados {clientes.count()} clientes")

        if not clientes.exists():
            logger.warning("No se encontraron clientes con los IDs proporcionados")
            messages.error(request, _("No se encontraron clientes con los IDs proporcionados."))
            return HttpResponseRedirect(reverse('ventas:cliente_segmentation'))

        # Preparar datos de clientes para la vista
        logger.info("Preparando datos de clientes")
        clientes_data = []
        for cliente in clientes:
            # Saltar clientes sin email
            if not cliente.email or cliente.email.strip() == '':
                continue

            try:
                gasto_total = cliente.gasto_total()


                # Obtener primer nombre de forma segura
                nombre_completo = (cliente.nombre or 'Cliente').strip()
                primer_nombre = nombre_completo.split()[0] if nombre_completo and ' ' in nombre_completo else nombre_completo

                # Obtener ubicación (preferir comuna sobre ciudad)
                ubicacion = 'N/A'
                if cliente.comuna:
                    ubicacion = cliente.comuna.nombre
                elif cliente.ciudad:
                    ubicacion = cliente.ciudad

                clientes_data.append({
                    'id': cliente.id,
                    'nombre_completo': nombre_completo,
                    'primer_nombre': primer_nombre,
                    'email': cliente.email.strip(),
                    'gasto_total': gasto_total,
                    'visitas': cliente.ventareserva_set.count(),
                    'ciudad': ubicacion
                })
            except Exception as e:
                # Log el error pero continua con el siguiente cliente
                logger.error(f"Error procesando cliente {cliente.id}: {str(e)}")
                continue

        # Verificar que haya al menos un cliente válido con email
        logger.info(f"Procesados {len(clientes_data)} clientes válidos con email")
        if not clientes_data:
            logger.warning("Ninguno de los clientes tiene email válido")
            messages.error(request, _("Ninguno de los clientes seleccionados tiene email válido. No se puede crear la campaña."))
            return HttpResponseRedirect(reverse('ventas:cliente_segmentation'))

        # Si es una petición AJAX para obtener datos de clientes
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            logger.info("Petición AJAX, retornando JSON")
            return JsonResponse({
                'clientes': clientes_data,
                'total': len(clientes_data)
            })

        # Renderizar página de creación de campaña
        logger.info("Renderizando página de creación de campaña")

        # Cargar template por defecto si existe (safe para cuando la tabla no existe aún)
        default_template = None
        try:
            default_template = CampaignEmailTemplate.objects.filter(is_default=True, is_active=True).first()
        except Exception as e:
            logger.warning(f"No se pudo cargar CampaignEmailTemplate (tabla aún no existe?): {e}")

        context = {
            'clientes': clientes_data,
            'clientes_json': json.dumps(clientes_data, cls=DjangoJSONEncoder),
            'total_clientes': len(clientes_data),
            'selected_client_ids': selected_client_ids,
            'selected_clients_string': selected_clients_string,
            'default_template': default_template,
        }

        return render(request, 'ventas/email_campaign_creator.html', context)

    except Exception as e:
        logger.error(f"ERROR CRÍTICO en create_email_campaign_from_segment: {str(e)}", exc_info=True)
        messages.error(request, f"Error al procesar la solicitud: {str(e)}")
        return HttpResponseRedirect(reverse('ventas:cliente_segmentation'))


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

            # OPTIMIZACIÓN: Crear EmailRecipients usando bulk_create
            # En lugar de procesar uno por uno, crear todos de una vez
            clientes = Cliente.objects.filter(
                id__in=selected_client_ids
            ).select_related('comuna').only(
                'id', 'nombre', 'email', 'ciudad', 'comuna'
            )

            recipients_to_create = []
            recipients_created = 0

            for cliente in clientes:
                # Saltar clientes sin email
                if not cliente.email or cliente.email.strip() == '':
                    continue

                try:
                    # Obtener primer nombre de forma segura
                    nombre_completo = (cliente.nombre or 'Cliente').strip()
                    primer_nombre = nombre_completo.split()[0] if nombre_completo and ' ' in nombre_completo else nombre_completo

                    # Personalizar contenido (sin {gasto_total} por ahora para velocidad)
                    subject = email_subject.replace('{nombre_cliente}', primer_nombre)
                    body = email_body.replace('{nombre_cliente}', primer_nombre)
                    # Dejar placeholder de gasto_total para calcular después
                    body = body.replace('{gasto_total}', '[Gasto Total]')

                    # Obtener ubicación (preferir comuna sobre ciudad)
                    ubicacion = 'N/A'
                    if cliente.comuna:
                        ubicacion = cliente.comuna.nombre
                    elif cliente.ciudad:
                        ubicacion = cliente.ciudad

                    # OPTIMIZACIÓN: Crear objeto sin guardarlo todavía
                    recipients_to_create.append(EmailRecipient(
                        campaign=campaign,
                        client=cliente,
                        email=cliente.email.strip(),
                        name=primer_nombre,
                        personalized_subject=subject,
                        personalized_body=body,
                        client_total_spend=0,  # Se calculará después en background
                        client_visit_count=0,  # Se calculará después en background
                        client_last_visit=None,  # Se calculará después en background
                        client_city=ubicacion,
                        status='pending',
                        send_enabled=True,
                        priority=1
                    ))

                    recipients_created += 1
                except Exception as e:
                    # Log el error pero continua con el siguiente cliente
                    logger.error(f"Error creando destinatario para cliente {cliente.id}: {str(e)}")
                    continue

            # OPTIMIZACIÓN: Guardar todos los recipients de una vez usando bulk_create
            if recipients_to_create:
                EmailRecipient.objects.bulk_create(recipients_to_create, batch_size=500)
                logger.info(f"✅ Creados {len(recipients_to_create)} EmailRecipients usando bulk_create")

            # Validar que se haya creado al menos un destinatario
            if recipients_created == 0:
                # Eliminar la campaña si no hay destinatarios
                campaign.delete()
                return JsonResponse({
                    'success': False,
                    'error': 'Ninguno de los clientes seleccionados tiene email válido o se pudo procesar correctamente.'
                }, status=400)

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
