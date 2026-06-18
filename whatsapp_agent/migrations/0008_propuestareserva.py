# Generated migration for H-028: PropuestaReserva model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_agent', '0007_tarifa_plantilla'),
    ]

    operations = [
        migrations.CreateModel(
            name='PropuestaReserva',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('propuesta_id', models.CharField(db_index=True, max_length=36, unique=True)),
                ('canal', models.CharField(max_length=20)),
                ('external_id', models.CharField(db_index=True, max_length=50)),
                ('cliente_data', models.JSONField(help_text='{"nombre", "email", "documento_identidad", "region_id", "comuna_id"}')),
                ('servicios', models.JSONField(help_text='[{"servicio_id": N, "fecha": "2026-06-20", "hora": "14:00", "cantidad_personas": 2}]')),
                ('total', models.DecimalField(decimal_places=0, max_digits=10)),
                ('resumen', models.TextField(blank=True, help_text='Texto resumido para aprobación')),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente aprobación'), ('creada', 'Reserva creada'), ('cancelada', 'Cancelada por usuario'), ('expirada', 'Expirada (>1h)')], db_index=True, default='pendiente', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(help_text='Propuesta válida 1 hora')),
                ('creada_at', models.DateTimeField(blank=True, help_text='Cuándo se creó la reserva', null=True)),
            ],
            options={
                'verbose_name': 'Propuesta de reserva',
                'verbose_name_plural': 'Propuestas de reserva',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='propuestareserva',
            index=models.Index(fields=['canal', 'external_id', 'estado'], name='whatsapp_ag_canal_abc123_idx'),
        ),
    ]
