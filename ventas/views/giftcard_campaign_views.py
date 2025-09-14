# -*- coding: utf-8 -*-
"""
Vistas para la campaña de giftcard de clientes de enero 2025
"""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import user_passes_test
from django.http import JsonResponse
from django.utils import timezone
from django.urls import reverse
from datetime import date
from django.db.models import Q, Count, Sum
from ventas.models import Cliente, VentaReserva, ReservaServicio, MailParaEnviar, Campaign, EmailTemplate
from ventas.views.admin_views import es_administrador


@login_required
@user_passes_test(es_administrador)
def giftcard_campaign_dashboard(request):
    """Dashboard para la campaña de giftcard flexible por mes/año"""
    
    try:
        # Obtener parámetros de la URL o usar defaults
        year = int(request.GET.get('year', 2025))
        month = int(request.GET.get('month', 1))
        giftcard_amount = int(request.GET.get('giftcard_amount', 15000))
        
        # Validar mes
        if month < 1 or month > 12:
            month = 1
            year = 2025
        
        # Obtener estadísticas de clientes del mes/año especificado
        import calendar
        month_start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        month_end = date(year, month, last_day)
        month_name = calendar.month_name[month]
    except Exception as e:
        # Si hay error en parámetros, usar defaults
        year = 2025
        month = 1
        giftcard_amount = 15000
        import calendar
        month_start = date(2025, 1, 1)
        month_end = date(2025, 1, 31)
        month_name = "Enero"
    
    try:
        # Clientes que visitaron en el mes/año especificado
        clientes_mes = Cliente.objects.filter(
            ventareserva__reservaservicios__fecha_agendamiento__range=(month_start, month_end)
        ).annotate(
            num_visitas_mes=Count('ventareserva__reservaservicios', 
                                filter=Q(ventareserva__reservaservicios__fecha_agendamiento__range=(month_start, month_end))),
            gasto_mes=Sum('ventareserva__total', 
                        filter=Q(ventareserva__reservaservicios__fecha_agendamiento__range=(month_start, month_end)))
        ).distinct()
        
        # Clientes con email válido
        clientes_con_email = clientes_mes.filter(
            email__isnull=False,
            email__gt=''
        ).exclude(email='')
    except Exception as e:
        # Si hay error en la consulta, usar valores por defecto
        clientes_mes = Cliente.objects.none()
        clientes_con_email = Cliente.objects.none()
    
    try:
        # Estadísticas de emails enviados
        emails_enviados = MailParaEnviar.objects.filter(
            asunto__icontains='giftcard',
            estado='ENVIADO'
        ).count()
        
        emails_pendientes = MailParaEnviar.objects.filter(
            asunto__icontains='giftcard',
            estado='PENDIENTE'
        ).count()
        
        emails_fallidos = MailParaEnviar.objects.filter(
            asunto__icontains='giftcard',
            estado='FALLIDO'
        ).count()
        
        # Clientes que aún no han recibido el email
        clientes_sin_email = clientes_con_email.exclude(
            id__in=MailParaEnviar.objects.filter(
                asunto__icontains='giftcard',
                estado__in=['ENVIADO', 'PENDIENTE']
            ).values_list('cliente_id', flat=True)
        )
    except Exception as e:
        # Si hay error en las estadísticas, usar valores por defecto
        emails_enviados = 0
        emails_pendientes = 0
        emails_fallidos = 0
        clientes_sin_email = clientes_con_email
    
    # Top clientes del mes
    top_clientes = clientes_con_email.order_by('-gasto_mes')[:10]
    
    # Estadísticas generales
    gasto_total_mes = clientes_con_email.aggregate(
        total=Sum('gasto_mes')
    )['total'] or 0
    
    gasto_promedio = clientes_con_email.aggregate(
        avg=Sum('gasto_mes') / Count('id')
    )['avg'] or 0
    
    context = {
        'title': f'Campaña Giftcard - Clientes {month_name} {year}',
        'year': year,
        'month': month,
        'month_name': month_name,
        'giftcard_amount': giftcard_amount,
        'clientes_mes_total': clientes_mes.count(),
        'clientes_con_email': clientes_con_email.count(),
        'clientes_sin_email': clientes_sin_email.count(),
        'emails_enviados': emails_enviados,
        'emails_pendientes': emails_pendientes,
        'emails_fallidos': emails_fallidos,
        'gasto_total_mes': gasto_total_mes,
        'gasto_promedio': gasto_promedio,
        'top_clientes': top_clientes,
        'month_start': month_start,
        'month_end': month_end,
    }
    
    return render(request, 'admin/giftcard_campaign_dashboard.html', context)


