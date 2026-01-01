# Generated manually on 2026-01-01
# Agregar campos precio_unitario_venta a ReservaProducto y ReservaServicio
# Estos campos almacenan el precio del producto/servicio al momento de agregarlo a la reserva,
# independiente de cambios futuros en el catálogo.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0074_reservaproducto_fecha_entrega'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservaproducto',
            name='precio_unitario_venta',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Precio del producto al momento de agregarlo a la reserva. Si está vacío, se usa el precio_base actual del producto.',
                max_digits=10,
                null=True,
                verbose_name='Precio Unitario de Venta'
            ),
        ),
        migrations.AddField(
            model_name='reservaservicio',
            name='precio_unitario_venta',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Precio del servicio al momento de agregarlo a la reserva. Si está vacío, se usa el precio_base actual del servicio.',
                max_digits=10,
                null=True,
                verbose_name='Precio Unitario de Venta'
            ),
        ),
    ]
