# -*- coding: utf-8 -*-
# Migración escrita a mano (NO con makemigrations) para agregar SOLO los
# interruptores de publicación al singleton, evitando el drift de AR-034.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0125_ritualriolandingconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='ritualriolandingconfig',
            name='mostrar_en_menu',
            field=models.BooleanField(default=False, help_text="Mostrar 'Ritual del Río' en el menú de navegación del sitio."),
        ),
        migrations.AddField(
            model_name='ritualriolandingconfig',
            name='mostrar_en_home',
            field=models.BooleanField(default=False, help_text='Mostrar un botón destacado del Ritual en la portada (home).'),
        ),
        migrations.AddField(
            model_name='ritualriolandingconfig',
            name='indexar_en_google',
            field=models.BooleanField(default=False, help_text='Permitir que Google la indexe (quita noindex) y la agrega al sitemap. Déjalo apagado si aún es solo para campañas.'),
        ),
    ]