@login_required
@user_passes_test(es_administrador)
def create_giftcard_campaign(request):
    """Crea la campaña de giftcard automáticamente"""
    
    if request.method == 'POST':
        try:
            # Obtener parámetros
            year = int(request.POST.get('year', 2025))
            month = int(request.POST.get('month', 1))
            giftcard_amount = int(request.POST.get('giftcard_amount', 15000))
            
            import calendar
            month_name = calendar.month_name[month]
            
            # Crear o actualizar campaña
            campaign_name = f"Giftcard Septiembre - Clientes {month_name} {year}"
            campaign, created = Campaign.objects.get_or_create(
                name=campaign_name,
                defaults={
                    'description': f'Campaña especial para clientes que visitaron en {month_name} {year}, ofreciendo giftcard de ${giftcard_amount:,} para usar en septiembre',
                    'status': 'Planning',
                    'goal': f'Reactivar clientes de {month_name} con oferta especial de giftcard',
                    'email_subject_template': f'🎁 ¡Tu giftcard de ${giftcard_amount:,} te espera en Aremko!',
                    'email_body_template': get_giftcard_email_template(giftcard_amount),
                    'target_min_visits': 1,
                    'target_min_spend': 0
                }
            )
            
            if created:
                messages.success(request, f"✅ Campaña creada: {campaign.name}")
            else:
                messages.info(request, f"ℹ️ Campaña ya existe: {campaign.name}")
            
            return redirect('ventas:giftcard_campaign_dashboard')
            
        except Exception as e:
            messages.error(request, f"❌ Error creando campaña: {str(e)}")
            return redirect('ventas:giftcard_campaign_dashboard')
    
    # Si es GET, redirigir al dashboard con parámetros
    year = request.GET.get('year', 2025)
    month = request.GET.get('month', 1)
    giftcard_amount = request.GET.get('giftcard_amount', 15000)
    
    return redirect(f"{reverse('ventas:giftcard_campaign_dashboard')}?year={year}&month={month}&giftcard_amount={giftcard_amount}")


@login_required
@user_passes_test(es_administrador)
def send_test_giftcard_email(request):
    """Envía un email de prueba de la campaña de giftcard"""
    
    if request.method == 'POST':
        test_email = request.POST.get('test_email', '').strip()
        year = int(request.POST.get('year', 2025))
        month = int(request.POST.get('month', 1))
        giftcard_amount = int(request.POST.get('giftcard_amount', 15000))
        
        if not test_email:
            messages.error(request, "❌ Debes proporcionar un email de prueba")
            return redirect('ventas:giftcard_campaign_dashboard')
        
        try:
            # Intentar cargar el template guardado
            try:
                saved_template = EmailTemplate.objects.get(
                    name=f"Giftcard {year}/{month:02d} - ${giftcard_amount:,}",
                    year=year, month=month, giftcard_amount=giftcard_amount,
                    campaign_type='giftcard', is_active=True
                )
                subject = saved_template.subject
                body_html = saved_template.body_html
                print(f"✅ Usando template guardado: {saved_template.name}")
            except EmailTemplate.DoesNotExist:
                # Usar template por defecto si no hay guardado
                template = get_giftcard_email_template()
                subject = f"🎁 ¡Tu giftcard de ${giftcard_amount:,} te espera en Aremko!"
                body_html = template.replace('$15,000', f'${giftcard_amount:,}')
                print("⚠️ Usando template por defecto (no hay guardado)")
            
            # Enviar email de prueba
            from django.core.mail import EmailMultiAlternatives
            from django.conf import settings
            
            from_email = getattr(settings, 'EMAIL_HOST_USER', 'ventas@aremko.cl')
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=body_html,
                from_email=from_email,
                to=[test_email],
                bcc=['aremkospa@gmail.com', 'ventas@aremko.cl'],
                reply_to=['ventas@aremko.cl']
            )
            
            email.attach_alternative(body_html, "text/html")
            
            # Log para debugging
            print(f"DEBUG: Enviando email de prueba a {test_email}")
            print(f"DEBUG: From: {from_email}")
            print(f"DEBUG: Subject: {subject}")
            print(f"DEBUG: Usando template guardado: {saved_template.name if 'saved_template' in locals() else 'No'}")
            
            email.send()
            
            messages.success(request, f"✅ Email de prueba enviado a {test_email}")
            
        except Exception as e:
            print(f"ERROR: Error enviando email de prueba: {str(e)}")
            messages.error(request, f"❌ Error enviando email de prueba: {str(e)}")
    
    return redirect('ventas:giftcard_campaign_dashboard')


