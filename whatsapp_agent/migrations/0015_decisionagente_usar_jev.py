"""Encargo PROMPT_JEV_AREMKO.md, etapa 2: registro de decisiones e interruptor de Jev.

Escrita a mano: `makemigrations whatsapp_agent` arrastra drift ajeno de la app (renombres
de índices y AlterField en propuestareserva, recordatorioluna y temaconversacion,
AR-033/AR-034) que no es de este cambio y no se aplica aquí.

- `DecisionAgente`: tabla nueva y aditiva; nada la lee en el camino de los mensajes.
- `usar_jev_en_aprendizaje`: patrón sin downtime, igual que 0007. `WhatsAppAgentConfig.
  get_solo()` se consulta en cada mensaje entrante: si el modelo tuviera el campo y la
  columna no existiera, se caería Luna. La columna se pre-agrega a mano ANTES de desplegar
  (`ADD COLUMN IF NOT EXISTS`, que aquí queda como no-op) y esta migración sincroniza el
  estado.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_agent', '0014_lecturaimagen'),
    ]

    operations = [
        migrations.CreateModel(
            name='DecisionAgente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uso', models.CharField(db_index=True, help_text='Para qué se usó, ej. «aprendizaje.correccion».', max_length=60)),
                ('referencia', models.CharField(blank=True, db_index=True, help_text='A qué fila corresponde (ej. el id del feedback).', max_length=60)),
                ('respuestas', models.JSONField(blank=True, default=dict)),
                ('confianza', models.FloatField(blank=True, null=True)),
                ('modelo', models.CharField(blank=True, max_length=80)),
                ('costo_usd', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('duracion_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('error', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'verbose_name': 'Decisión del modelo',
                'verbose_name_plural': 'Decisiones del modelo',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='decisionagente',
            index=models.Index(fields=['uso', '-created_at'], name='whatsapp_ag_uso_e975d0_idx'),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='whatsappagentconfig',
                    name='usar_jev_en_aprendizaje',
                    field=models.BooleanField(
                        default=False,
                        help_text='Clasifica las correcciones con el modelo de decisión (Jev) en vez '
                                  'del prompt JSON. Si se apaga, vuelve al camino anterior.',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE whatsapp_agent_whatsappagentconfig ADD COLUMN IF NOT EXISTS usar_jev_en_aprendizaje boolean NOT NULL DEFAULT false;",
                    reverse_sql="ALTER TABLE whatsapp_agent_whatsappagentconfig DROP COLUMN IF EXISTS usar_jev_en_aprendizaje;",
                ),
            ],
        ),
    ]
