# Generated manually on 2025-12-30
# Agregar campo fecha_entrega a ReservaProducto

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0073_agregar_indices_performance'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservaproducto',
            name='fecha_entrega',
            field=models.DateField(
                blank=True,
                help_text='Fecha en que el producto fue/será entregado al cliente. Si está vacío, se asume la fecha del primer servicio de la reserva.',
                null=True,
                verbose_name='Fecha de Entrega'
            ),
        ),
    ]
