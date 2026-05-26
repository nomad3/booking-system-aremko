"""
0106_contactowhatsapp_estado_expirado_acumulacion
==================================================

Agrega el nuevo estado 'expirado_acumulacion' a las choices de
ContactoWhatsApp.estado.

Contexto:
    Feature de acumulación de pendientes entre días — cuando un contacto
    queda pendiente más de OVC_DIAS_MAX_ACUMULACION días (default 7), el
    cron lo marca como 'expirado_acumulacion' para que la bandeja no se
    atasque indefinidamente. El cliente puede volver a entrar más adelante
    si su clasificación lo selecciona en un cron posterior.

Migración trivial: solo AlterField sobre choices. No requiere data
migration ni cambio en valores existentes.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0105_fix_mesa_chica_a_preferentes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contactowhatsapp',
            name='estado',
            field=models.CharField(
                choices=[
                    ('pendiente', 'Pendiente'),
                    ('enviado', 'Enviado'),
                    ('omitido', 'Omitido (sin enviar)'),
                    ('no_aplica', 'No aplica'),
                    ('descartado', 'Descartado por revalidación'),
                    ('expirado_acumulacion', 'Expirado por acumulación (>7 días sin acción)'),
                ],
                db_index=True,
                default='pendiente',
                max_length=20,
            ),
        ),
    ]
