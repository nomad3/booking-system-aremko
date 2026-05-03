"""Migración: agregar campo contacto_telefono a EncuestaSatisfaccion.

Permite capturar teléfono opcional en el form para contactar al cliente
si requiere follow-up (especialmente útil cuando no hay Cliente vinculado).

⚠️ EJECUCIÓN MANUAL — esta migración NO corre automáticamente.
Debe ejecutarse desde shell de Render con:
    python manage.py migrate ventas 0085_encuesta_contacto_telefono
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0084_encuestasatisfaccion'),
    ]

    operations = [
        migrations.AddField(
            model_name='encuestasatisfaccion',
            name='contacto_telefono',
            field=models.CharField(
                blank=True, max_length=30,
                help_text=(
                    'Teléfono opcional para contacto si requiere follow-up. '
                    'Si la encuesta viene vinculada a un Cliente, se prellena con su teléfono.'
                ),
            ),
        ),
    ]