@login_required
@user_passes_test(es_administrador)
def preview_giftcard_email(request):
    """Muestra una vista previa del email de la campaña de giftcard"""
    
    try:
        # Obtener parámetros
        year = int(request.GET.get('year', 2025))
        month = int(request.GET.get('month', 1))
        giftcard_amount = int(request.GET.get('giftcard_amount', 15000))
        
        # Validar mes
        if month < 1 or month > 12:
            month = 1
            year = 2025
        
        import calendar
        month_name = calendar.month_name[month]
        
        # Buscar template guardado o usar el por defecto
        template_name = f"Giftcard {year}/{month:02d} - ${giftcard_amount:,}"
        try:
            saved_template = EmailTemplate.objects.get(
                name=template_name,
                year=year,
                month=month,
                giftcard_amount=giftcard_amount,
                campaign_type='giftcard',
                is_active=True
            )
            subject = saved_template.subject
            body_html = saved_template.body_html
        except EmailTemplate.DoesNotExist:
            # Usar template por defecto
            template = get_giftcard_email_template()
            subject = f"🎁 ¡Tu giftcard de ${giftcard_amount:,} te espera en Aremko!"
            body_html = template.replace('$15,000', f'${giftcard_amount:,}')
        
        context = {
            'title': f'Vista Previa - Campaña Giftcard {month_name} {year}',
            'subject': subject,
            'body_html': body_html,
            'year': year,
            'month': month,
            'month_name': month_name,
            'giftcard_amount': giftcard_amount,
        }
        
        return render(request, 'admin/giftcard_email_preview.html', context)
        
    except Exception as e:
        messages.error(request, f"❌ Error generando vista previa: {str(e)}")
        return redirect('ventas:giftcard_campaign_dashboard')


@login_required
@user_passes_test(es_administrador)
def save_email_template(request):
    """Guarda los cambios del template de email"""
    
    if request.method == 'POST':
        try:
            subject = request.POST.get('subject', '')
            body_html = request.POST.get('body_html', '')
            year = int(request.POST.get('year', 2025))
            month = int(request.POST.get('month', 1))
            giftcard_amount = int(request.POST.get('giftcard_amount', 15000))
            
            # Crear o actualizar el template
            template_name = f"Giftcard {year}/{month:02d} - ${giftcard_amount:,}"
            
            template, created = EmailTemplate.objects.get_or_create(
                name=template_name,
                year=year,
                month=month,
                giftcard_amount=giftcard_amount,
                campaign_type='giftcard',
                defaults={
                    'subject': subject,
                    'body_html': body_html,
                    'is_active': True
                }
            )
            
            if not created:
                # Actualizar template existente
                template.subject = subject
                template.body_html = body_html
                template.updated_at = timezone.now()
                template.save()
            
            if created:
                messages.success(request, f"✅ Template creado: {template_name}")
            else:
                messages.success(request, f"✅ Template actualizado: {template_name}")
            
            # Redirigir de vuelta a la vista previa con los parámetros
            return redirect(f"{reverse('ventas:preview_giftcard_email')}?year={year}&month={month}&giftcard_amount={giftcard_amount}")
            
        except Exception as e:
            print(f"ERROR: Error guardando template: {str(e)}")
            messages.error(request, f"❌ Error guardando template: {str(e)}")
            return redirect('ventas:giftcard_campaign_dashboard')
    
    return redirect('ventas:giftcard_campaign_dashboard')


