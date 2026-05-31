from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Agrega Servicio.video_url (URL de video corto opcional por servicio).

    Se usa SeparateDatabaseAndState con `ADD COLUMN IF NOT EXISTS` para que la
    migracion sea segura e idempotente en ambos flujos de deploy:

    - Deploy simple: `migrate` agrega la columna normalmente.
    - Deploy sin downtime: se agrega la columna a mano ANTES del deploy con
      `ALTER TABLE ventas_servicio ADD COLUMN IF NOT EXISTS video_url varchar(500) NOT NULL DEFAULT '';`
      y luego `migrate` corre el RunSQL como no-op (IF NOT EXISTS) y solo
      actualiza el estado de Django. No requiere --fake.
    """

    dependencies = [
        ('ventas', '0115_plantillas_refugio_aremko'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='servicio',
                    name='video_url',
                    field=models.URLField(
                        blank=True,
                        default='',
                        max_length=500,
                        help_text=(
                            'URL de un video corto opcional (mp4/webm directo, ej. Cloudinary). '
                            'Si se completa, se muestra en la card en lugar de las fotos. '
                            'Si queda vacio, se muestran las fotos.'
                        ),
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE ventas_servicio ADD COLUMN IF NOT EXISTS video_url varchar(500) NOT NULL DEFAULT '';",
                    reverse_sql="ALTER TABLE ventas_servicio DROP COLUMN IF EXISTS video_url;",
                ),
            ],
        ),
    ]
