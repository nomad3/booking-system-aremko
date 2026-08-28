# Migración escrita a mano (el proyecto tiene drift: makemigrations abre
# preguntas interactivas). Solo agrega una columna nullable.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('ventas', '0135_calendariocabana')]

    operations = [
        migrations.AddField(
            model_name='ritualriolandingconfig',
            name='foto_acto4',
            field=models.ImageField(
                blank=True, null=True, upload_to='ritual_rio/',
                help_text='Desayuno sureño de llegada (landing «Cabaña y spa por el '
                          'día»). Si queda vacía, esa tarjeta se muestra sin foto.'),
        ),
    ]
