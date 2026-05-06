"""Modelo Review individual con screenshot para procesamiento IA — Tarea 2.8 fase 2.

Migración manual en Render (regla del proyecto).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0086_reviewsnapshot'),
    ]

    operations = [
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fuente', models.CharField(choices=[('google', 'Google Maps'), ('tripadvisor', 'TripAdvisor')], db_index=True, max_length=20)),
                ('screenshot', models.ImageField(blank=True, help_text='Captura de pantalla del review para extracción con IA', null=True, upload_to='reviews/%Y/%m/')),
                ('fecha_review', models.DateField(blank=True, db_index=True, null=True)),
                ('autor', models.CharField(blank=True, max_length=200)),
                ('rating', models.PositiveSmallIntegerField(blank=True, help_text='1-5 estrellas', null=True)),
                ('texto', models.TextField(blank=True, help_text='Vacío si el cliente solo dejó estrellas sin comentario')),
                ('idioma', models.CharField(choices=[('es', 'Español'), ('en', 'Inglés'), ('pt', 'Portugués'), ('otro', 'Otro')], default='es', max_length=10)),
                ('extraccion_completada', models.BooleanField(default=False, help_text='True cuando la IA ya procesó el screenshot')),
                ('respuesta_sugerida', models.TextField(blank=True, help_text='Respuesta generada por IA, lista para copiar/pegar')),
                ('respuesta_publicada', models.BooleanField(default=False)),
                ('respuesta_publicada_at', models.DateTimeField(blank=True, null=True)),
                ('sentimiento', models.CharField(blank=True, choices=[('positivo', 'Positivo'), ('neutro', 'Neutro'), ('negativo', 'Negativo')], help_text='Auto-derivado del rating (1-3 negativo, 4 neutro, 5 positivo)', max_length=15)),
                ('temas_detectados', models.JSONField(blank=True, default=list, help_text='Lista de temas mencionados (ej. ["temperatura_tina", "limpieza"])')),
                ('notas_internas', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Review externo',
                'verbose_name_plural': 'Reviews externos',
                'ordering': ['-fecha_review', '-created_at'],
            },
        ),
    ]
