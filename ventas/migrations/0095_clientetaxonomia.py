"""
Migración: crea la tabla ventas_clientetaxonomia.

Modelo de etiquetas multidimensionales (Valor + Estilo + Contexto) + snapshot
de features por cliente. Diseñado en base al análisis exploratorio del
comando analyze_customer_taxonomy v4 (commit a3bd2d4).

Importante: esta migración SOLO crea la nueva tabla. No toca ninguna otra
estructura. Se ejecuta manual en Render con `python manage.py migrate ventas`
después de hacer pull de este commit.

No requiere data backfill — el comando recalcular_taxonomia_clientes (Paso 2)
poblará las filas en una primera corrida.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0094_documentosistemacache'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClienteTaxonomia',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),

                # ----- Etiquetas (3 ejes) -----
                ('eje_valor', models.CharField(choices=[
                    ('Campeón', 'Campeón'),
                    ('Leal', 'Leal'),
                    ('Gran Gastador Ocasional', 'Gran Gastador Ocasional'),
                    ('Regular', 'Regular'),
                    ('En Prueba', 'En Prueba'),
                    ('En Riesgo', 'En Riesgo'),
                    ('Dormido', 'Dormido'),
                    ('Pre-sistema', 'Pre-sistema'),
                ], db_index=True, max_length=40)),
                ('eje_estilo', models.CharField(choices=[
                    ('Devoto del Masaje', 'Devoto del Masaje'),
                    ('Amante de las Tinas', 'Amante de las Tinas'),
                    ('Experiencia Completa', 'Experiencia Completa'),
                    ('Buscador de Alojamiento', 'Buscador de Alojamiento'),
                    ('Probador Esporádico', 'Probador Esporádico'),
                    ('N/A (pre-sistema)', 'N/A (pre-sistema)'),
                ], db_index=True, max_length=40)),
                ('eje_contexto', models.CharField(choices=[
                    ('Pareja Romántica', 'Pareja Romántica'),
                    ('Auto-cuidado Solo', 'Auto-cuidado Solo'),
                    ('Grupo', 'Grupo'),
                    ('Familiar', 'Familiar'),
                    ('Turista Estacional', 'Turista Estacional'),
                    ('Local Frecuente', 'Local Frecuente'),
                    ('Visitante Solo', 'Visitante Solo'),
                    ('Visitante Pareja', 'Visitante Pareja'),
                    ('Visitante Grupal', 'Visitante Grupal'),
                    ('Sin clasificar', 'Sin clasificar'),
                    ('N/A (pre-sistema)', 'N/A (pre-sistema)'),
                ], db_index=True, max_length=40)),

                # ----- Metadatos del cálculo -----
                ('meses_ventana', models.PositiveSmallIntegerField(
                    default=24,
                    help_text='Horizonte (en meses) usado para computar este snapshot.'
                )),
                ('calculado_en', models.DateTimeField(
                    auto_now=True, db_index=True,
                    help_text='Última vez que se recalculó este snapshot.'
                )),

                # ----- Snapshot sistema actual -----
                ('total_visitas', models.IntegerField(default=0)),
                ('gasto_total', models.IntegerField(default=0, help_text='CLP')),
                ('ticket_promedio', models.IntegerField(default=0, help_text='CLP')),
                ('primera_visita_actual', models.DateField(blank=True, null=True)),
                ('ultima_visita', models.DateField(blank=True, null=True)),
                ('dias_desde_ultima_visita', models.IntegerField(blank=True, null=True)),
                ('dias_entre_visitas_avg', models.FloatField(blank=True, null=True)),
                ('meses_relacion_actual', models.FloatField(default=0)),

                # ----- Mix de servicios -----
                ('pct_tinas', models.FloatField(default=0)),
                ('pct_masajes', models.FloatField(default=0)),
                ('pct_cabanas', models.FloatField(default=0)),
                ('pct_otros', models.FloatField(default=0)),
                ('gasto_tinas', models.IntegerField(default=0, help_text='CLP')),
                ('gasto_masajes', models.IntegerField(default=0, help_text='CLP')),
                ('gasto_cabanas', models.IntegerField(default=0, help_text='CLP')),
                ('gasto_otros', models.IntegerField(default=0, help_text='CLP')),

                # ----- Patrón compañía -----
                ('avg_cantidad_personas', models.FloatField(blank=True, null=True)),
                ('pct_reservas_bundle', models.FloatField(default=0)),
                ('count_reservas_bundle', models.IntegerField(default=0)),

                # ----- Patrón temporal -----
                ('pct_finde', models.FloatField(default=0)),
                ('pct_verano', models.FloatField(default=0)),
                ('pct_otono', models.FloatField(default=0)),
                ('pct_invierno', models.FloatField(default=0)),
                ('pct_primavera', models.FloatField(default=0)),

                # ----- Historial pre-sistema -----
                ('tiene_historial_pre_sistema', models.BooleanField(default=False)),
                ('visitas_history_count', models.IntegerField(default=0)),
                ('primera_visita_global', models.DateField(blank=True, null=True)),
                ('antiguedad_meses', models.IntegerField(default=0)),

                # ----- FK -----
                ('cliente', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='taxonomia',
                    to='ventas.cliente',
                )),
            ],
            options={
                'verbose_name': 'Taxonomía de Cliente',
                'verbose_name_plural': 'Taxonomías de Clientes',
            },
        ),

        # Índices compuestos para queries frecuentes de cohortes
        migrations.AddIndex(
            model_name='clientetaxonomia',
            index=models.Index(fields=['eje_valor', 'eje_estilo'], name='idx_taxo_val_est'),
        ),
        migrations.AddIndex(
            model_name='clientetaxonomia',
            index=models.Index(fields=['eje_valor', 'eje_contexto'], name='idx_taxo_val_ctx'),
        ),
        migrations.AddIndex(
            model_name='clientetaxonomia',
            index=models.Index(fields=['eje_estilo', 'eje_contexto'], name='idx_taxo_est_ctx'),
        ),
    ]
