import logging
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import Activity, Contact, Campaign, User

logger = logging.getLogger(__name__)

def log_communication_activity(contact: Contact, campaign: Campaign, activity_type: str, subject: str, notes: str = "", created_by: User = None):
    """
    Logs a communication attempt as an Activity linked to a Contact and Campaign.
    """
    if not isinstance(contact, Contact):
        logger.error(f"Invalid contact object provided for logging activity: {contact}")
        return None
    if not isinstance(campaign, Campaign):
        logger.error(f"Invalid campaign object provided for logging activity: {campaign}")
        return None

    try:
        activity = Activity.objects.create(
            related_contact=contact,
            campaign=campaign,
            activity_type=activity_type,
            subject=subject,
            notes=notes,
            created_by=created_by,
            activity_date=timezone.now()
        )
        logger.info(f"Logged activity '{activity_type}' for contact {contact.id} regarding campaign {campaign.id if campaign else 'N/A'}")
        return activity
    except Exception as e:
        logger.error(f"Error creating Activity log for contact {contact.id}, campaign {campaign.id if campaign else 'N/A'}: {e}")
        return None

# Removed send_campaign_email, log_sms_activity, log_whatsapp_activity, log_call_activity
# Communication sending will be handled externally (e.g., by n8n).
# This file now only contains the utility to log activities via the API endpoint.
