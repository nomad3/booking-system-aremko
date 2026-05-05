"""Modelo ReviewSnapshot — Tarea 2.8 plan maestro.

Snapshot semanal manual de reviews externas (Google + TripAdvisor).
Migración manual en Render como pide la convención del proyecto.
"""
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0085_encuesta_contacto_telefono'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReviewSnapshot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(default=django.utils.timezone.localdate, db_index=True, help_text='Lunes de la semana del snapshot. Solo 1 por fecha.', unique=True)),
                ('google_rating', models.DecimalField(blank=True, decimal_places=2, help_text='Rating promedio Google (1.00 - 5.00)', max_digits=3, null=True)),
                ('google_total', models.PositiveIntegerField(blank=True, help_text='Total de reviews acumuladas en Google', null=True)),
                ('google_url', models.URLField(blank=True, help_text='URL del perfil de Google Maps (autocompletada desde el último snapshot)', max_length=500)),
                ('tripadvisor_rating', models.DecimalField(blank=True, decimal_places=2, help_text='Rating promedio TripAdvisor (1.00 - 5.00)', max_digits=3, null=True)),
                ('tripadvisor_total', models.PositiveIntegerField(blank=True, help_text='Total de reviews acumuladas en TripAdvisor', null=True)),
                ('tripadvisor_url', models.URLField(blank=True, help_text='URL del perfil de TripAdvisor (autocompletada desde el último snapshot)', max_length=500)),
                ('notas', models.TextField(blank=True, help_text='Cualquier observación relevante: review reciente notable, cambio de rating, comentarios destacados...')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Snapshot de reviews externas',
                'verbose_name_plural': 'Snapshots de reviews externas',
                'ordering': ['-fecha'],
            },
        ),
    ]
