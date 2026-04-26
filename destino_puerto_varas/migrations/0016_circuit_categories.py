"""Add Circuit categorías multi-valor (cultura, naturaleza, gastronomía).

Drift-safe:
- Solo AddField sobre tabla existente, default=False.
- RunPython backfill que infiere flags a partir de place_type de las paradas
  (no toca otras apps, no requiere modelos no aplicados).

Inferencia:
- THEATER, MUSEUM, CHURCH, CULTURAL_CENTER → is_culture
- RESTAURANT, CAFE → is_gastronomy
- PARK, VIEWPOINT, ATTRACTION (place_type natural) → is_nature
"""
from django.db import migrations, models


CULTURE_TYPES = {"THEATER", "MUSEUM", "CHURCH", "CULTURAL_CENTER"}
GASTRONOMY_TYPES = {"RESTAURANT", "CAFE"}
NATURE_TYPES = {"PARK", "VIEWPOINT", "ATTRACTION"}


def backfill_categories(apps, schema_editor):
    """Marca is_nature/is_culture/is_gastronomy según place_type de las paradas."""
    Circuit = apps.get_model("destino_puerto_varas", "Circuit")
    for circuit in Circuit.objects.all():
        types = set()
        for day in circuit.days.all():
            for stop in day.place_stops.all():
                pt = stop.place.place_type
                if pt:
                    types.add(pt)
        circuit.is_culture = bool(types & CULTURE_TYPES)
        circuit.is_gastronomy = bool(types & GASTRONOMY_TYPES)
        circuit.is_nature = bool(types & NATURE_TYPES)
        circuit.save(update_fields=["is_culture", "is_gastronomy", "is_nature"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0015_place_practical_services"),
    ]

    operations = [
        migrations.AddField(
            model_name="circuit",
            name="is_nature",
            field=models.BooleanField(
                default=False,
                help_text="Naturaleza escénica (parques, miradores, lagos, volcanes).",
            ),
        ),
        migrations.AddField(
            model_name="circuit",
            name="is_culture",
            field=models.BooleanField(
                default=False,
                help_text="Cultura y patrimonio (museos, teatros, iglesias, pueblos típicos).",
            ),
        ),
        migrations.AddField(
            model_name="circuit",
            name="is_gastronomy",
            field=models.BooleanField(
                default=False,
                help_text="Gastronomía (restaurantes, mercados, cervecerías, repostería).",
            ),
        ),
        migrations.RunPython(backfill_categories, noop_reverse),
    ]
