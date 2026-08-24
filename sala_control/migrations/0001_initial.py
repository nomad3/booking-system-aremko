# Migración escrita a mano (el proyecto tiene drift: makemigrations abre
# preguntas interactivas). Solo crea tablas nuevas — no toca nada existente.
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='PrioridadSemana',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('semana_inicio', models.DateField(
                    db_index=True, verbose_name='semana (lunes)',
                    help_text='El lunes de la semana a la que pertenece. '
                              'Se muestran las de la semana en curso.')),
                ('negocio', models.CharField(
                    choices=[('aremko', 'Aremko'), ('datamatic', 'Datamatic'),
                             ('torqueria', 'Torquería')],
                    default='aremko', max_length=20)),
                ('orden', models.PositiveSmallIntegerField(
                    default=1, help_text='1, 2, 3… El orden en que las quieres leer.')),
                ('texto', models.CharField(max_length=200)),
                ('hecha', models.BooleanField(
                    default=False, verbose_name='lista',
                    help_text='Marcada, deja de aparecer como pendiente en el resumen.')),
                ('creada', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Prioridad de la semana',
                'verbose_name_plural': 'Prioridades de la semana',
                'ordering': ['negocio', 'orden', 'id'],
            },
        ),
        migrations.CreateModel(
            name='NotaNegocio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('negocio', models.CharField(
                    choices=[('aremko', 'Aremko'), ('datamatic', 'Datamatic'),
                             ('torqueria', 'Torquería')],
                    max_length=20, unique=True)),
                ('texto', models.CharField(max_length=300)),
                ('actualizada', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Nota de negocio',
                'verbose_name_plural': 'Notas de negocios',
                'ordering': ['negocio'],
            },
        ),
    ]
