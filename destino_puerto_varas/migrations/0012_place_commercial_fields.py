"""DPV CMS-IA · Negocios y comercios: extiende Place con datos comerciales.

Agrega:
- Nuevos PlaceType (LODGING, SPA, TOUR_OPERATOR, BUSINESS, THEATER, CHURCH, CULTURAL_CENTER).
- partnership_level (OWNED / PARTNER / LISTED / DIRECTORY).
- Campos comerciales nullable: phone, website, instagram, reservations_url,
  price_range, opening_hours (JSON).

Drift-safe: solo aditivo, todos nullable/con default. No toca el resto del schema.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0011_update_main_guide_prompt"),
    ]

    operations = [
        # ─── Ampliación de choices en place_type ───
        migrations.AlterField(
            model_name="place",
            name="place_type",
            field=models.CharField(
                choices=[
                    ("ATTRACTION", "Atracción"),
                    ("VIEWPOINT", "Mirador"),
                    ("PARK", "Parque"),
                    ("RESTAURANT", "Restaurante"),
                    ("CAFE", "Café"),
                    ("SHOP", "Tienda"),
                    ("LODGING", "Alojamiento"),
                    ("SPA", "Spa / Bienestar"),
                    ("TOUR_OPERATOR", "Operador turístico"),
                    ("BUSINESS", "Empresa / Servicio"),
                    ("ACTIVITY", "Actividad"),
                    ("MUSEUM", "Museo"),
                    ("THEATER", "Teatro / Sala"),
                    ("CHURCH", "Iglesia"),
                    ("CULTURAL_CENTER", "Centro cultural"),
                    ("OTHER", "Otro"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
        # ─── Nuevos campos comerciales ───
        migrations.AddField(
            model_name="place",
            name="partnership_level",
            field=models.CharField(
                choices=[
                    ("OWNED", "Propio (Aremko)"),
                    ("PARTNER", "Partner / Aliado"),
                    ("LISTED", "Listado (sin acuerdo comercial)"),
                    ("DIRECTORY", "Directorio (referencial)"),
                ],
                db_index=True,
                default="LISTED",
                help_text=(
                    "Nivel de relación comercial. PROPIO=Aremko; PARTNER=acuerdo activo; "
                    "LISTED=mencionable sin acuerdo; DIRECTORY=solo referencia (atracción natural, "
                    "iglesia, etc. sin relación comercial)."
                ),
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="phone",
            field=models.CharField(
                blank=True,
                help_text="Teléfono de contacto (formato libre).",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="website",
            field=models.URLField(
                blank=True,
                help_text="Sitio web oficial.",
                max_length=300,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="instagram",
            field=models.CharField(
                blank=True,
                help_text="Handle de Instagram (sin @) o URL.",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="reservations_url",
            field=models.URLField(
                blank=True,
                help_text="URL directa para reservar (si aplica).",
                max_length=400,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="price_range",
            field=models.CharField(
                blank=True,
                help_text="$, $$, $$$, $$$$ — escala de precios relativa.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="opening_hours",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Horarios estructurados. Estructura sugerida: "
                    "{'mon': '09:00-18:00', 'tue': '09:00-18:00', ..., 'sun': 'cerrado', "
                    "'notes': 'cerrado feriados'}. Vacío si no aplica."
                ),
            ),
        ),
    ]
