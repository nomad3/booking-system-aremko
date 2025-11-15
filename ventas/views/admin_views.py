from django.contrib import admin
from django.contrib.admin import helpers # Import helpers
from django import forms # Import forms module
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction # Import transaction
from django.db import models # Import models for Q lookup
from django.template.loader import render_to_string
from weasyprint import HTML

from ..models import Cliente, Contact, Campaign, Company, Activity, VentaReserva, CommunicationLog # Added CommunicationLog
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import csv, io, threading
from ..forms import SelectCampaignForm # Keep this if still used elsewhere, otherwise remove
# Import CampaignForm if needed for a custom form, or rely on ModelAdmin form
# from ..forms import CampaignForm # Example if you create a custom Campaign form
from .. import communication_utils

# Helper function (can be moved to a utils file)
def es_administrador(user):
    return user.is_staff or user.is_superuser

# Removed select_campaign_for_remarketing view as the workflow changed

@login_required
@user_passes_test(es_administrador) # Ensure only staff/superusers can access
def campaign_setup_view(request, campaign_id=None):
    """
    View for creating or editing a Campaign with a structured layout.
    """
    if campaign_id:
        campaign = get_object_or_404(Campaign, pk=campaign_id)
        form_title = _("Editar Campaña")
    else:
        campaign = None
        form_title = _("Crear Nueva Campaña")

    # Get the ModelAdmin instance for Campaign
    campaign_admin = admin.site._registry[Campaign]
    # Get the form class from the ModelAdmin
    CampaignForm = campaign_admin.get_form(request, obj=campaign)

    if request.method == 'POST':
        form = CampaignForm(request.POST, request.FILES, instance=campaign) # Include request.FILES
        if form.is_valid():
            saved_campaign = form.save()
            messages.success(request, _(f"Campaña '{saved_campaign.name}' guardada exitosamente."))
            # Redirect to campaign changelist or detail view
            return HttpResponseRedirect(reverse('admin:ventas_campaign_changelist'))
        else:
            messages.error(request, _("Por favor corrija los errores en el formulario."))
    else:
        form = CampaignForm(instance=campaign)

    # Create the AdminForm helper object
    admin_form = helpers.AdminForm(
        form=form,
        # Get fieldsets from the ModelAdmin instance
        fieldsets=campaign_admin.get_fieldsets(request, campaign),
        # Get prepopulated fields (if any)
        prepopulated_fields=campaign_admin.get_prepopulated_fields(request, campaign),
        # Get readonly fields (important for display)
        readonly_fields=campaign_admin.get_readonly_fields(request, campaign),
        model_admin=campaign_admin,
    )

    context = {
        **admin.site.each_context(request), # Include admin context
        'title': form_title,
        'adminform': admin_form, # Pass the AdminForm object
        'form': form, # Keep original form if needed elsewhere, but template should use adminform
        'opts': Campaign._meta, # Pass model meta options
        'has_view_permission': True, # Assuming view implies permission
        'has_add_permission': campaign_admin.has_add_permission(request),
        'has_change_permission': campaign_admin.has_change_permission(request, campaign) if campaign else False,
        'has_delete_permission': campaign_admin.has_delete_permission(request, campaign) if campaign else False,
        'object_id': campaign_id, # For admin template context
        'original': campaign, # For admin template context
        'add': campaign_id is None, # Required by submit_row tag
        'change': campaign_id is not None, # Required by submit_row tag
        'is_popup': False,
        'save_as': False,
        'show_save': True,
        'show_save_and_continue': True,
        'show_save_and_add_another': True, # Control visibility as needed
        'show_delete_link': campaign_admin.has_delete_permission(request, campaign) if campaign else False,
        # Use the form's is_multipart() method to check for file fields
        'has_file_field': admin_form.form.is_multipart(),
        'form_url': '', # form action url - typically handled by template logic or passed explicitly if needed
        'has_editable_inline_admin_formsets': False, # Required by submit_row tag; False as we don't have inlines here
    }
    # Use a specific template for this view
    return render(request, 'admin/ventas/campaign/campaign_setup.html', context)

