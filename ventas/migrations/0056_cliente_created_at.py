# Generated migration for Cliente.created_at field
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0055_create_default_email_templates'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
        ),
    ]
