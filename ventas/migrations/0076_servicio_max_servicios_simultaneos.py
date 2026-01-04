# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0075_agregar_precios_congelados'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicio',
            name='max_servicios_simultaneos',
            field=models.PositiveIntegerField(
                default=1,
                help_text='Cantidad máxima de veces que este servicio se puede reservar en el mismo horario (default: 1). Usar 2 para masajes que permiten reservas simultáneas.',
                verbose_name='Máximo de servicios simultáneos por slot'
            ),
        ),
    ]
