from django.contrib import admin
from django.contrib.admin import helpers # Import helpers
from django import forms # Import forms module
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction # Import transaction
from django.db import models # Import models for Q lookup
from django.template.loader import render_to_string
from weasyprint import HTML, CSS # Importar CSS también para posibles estilos adicionales

from ..models import Cliente, Contact, Campaign, Company, Activity, VentaReserva # Added Activity and VentaReserva
from ..forms import SelectCampaignForm # Keep this if still used elsewhere, otherwise remove
# Import CampaignForm if needed for a custom form, or rely on ModelAdmin form
# from ..forms import CampaignForm # Example if you create a custom Campaign form
from .. import communication_utils
from django.contrib.admin.views.decorators import staff_member_required # Para seguridad

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

@staff_member_required # Asegura que solo personal logueado acceda
def generate_reserva_pdf(request, reserva_id):
    """Genera un PDF resumen de una VentaReserva específica."""
    # Optimizar consulta pre-cargando datos relacionados
    reserva = get_object_or_404(
        VentaReserva.objects.prefetch_related(
            'reservaservicios__servicio', 
            'reservaservicios__proveedor_asignado',
            'cliente' # Cargar cliente
        ), 
        id=reserva_id
    )
    
    # Renderizar la plantilla HTML a una cadena
    html_string = render_to_string('ventas/reserva_summary_pdf.html', {'reserva': reserva})
    
    # Generar PDF con WeasyPrint
    # Pasar la URL base es importante para que WeasyPrint encuentre archivos estáticos (CSS, imágenes) si los usas en la plantilla
    base_url = request.build_absolute_uri('/') 
    pdf_file = HTML(string=html_string, base_url=base_url).write_pdf()
    
    # Crear respuesta HTTP con el PDF
    response = HttpResponse(pdf_file, content_type='application/pdf')
    # Mostrar inline en el navegador, pero permite guardar/descargar
    # El nombre del archivo incluirá el ID de la reserva
    response['Content-Disposition'] = f'inline; filename="reserva_{reserva.id}.pdf"' 
    return response
