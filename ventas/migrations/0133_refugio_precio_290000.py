# -*- coding: utf-8 -*-
"""El Refugio vale $290.000, no $270.000.

Solo cambian los `default=` de dos campos, así que esto es estado, no datos:
Django no persiste los defaults en el esquema. La config de producción es un
singleton que YA existe, y su `precio_clp` ya está en 290000 — esta migración
no lo toca. Lo que arregla es que una config nueva (o un ambiente nuevo) nazca
con el precio correcto en vez del viejo.

`seo_description` se deja como está en producción a propósito: es texto que
edita Jorge, y pisárselo desde una migración sería decidir por él. El default
nuevo solo aplica a configs nuevas.

Escrita a mano: `makemigrations ventas` arrastra el drift AR-033/034.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0132_giftcardexperiencia_destacada_web'),
    ]

    operations = [
        migrations.AlterField(
            model_name='refugioconfig',
            name='precio_clp',
            field=models.PositiveIntegerField(
                default=290000,
                help_text='Precio total del paquete Refugio en pesos chilenos.',
                verbose_name='Precio (CLP)'),
        ),
        migrations.AlterField(
            model_name='refugioconfig',
            name='seo_description',
            field=models.CharField(
                default=('Tres días para volver a tu centro. Cabaña en naturaleza, '
                         'masaje en pareja, tinas calientes. La segunda noche, cortesía '
                         'Aremko. $290.000 por 2 personas.'),
                max_length=300, verbose_name='SEO Meta Description'),
        ),
    ]
