# -*- coding: utf-8 -*-
"""
Vistas para el sistema avanzado de campañas de email marketing
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import user_passes_test
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q, Count, Sum, Max
from django.core.paginator import Paginator
from datetime import date, datetime
import calendar
import json

from ventas.models import (
    EmailCampaign, EmailRecipient, Cliente, VentaReserva, 
    ReservaServicio, EmailBlacklist
)
from ventas.services.ai_service import generate_personalized_content, ai_service
from ventas.views.admin_views import es_administrador


@login_required
@user_passes_test(es_administrador)
def campaign_list_view(request):
    """Vista de lista de campañas de email"""
    campaigns = EmailCampaign.objects.all().order_by('-created_at')
    
    # Paginación
    paginator = Paginator(campaigns, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'campaigns': page_obj,
        'title': 'Campañas de Email Marketing'
    }
    return render(request, 'admin/campaign_list.html', context)


@login_required
@user_passes_test(es_administrador)
def campaign_create_view(request):
    """Vista para crear una nueva campaña"""
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            
            # Criterios de selección
            month = int(request.POST.get('month', 1))
            year = int(request.POST.get('year', 2025))
            spend_min = request.POST.get('spend_min', '')
            spend_max = request.POST.get('spend_max', '')
            visit_count_min = request.POST.get('visit_count_min', '')
            visit_count_max = request.POST.get('visit_count_max', '')
            cities = request.POST.getlist('cities')
            
            # Configuración de envío
            start_time = request.POST.get('start_time', '08:00')
            end_time = request.POST.get('end_time', '18:00')
            batch_size = int(request.POST.get('batch_size', 2))
            interval_minutes = int(request.POST.get('interval_minutes', 6))
            
            # Template de email
            email_subject = request.POST.get('email_subject', '')
            email_body = request.POST.get('email_body', '')
            
            # Configuración avanzada
            ai_variation = request.POST.get('ai_variation') == 'on'
            anti_spam = request.POST.get('anti_spam') == 'on'
            
            # Validaciones
            if not name:
                messages.error(request, "El nombre de la campaña es obligatorio")
                return redirect('ventas:campaign_create')
            
            if not email_subject or not email_body:
                messages.error(request, "El asunto y cuerpo del email son obligatorios")
                return redirect('ventas:campaign_create')
            
            # Crear criterios JSON
            criteria = {
                'month': month,
                'year': year
            }
            
            if spend_min:
                criteria['spend_min'] = float(spend_min)
            if spend_max:
                criteria['spend_max'] = float(spend_max)
            if visit_count_min:
                criteria['visit_count_min'] = int(visit_count_min)
            if visit_count_max:
                criteria['visit_count_max'] = int(visit_count_max)
            if cities:
                criteria['cities'] = cities
            
            # Crear configuración de horarios JSON
            schedule_config = {
                'start_time': start_time,
                'end_time': end_time,
                'batch_size': batch_size,
                'interval_minutes': interval_minutes,
                'timezone': 'America/Santiago'
            }
            
            # Crear la campaña
            campaign = EmailCampaign.objects.create(
                name=name,
                description=description,
                criteria=criteria,
                schedule_config=schedule_config,
                email_subject_template=email_subject,
                email_body_template=email_body,
                ai_variation_enabled=ai_variation,
                anti_spam_enabled=anti_spam,
                created_by=request.user,
                status='draft'
            )
            
            try:
                messages.success(request, f"✅ Campaña '{name}' creada exitosamente")
            except:
                pass  # Ignore message errors in tests
            return redirect('ventas:campaign_review', campaign_id=campaign.id)
            
        except Exception as e:
            try:
                messages.error(request, f"❌ Error creando campaña: {str(e)}")
            except:
                pass  # Ignore message errors in tests
            return redirect('ventas:campaign_create')
    
    # GET request - mostrar formulario
    context = {
        'title': 'Crear Nueva Campaña',
        'years': range(2023, 2027),
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'cities': get_client_cities(),
        'current_year': date.today().year,
        'current_month': date.today().month,
    }
    return render(request, 'admin/campaign_create.html', context)


@login_required
@user_passes_test(es_administrador)
def campaign_review_view(request, campaign_id):
    """Vista para revisar y modificar la lista de destinatarios"""
    campaign = get_object_or_404(EmailCampaign, id=campaign_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'generate_recipients':
            # Generar lista de destinatarios
            try:
                generated_count = generate_campaign_recipients(campaign)
                try:
                    messages.success(request, f"✅ {generated_count} destinatarios generados")
                except:
                    pass
            except Exception as e:
                try:
                    messages.error(request, f"❌ Error generando destinatarios: {str(e)}")
                except:
                    pass
        
        elif action == 'update_recipients':
            # Actualizar habilitación de destinatarios
            recipient_ids = request.POST.getlist('enabled_recipients')
            
            # Deshabilitar todos
            EmailRecipient.objects.filter(campaign=campaign).update(send_enabled=False)
            
            # Habilitar seleccionados
            if recipient_ids:
                EmailRecipient.objects.filter(
                    campaign=campaign, 
                    id__in=recipient_ids
                ).update(send_enabled=True)
            
            try:
                messages.success(request, f"✅ Lista de destinatarios actualizada")
            except:
                pass
        
        elif action == 'finalize_campaign':
            # Finalizar campaña y marcar como lista para envío
            enabled_count = EmailRecipient.objects.filter(
                campaign=campaign, 
                send_enabled=True
            ).count()
            
            if enabled_count == 0:
                try:
                    messages.error(request, "❌ Debe habilitar al menos un destinatario")
                except:
                    pass
            else:
                campaign.total_recipients = enabled_count
                campaign.status = 'ready'
                campaign.save()
                
                try:
                    messages.success(request, f"✅ Campaña lista para envío con {enabled_count} destinatarios")
                except:
                    pass
                return redirect('ventas:campaign_detail', campaign_id=campaign.id)
    
    # Obtener destinatarios paginados
    recipients = EmailRecipient.objects.filter(campaign=campaign).order_by('priority', 'name')
    
    # Filtros
    status_filter = request.GET.get('status', 'all')
    enabled_filter = request.GET.get('enabled', 'all')
    
    if status_filter != 'all':
        recipients = recipients.filter(status=status_filter)
    if enabled_filter == 'enabled':
        recipients = recipients.filter(send_enabled=True)
    elif enabled_filter == 'disabled':
        recipients = recipients.filter(send_enabled=False)
    
    # Paginación
    paginator = Paginator(recipients, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    stats = {
        'total': EmailRecipient.objects.filter(campaign=campaign).count(),
        'enabled': EmailRecipient.objects.filter(campaign=campaign, send_enabled=True).count(),
        'disabled': EmailRecipient.objects.filter(campaign=campaign, send_enabled=False).count(),
    }
    
    context = {
        'campaign': campaign,
        'recipients': page_obj,
        'stats': stats,
        'title': f'Revisar Campaña: {campaign.name}',
        'status_filter': status_filter,
        'enabled_filter': enabled_filter,
    }
    return render(request, 'admin/campaign_review.html', context)


@login_required
@user_passes_test(es_administrador)
def campaign_detail_view(request, campaign_id):
    """Vista de detalle y monitoreo de campaña"""
    campaign = get_object_or_404(EmailCampaign, id=campaign_id)
    
    # Estadísticas detalladas
    recipients_by_status = EmailRecipient.objects.filter(campaign=campaign).values('status').annotate(count=Count('id'))
    status_stats = {item['status']: item['count'] for item in recipients_by_status}
    
    context = {
        'campaign': campaign,
        'status_stats': status_stats,
        'title': f'Campaña: {campaign.name}',
    }
    return render(request, 'admin/campaign_detail.html', context)


def get_client_cities():
    """Obtiene lista de ciudades únicas de los clientes"""
    cities = Cliente.objects.filter(
        ciudad__isnull=False
    ).exclude(
        ciudad=''
    ).values_list('ciudad', flat=True).distinct().order_by('ciudad')
    
    return list(cities)


def generate_campaign_recipients(campaign):
    """Genera la lista de destinatarios basada en los criterios de la campaña"""
    criteria = campaign.criteria
    
    # Filtro base por fecha de reserva
    month = criteria.get('month', 1)
    year = criteria.get('year', 2025)
    
    month_start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    month_end = date(year, month, last_day)
    
    # Query base
    clients_query = Cliente.objects.filter(
        ventareserva__reservaservicios__fecha_agendamiento__range=(month_start, month_end),
        email__isnull=False,
        email__gt=''
    ).exclude(email='').distinct()
    
    # Filtros opcionales por gasto (SOLO del mes específico)
    if 'spend_min' in criteria or 'spend_max' in criteria:
        # Calcular gasto total por cliente SOLO en el mes especificado
        clients_with_spend = clients_query.annotate(
            total_spend=Sum(
                'ventareserva__total',
                filter=Q(ventareserva__reservaservicios__fecha_agendamiento__range=(month_start, month_end))
            )
        )
        
        if 'spend_min' in criteria:
            clients_with_spend = clients_with_spend.filter(
                total_spend__gte=criteria['spend_min']
            )
        
        if 'spend_max' in criteria:
            clients_with_spend = clients_with_spend.filter(
                total_spend__lte=criteria['spend_max']
            )
        
        clients_query = clients_with_spend
    
    # Filtros opcionales por número de visitas
    if 'visit_count_min' in criteria or 'visit_count_max' in criteria:
        clients_with_visits = clients_query.annotate(
            visit_count=Count('ventareserva__reservaservicios', distinct=True)
        )
        
        if 'visit_count_min' in criteria:
            clients_with_visits = clients_with_visits.filter(
                visit_count__gte=criteria['visit_count_min']
            )
        
        if 'visit_count_max' in criteria:
            clients_with_visits = clients_with_visits.filter(
                visit_count__lte=criteria['visit_count_max']
            )
        
        clients_query = clients_with_visits
    
    # Filtro opcional por ciudades
    if 'cities' in criteria and criteria['cities']:
        clients_query = clients_query.filter(ciudad__in=criteria['cities'])
    
    # Excluir emails en lista negra
    blacklisted_emails = EmailBlacklist.objects.filter(
        is_active=True
    ).values_list('email', flat=True)
    
    clients_query = clients_query.exclude(email__in=blacklisted_emails)
    
    # Limpiar destinatarios existentes de forma segura
    EmailRecipient.objects.filter(campaign=campaign).delete()
    
    # Crear destinatarios con manejo de duplicados
    recipients_created = 0
    for client in clients_query:
        # Calcular datos adicionales del cliente
        client_spend = VentaReserva.objects.filter(cliente=client).aggregate(
            total=Sum('total')
        )['total'] or 0
        
        client_visits = ReservaServicio.objects.filter(
            venta_reserva__cliente=client
        ).count()
        
        last_visit = ReservaServicio.objects.filter(
            venta_reserva__cliente=client
        ).aggregate(
            last_date=Max('fecha_agendamiento')
        )['last_date']
        
        # NUEVA ARQUITECTURA: Guardar templates sin procesar para IA en tiempo real
        # La personalización y IA se harán durante el envío, no aquí
        personalized_subject = campaign.email_subject_template  # Template crudo
        personalized_body = campaign.email_body_template        # Template crudo

        # Crear destinatario con manejo de duplicados
        try:
            EmailRecipient.objects.create(
                campaign=campaign,
                client=client,
                email=client.email,
                name=client.nombre,
                personalized_subject=personalized_subject,
                personalized_body=personalized_body,
                send_enabled=True,
                priority=1,
                client_total_spend=client_spend,
                client_visit_count=client_visits,
                client_last_visit=last_visit,
                client_city=client.ciudad or ''
            )
            recipients_created += 1
        except Exception as e:
            # Skip duplicates or other errors
            continue
    
    return recipients_created


@login_required
@user_passes_test(es_administrador)
def campaign_preview_recipients_ajax(request):
    """Vista AJAX para previsualizar destinatarios antes de crear la campaña"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        # Obtener criterios del request
        month = int(request.POST.get('month', 1))
        year = int(request.POST.get('year', 2025))
        spend_min = request.POST.get('spend_min', '')
        spend_max = request.POST.get('spend_max', '')
        visit_count_min = request.POST.get('visit_count_min', '')
        visit_count_max = request.POST.get('visit_count_max', '')
        cities = request.POST.getlist('cities')
        
        # Crear criterios temporales
        criteria = {'month': month, 'year': year}
        if spend_min:
            criteria['spend_min'] = float(spend_min)
        if spend_max:
            criteria['spend_max'] = float(spend_max)
        if visit_count_min:
            criteria['visit_count_min'] = int(visit_count_min)
        if visit_count_max:
            criteria['visit_count_max'] = int(visit_count_max)
        if cities:
            criteria['cities'] = cities
        
        # Crear campaña temporal para preview
        temp_campaign = EmailCampaign(criteria=criteria)
        
        # Generar preview (sin crear en DB)
        count = preview_campaign_recipients(temp_campaign)
        
        return JsonResponse({
            'success': True,
            'recipient_count': count,
            'message': f'{count} destinatarios encontrados con estos criterios'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


def preview_campaign_recipients(campaign):
    """Preview de destinatarios sin crear en DB"""
    criteria = campaign.criteria
    
    # Misma lógica que generate_campaign_recipients pero solo cuenta
    month = criteria.get('month', 1)
    year = criteria.get('year', 2025)
    
    month_start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    month_end = date(year, month, last_day)
    
    clients_query = Cliente.objects.filter(
        ventareserva__reservaservicios__fecha_agendamiento__range=(month_start, month_end),
        email__isnull=False,
        email__gt=''
    ).exclude(email='').distinct()
    
    # Aplicar filtros opcionales (SOLO del mes específico)
    if 'spend_min' in criteria or 'spend_max' in criteria:
        clients_with_spend = clients_query.annotate(
            total_spend=Sum(
                'ventareserva__total',
                filter=Q(ventareserva__reservaservicios__fecha_agendamiento__range=(month_start, month_end))
            )
        )
        
        if 'spend_min' in criteria:
            clients_with_spend = clients_with_spend.filter(
                total_spend__gte=criteria['spend_min']
            )
        
        if 'spend_max' in criteria:
            clients_with_spend = clients_with_spend.filter(
                total_spend__lte=criteria['spend_max']
            )
        
        clients_query = clients_with_spend
    
    if 'visit_count_min' in criteria or 'visit_count_max' in criteria:
        clients_with_visits = clients_query.annotate(
            visit_count=Count('ventareserva__reservaservicios', distinct=True)
        )
        
        if 'visit_count_min' in criteria:
            clients_with_visits = clients_with_visits.filter(
                visit_count__gte=criteria['visit_count_min']
            )
        
        if 'visit_count_max' in criteria:
            clients_with_visits = clients_with_visits.filter(
                visit_count__lte=criteria['visit_count_max']
            )
        
        clients_query = clients_with_visits
    
    if 'cities' in criteria and criteria['cities']:
        clients_query = clients_query.filter(ciudad__in=criteria['cities'])
    
    # Excluir lista negra
    blacklisted_emails = EmailBlacklist.objects.filter(
        is_active=True
    ).values_list('email', flat=True)
    
    clients_query = clients_query.exclude(email__in=blacklisted_emails)
    
    return clients_query.count()


@login_required
@user_passes_test(es_administrador)
def test_ai_service_ajax(request):
    """Vista AJAX para probar el servicio de IA"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        test_subject = request.POST.get('subject', '🎁 ¡Tu giftcard de $15,000 te espera!')
        test_body = request.POST.get('body', 'Hola {nombre_cliente}, tenemos una sorpresa especial para ti...')
        client_name = request.POST.get('client_name', 'María González')
        
        # Verificar estado del servicio
        status = ai_service.get_status()
        
        if not status['enabled'] or not status['api_key_configured']:
            return JsonResponse({
                'success': False,
                'error': 'Servicio de IA no configurado correctamente',
                'status': status
            })
        
        # Generar variaciones
        subject_variations = ai_service.generate_subject_variations(test_subject, 3)
        body_variation = ai_service.generate_body_variations(test_body, client_name)
        
        # Generar contenido personalizado completo
        final_subject, final_body = generate_personalized_content(
            test_subject, test_body, client_name
        )
        
        return JsonResponse({
            'success': True,
            'service_status': status,
            'results': {
                'original_subject': test_subject,
                'subject_variations': subject_variations,
                'original_body': test_body,
                'body_variation': body_variation,
                'final_subject': final_subject,
                'final_body': final_body
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'service_status': ai_service.get_status()
        }, status=500)