# Dimensiones reales por foto (chequeo de formato exacto, no "a ojo").

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketing_briefs', '0003_publicacionplanificada_revision_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicacionplanificada',
            name='material_meta',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Dimensiones reales por foto (lista alineada a material_urls): '
                          '{url, width, height, ratio, orientacion}. Medido al subir para que '
                          'el chequeo de formato (9:16, 4:5, 1:1) sea exacto, no "a ojo" del modelo.',
            ),
        ),
    ]
