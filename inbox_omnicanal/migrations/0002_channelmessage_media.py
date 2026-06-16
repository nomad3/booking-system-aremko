"""Adjuntos de Instagram (Fase 5): agrega media_file / mime_type / original_filename
a ChannelMessage (foto/audio/video subidos por aremko-cli vía /api/instagram/inbound-media).

Mismo patrón que ventas.0120: SeparateDatabaseAndState + `ADD COLUMN IF NOT EXISTS`
para deploy seguro/idempotente sin downtime (migrate MANUAL en Render; la bandeja IG
está en uso). Las columnas se pueden agregar a mano ANTES, evitando la ventana en que
el código nuevo consulta columnas inexistentes.

Nota: `storage=RawMediaCloudinaryStorage()` se define en el MODELO; no afecta el esquema
(la columna es solo varchar con la ruta del archivo).
"""

import cloudinary_storage.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inbox_omnicanal', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='channelmessage',
                    name='media_file',
                    field=models.FileField(
                        blank=True, null=True, max_length=255,
                        upload_to='instagram/',
                        storage=cloudinary_storage.storage.RawMediaCloudinaryStorage(),
                        help_text='Adjunto del DM (foto/audio/video). Nombre con UUID.',
                    ),
                ),
                migrations.AddField(
                    model_name='channelmessage',
                    name='mime_type',
                    field=models.CharField(blank=True, max_length=120, help_text='Ej. image/jpeg, audio/ogg.'),
                ),
                migrations.AddField(
                    model_name='channelmessage',
                    name='original_filename',
                    field=models.CharField(blank=True, max_length=255, help_text='Nombre original del archivo (si viene).'),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE inbox_omnicanal_channelmessage ADD COLUMN IF NOT EXISTS media_file varchar(255) NULL;"
                        "ALTER TABLE inbox_omnicanal_channelmessage ADD COLUMN IF NOT EXISTS mime_type varchar(120) NOT NULL DEFAULT '';"
                        "ALTER TABLE inbox_omnicanal_channelmessage ADD COLUMN IF NOT EXISTS original_filename varchar(255) NOT NULL DEFAULT '';"
                    ),
                    reverse_sql=(
                        "ALTER TABLE inbox_omnicanal_channelmessage DROP COLUMN IF EXISTS media_file;"
                        "ALTER TABLE inbox_omnicanal_channelmessage DROP COLUMN IF EXISTS mime_type;"
                        "ALTER TABLE inbox_omnicanal_channelmessage DROP COLUMN IF EXISTS original_filename;"
                    ),
                ),
            ],
        ),
    ]
