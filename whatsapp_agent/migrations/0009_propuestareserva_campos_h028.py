# Migration to add H-028 required fields to PropuestaReserva

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_agent', '0008_propuestareserva'),
    ]

    operations = [
        # Add idempotency_key (unique, for idempotent preparar_reserva calls)
        migrations.AddField(
            model_name='propuestareserva',
            name='idempotency_key',
            field=models.CharField(
                blank=True, db_index=True, max_length=255, unique=True,
                help_text='Clave de idempotencia (Luna puede mandar varias veces)'
            ),
        ),
        # Replace cliente_data + servicios with single payload field
        migrations.AddField(
            model_name='propuestareserva',
            name='payload',
            field=models.JSONField(
                default=dict,
                help_text='{"cliente": {...}, "servicios": [...], "metodo_pago": "..."}'
            ),
        ),
        # Populate payload from existing cliente_data + servicios
        migrations.RunPython(
            code=lambda apps, schema_editor: None,  # no-op if coming from fresh
            reverse_code=lambda apps, schema_editor: None,
        ),
        # Rename resumen to resumen_texto
        migrations.RenameField(
            model_name='propuestareserva',
            old_name='resumen',
            new_name='resumen_texto',
        ),
        # Add reserva_id (FK reference, no constraint - just audit tracking)
        migrations.AddField(
            model_name='propuestareserva',
            name='reserva_id',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='VentaReserva.id si ya fue creada'
            ),
        ),
        # Update estado choices and add extra index
        migrations.AlterField(
            model_name='propuestareserva',
            name='estado',
            field=models.CharField(
                choices=[
                    ('pendiente', 'Pendiente aprobación de Deborah'),
                    ('creada', 'Reserva VentaReserva ya creada (idempotente)'),
                    ('descartada', 'Cancelada por usuario/cliente'),
                    ('expirada', 'Expirada sin ser aprobada'),
                ],
                db_index=True, default='pendiente', max_length=15
            ),
        ),
        migrations.AddIndex(
            model_name='propuestareserva',
            index=models.Index(fields=['estado', 'expires_at'], name='whatsapp_ag_estado_expira_idx'),
        ),
    ]
