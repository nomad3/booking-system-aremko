# -*- coding: utf-8 -*-
# Migración escrita a mano (NO con makemigrations) para agregar SOLO la columna
# hero_video a HomepageConfig, evitando el drift de AR-034 (mismo criterio que
# 0126/0127/0128).
#
# HomepageConfig se lee en CADA carga de la portada (hot-path). Para desplegar
# sin downtime, la operación de BD usa ADD COLUMN IF NOT EXISTS (idempotente):
# si la columna se pre-agregó a mano, no falla; si no, la crea. SeparateDatabase
# AndState separa el efecto en BD (RunSQL) del estado del ORM (AddField), para
# que Django registre el campo sin volver a intentar un ALTER que podría chocar.
import cloudinary_storage.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0129_giftcard_experiencia_galeria'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE ventas_homepageconfig "
                        "ADD COLUMN IF NOT EXISTS hero_video varchar(255) NULL;",
                    reverse_sql="ALTER TABLE ventas_homepageconfig "
                                "DROP COLUMN IF EXISTS hero_video;",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='homepageconfig',
                    name='hero_video',
                    field=models.FileField(
                        blank=True, null=True, max_length=255,
                        upload_to='homepage/',
                        storage=cloudinary_storage.storage.VideoMediaCloudinaryStorage(),
                        help_text="VIDEO DE PORTADA: se reproduce de fondo en el hero de la "
                                  "home (autoplay, silenciado, en loop). La imagen de fondo "
                                  "de arriba queda de respaldo mientras el video carga o si "
                                  "está vacío. mp4 <5MB (comprimir antes). Ideal 15-25 seg "
                                  "con loop natural.",
                    ),
                ),
            ],
        ),
    ]
