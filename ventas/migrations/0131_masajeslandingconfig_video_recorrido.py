# -*- coding: utf-8 -*-
# Migración escrita a mano (NO con makemigrations) para agregar SOLO la columna
# video_recorrido a MasajesLandingConfig, evitando el drift de AR-034 (mismo
# criterio que 0126/0127/0128/0130).
#
# SeparateDatabaseAndState + ADD COLUMN IF NOT EXISTS (idempotente) para deploy
# seguro; la columna es nullable, así que la instancia vieja la ignora.
import cloudinary_storage.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0130_homepageconfig_hero_video'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE ventas_masajeslandingconfig "
                        "ADD COLUMN IF NOT EXISTS video_recorrido varchar(255) NULL;",
                    reverse_sql="ALTER TABLE ventas_masajeslandingconfig "
                                "DROP COLUMN IF EXISTS video_recorrido;",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='masajeslandingconfig',
                    name='video_recorrido',
                    field=models.FileField(
                        blank=True, null=True, max_length=255,
                        upload_to='masajes_landing/',
                        storage=cloudinary_storage.storage.VideoMediaCloudinaryStorage(),
                        help_text="EL RECORRIDO COMPLETO: video largo del pasillo → pasarelas → "
                                  "mirador, CON audio del río, que el visitante reproduce con "
                                  "controles (no es de fondo). Se muestra en su propia sección tras "
                                  "el circuito. Si está vacío, esa sección no aparece. mp4 comprimido "
                                  "(idealmente <25MB para que suba sin timeout).",
                    ),
                ),
            ],
        ),
    ]
