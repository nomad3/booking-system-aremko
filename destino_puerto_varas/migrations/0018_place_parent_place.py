"""Add parent_place self-FK a Place (Aremko hybrid hub/leaf, Alt C).

Drift-safe: solo AddField con null=True/blank=True/SET_NULL, sin backfill.
Permite que un Place tenga sub-servicios (ej: Aremko Spa Boutique → Tinas Calientes)
sin afectar lugares standalone (parent_place=NULL).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0017_circuit_hero_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="place",
            name="parent_place",
            field=models.ForeignKey(
                to="destino_puerto_varas.place",
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name="children",
                help_text=(
                    "Place padre cuando este lugar es un sub-servicio o variante de otro. "
                    "Ej: 'Aremko Tinas Calientes' tiene como parent 'Aremko Spa Boutique'. "
                    "El padre concentra autoridad SEO + branding; los hijos son entradas concretas "
                    "para circuitos con duración específica. Vacío para lugares standalone."
                ),
            ),
        ),
    ]
