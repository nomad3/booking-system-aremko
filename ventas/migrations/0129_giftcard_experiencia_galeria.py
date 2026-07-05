# -*- coding: utf-8 -*-
# Migración escrita a mano (NO con makemigrations) para agregar SOLO las 2 fotos
# extra del carrusel de GiftCardExperiencia, evitando el drift de AR-034 (mismo
# criterio que 0126/0127/0128).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0128_masajes_landing_fotos'),
    ]

    operations = [
        migrations.AddField(
            model_name='giftcardexperiencia',
            name='imagen_2',
            field=models.ImageField(blank=True, help_text='Segunda foto (opcional): otro componente de la experiencia (ej. el masaje).', null=True, upload_to='giftcards/experiencias/'),
        ),
        migrations.AddField(
            model_name='giftcardexperiencia',
            name='imagen_3',
            field=models.ImageField(blank=True, help_text='Tercera foto (opcional): otro componente (ej. la cabaña o el desayuno).', null=True, upload_to='giftcards/experiencias/'),
        ),
    ]
