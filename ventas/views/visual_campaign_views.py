# -*- coding: utf-8 -*-
"""
Vistas para el NUEVO sistema de campañas visuales (EmailCampaignTemplate).
Sistema simplificado con interfaz de cards y editor visual.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import Context, Template
from django.conf import settings
from django.utils import timezone
from django.views.decorators.http import require_POST

from ventas.models import EmailCampaignTemplate, CampaignSendLog, NewsletterSubscriber
import logging
import threading
import time

logger = logging.getLogger(__name__)


def is_staff_user(user):
    """Verifica que el usuario sea staff o admin"""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_staff_user)
def visual_campaign_dashboard(request):
    """Dashboard visual con cards de todas las campañas"""
    try:
        campañas = EmailCampaignTemplate.objects.all()
        
        # Estadísticas generales
        total_campaigns = campañas.count()
        active_campaigns = campañas.filter(status='sending').count()
        completed_campaigns = campañas.filter(status='completed').count()
        
        context = {
            'campañas': campañas,
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'completed_campaigns': completed_campaigns,
            'site_header': 'Aremko Admin',
            'site_title': 'Aremko Admin',
            'has_permission': True,
        }
        
        return render(request, 'ventas/crm/campanias/visual_dashboard.html', context)
    except Exception as e:
        logger.error(f"Error en visual_campaign_dashboard: {e}")
        messages.error(request, f"Error cargando dashboard: {e}")
        return redirect('admin:index')


@login_required
@user_passes_test(is_staff_user)
def visual_campaign_create(request):
    """Crear nueva campaña visual"""
    if request.method == 'POST':
        try:
            # Cargar template base si se selecciona
            template_type = request.POST.get('template_type', 'blank')
            html_content = ''
            
            if template_type == 'giftcard_digital':
                try:
                    with open(settings.BASE_DIR / 'templates/emails/giftcard_digital_launch.html', 'r') as f:
                        html_content = f.read()
                except:
                    html_content = ''
            
            campaign = EmailCampaignTemplate.objects.create(
                name=request.POST.get('name', 'Nueva Campaña'),
                subject=request.POST.get('subject', ''),
                html_content=html_content or request.POST.get('html_content', ''),
                preview_text=request.POST.get('preview_text', ''),
                audience_type='all',  # Por defecto todos
                created_by=request.user,
                status='draft'
            )
            
            messages.success(request, f'Campaña "{campaign.name}" creada exitosamente.')
            return redirect('visual_campaign_edit', pk=campaign.pk)
            
        except Exception as e:
            logger.error(f'Error creando campaña: {e}')
            messages.error(request, f'Error al crear la campaña: {str(e)}')
            return redirect('visual_campaign_dashboard')
    
    # GET - Mostrar modal/formulario de creación
    context = {
        'site_header': 'Aremko Admin',
        'site_title': 'Aremko Admin',
    }
    return render(request, 'ventas/crm/campanias/visual_create.html', context)


@login_required
@user_passes_test(is_staff_user)
def visual_campaign_edit(request, pk):
    """Editar campaña visual"""
    campaign = get_object_or_404(EmailCampaignTemplate, pk=pk)
    
    if request.method == 'POST':
        if not campaign.can_edit():
            messages.error(request, 'No se puede editar una campaña en este estado.')
            return redirect('visual_campaign_dashboard')
        
        try:
            campaign.name = request.POST.get('name', campaign.name)
            campaign.subject = request.POST.get('subject', campaign.subject)
            campaign.html_content = request.POST.get('html_content', campaign.html_content)
            campaign.preview_text = request.POST.get('preview_text', campaign.preview_text)
            campaign.batch_size = int(request.POST.get('batch_size', 25))
            campaign.batch_delay_minutes = int(request.POST.get('batch_delay_minutes', 15))
            
            # Actualizar estado si se solicita
            if request.POST.get('mark_as_ready'):
                campaign.status = 'ready'
                # Calcular destinatarios
                campaign.total_recipients = NewsletterSubscriber.objects.filter(is_active=True).count()
            
            campaign.save()
            messages.success(request, 'Campaña actualizada exitosamente.')
            
        except Exception as e:
            logger.error(f'Error actualizando campaña {pk}: {e}')
            messages.error(request, f'Error al actualizar: {str(e)}')
    
    context = {
        'campaign': campaign,
        'total_subs': NewsletterSubscriber.objects.filter(is_active=True).count(),
        'site_header': 'Aremko Admin',
        'site_title': 'Aremko Admin',
    }
    
    return render(request, 'ventas/crm/campanias/visual_edit.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_POST
def visual_campaign_send_test(request, pk):
    """Envía un email de prueba"""
    campaign = get_object_or_404(EmailCampaignTemplate, pk=pk)
    
    try:
        template = Template(campaign.html_content)
        context_data = {
            'nombre': request.user.first_name or 'Usuario',
            'email': request.user.email,
        }
        html_content = template.render(Context(context_data))

        # Agregar footer con link de unsubscribe
        from ventas.utils.email_footer import get_email_footer_html
        html_content_con_footer = html_content + get_email_footer_html(request.user.email)

        email = EmailMultiAlternatives(
            subject=f'[PRUEBA] {campaign.subject}',
            body='Este es un email de prueba.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[request.user.email],
        )
        email.attach_alternative(html_content_con_footer, "text/html")
        email.send()
        
        messages.success(request, f'Email de prueba enviado a {request.user.email}')
        
    except Exception as e:
        logger.error(f'Error enviando email de prueba: {e}')
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('visual_campaign_edit', pk=pk)


@login_required
@user_passes_test(is_staff_user)
def visual_campaign_start(request, pk):
    """Inicia el envío de la campaña"""
    campaign = get_object_or_404(EmailCampaignTemplate, pk=pk)
    
    if request.method == 'POST':
        if not campaign.can_send():
            messages.error(request, 'La campaña no puede ser enviada.')
            return redirect('visual_campaign_dashboard')
        
        try:
            campaign.status = 'sending'
            campaign.started_at = timezone.now()
            campaign.save()
            
            # Iniciar en background
            thread = threading.Thread(target=send_visual_campaign_async, args=(campaign.pk,))
            thread.daemon = True
            thread.start()
            
            messages.success(request, f'Campaña iniciada. Se enviará en background.')
            return redirect('visual_campaign_stats', pk=pk)
            
        except Exception as e:
            logger.error(f'Error iniciando campaña {pk}: {e}')
            campaign.status = 'ready'
            campaign.save()
            messages.error(request, f'Error: {str(e)}')
    
    # GET - Mostrar confirmación
    context = {
        'campaign': campaign,
        'site_header': 'Aremko Admin',
        'site_title': 'Aremko Admin',
    }
    return render(request, 'ventas/crm/campanias/visual_confirm_send.html', context)


def send_visual_campaign_async(campaign_pk):
    """Envío async en background"""
    campaign = EmailCampaignTemplate.objects.get(pk=campaign_pk)
    
    try:
        destinatarios = NewsletterSubscriber.objects.filter(is_active=True)
        total = destinatarios.count()
        campaign.total_recipients = total
        campaign.save()
        
        template = Template(campaign.html_content)
        batch_delay = campaign.batch_delay_minutes * 60
        
        for i, subscriber in enumerate(destinatarios):
            try:
                context_data = {
                    'nombre': subscriber.first_name or 'Cliente',
                    'email': subscriber.email,
                }
                html_content = template.render(Context(context_data))

                # Agregar footer con link de unsubscribe
                from ventas.utils.email_footer import get_email_footer_html
                html_content_con_footer = html_content + get_email_footer_html(subscriber.email)

                email = EmailMultiAlternatives(
                    subject=campaign.subject,
                    body='Active visualización HTML.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[subscriber.email],
                )
                email.attach_alternative(html_content_con_footer, "text/html")
                email.send()
                
                CampaignSendLog.objects.create(
                    campaign=campaign,
                    recipient_email=subscriber.email,
                    recipient_name=subscriber.get_full_name(),
                    status='sent',
                    sent_at=timezone.now()
                )
                
                campaign.emails_sent += 1
                campaign.save()
                
                # Delay entre lotes
                if (i + 1) % campaign.batch_size == 0 and (i + 1) < total:
                    logger.info(f'Lote completado. Esperando {campaign.batch_delay_minutes} min...')
                    time.sleep(batch_delay)
                    
            except Exception as e:
                logger.error(f'Error enviando a {subscriber.email}: {e}')
                CampaignSendLog.objects.create(
                    campaign=campaign,
                    recipient_email=subscriber.email,
                    recipient_name=subscriber.get_full_name(),
                    status='failed',
                    error_message=str(e)
                )
        
        campaign.status = 'completed'
        campaign.completed_at = timezone.now()
        campaign.save()
        
        logger.info(f'Campaña {campaign_pk} completada.')
        
    except Exception as e:
        logger.error(f'Error fatal en campaña {campaign_pk}: {e}')
        campaign.status = 'paused'
        campaign.save()


@login_required
@user_passes_test(is_staff_user)
def visual_campaign_stats(request, pk):
    """Estadísticas de la campaña"""
    campaign = get_object_or_404(EmailCampaignTemplate, pk=pk)
    
    recent_logs = campaign.send_logs.all()[:100]
    
    from django.db.models import Count
    status_stats = campaign.send_logs.values('status').annotate(count=Count('id'))
    
    context = {
        'campaign': campaign,
        'recent_logs': recent_logs,
        'status_stats': status_stats,
        'site_header': 'Aremko Admin',
        'site_title': 'Aremko Admin',
    }
    
    return render(request, 'ventas/crm/campanias/visual_stats.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_POST
def visual_campaign_pause(request, pk):
    """Pausa una campaña"""
    campaign = get_object_or_404(EmailCampaignTemplate, pk=pk)
    
    if campaign.can_pause():
        campaign.status = 'paused'
        campaign.save()
        messages.success(request, 'Campaña pausada.')
    else:
        messages.error(request, 'No se puede pausar.')
    
    return redirect('visual_campaign_stats', pk=pk)


@login_required
@user_passes_test(is_staff_user)
@require_POST
def visual_campaign_delete(request, pk):
    """Elimina una campaña"""
    campaign = get_object_or_404(EmailCampaignTemplate, pk=pk)

    if campaign.status in ['draft', 'completed', 'cancelled']:
        name = campaign.name
        campaign.delete()
        messages.success(request, f'Campaña "{name}" eliminada.')
    else:
        messages.error(request, 'No se puede eliminar una campaña activa.')

    return redirect('visual_campaign_dashboard')


@login_required
@user_passes_test(is_staff_user)
@require_POST
def resume_all_campaigns(request):
    """
    Ejecuta el comando enviar_campana_email --auto para reanudar campañas.
    Este comando busca campañas con status 'ready' o 'sending' y las procesa.
    """
    try:
        from django.core.management import call_command
        from io import StringIO

        # Capturar la salida del comando
        output = StringIO()

        # Ejecutar el comando en segundo plano
        call_command('enviar_campana_email', '--auto', stdout=output)

        # Obtener el resultado
        result = output.getvalue()

        messages.success(
            request,
            '✅ Proceso de reanudación de campañas iniciado. '
            'Las campañas pendientes o en proceso serán procesadas automáticamente.'
        )
        logger.info(f'Usuario {request.user.username} ejecutó resume_all_campaigns. Output: {result}')

    except Exception as e:
        logger.error(f'Error ejecutando resume_all_campaigns: {e}')
        messages.error(request, f'Error al reanudar campañas: {str(e)}')

    return redirect('ventas:visual_campaign_dashboard')
