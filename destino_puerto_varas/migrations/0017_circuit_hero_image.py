"""Add hero_image + hero_image_credit a Circuit (acuarela/foto del listado público).

Drift-safe: solo AddField con blank/null, sin backfill.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0016_circuit_categories"),
    ]

    operations = [
        migrations.AddField(
            model_name="circuit",
            name="hero_image",
            field=models.ImageField(
                upload_to="dpv/circuits/",
                blank=True,
                null=True,
                help_text=(
                    "Imagen hero para la tarjeta del circuito en el listado público. "
                    "Recomendado: acuarela del paisaje principal (ratio ~16:9, ~1200×675 px). "
                    "Si está vacía, el sitio usa la primera foto del primer lugar como fallback."
                ),
            ),
        ),
        migrations.AddField(
            model_name="circuit",
            name="hero_image_credit",
            field=models.CharField(
                max_length=200,
                blank=True,
                help_text="Atribución/crédito de la imagen (ej: 'Acuarela generada por IA').",
            ),
        ),
    ]
