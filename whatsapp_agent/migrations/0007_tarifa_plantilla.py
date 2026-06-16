"""H-021: tarifa por plantilla de marketing (CLP) en la config del agente.

Editable desde el admin (formulario de config), no por env. La usa el tablero de
métricas para estimar el costo de las campañas.

Patrón SeparateDatabaseAndState + `ADD COLUMN IF NOT EXISTS` (sin downtime): la columna
se pre-agrega a mano ANTES de desplegar el código, porque `WhatsAppAgentConfig.get_solo()`
se consulta en el inbound en vivo — si el modelo tuviera el campo y la columna no existiera,
se caería el agente en ambos canales. En PostgreSQL `PositiveIntegerField` es `integer`
plano (sin CHECK), así que el SQL calza con el estado del ORM.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_agent', '0006_sugerenciaaprendizaje'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='whatsappagentconfig',
                    name='tarifa_plantilla_clp',
                    field=models.PositiveIntegerField(
                        default=0,
                        verbose_name='Tarifa por plantilla de marketing (CLP)',
                        help_text='Costo por mensaje de plantilla de marketing (WhatsApp), en CLP. '
                                  '0 = sin configurar (el tablero de métricas muestra costo nulo).',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE whatsapp_agent_whatsappagentconfig ADD COLUMN IF NOT EXISTS tarifa_plantilla_clp integer NOT NULL DEFAULT 0;",
                    reverse_sql="ALTER TABLE whatsapp_agent_whatsappagentconfig DROP COLUMN IF EXISTS tarifa_plantilla_clp;",
                ),
            ],
        ),
    ]
