"""Modelo DocumentoSistemaCache (singleton).

Cache de la narrativa del documento maestro del sistema, generada por LLM.
Se regenera explícitamente desde botón en admin.

Migración manual en Render (regla del proyecto).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0093_contextooperativo'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentoSistemaCache',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('narrativa_md', models.TextField(
                    blank=True,
                    help_text='Cuerpo narrativo del documento maestro, generado por LLM. Se combina con inventarios live al descargar el PDF.',
                    verbose_name='Narrativa cacheada (markdown)',
                )),
                ('actualizado_en', models.DateTimeField(blank=True, editable=False, null=True)),
                ('generado_por_modelo', models.CharField(
                    blank=True, editable=False, max_length=100,
                    verbose_name='Modelo LLM usado',
                )),
                ('tokens_input', models.IntegerField(default=0, editable=False)),
                ('tokens_output', models.IntegerField(default=0, editable=False)),
                ('costo_usd_aprox', models.DecimalField(
                    decimal_places=4, default=0, editable=False, max_digits=8,
                    verbose_name='Costo estimado USD',
                )),
                ('introspect_snapshot', models.JSONField(
                    blank=True, default=dict, editable=False,
                    help_text='Snapshot del estado del sistema al momento de generar (modelos, endpoints, etc.)',
                )),
            ],
            options={
                'verbose_name': 'Documento del Sistema (cache)',
                'verbose_name_plural': 'Documento del Sistema (cache)',
            },
        ),
    ]
