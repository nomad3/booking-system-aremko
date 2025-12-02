#!/usr/bin/env python
"""
Script para crear la migración 0062 en producción (Homepage Config Text Fields)
"""
import os

migration_content = """from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0061_giftcardexperiencia'),
    ]

    operations = [
        migrations.AddField(
            model_name='homepageconfig',
            name='cta_button_text',
            field=models.CharField(default='Reservar Mi Experiencia Ahora', max_length=50, verbose_name='Texto Botón CTA Final'),
        ),
        migrations.AddField(
            model_name='homepageconfig',
            name='cta_subtitle',
            field=models.TextField(default='Regálate el descanso que mereces. Elige tu masaje ideal, sumérgete en nuestras tinajas o planifica tu estancia completa. ¡Tu momento de paz te espera!', verbose_name='Subtítulo CTA Final'),
        ),
        migrations.AddField(
            model_name='homepageconfig',
            name='cta_title',
            field=models.CharField(default='¿Listo para Vivir la Experiencia Aremko?', max_length=255, verbose_name='Título CTA Final'),
        ),
        migrations.AddField(
            model_name='homepageconfig',
            name='hero_cta_link',
            field=models.CharField(default='#servicios', max_length=255, verbose_name='Enlace Botón Hero'),
        ),
        migrations.AddField(
            model_name='homepageconfig',
            name='hero_cta_text',
            field=models.CharField(default='Descubre Tu Experiencia Ideal', max_length=50, verbose_name='Texto Botón Hero'),
        ),
        migrations.AddField(
            model_name='homepageconfig',
            name='hero_subtitle',
            field=models.TextField(default='Sumérgete en un oasis de tranquilidad en Puerto Varas. Descubre experiencias únicas de masajes, tinas calientes y alojamiento diseñadas para tu bienestar total.', verbose_name='Subtítulo Hero'),
        ),
        migrations.AddField(
            model_name='homepageconfig',
            name='hero_title',
            field=models.CharField(default='Desconecta y Renueva Tus Sentidos en Aremko Spa', max_length=255, verbose_name='Título Hero'),
        ),
        migrations.AddField(
            model_name='homepageconfig',
            name='philosophy_cta_text',
            field=models.CharField(default='Explora Nuestros Servicios', max_length=50, verbose_name='Texto Botón Filosofía'),
        ),
        migrations.AddField(
            model_name='homepageconfig',
            name='philosophy_text_1',
            field=models.TextField(default='Más que un spa, somos un refugio para el alma. En Aremko, creemos en el poder sanador de la naturaleza y la desconexión. Nuestra filosofía se centra en ofrecerte un espacio de paz donde puedas renovar tu energía, cuidar tu cuerpo y calmar tu mente.', verbose_name='Texto Filosofía 1'),
        ),
        migrations.AddField(
            model_name='homepageconfig',
            name='philosophy_text_2',
            field=models.TextField(default='Desde masajes terapéuticos hasta la inmersión en nuestras tinajas calientes bajo las estrellas, cada detalle está pensado para tu máximo bienestar. Ven y descubre por qué nuestros visitantes nos eligen como su escape perfecto en Puerto Varas.', verbose_name='Texto Filosofía 2'),
        ),
        migrations.AddField(
            model_name='homepageconfig',
            name='philosophy_title',
            field=models.CharField(default='Vive la Experiencia Aremko', max_length=255, verbose_name='Título Filosofía'),
        ),
    ]
"""

# Crear el archivo
migration_path = 'ventas/migrations/0062_homepageconfig_text_fields.py'

try:
    with open(migration_path, 'w') as f:
        f.write(migration_content)
    print(f"✅ Archivo de migración creado: {migration_path}")
    print("\\nAhora ejecuta:")
    print("  python manage.py migrate ventas")
except Exception as e:
    print(f"❌ Error creando archivo: {e}")
