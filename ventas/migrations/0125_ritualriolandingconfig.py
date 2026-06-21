# -*- coding: utf-8 -*-
# Migración escrita a mano (NO con makemigrations) para crear SOLO el modelo
# nuevo RitualRioLandingConfig, evitando arrastrar el drift de AR-034.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0124_seguimiento_masaje_auditoria_outbox'),
    ]

    operations = [
        migrations.CreateModel(
            name='RitualRioLandingConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('foto_hero', models.ImageField(blank=True, help_text='Foto/video principal: tina humeante junto al río, al atardecer.', null=True, upload_to='ritual_rio/')),
                ('foto_acto1', models.ImageField(blank=True, help_text='Acto 1 — Masaje nocturno.', null=True, upload_to='ritual_rio/')),
                ('foto_acto2', models.ImageField(blank=True, help_text='Acto 2 — Tina caliente / circuito térmico bajo las estrellas.', null=True, upload_to='ritual_rio/')),
                ('foto_acto3', models.ImageField(blank=True, help_text='Acto 3 — Cabaña y desayuno al despertar.', null=True, upload_to='ritual_rio/')),
                ('resena1_foto', models.ImageField(blank=True, help_text='Foto de la pareja (reseña 1).', null=True, upload_to='ritual_rio/resenas/')),
                ('resena1_texto', models.TextField(blank=True, default='', help_text='Texto de la reseña 1.')),
                ('resena1_autor', models.CharField(blank=True, default='', help_text='Ej: Pareja de Puerto Montt.', max_length=120)),
                ('resena2_foto', models.ImageField(blank=True, help_text='Foto de la pareja (reseña 2).', null=True, upload_to='ritual_rio/resenas/')),
                ('resena2_texto', models.TextField(blank=True, default='', help_text='Texto de la reseña 2.')),
                ('resena2_autor', models.CharField(blank=True, default='', help_text='Ej: Pareja de Osorno.', max_length=120)),
                ('resena3_foto', models.ImageField(blank=True, help_text='Foto de la pareja (reseña 3).', null=True, upload_to='ritual_rio/resenas/')),
                ('resena3_texto', models.TextField(blank=True, default='', help_text='Texto de la reseña 3.')),
                ('resena3_autor', models.CharField(blank=True, default='', help_text='Ej: Pareja de Puerto Varas.', max_length=120)),
            ],
            options={
                'verbose_name': 'Landing Ritual del Río',
                'verbose_name_plural': 'Landing Ritual del Río',
            },
        ),
    ]
