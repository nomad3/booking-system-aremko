# Mejor hora de publicación (viene del calendario_semanal del brief).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketing_briefs', '0004_publicacionplanificada_material_meta'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicacionplanificada',
            name='hora_sugerida',
            field=models.CharField(
                blank=True,
                default='',
                max_length=5,
                help_text='Mejor hora para publicar (HH:MM), tomada del calendario del brief. '
                          'Sugerencia de alcance, no una obligación.',
            ),
        ),
    ]
