from django.db import migrations, models


class Migration(migrations.Migration):
    """Dos espacios más de preguntas frecuentes en SEOContent (faq_7 y faq_8).

    Jorge (17-09-2026) pidió agregar «¿Debo pagar por late check-out?» al final
    de las preguntas de alojamientos, y los 6 espacios ya estaban ocupados.

    Mismo patrón que 0116/0117/0120: SeparateDatabaseAndState + `ADD COLUMN IF
    NOT EXISTS`, idempotente, para migrate MANUAL en Render sin caída.

    Esta migración se sube SOLA, antes que los campos del modelo: así el migrate
    crea las columnas mientras el código vivo todavía no las lee. Recién después
    se despliega el modelo con faq_7/faq_8. Al revés, las páginas de categoría
    darían 500 entre el deploy y el migrate (SELECT de una columna inexistente).
    """

    dependencies = [
        ('ventas', '0137_renombra_medio_transferencia_mp'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='seocontent', name='faq_7_pregunta',
                    field=models.CharField(blank=True, max_length=200)),
                migrations.AddField(
                    model_name='seocontent', name='faq_7_respuesta',
                    field=models.TextField(blank=True)),
                migrations.AddField(
                    model_name='seocontent', name='faq_8_pregunta',
                    field=models.CharField(blank=True, max_length=200)),
                migrations.AddField(
                    model_name='seocontent', name='faq_8_respuesta',
                    field=models.TextField(blank=True)),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE ventas_seocontent ADD COLUMN IF NOT EXISTS faq_7_pregunta varchar(200) NOT NULL DEFAULT '';"
                        "ALTER TABLE ventas_seocontent ADD COLUMN IF NOT EXISTS faq_7_respuesta text NOT NULL DEFAULT '';"
                        "ALTER TABLE ventas_seocontent ADD COLUMN IF NOT EXISTS faq_8_pregunta varchar(200) NOT NULL DEFAULT '';"
                        "ALTER TABLE ventas_seocontent ADD COLUMN IF NOT EXISTS faq_8_respuesta text NOT NULL DEFAULT '';"
                    ),
                    reverse_sql=(
                        "ALTER TABLE ventas_seocontent DROP COLUMN IF EXISTS faq_7_pregunta;"
                        "ALTER TABLE ventas_seocontent DROP COLUMN IF EXISTS faq_7_respuesta;"
                        "ALTER TABLE ventas_seocontent DROP COLUMN IF EXISTS faq_8_pregunta;"
                        "ALTER TABLE ventas_seocontent DROP COLUMN IF EXISTS faq_8_respuesta;"
                    ),
                ),
            ],
        ),
    ]