@login_required
@user_passes_test(es_administrador) # Ensure only staff/superusers can access
def select_campaign_for_clients_view(request):
    """
    View to select a campaign for a list of selected clients.
    """
    if request.method == 'POST':
        selected_clients_string = request.POST.get('selected_clients', '')
        if not selected_clients_string:
            messages.error(request, _("No clients were selected."))
            return HttpResponseRedirect(reverse('ventas:cliente_segmentation')) # Redirect back to segmentation

        # Split the string into a list of client IDs
        try:
            selected_client_ids = [int(client_id) for client_id in selected_clients_string.split(',') if client_id.isdigit()]
        except ValueError:
            messages.error(request, _("Invalid client IDs provided."))
            return HttpResponseRedirect(reverse('ventas:cliente_segmentation')) # Redirect back to segmentation


        # Get the form with POST data
        form = SelectCampaignForm(request.POST)

        if form.is_valid():
            campaign = form.cleaned_data['campaign']
            # Retrieve the selected clients
            clients_to_add = Cliente.objects.filter(id__in=selected_client_ids)

            activities_created_count = 0
            with transaction.atomic(): # Ensure atomicity
                for client in clients_to_add:
                    # Try to find a matching Contact for the client
                    # Assuming Contact can be linked by email or phone
                    contact = Contact.objects.filter(
                        models.Q(email=client.email) | models.Q(phone=client.telefono)
                    ).first()

                    if contact:
                        # Create an Activity for each selected client linked to the campaign and contact
                        Activity.objects.create(
                            activity_type='Campaign Initiation', # Define a suitable activity type
                            subject=f"Initiated campaign '{campaign.name}'",
                            notes=f"Client selected from segment for campaign '{campaign.name}'.",
                            related_contact=contact,
                            campaign=campaign,
                            created_by=request.user # Link the user who initiated the action
                        )
                        activities_created_count += 1
                    else:
                        # Handle cases where no matching Contact is found for a Cliente
                        messages.warning(request, _(f"No matching Contact found for client '{client.nombre}' ({client.id}). Activity not created for this client."))


            messages.success(request, _(f"Initiated campaign '{campaign.name}' for {activities_created_count} selected clients."))

            # Redirect to the campaign detail page or changelist
            return HttpResponseRedirect(reverse('admin:ventas_campaign_change', args=[campaign.id]))
        else:
            # If form is not valid, re-render the template with errors
            # Need to pass the selected client IDs back to the template
            context = {
                **admin.site.each_context(request),
                'title': _("Select Campaign for Clients"),
                'form': form,
                'selected_clients_string': selected_clients_string, # Pass back the string
                'selected_clients_count': len(selected_client_ids), # Pass count for display
                'opts': Cliente._meta, # Use Cliente meta for breadcrumbs/context
            }
            return render(request, 'admin/ventas/cliente/select_campaign_for_remarketing.html', context)

    else:
        # Handle GET request (e.g., direct access to this URL)
        messages.warning(request, _("This page is accessed by selecting clients from a segment."))
        return HttpResponseRedirect(reverse('ventas:cliente_segmentation')) # Redirect back to segmentation

# --- Admin Section Views ---

@login_required
@user_passes_test(es_administrador)
def admin_section_crm_view(request):
    context = {**admin.site.each_context(request), 'title': 'CRM y Marketing'}
    return render(request, 'admin/section_crm.html', context)


# =============== CSV Campaign Uploader (Beta) ===============

