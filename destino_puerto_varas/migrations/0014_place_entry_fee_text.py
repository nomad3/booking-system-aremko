"""Add Place.entry_fee_text — texto libre para tarifas complejas.

Drift-safe: solo AddField sobre tabla existente. No depende de modelos no
aplicados. Sin alteraciones a otros campos.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0013_circuit_composition_draft"),
    ]

    operations = [
        migrations.AddField(
            model_name="place",
            name="entry_fee_text",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Detalle de tarifas en texto libre. Cubre casos donde "
                    "entry_fee_clp no basta: diferencial adulto/niño/extranjero, "
                    "café por consumo, restaurante por menú, estacionamiento por "
                    "hora, museo por exposición, etc. Ej: 'Adultos chilenos $4.000, "
                    "niños $2.000, extranjeros $7.000'."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="place",
            name="entry_fee_clp",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text=(
                    "Entrada en CLP (0 = gratis, null = no aplica/desconocido). "
                    "Valor representativo único."
                ),
            ),
        ),
    ]
