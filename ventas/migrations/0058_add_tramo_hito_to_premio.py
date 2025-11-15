# Generated manually to add tramo_hito field to Premio model
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0057_emailcontenttemplate_whatsapp_button'),
    ]

    operations = [
        migrations.AddField(
            model_name='premio',
            name='tramo_hito',
            field=models.IntegerField(
                blank=True,
                null=True,
                help_text='Tramo en que se otorga este premio automáticamente (ej: 5, 10, 15, 20). NULL = no se otorga automáticamente'
            ),
        ),
    ]