@login_required
@user_passes_test(es_administrador)
@require_http_methods(["GET", "POST"])
def csv_campaign_uploader(request):
    cache_key = 'csv_campaign_progress'
    if request.method == 'POST':
        asunto = request.POST.get('subject', '').strip()
        cuerpo = request.POST.get('body', '').strip()
        file = request.FILES.get('csv_file')
        send_test = request.POST.get('send_test') == 'on'
        test_email = request.POST.get('test_email', '').strip()

        if not asunto or not cuerpo or not file:
            messages.error(request, 'Asunto, cuerpo y archivo CSV son obligatorios.')
        else:
            try:
                data = file.read().decode('utf-8')
                reader = csv.DictReader(io.StringIO(data))
                rows = list(reader)
                total = len(rows)
                cache.set(cache_key, {'status': 'queued', 'total': total, 'sent': 0, 'failed': 0}, 3600)

                def worker():
                    progress = {'status': 'running', 'total': total, 'queued': 0, 'failed': 0, 'test_sent': False}
                    cache.set(cache_key, progress, 3600)

                    def val(row, *keys):
                        for k in keys:
                            if k in row and row[k] not in (None, ''):
                                return str(row[k]).strip()
                        return ''

                    def norm_email(v):
                        v = (v or '').strip().lower()
                        return v if v and '@' in v else ''

                    def norm_phone(v):
                        d = ''.join(filter(str.isdigit, str(v or '')))
                        if d.startswith('56') and len(d) >= 11:
                            d = d[-9:]
                        if len(d) == 8:
                            d = '9' + d
                        return f'+56{d}' if len(d) == 9 and d.startswith('9') else ''

                    # Envío de prueba si corresponde
                    if send_test and test_email:
                        body = cuerpo.replace('[Nombre]', 'Jorge')
                        from_email = getattr(settings, 'EMAIL_HOST_USER', None) or getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')
                        m = EmailMultiAlternatives(subject=asunto, body=body, from_email=from_email, to=[test_email], reply_to=[getattr(settings,'VENTAS_FROM_EMAIL','ventas@aremko.cl')])
                        if '<' in body and '>' in body:
                            m.attach_alternative(body, 'text/html')
                        try:
                            m.send()
                            progress['test_sent'] = True
                        except Exception as e:
                            progress['test_sent'] = f'Error: {str(e)}'
                        cache.set(cache_key, progress, 3600)

                    # Sembrar cola
                    msg_types = dict(CommunicationLog.MESSAGE_TYPES)
                    promo_key = 'PROMOTIONAL' if 'PROMOTIONAL' in msg_types else 'PROMOCIONAL'
                    
                    for row in rows:
                        email = norm_email(val(row, 'email'))
                        if not email:
                            progress['failed'] += 1
                            cache.set(cache_key, progress, 3600)
                            continue
                            
                        nombre = val(row, 'nombre', 'first_name') or '-'
                        apellido = val(row, 'apellido', 'last_name')
                        phone = norm_phone(val(row, 'celular', 'phone')) or None
                        empresa = val(row, 'empresa', 'company_name')
                        rubro = val(row, 'rubro', 'industry')
                        ciudad = val(row, 'ciudad', 'city')

                        # Crear/actualizar Company si aplica
                        company = None
                        if empresa:
                            company, _ = Company.objects.get_or_create(name=empresa)
                            if rubro and hasattr(company, 'industry') and (company.industry or '') != rubro:
                                company.industry = rubro
                                company.save(update_fields=['industry'])

                        # Crear/actualizar Contact
                        c, _ = Contact.objects.get_or_create(email=email, defaults={
                            'first_name': nombre, 'last_name': apellido, 'phone': phone, 'company': company,
                            'notes': '; '.join([p for p in [f"Ciudad: {ciudad}" if ciudad else '', f"Rubro: {rubro}" if rubro else ''] if p])
                        })
                        
                        # Crear/actualizar Cliente (requerido por CommunicationLog)
                        try:
                            display_name = f"{nombre} {apellido}".strip() or (email.split('@')[0])
                            cliente_obj, _ = Cliente.objects.get_or_create(
                                email=email,
                                defaults={'nombre': display_name, 'telefono': phone}
                            )
                        except Exception:
                            cliente_obj = Cliente.objects.filter(email=email).first()

                        # Crear CommunicationLog PENDING solo si no existe ya uno pendiente
                        if cliente_obj:
                            existing = CommunicationLog.objects.filter(
                                destination=email,
                                communication_type='EMAIL',
                                message_type=promo_key,
                                status='PENDING'
                            ).exists()
                            
                            if not existing:
                                CommunicationLog.objects.create(
                                    cliente=cliente_obj, 
                                    campaign=None, 
                                    communication_type='EMAIL',
                                    message_type=promo_key,
                                    subject=asunto, 
                                    content=cuerpo, 
                                    destination=email, 
                                    status='PENDING'
                                )
                                progress['queued'] += 1
                            else:
                                progress['queued'] += 1  # Ya existía, pero lo contamos como exitoso
                        else:
                            progress['failed'] += 1
                        
                        cache.set(cache_key, progress, 3600)

                    # Actualizar progreso final
                    total_pending = CommunicationLog.objects.filter(
                        communication_type='EMAIL',
                        message_type=promo_key,
                        status='PENDING'
                    ).count()
                    
                    progress.update({
                        'status': 'completed_seeding',
                        'pending': total_pending,
                        'message': f'Cola preparada con {total_pending} emails. El goteo automático los enviará cada 10 minutos.'
                    })
                    cache.set(cache_key, progress, 3600)
                    
                    # Iniciar el proceso de envío automático inmediatamente
                    try:
                        from django.core.management import call_command
                        # Usar el contenido almacenado en los CommunicationLog en lugar de template externo
                        call_command('send_next_campaign_drip', 
                                   use_stored_content=True,
                                   batch_size=5)  # Enviar 5 por vez en lugar de 1
                        progress['auto_start'] = 'Primer lote enviado automáticamente'
                    except Exception as e:
                        progress['auto_send_error'] = f'Error iniciando envío: {str(e)}'
                        cache.set(cache_key, progress, 3600)

                threading.Thread(target=worker, daemon=True).start()
                messages.success(request, 'Archivo recibido. Sembrando cola y enviando prueba...')
            except Exception as e:
                messages.error(request, f'Error procesando CSV: {e}')

    context = {**admin.site.each_context(request), 'title': 'Campaña por CSV (beta)'}
    context['progress'] = cache.get(cache_key)
    return render(request, 'admin/csv_campaign_uploader.html', context)


