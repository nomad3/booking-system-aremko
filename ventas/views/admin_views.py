from django.contrib import admin
from django.contrib.admin import helpers # Import helpers
from django import forms # Import forms module
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required, user_passes_test

from ..models import Cliente, Contact, Campaign, Company
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
    }
    # Use a specific template for this view
    return render(request, 'admin/ventas/campaign/campaign_setup.html', context)
