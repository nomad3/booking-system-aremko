# -*- coding: utf-8 -*-
"""Columna nueva con default: aditiva y sin ventana de corte.

A mano, como las tres anteriores: `makemigrations finanzas` quiere además
alterar campos existentes por el drift AR-033/034.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0006_categoriafinanciera_presupuesto_pct_ventas'),
    ]

    operations = [
        migrations.AddField(
            model_name='categoriafinanciera',
            name='familia_ventas',
            field=models.CharField(
                blank=True, default='',
                choices=[('', 'Todas las ventas'), ('Tinas', 'Solo Tinas'),
                         ('Masajes', 'Solo Masajes'), ('Cabañas', 'Solo Cabañas'),
                         ('Ambientaciones', 'Solo Ambientaciones')],
                help_text='Contra qué venta se calcula el %. Vacío = ventas totales.',
                max_length=20),
        ),
    ]
