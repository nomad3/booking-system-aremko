"""Modelos WeeklySurveyAnalysis + WeeklyObjective para enriquecer el brief.

WeeklySurveyAnalysis: cache del analisis IA de encuestas (lunes 9 AM)
WeeklyObjective: objetivo de la semana editable desde admin (Jorge)

Migracion manual en Render (regla del proyecto).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0089_metasnapshot'),
    ]

    operations = [
        migrations.CreateModel(
            name='WeeklySurveyAnalysis',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('semana_inicio', models.DateField(db_index=True, help_text='Lunes de la semana que se analizo')),
                ('semana_fin', models.DateField(help_text='Domingo de la semana que se analizo')),
                ('encuestas_count', models.PositiveIntegerField(default=0)),
                ('nps_promedio', models.FloatField(blank=True, null=True)),
                ('datos', models.JSONField(help_text='Output completo del LLM: resumen, alertas, oportunidades, ideas marketing, follow-ups urgentes')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'verbose_name': 'Analisis IA encuestas semanal',
                'verbose_name_plural': 'Analisis IA encuestas semanales',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='weeklysurveyanalysis',
            index=models.Index(fields=['-created_at'], name='ventas_weekl_created_idx'),
        ),
        migrations.AddIndex(
            model_name='weeklysurveyanalysis',
            index=models.Index(fields=['-semana_inicio'], name='ventas_weekl_sem_inic_idx'),
        ),
        migrations.CreateModel(
            name='WeeklyObjective',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('semana_inicio', models.DateField(
                    db_index=True, unique=True,
                    help_text='Lunes de la semana a la que aplica este objetivo',
                )),
                ('objetivo', models.TextField(
                    help_text='Texto libre. 2-3 parrafos. Que se quiere priorizar esta semana, '
                              'que evitar, que metricas mover, fechas clave del periodo.',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Objetivo semanal',
                'verbose_name_plural': 'Objetivos semanales',
                'ordering': ['-semana_inicio'],
            },
        ),
    ]
