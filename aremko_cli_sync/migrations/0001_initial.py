# Migración inicial de aremko_cli_sync (H-058 · snapshot de gasto en Ads por programa)

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='WeeklyBriefSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fetched_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('success', models.BooleanField(default=False, help_text='True si el fetch a aremko-cli respondió 200 con datos utilizables.')),
                ('google_ads', models.JSONField(blank=True, default=dict, help_text='{"ritual": {"campaign_name", "weekly": [{label,spend,activity,reservas,ingresos}, ...]}, "refugio": {...}, "pausa": {...}}')),
                ('meta_ads', models.JSONField(blank=True, default=dict, help_text='Mismo shape que google_ads, para Meta Ads.')),
                ('error_message', models.TextField(blank=True, default='')),
            ],
            options={
                'verbose_name': 'Snapshot semanal aremko-cli',
                'verbose_name_plural': 'Snapshots semanales aremko-cli',
                'db_table': 'aremko_cli_sync_weeklybriefsnapshot',
                'ordering': ['-fetched_at'],
            },
        ),
    ]
