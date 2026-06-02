from django.db import migrations, models


class Migration(migrations.Migration):
    """Adjuntos de WhatsApp: agrega media_file / mime_type / original_filename
    a WhatsAppMessage (foto/PDF/voz/video subidos por aremko-cli vía
    /api/whatsapp/inbound-media).

    Mismo patrón que 0116/0117: SeparateDatabaseAndState + `ADD COLUMN IF NOT
    EXISTS` para deploy seguro/idempotente sin downtime (migrate MANUAL en Render).
    Las columnas se agregan a mano ANTES (o el migrate las crea si faltan), evitando
    la ventana en que el código nuevo consulta columnas inexistentes.

    Nota: `storage=RawMediaCloudinaryStorage()` se define en el MODELO; no afecta el
    esquema (la columna es solo varchar con la ruta del archivo).
    """

    dependencies = [
        ('ventas', '0119_whatsappmessage'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='whatsappmessage',
                    name='media_file',
                    field=models.FileField(
                        blank=True, null=True, max_length=255,
                        upload_to='whatsapp/',
                        help_text='Adjunto del mensaje (comprobante, foto, audio, etc.). Nombre con UUID.',
                    ),
                ),
                migrations.AddField(
                    model_name='whatsappmessage',
                    name='mime_type',
                    field=models.CharField(blank=True, max_length=120, help_text='Ej. image/jpeg, application/pdf, audio/ogg.'),
                ),
                migrations.AddField(
                    model_name='whatsappmessage',
                    name='original_filename',
                    field=models.CharField(blank=True, max_length=255, help_text='Nombre original del archivo (útil en documentos).'),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE ventas_whatsappmessage ADD COLUMN IF NOT EXISTS media_file varchar(255) NULL;"
                        "ALTER TABLE ventas_whatsappmessage ADD COLUMN IF NOT EXISTS mime_type varchar(120) NOT NULL DEFAULT '';"
                        "ALTER TABLE ventas_whatsappmessage ADD COLUMN IF NOT EXISTS original_filename varchar(255) NOT NULL DEFAULT '';"
                    ),
                    reverse_sql=(
                        "ALTER TABLE ventas_whatsappmessage DROP COLUMN IF EXISTS media_file;"
                        "ALTER TABLE ventas_whatsappmessage DROP COLUMN IF EXISTS mime_type;"
                        "ALTER TABLE ventas_whatsappmessage DROP COLUMN IF EXISTS original_filename;"
                    ),
                ),
            ],
        ),
    ]
