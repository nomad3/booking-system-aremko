"""Modelo MetaSnapshot: snapshots consolidados de Facebook + Instagram + Ads.

Generados manualmente desde admin (botones de diagnostico) o automaticamente
desde el brief semanal (lunes 10am). Datos servidos por meta_reporter.py
via Meta Graph API v21.0.

Migracion manual en Render (regla del proyecto).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0088_pendingreservation'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetaSnapshot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(
                    choices=[
                        ('full', 'Completo (FB + IG + Ads)'),
                        ('facebook', 'Solo Facebook'),
                        ('instagram', 'Solo Instagram'),
                        ('ads', 'Solo Ads (paid)'),
                    ],
                    db_index=True,
                    default='full',
                    max_length=20,
                )),
                ('period_days', models.PositiveIntegerField(
                    default=28,
                    help_text='Ventana de dias del snapshot (28 default para tendencia mensual)',
                )),
                ('datos', models.JSONField(help_text='JSON completo devuelto por meta_reporter')),
                ('analisis_ia', models.TextField(
                    blank=True,
                    help_text='Analisis IA del snapshot (cache, opcional)',
                )),
                ('generado_por', models.CharField(
                    choices=[
                        ('admin_manual', 'Admin Django (manual)'),
                        ('cron_weekly', 'Cron semanal (lunes)'),
                        ('management_command', 'Comando manual desde shell'),
                        ('api', 'API endpoint'),
                    ],
                    db_index=True,
                    default='admin_manual',
                    max_length=30,
                )),
                ('error', models.TextField(blank=True, help_text='Mensajes de error si la captura fue parcial')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'verbose_name': 'Snapshot Meta (FB + IG + Ads)',
                'verbose_name_plural': 'Snapshots Meta',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='metasnapshot',
            index=models.Index(fields=['-created_at'], name='ventas_meta_created_idx'),
        ),
        migrations.AddIndex(
            model_name='metasnapshot',
            index=models.Index(fields=['tipo', '-created_at'], name='ventas_meta_tipo_creat_idx'),
        ),
    ]
