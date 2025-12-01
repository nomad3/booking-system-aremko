# -*- coding: utf-8 -*-
"""Migration to create NewsletterSubscriber entries for existing Cliente records.

- Only clients that have a non‑empty email are added.
- If a subscriber already exists (by email) we skip to avoid duplicates.
- This migration does **not** affect clients without an email; they will be handled later via a signal.
"""

from django.db import migrations, models
from django.utils import timezone

def create_newsletter_subscribers(apps, schema_editor):
    Cliente = apps.get_model('ventas', 'Cliente')
    NewsletterSubscriber = apps.get_model('ventas', 'NewsletterSubscriber')
    # Iterate over all clients with a valid email
    for cliente in Cliente.objects.filter(email__isnull=False).exclude(email=''):
        email = cliente.email.strip().lower()
        # Skip if already present in NewsletterSubscriber (unique constraint on email)
        if NewsletterSubscriber.objects.filter(email=email).exists():
            continue
        # Create subscriber entry
        NewsletterSubscriber.objects.create(
            email=email,
            first_name=cliente.nombre or '',
            last_name=cliente.apellido or '',
            subscribed_at=timezone.now(),
            is_active=True,
            source='Migration - existing clientes',
        )

class Migration(migrations.Migration):
    dependencies = [
        ('ventas', '0062_homepageconfig_text_fields'),  # adjust if later migrations exist
    ]

    operations = [
        migrations.RunPython(create_newsletter_subscribers, reverse_code=migrations.RunPython.noop),
    ]
