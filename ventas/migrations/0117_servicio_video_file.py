from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Agrega Servicio.video (FileField) para subir un video corto desde el admin
    (almacenado en Cloudinary como resource_type=video via el storage del modelo).

    Igual que 0116: SeparateDatabaseAndState + `ADD COLUMN IF NOT EXISTS` para
    deploy seguro/idempotente (simple o sin downtime, sin --fake).

    Nota: el `storage=VideoMediaCloudinaryStorage()` se define en el campo del
    MODELO (no afecta el esquema de BD: la columna es solo varchar con la ruta).
    Por eso aquí no se incluye storage, para mantener la migración desacoplada.
    """

    dependencies = [
        ('ventas', '0116_servicio_video_url'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='servicio',
                    name='video',
                    field=models.FileField(
                        blank=True,
                        null=True,
                        max_length=255,
                        upload_to='servicios/videos/',
                        help_text=(
                            'Video corto opcional subido desde tu computador (mp4/webm, '
                            'idealmente <15 seg y liviano). Si se sube, se muestra en la card '
                            "en lugar de las fotos. Para videos grandes ya hosteados, usa 'Video URL'."
                        ),
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE ventas_servicio ADD COLUMN IF NOT EXISTS video varchar(255) NULL;",
                    reverse_sql="ALTER TABLE ventas_servicio DROP COLUMN IF EXISTS video;",
                ),
            ],
        ),
    ]
