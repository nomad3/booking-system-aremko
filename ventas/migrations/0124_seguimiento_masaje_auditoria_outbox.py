from django.db import migrations, models


class Migration(migrations.Migration):
    """Bandeja de salida de masajes: campos de auditoría en
    SeguimientoBienestarMasaje (quién envió / quién y cuándo editó), para el
    envío manual revisado desde aremko-cli.

    Mismo patrón zero-downtime que 0122/0123: SeparateDatabaseAndState +
    ADD COLUMN IF NOT EXISTS (migrate MANUAL en Render).
    """

    dependencies = [
        ('ventas', '0123_bienestarficha_alergia_aceites'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='seguimientobienestarmasaje',
                    name='enviado_por',
                    field=models.CharField(
                        blank=True, max_length=80,
                        help_text='Operador que envió el correo (debora/angelica/jorge).',
                    ),
                ),
                migrations.AddField(
                    model_name='seguimientobienestarmasaje',
                    name='editado_por',
                    field=models.CharField(
                        blank=True, max_length=80,
                        help_text='Operador que editó por última vez asunto/cuerpo.',
                    ),
                ),
                migrations.AddField(
                    model_name='seguimientobienestarmasaje',
                    name='editado_at',
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE ventas_seguimientobienestarmasaje ADD COLUMN IF NOT EXISTS enviado_por varchar(80) NOT NULL DEFAULT '';"
                        "ALTER TABLE ventas_seguimientobienestarmasaje ADD COLUMN IF NOT EXISTS editado_por varchar(80) NOT NULL DEFAULT '';"
                        "ALTER TABLE ventas_seguimientobienestarmasaje ADD COLUMN IF NOT EXISTS editado_at timestamp with time zone NULL;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE ventas_seguimientobienestarmasaje DROP COLUMN IF EXISTS enviado_por;"
                        "ALTER TABLE ventas_seguimientobienestarmasaje DROP COLUMN IF EXISTS editado_por;"
                        "ALTER TABLE ventas_seguimientobienestarmasaje DROP COLUMN IF EXISTS editado_at;"
                    ),
                ),
            ],
        ),
    ]
