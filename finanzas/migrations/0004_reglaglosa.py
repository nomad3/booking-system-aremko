# -*- coding: utf-8 -*-
"""Tabla nueva y nada más.

Escrita a mano a propósito: `makemigrations finanzas` quiso además alterar
campos existentes (el drift AR-033/034 vive también acá) y eso en producción
es exactamente lo que no queremos. Esta migración SOLO crea ReglaGlosa, así
que es aditiva: no toca ninguna tabla en uso y no necesita ventana de corte.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finanzas', '0003_alter_categoriafinanciera_grupo'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReglaGlosa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('patron', models.CharField(
                    help_text='Texto que debe aparecer en la glosa. Se guarda '
                              'en MAYÚSCULAS y se compara sin distinguir '
                              'mayúsculas.',
                    max_length=120, unique=True)),
                ('nota', models.CharField(
                    blank=True, default='',
                    help_text='Por qué es de Aremko. Para acordarse en seis meses.',
                    max_length=200)),
                ('activa', models.BooleanField(default=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('categoria', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='reglas_glosa', to='finanzas.categoriafinanciera')),
                ('creada_por', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reglas_glosa', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Regla de glosa',
                'verbose_name_plural': 'Reglas de glosa (siempre Aremko)',
                'ordering': ['patron'],
            },
        ),
    ]
