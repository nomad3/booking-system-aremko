# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0059_add_tramos_validos'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientepremio',
            name='fecha_envio_whatsapp',
            field=models.DateTimeField(blank=True, help_text='Fecha cuando se envió por WhatsApp', null=True),
        ),
    ]