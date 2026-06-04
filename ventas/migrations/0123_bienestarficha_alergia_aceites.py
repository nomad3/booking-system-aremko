from django.db import migrations, models


class Migration(migrations.Migration):
    """Ficha de bienestar: pregunta de sensibilidad/alergia a aceites de masaje.
    Agrega alergia_aceites (bool) + alergia_aceites_detalle (texto).

    Mismo patrón zero-downtime que las anteriores: SeparateDatabaseAndState +
    ADD COLUMN IF NOT EXISTS (migrate MANUAL en Render).
    """

    dependencies = [
        ('ventas', '0122_proveedor_usuario'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='bienestarmasajeficha',
                    name='alergia_aceites',
                    field=models.BooleanField(
                        default=False,
                        verbose_name='¿Sensibilidad o alergia a algún aceite de masaje?',
                    ),
                ),
                migrations.AddField(
                    model_name='bienestarmasajeficha',
                    name='alergia_aceites_detalle',
                    field=models.CharField(
                        blank=True, max_length=255,
                        verbose_name='¿A cuál aceite?',
                        help_text='Indica el/los aceite(s) a evitar, si la persona lo sabe.',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE ventas_bienestarmasajeficha ADD COLUMN IF NOT EXISTS alergia_aceites boolean NOT NULL DEFAULT false;"
                        "ALTER TABLE ventas_bienestarmasajeficha ADD COLUMN IF NOT EXISTS alergia_aceites_detalle varchar(255) NOT NULL DEFAULT '';"
                    ),
                    reverse_sql=(
                        "ALTER TABLE ventas_bienestarmasajeficha DROP COLUMN IF EXISTS alergia_aceites;"
                        "ALTER TABLE ventas_bienestarmasajeficha DROP COLUMN IF EXISTS alergia_aceites_detalle;"
                    ),
                ),
            ],
        ),
    ]