@login_required
@user_passes_test(es_administrador)
@require_http_methods(["GET", "POST"])
def mail_csv_uploader(request):
    """Subir CSV a la tabla MailParaEnviar"""
    if request.method == 'POST':
        asunto = request.POST.get('subject', '').strip()
        contenido = request.POST.get('body', '').strip()
        file = request.FILES.get('csv_file')
        campana = request.POST.get('campaign', '').strip()

        if not asunto or not contenido or not file:
            messages.error(request, 'Asunto, contenido y archivo CSV son obligatorios.')
        else:
            try:
                from ventas.models import MailParaEnviar
                data = file.read().decode('utf-8')
                reader = csv.DictReader(io.StringIO(data))
                rows = list(reader)
                
                def val(row, *keys):
                    for k in keys:
                        if k in row and row[k]:
                            return str(row[k]).strip()
                    return ''

                def norm_email(v):
                    v = (v or '').strip().lower()
                    return v if v and '@' in v else ''

                creados = 0
                saltados = 0
                
                for row in rows:
                    email = norm_email(val(row, 'email'))
                    if not email:
                        saltados += 1
                        continue
                        
                    nombre = val(row, 'nombre', 'empresa') or 'Sin nombre'
                    ciudad = val(row, 'ciudad')
                    rubro = val(row, 'rubro')
                    
                    # Verificar si ya existe
                    if MailParaEnviar.objects.filter(email=email, estado='PENDIENTE').exists():
                        saltados += 1
                        continue
                    
                    # Crear registro
                    MailParaEnviar.objects.create(
                        nombre=nombre,
                        email=email,
                        ciudad=ciudad,
                        rubro=rubro,
                        asunto=asunto,
                        contenido_html=contenido,
                        estado='PENDIENTE',
                        prioridad=1,
                        campana=campana or 'Sin campaña'
                    )
                    creados += 1
                
                messages.success(request, f'✅ Importación completada: {creados} emails creados, {saltados} saltados.')
                
                # Mostrar total pendientes
                total_pendientes = MailParaEnviar.objects.filter(estado='PENDIENTE').count()
                messages.info(request, f'📊 Total emails PENDIENTES: {total_pendientes}')
                
            except Exception as e:
                messages.error(request, f'Error procesando CSV: {e}')

    context = {**admin.site.each_context(request), 'title': 'Importar Emails desde CSV'}
    return render(request, 'admin/mail_csv_uploader.html', context)

@login_required
@user_passes_test(es_administrador)
def admin_section_ventas_view(request):
    context = {**admin.site.each_context(request), 'title': 'Ventas y Reservas'}
    return render(request, 'admin/section_ventas.html', context)

@login_required
@user_passes_test(es_administrador)
def admin_section_servicios_view(request):
    context = {**admin.site.each_context(request), 'title': 'Servicios y Proveedores'}
    return render(request, 'admin/section_servicios.html', context)

@login_required
@user_passes_test(es_administrador)
def admin_section_productos_view(request):
    context = {**admin.site.each_context(request), 'title': 'Productos y Compras'}
    return render(request, 'admin/section_productos.html', context)

@login_required
@user_passes_test(es_administrador)
def admin_section_config_view(request):
    context = {**admin.site.each_context(request), 'title': 'Configuración'}
    return render(request, 'admin/section_config.html', context)

@login_required
@user_passes_test(es_administrador)
def generate_reserva_pdf(request, reserva_id):
    reserva = get_object_or_404(VentaReserva, pk=reserva_id)
    rendered = render_to_string('ventas/reserva_summary_pdf.html', {'reserva': reserva})
    html = HTML(string=rendered, base_url=request.build_absolute_uri())
    pdf = html.write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reserva_{reserva_id}.pdf"'
    return response
