# -*- coding: utf-8 -*-
"""Columna nueva con default: aditiva y sin ventana de corte.

A mano, como las dos anteriores: `makemigrations finanzas` quiere además
alterar campos existentes por el drift AR-033/034.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0005_categoriafinanciera_presupuesto_mensual'),
    ]

    operations = [
        migrations.AddField(
            model_name='categoriafinanciera',
            name='presupuesto_pct_ventas',
            field=models.DecimalField(
                decimal_places=2, default=0,
                help_text='% de las ventas del mes. Si es mayor que 0, manda '
                          'sobre el monto fijo. Ej: 20 = 20% de lo vendido ese mes.',
                max_digits=5),
        ),
    ]
