# Migración escrita a mano (el proyecto tiene drift: makemigrations abre
# preguntas interactivas). Solo crea tablas nuevas — no toca nada existente.
from django.db import migrations, models

NEGOCIOS = [('aremko', 'Aremko'), ('datamatic', 'Datamatic'),
            ('torqueria', 'Torquería')]


class Migration(migrations.Migration):

    dependencies = [('sala_control', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='MarcaPublicacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(db_index=True)),
                ('publicacion_id', models.PositiveIntegerField(
                    help_text='Id de la pieza en el Telar (Datamatic). Llave estable: '
                              'el título se edita y la hora se mueve.')),
                ('titulo', models.CharField(
                    blank=True, default='', max_length=200,
                    help_text='Copia de cortesía para poder leer el historial sin ir al Telar.')),
                ('marcada_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Publicación marcada',
                'verbose_name_plural': 'Publicaciones marcadas',
                'ordering': ['-fecha', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='marcapublicacion',
            constraint=models.UniqueConstraint(
                fields=('fecha', 'publicacion_id'),
                name='marca_unica_por_pieza_y_dia'),
        ),
        migrations.CreateModel(
            name='NotaDelDia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(db_index=True)),
                ('texto', models.CharField(max_length=300)),
                ('link', models.URLField(
                    blank=True, default='',
                    help_text='Opcional: el correo, el panel o el documento del que se trata.')),
                ('negocio', models.CharField(choices=NEGOCIOS, default='aremko',
                                             max_length=20)),
                ('hecha', models.BooleanField(default=False)),
                ('creada', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Nota del día',
                'verbose_name_plural': 'Notas del día',
                'ordering': ['hecha', 'id'],
            },
        ),
        migrations.CreateModel(
            name='CorteAds',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(unique=True)),
                ('meta', models.DecimalField(
                    blank=True, decimal_places=0, max_digits=12, null=True,
                    help_text='Vacío = no se pudo leer, que no es lo mismo que cero.')),
                ('google', models.DecimalField(blank=True, decimal_places=0,
                                               max_digits=12, null=True)),
                ('dias_ventana', models.PositiveSmallIntegerField(default=0)),
                ('calculado_en', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Corte de publicidad',
                'verbose_name_plural': 'Cortes de publicidad',
                'ordering': ['-fecha'],
            },
        ),
    ]
