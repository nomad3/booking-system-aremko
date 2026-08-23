# -*- coding: utf-8 -*-
"""Campo para poder DESHACER un calce sin perder la categoría original.

Escrita a mano —como todas en este repo— porque `makemigrations` arrastra el
drift de AR-033/034 y pide input interactivo por cambios preexistentes.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0007_categoriafinanciera_familia_ventas'),
    ]

    operations = [
        migrations.AddField(
            model_name='movimientofinanciero',
            name='categoria_previa',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='finanzas.categoriafinanciera',
                help_text='Categoría que tenía antes de convertirse en traspaso. '
                          'Solo la usa «deshacer el calce» para dejarlo como estaba.'),
        ),
    ]
