from django.db import migrations, models


class Migration(migrations.Migration):
    """Cloud API: mapeo de ScriptWhatsApp a plantilla aprobada de Meta.
    Agrega meta_template_name / meta_language / meta_variables_orden.

    Mismo patrón que 0116/0117/0120: SeparateDatabaseAndState + ADD COLUMN IF
    NOT EXISTS para deploy seguro/idempotente sin downtime (migrate MANUAL en
    Render). Correr el SQL ANTES (o el migrate lo crea si falta) evita la ventana
    en que el código nuevo consulta columnas inexistentes.
    """

    dependencies = [
        ('ventas', '0120_whatsappmessage_media'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='scriptwhatsapp',
                    name='meta_template_name',
                    field=models.CharField(
                        blank=True, max_length=100,
                        help_text="Nombre de la plantilla aprobada en Meta (ej. 'vuelta_en_riesgo_1'). Vacío = no se envía automático.",
                    ),
                ),
                migrations.AddField(
                    model_name='scriptwhatsapp',
                    name='meta_language',
                    field=models.CharField(
                        default='es', max_length=10,
                        help_text="Código de idioma de la plantilla en Meta (ej. 'es'). Meta no tiene es_CL.",
                    ),
                ),
                migrations.AddField(
                    model_name='scriptwhatsapp',
                    name='meta_variables_orden',
                    field=models.JSONField(
                        blank=True, default=list,
                        help_text='Lista ordenada de placeholders que mapean a {{1}},{{2}}… de la plantilla Meta. Ej: ["nombre", "ultima_visita_humanizada"]. Vacío = plantilla sin variables.',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE ventas_scriptwhatsapp ADD COLUMN IF NOT EXISTS meta_template_name varchar(100) NOT NULL DEFAULT '';"
                        "ALTER TABLE ventas_scriptwhatsapp ADD COLUMN IF NOT EXISTS meta_language varchar(10) NOT NULL DEFAULT 'es';"
                        "ALTER TABLE ventas_scriptwhatsapp ADD COLUMN IF NOT EXISTS meta_variables_orden jsonb NOT NULL DEFAULT '[]'::jsonb;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE ventas_scriptwhatsapp DROP COLUMN IF EXISTS meta_template_name;"
                        "ALTER TABLE ventas_scriptwhatsapp DROP COLUMN IF EXISTS meta_language;"
                        "ALTER TABLE ventas_scriptwhatsapp DROP COLUMN IF EXISTS meta_variables_orden;"
                    ),
                ),
            ],
        ),
    ]
