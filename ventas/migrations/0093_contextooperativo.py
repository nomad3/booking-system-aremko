"""Modelo ContextoOperativo: singleton con sección manual + caché automática.

Inyectable como markdown al system prompt de análisis IA (aremko-cli).

Migración manual en Render (regla del proyecto).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0092_cotizacion_empresa'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContextoOperativo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('seccion_manual', models.TextField(
                    blank=True,
                    help_text=(
                        "Markdown editable. Información que NO está en código pero el LLM debería saber: "
                        "campañas de marketing activas, decisiones de management, alianzas vigentes, "
                        "iniciativas externas, etc."
                    ),
                    verbose_name='Sección manual (markdown editable)',
                )),
                ('seccion_automatica_cache', models.TextField(
                    blank=True,
                    editable=False,
                    help_text='Generada automáticamente desde el código. No editar manualmente.',
                    verbose_name='Sección automática (caché)',
                )),
                ('seccion_automatica_actualizada_en', models.DateTimeField(
                    blank=True, null=True, editable=False,
                    verbose_name='Última regeneración automática',
                )),
            ],
            options={
                'verbose_name': 'Contexto Operativo',
                'verbose_name_plural': 'Contexto Operativo',
            },
        ),
    ]
