"""Modelos GA4Snapshot y SearchConsoleSnapshot.

Persisten metricas semanales de Google Analytics 4 y Search Console.
Hasta hoy ambos se consultaban en vivo en cada brief y se perdia el dato
historico. Estos snapshots permiten ver tendencias semana-vs-semana y
mes-vs-mes (Fase 2 del plan marketing integral).

Migracion manual en Render (regla del proyecto).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0090_weeklysurveyanalysis_weeklyobjective'),
    ]

    operations = [
        migrations.CreateModel(
            name='GA4Snapshot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_snapshot', models.DateField(
                    db_index=True,
                    help_text='Fecha del snapshot (tipicamente lunes de la semana)',
                )),
                ('datos', models.JSONField(help_text='JSON completo de ga4_reporter.get_full_snapshot()')),
                ('sessions', models.PositiveIntegerField(default=0)),
                ('total_users', models.PositiveIntegerField(default=0)),
                ('new_users', models.PositiveIntegerField(default=0)),
                ('engaged_sessions', models.PositiveIntegerField(default=0)),
                ('avg_session_duration', models.FloatField(
                    default=0, help_text='Segundos promedio por sesion',
                )),
                ('screen_page_views', models.PositiveIntegerField(default=0)),
                ('conversions', models.PositiveIntegerField(default=0)),
                ('whatsapp_clicks', models.PositiveIntegerField(default=0)),
                ('phone_clicks', models.PositiveIntegerField(default=0)),
                ('cta_blog_clicks', models.PositiveIntegerField(default=0)),
                ('reservation_started', models.PositiveIntegerField(default=0)),
                ('reservation_completed', models.PositiveIntegerField(default=0)),
                ('generado_por', models.CharField(
                    choices=[
                        ('cron_weekly', 'Cron semanal (lunes)'),
                        ('management_command', 'Comando manual desde shell'),
                        ('admin_manual', 'Admin Django (manual)'),
                    ],
                    db_index=True,
                    default='cron_weekly',
                    max_length=30,
                )),
                ('error', models.TextField(blank=True, help_text='Errores parciales si los hubo')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'verbose_name': 'Snapshot GA4 (semanal)',
                'verbose_name_plural': 'Snapshots GA4 (semanales)',
                'ordering': ['-fecha_snapshot', '-created_at'],
                'indexes': [
                    models.Index(fields=['-fecha_snapshot'], name='ventas_ga4s_fecha_s_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='SearchConsoleSnapshot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_snapshot', models.DateField(
                    db_index=True,
                    help_text='Fecha del snapshot (tipicamente lunes de la semana)',
                )),
                ('datos', models.JSONField(help_text='JSON completo de gsc_reporter.get_full_snapshot()')),
                ('clicks', models.PositiveIntegerField(default=0)),
                ('impressions', models.PositiveIntegerField(default=0)),
                ('ctr', models.FloatField(default=0, help_text='Click-through rate %, 0-100')),
                ('position', models.FloatField(
                    default=0, help_text='Posicion promedio ponderada por impresiones',
                )),
                ('generado_por', models.CharField(
                    choices=[
                        ('cron_weekly', 'Cron semanal (lunes)'),
                        ('management_command', 'Comando manual desde shell'),
                        ('admin_manual', 'Admin Django (manual)'),
                    ],
                    db_index=True,
                    default='cron_weekly',
                    max_length=30,
                )),
                ('error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'verbose_name': 'Snapshot Search Console (semanal)',
                'verbose_name_plural': 'Snapshots Search Console (semanales)',
                'ordering': ['-fecha_snapshot', '-created_at'],
                'indexes': [
                    models.Index(fields=['-fecha_snapshot'], name='ventas_gsc_fecha_s_idx'),
                ],
            },
        ),
    ]
