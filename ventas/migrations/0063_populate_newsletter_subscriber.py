# -*- coding: utf-8 -*-
"""Migration to register NewsletterSubscriber model and populate it.

NOTE ON MIGRATION STRATEGY (PARCHE):
This migration uses `ConditionalCreateModel` to handle a discrepancy between
Django's migration state and the actual database schema.

The table `ventas_newslettersubscriber` ALREADY EXISTS in the production database,
but Django's migration history does not have a record of its creation (likely due
to a lost or squashed migration).

To fix the `LookupError` without causing a "table already exists" crash:
1. We define `ConditionalCreateModel` (helper class).
2. We "create" the model using this helper. It checks if the table exists:
   - If YES: It skips the SQL creation but registers the model in Django's state.
   - If NO: It creates the table normally.
3. Once the model is registered, `RunPython` can safely access it to populate data.

FUTURE MIGRATIONS:
If you encounter similar "model not found" or "table already exists" issues for
existing tables, reuse the `ConditionalCreateModel` pattern defined here.
"""

from django.db import migrations, models, connection
from django.utils import timezone


def check_table_exists(table_name):
    """Check if a table exists in the database."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
        """, [table_name])
        return cursor.fetchone()[0]


class ConditionalCreateModel(migrations.CreateModel):
    """Custom CreateModel operation that checks if table exists first."""
    
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        table_name = self.name.lower()
        # Django appends app_label to table name usually, but let's be safe
        # Standard Django table name format: app_model
        full_table_name = f"{app_label}_{table_name}"
        
        if not check_table_exists(full_table_name):
            # Table doesn't exist, create it normally
            super().database_forwards(app_label, schema_editor, from_state, to_state)
        else:
            # Table exists, just add to Django's migration history (fake apply)
            pass


def create_newsletter_subscribers(apps, schema_editor):
    Cliente = apps.get_model('ventas', 'Cliente')
    NewsletterSubscriber = apps.get_model('ventas', 'NewsletterSubscriber')
    
    # Emails to exclude (internal or admin emails)
    EXCLUDED_EMAILS = {
        'cliente@aremko.cl',
        'aremkospa@aremko.cl',
        'contacto@aremko.cl', 
        'reservas@aremko.cl',
        'administracion@aremko.cl'
    }

    # Iterate over all clients with a valid email
    for cliente in Cliente.objects.filter(email__isnull=False).exclude(email=''):
        email = cliente.email.strip().lower()
        
        # Skip excluded emails
        if email in EXCLUDED_EMAILS:
            continue

        # Skip if already present in NewsletterSubscriber (unique constraint on email)
        if NewsletterSubscriber.objects.filter(email=email).exists():
            continue
        
        # Split nombre into first and last name
        nombre_completo = (cliente.nombre or '').strip()
        parts = nombre_completo.split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ''
        
        # Create subscriber entry
        NewsletterSubscriber.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            subscribed_at=timezone.now(),
            is_active=True,
            source='Migration - existing clientes',
        )


class Migration(migrations.Migration):
    dependencies = [
        ('ventas', '0062_homepageconfig_text_fields'),
    ]

    operations = [
        # 1. Register the model conditionally (The "Patch")
        ConditionalCreateModel(
            name='NewsletterSubscriber',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('first_name', models.CharField(blank=True, max_length=100, null=True)),
                ('last_name', models.CharField(blank=True, max_length=100, null=True)),
                ('subscribed_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('source', models.CharField(default='Website Footer', max_length=100)),
                ('email_open_count', models.IntegerField(default=0)),
                ('email_click_count', models.IntegerField(default=0)),
                ('last_email_sent', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Suscriptor Newsletter',
                'verbose_name_plural': 'Suscriptores Newsletter',
            },
        ),
        
        # 2. Populate data
        migrations.RunPython(create_newsletter_subscribers, reverse_code=migrations.RunPython.noop),
    ]
