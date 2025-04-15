from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _

from ..models import Cliente, Contact, Campaign, Company
from ..forms import SelectCampaignForm
from .. import communication_utils # Correct relative import (go up one level)

@admin.site.admin_view # Decorator to ensure admin permissions and context
def select_campaign_for_remarketing(request):
    """
    Intermediate view for selecting a campaign before triggering remarketing
    for selected clients.
    """
    if request.method == 'POST':
        form = SelectCampaignForm(request.POST)
        if form.is_valid():
            campaign = form.cleaned_data['campaign']
            selected_client_ids_str = form.cleaned_data['selected_clients']
            selected_client_ids = selected_client_ids_str.split(',')

            clientes = Cliente.objects.filter(pk__in=selected_client_ids)
            target_contacts = []
            skipped_clients = 0
            created_contacts = 0

            # Find or create Contact for each selected Cliente
            for cliente in clientes:
                contact = None
                if cliente.email:
                    contact, created = Contact.objects.get_or_create(
                        email=cliente.email,
                        defaults={
                            'first_name': cliente.nombre.split(' ')[0] if cliente.nombre else 'Cliente',
                            'last_name': ' '.join(cliente.nombre.split(' ')[1:]) if cliente.nombre and ' ' in cliente.nombre else '',
                            'phone': cliente.telefono,
                        }
                    )
                    if created:
                        created_contacts += 1
                elif cliente.telefono: # Fallback to phone
                     contact, created = Contact.objects.get_or_create(
                        phone=cliente.telefono,
                         defaults={
                            'first_name': cliente.nombre.split(' ')[0] if cliente.nombre else 'Cliente',
                            'last_name': ' '.join(cliente.nombre.split(' ')[1:]) if cliente.nombre and ' ' in cliente.nombre else '',
                            'email': None,
                        }
                     )
                     if created:
                        created_contacts += 1

                if contact:
                    target_contacts.append(contact)
                else:
                    skipped_clients += 1
                    messages.warning(request, f"Cliente omitido (ID: {cliente.pk}, Nombre: {cliente.nombre}) por falta de email/teléfono.")

            if not target_contacts:
                messages.error(request, "No se pudieron encontrar o crear Contactos para los Clientes seleccionados.")
                # Redirect back to client changelist
                return HttpResponseRedirect(reverse('admin:ventas_cliente_changelist'))

            # --- Perform Communication & Logging ---
            email_sent_count = 0
            email_failed_count = 0
            sms_logged = 0
            whatsapp_logged = 0
            call_logged = 0

            email_subject = f"Oferta especial de Aremko (Campaña: {campaign.name})"
            email_message_template = "Hola {contact_name},\n\nComo cliente de Aremko, queremos contarte sobre nuestra campaña '{campaign_name}'...\n\nSaludos,\nEquipo Aremko"

            for contact in target_contacts:
                email_message = email_message_template.format(contact_name=contact.first_name, campaign_name=campaign.name)
                success = communication_utils.send_campaign_email(
                    contact=contact,
                    campaign=campaign, # Link activity to the selected campaign
                    subject=email_subject,
                    message=email_message,
                    created_by=request.user
                )
                if success: email_sent_count += 1
                else: email_failed_count += 1

                # Log other placeholder activities, now linked to the campaign
                if communication_utils.log_sms_activity(contact, campaign, f"SMS Remarketing: {campaign.name}", "Placeholder para envío SMS.", request.user): sms_logged += 1
                if communication_utils.log_whatsapp_activity(contact, campaign, f"WhatsApp Remarketing: {campaign.name}", "Placeholder para envío WhatsApp.", request.user): whatsapp_logged += 1
                if communication_utils.log_call_activity(contact, campaign, f"Llamada Remarketing: {campaign.name}", "Placeholder para llamada.", request.user): call_logged += 1

            message_parts = [
                f"Remarketing para campaña '{campaign.name}' iniciado para {len(target_contacts)} contactos ({created_contacts} nuevos creados).",
                f"Clientes omitidos: {skipped_clients}." if skipped_clients > 0 else "",
                f"Emails enviados: {email_sent_count} (Fallidos: {email_failed_count}).",
                f"SMS Logged: {sms_logged}.",
                f"WhatsApp Logged: {whatsapp_logged}.",
                f"Calls Logged: {call_logged}."
            ]
            messages.success(request, " ".join(filter(None, message_parts)))
            return HttpResponseRedirect(reverse('admin:ventas_cliente_changelist'))

        else:
            # Form is invalid, re-render it (shouldn't happen with just a ModelChoiceField unless no campaigns exist)
            messages.error(request, "Error en el formulario. Por favor, intente de nuevo.")
            # Need to repopulate the hidden field if re-rendering
            selected_client_ids_str = request.POST.get('selected_clients', '')
            form.fields['selected_clients'].initial = selected_client_ids_str

    else: # GET request
        selected_action = request.GET.getlist(admin.helpers.ACTION_CHECKBOX_NAME)
        if not selected_action:
            messages.warning(request, "No se seleccionaron clientes.")
            return HttpResponseRedirect(reverse('admin:ventas_cliente_changelist'))

        selected_clients_str = ",".join(selected_action)
        form = SelectCampaignForm(initial={'selected_clients': selected_clients_str})

    context = {
        **admin.site.each_context(request),
        'title': _('Seleccionar Campaña para Remarketing'),
        'form': form,
        'selected_clients_count': len(selected_action) if request.method == 'GET' else len(selected_client_ids),
        'opts': Cliente._meta, # Pass model meta options for admin template context
        'has_view_permission': True, # Assume user has permission if they got here
    }
    return render(request, 'admin/ventas/cliente/select_campaign_for_remarketing.html', context)
