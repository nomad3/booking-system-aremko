# Escrita a mano: makemigrations se queda esperando una respuesta interactiva
# por drift pendiente de OTRA app. Acá solo se agrega el campo nuevo.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0006_unidad_sii'),
    ]

    operations = [
        migrations.AddField(
            model_name='boletaelectronica',
            name='enviada_cliente_at',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text='Cuándo se le envió al cliente por WhatsApp.'),
        ),
    ]
