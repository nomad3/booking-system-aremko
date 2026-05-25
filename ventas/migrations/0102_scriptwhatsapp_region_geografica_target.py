"""
Migración: Etapa Geo.3.a — campo region_geografica_target en ScriptWhatsApp.

Permite que cada plantilla de WhatsApp declare a qué región geográfica
del cliente está dirigida:
  - ''               : cualquier región (fallback, sirve para 'sur')
  - 'sur'            : plantilla específica para sur (futuro)
  - 'nacional'       : plantillas con propuesta de pack alojamiento
  - 'sin_clasificar' : plantillas neutras que capturan implícitamente ubicación

Las 17 plantillas existentes quedan con default='' (cualquier región),
manteniendo backward-compatibility — siguen funcionando como hasta ahora
para clientes 'sur' (la mayoría). Las plantillas nuevas para 'nacional' y
'sin_clasificar' las carga la migración data 0104.

Sin data backfill: las filas existentes mantienen default=''.

Próximo: 0103 reservado para plantillas seed.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0101_seed_ciudades_extra'),
    ]

    operations = [
        migrations.AddField(
            model_name='scriptwhatsapp',
            name='region_geografica_target',
            field=models.CharField(
                max_length=20,
                blank=True, default='',
                choices=[
                    ('', 'Cualquier región'),
                    ('sur', 'Sur'),
                    ('nacional', 'Resto de Chile'),
                    ('sin_clasificar', 'Sin clasificar'),
                ],
                help_text=(
                    'Región geográfica del cliente a la que aplica esta plantilla. '
                    "Vacío = aplica a cualquier región (fallback). "
                    "'sur'/'nacional'/'sin_clasificar' = plantilla específica."
                ),
            ),
        ),
        migrations.AddIndex(
            model_name='scriptwhatsapp',
            index=models.Index(
                fields=['region_geografica_target', 'estado_valor_target', 'salva'],
                name='idx_script_region_match',
            ),
        ),
    ]