def get_giftcard_email_template(giftcard_amount=15000):
    """Retorna la plantilla de email para la campaña de giftcard"""
    return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Giftcard Especial - Aremko Hotel Spa</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            line-height: 1.6; 
            color: #333; 
            margin: 0; 
            padding: 0; 
            background-color: #f5f5f5;
        }
        .container { 
            max-width: 600px; 
            margin: 0 auto; 
            background: #fff; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header { 
            background: #4a90e2; 
            color: white; 
            padding: 40px 30px; 
            text-align: center; 
        }
        .header h1 { 
            margin: 0; 
            font-size: 2.2em; 
            font-weight: bold; 
        }
        .header h2 { 
            margin: 10px 0 5px 0; 
            font-size: 1.4em; 
            font-weight: normal; 
        }
        .header p { 
            margin: 0; 
            font-size: 1.1em; 
            opacity: 0.9; 
        }
        .content { 
            padding: 40px 30px; 
            background: #fff; 
        }
        .giftcard { 
            background: #fff; 
            border: 3px dashed #28a745; 
            padding: 30px 20px; 
            margin: 30px 0; 
            text-align: center; 
            border-radius: 8px;
        }
        .giftcard h3 { 
            margin: 0 0 15px 0; 
            font-size: 1.3em; 
            color: #333; 
        }
        .giftcard-amount { 
            font-size: 3.5em; 
            font-weight: bold; 
            color: #28a745; 
            margin: 15px 0; 
            text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
        }
        .giftcard-validity { 
            font-size: 1.2em; 
            font-weight: bold; 
            color: #6f42c1; 
            margin: 10px 0; 
        }
        .giftcard-conditions { 
            color: #666; 
            font-size: 0.95em; 
            margin: 10px 0; 
        }
        .highlight { 
            background: #fff3cd; 
            padding: 25px; 
            border-left: 4px solid #ffc107; 
            margin: 30px 0; 
            border-radius: 0 8px 8px 0;
        }
        .highlight h4 { 
            margin: 0 0 15px 0; 
            font-size: 1.2em; 
            color: #333; 
        }
        .highlight ul { 
            margin: 0; 
            padding-left: 20px; 
        }
        .highlight li { 
            margin: 8px 0; 
            color: #555; 
        }
        .instructions { 
            background: #f8f9fa; 
            padding: 25px; 
            margin: 30px 0; 
            border-radius: 8px; 
        }
        .instructions h4 { 
            margin: 0 0 15px 0; 
            font-size: 1.2em; 
            color: #333; 
        }
        .instructions ol { 
            margin: 0; 
            padding-left: 20px; 
        }
        .instructions li { 
            margin: 10px 0; 
            color: #555; 
        }
        .cta-button { 
            background: #28a745; 
            color: white; 
            padding: 18px 35px; 
            text-decoration: none; 
            border-radius: 8px; 
            display: inline-block; 
            margin: 25px 0; 
            font-weight: bold; 
            font-size: 1.1em;
            box-shadow: 0 2px 4px rgba(40,167,69,0.3);
        }
        .cta-button:hover { 
            background: #218838; 
        }
        .services-list { 
            background: #e9ecef; 
            padding: 25px; 
            margin: 30px 0; 
            border-radius: 8px; 
        }
        .services-list h4 { 
            margin: 0 0 15px 0; 
            font-size: 1.2em; 
            color: #333; 
        }
        .services-list ul { 
            margin: 0; 
            padding-left: 20px; 
        }
        .services-list li { 
            margin: 10px 0; 
            color: #555; 
        }
        .footer { 
            text-align: center; 
            margin-top: 40px; 
            color: #666; 
            font-size: 0.9em; 
            padding: 30px; 
            background: #f8f9fa; 
        }
        .footer p { 
            margin: 5px 0; 
        }
        .footer strong { 
            color: #333; 
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏨 Aremko Hotel Spa</h1>
            <h2>¡Hola {nombre_cliente}!</h2>
            <p>Esperamos que hayas disfrutado tu visita en enero</p>
        </div>
        
        <div class="content">
            <p>Tenemos una sorpresa especial para ti que sabemos que te va a encantar:</p>
            
            <div class="giftcard">
                <h3>🎁 Tu Giftcard Especial</h3>
                <div class="giftcard-amount">$15,000</div>
                <div class="giftcard-validity">⏰ Válida solo durante septiembre 2025</div>
                <div class="giftcard-conditions">🏊‍♀️ Válida únicamente para Tinas Calientes y Cabañas</div>
            </div>
            
            <div class="highlight">
                <h4>📋 Términos y Condiciones:</h4>
                <ul>
                    <li><strong>🏊‍♀️ Servicios:</strong> Válida únicamente para Tinas Calientes y Cabañas</li>
                    <li><strong>📅 Validez:</strong> Solo durante septiembre 2025</li>
                    <li><strong>🚫 No acumulable:</strong> No se puede sumar a otras promociones</li>
                    <li><strong>👤 Intransferible:</strong> Solo la puede usar el titular de la reserva</li>
                </ul>
            </div>
            
            <div class="instructions">
                <h4>📞 ¿Cómo cobrar la Gift Card?</h4>
                <p style="margin: 0 0 15px 0; color: #555; font-size: 1.1em;">
                    <strong>Escribe por WhatsApp al +56 9 5790 2525 o por correo a ventas@aremko.cl</strong> 
                    para solicitar tu reserva y hacer uso de esta gift card.
                </p>
                <ol>
                    <li>Contacta por WhatsApp o email para reservar tu cita en septiembre</li>
                    <li>Menciona "Giftcard Enero 2025" al hacer tu reserva</li>
                    <li>¡Disfruta de $15.000 de descuento en tu servicio!</li>
                </ol>
            </div>
            
            <div style="text-align: center;">
                <a href="https://wa.me/56957902525?text=Hola%2C%20quiero%20reservar%20mi%20cita%20para%20septiembre%20mencionando%20%22Giftcard%20Enero%202025%22" class="cta-button">
                    🗓️ Reservar Ahora
                </a>
            </div>
            
            <div class="services-list">
                <h4>🛀 Servicios incluidos en la giftcard:</h4>
                <ul>
                    <li><strong>🔥 Tinas Calientes:</strong> Con o sin hidromasajes</li>
                    <li><strong>🏡 Cabañas:</strong> Para dos personas</li>
                </ul>
                <p style="color: #666; font-size: 0.9em; margin: 15px 0 0 0;">
                    <strong>Importante:</strong> Esta giftcard es intransferible y solo puede ser utilizada por el titular de la reserva. 
                    No es acumulable con otras promociones vigentes.
                </p>
            </div>
            
            <p>¡No dejes pasar esta oportunidad especial! Tu bienestar nos importa y queremos verte de vuelta en septiembre.</p>
            
            <p>Con cariño,<br>
            <strong>El equipo de Aremko Hotel Spa</strong></p>
        </div>
        
        <div class="footer">
            <p><strong>📞 +56 9 5790 2525</strong> | <strong>📧 ventas@aremko.cl</strong></p>
            <p>📍 Río Pescado Km 4, Puerto Varas, Chile</p>
            <p><small>Si no deseas recibir más emails promocionales, puedes <a href="#">darte de baja aquí</a></small></p>
        </div>
    </div>
</body>
</html>
    """