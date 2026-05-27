"""
0110_contactowhatsapp_es_relleno
=================================

Agrega campo `es_relleno` (BooleanField, indexed) a ContactoWhatsApp.

Solicitado por aremko-cli 2026-05-27 PM: distinguir contactos óptimos
(P0-P4) vs los que entraron por fallback del target OVC_TARGET_DIARIO
(P5/P6 cuando los óptimos no llenaron cupo).

Permite análisis diferenciado de conversión: si tasa_conversion_optimos
es muy distinta a tasa_conversion_rellenos, evaluamos revertir el
fallback o ajustar política.

Migración trivial: solo AddField. Sin data migration.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0109_cliente_es_staff_proxy'),
    ]

    operations = [
        migrations.AddField(
            model_name='contactowhatsapp',
            name='es_relleno',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    'True si entró por fallback target (P5/P6 que llenaron cupo). '
                    'False si vino de prioridad óptima P0-P4 propia.'
                ),
            ),
        ),
    ]
