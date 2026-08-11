# -*- coding: utf-8 -*-
"""Columna nueva con default: aditiva y sin ventana de corte.

A mano, igual que la 0004: `makemigrations finanzas` quiere además alterar
campos existentes por el drift AR-033/034, y eso en producción no va.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0004_reglaglosa'),
    ]

    operations = [
        migrations.AddField(
            model_name='categoriafinanciera',
            name='presupuesto_mensual',
            field=models.DecimalField(
                decimal_places=0, default=0,
                help_text='Monto mensual esperado. 0 = sin presupuesto definido.',
                max_digits=12),
        ),
    ]
