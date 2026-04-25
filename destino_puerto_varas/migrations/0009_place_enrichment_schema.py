"""DPV CMS-IA · Capa 1: schema para enriquecimiento de Places por IA.

Añade a Place campos estructurados (elevation_m, year_established, has_*,
entry_fee_clp, best_season, accessibility_notes, distance/drive desde Pto Varas)
+ JSONField extra_data para campos no anticipados.

Crea PlacePhoto (FK a Place, image/source_url, caption, credit, is_primary, order).

Crea PlaceEnrichmentDraft (FK a Place, status, proposed_data JSON, raw_search_response,
review_notes, reviewed_by/at, applied_at) — cada draft debe ser aprobado por un humano
antes de aplicarse al Place real.

Escrito a mano para evitar disparar makemigrations sobre apps con drift (AR-034).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0008_seed_dpv_main_guide_prompt"),
    ]

    operations = [
        # ─── Nuevos campos estructurados en Place ───
        migrations.AddField(
            model_name="place",
            name="elevation_m",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Altitud en metros sobre el nivel del mar (ej: 2652 para Volcán Osorno).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="year_established",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Año de creación / declaración (ej: 1926 para Parque Vicente Pérez Rosales).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="has_parking",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="place",
            name="has_restrooms",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="place",
            name="has_conaf_office",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="place",
            name="has_food_service",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="place",
            name="entry_fee_clp",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Entrada en CLP (0 = gratis, null = no aplica/desconocido).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="best_season",
            field=models.CharField(
                blank=True,
                help_text="Mejor temporada para visitar. Ej: 'Diciembre a marzo' o 'Todo el año'.",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="accessibility_notes",
            field=models.TextField(
                blank=True,
                help_text="Accesibilidad para personas con movilidad reducida, niños pequeños, etc.",
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="distance_from_pv_km",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                help_text="Distancia en km desde Puerto Varas centro.",
                max_digits=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="drive_time_from_pv_min",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Tiempo en auto desde Puerto Varas centro (minutos).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="extra_data",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Campos no anticipados que la IA puede extraer (glaciar, fauna, "
                    "infraestructura adicional, etc.). Estructura libre."
                ),
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="last_enriched_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Última vez que un draft IA fue aprobado y aplicado a este lugar.",
                null=True,
            ),
        ),
        # ─── PlacePhoto ───
        migrations.CreateModel(
            name="PlacePhoto",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        blank=True,
                        help_text=(
                            "Foto subida a storage (Cloudinary). Opcional si solo "
                            "tenemos source_url."
                        ),
                        null=True,
                        upload_to="dpv/places/",
                    ),
                ),
                (
                    "source_url",
                    models.URLField(
                        blank=True,
                        help_text=(
                            "URL de origen si la foto vino de la web (Wikipedia, "
                            "Unsplash, etc.). Para fotos propias, dejar vacío."
                        ),
                        max_length=500,
                    ),
                ),
                ("caption", models.CharField(blank=True, max_length=255)),
                (
                    "credit",
                    models.CharField(
                        blank=True,
                        help_text="Atribución (ej: 'Foto: Wikimedia Commons, CC-BY-SA').",
                        max_length=200,
                    ),
                ),
                (
                    "is_primary",
                    models.BooleanField(
                        default=False,
                        help_text="Foto principal del lugar (la que sale primero).",
                    ),
                ),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "place",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="photos",
                        to="destino_puerto_varas.place",
                    ),
                ),
            ],
            options={
                "verbose_name": "Foto de lugar",
                "verbose_name_plural": "Fotos de lugares",
                "ordering": ["place", "order", "id"],
            },
        ),
        # ─── PlaceEnrichmentDraft ───
        migrations.CreateModel(
            name="PlaceEnrichmentDraft",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Borrador (pendiente revisión)"),
                            ("approved", "Aprobado (listo para aplicar)"),
                            ("rejected", "Rechazado"),
                            ("applied", "Aplicado al Place"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "proposed_data",
                    models.JSONField(
                        default=dict,
                        help_text=(
                            "Estructura: {'fields': {'elevation_m': 2652, ...}, "
                            "'extra_data': {...}, 'photos': [{url, caption, credit}, ...], "
                            "'long_description': '...'}"
                        ),
                    ),
                ),
                (
                    "raw_search_response",
                    models.JSONField(
                        blank=True,
                        help_text="Respuesta cruda del proveedor de búsqueda (Perplexity) para auditoría.",
                        null=True,
                    ),
                ),
                (
                    "search_provider",
                    models.CharField(
                        default="perplexity",
                        help_text="Proveedor usado: perplexity, tavily, brave, etc.",
                        max_length=40,
                    ),
                ),
                ("llm_model", models.CharField(blank=True, default="", max_length=80)),
                ("llm_input_tokens", models.PositiveIntegerField(default=0)),
                ("llm_output_tokens", models.PositiveIntegerField(default=0)),
                ("llm_latency_ms", models.PositiveIntegerField(default=0)),
                (
                    "review_notes",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "Comentarios del revisor humano (qué se cambió, "
                            "por qué se rechazó, etc.)."
                        ),
                    ),
                ),
                (
                    "reviewed_by",
                    models.CharField(
                        blank=True,
                        help_text="Username de quien revisó (admin Django).",
                        max_length=80,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "place",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="enrichment_drafts",
                        to="destino_puerto_varas.place",
                    ),
                ),
            ],
            options={
                "verbose_name": "Borrador de enriquecimiento",
                "verbose_name_plural": "Borradores de enriquecimiento",
                "ordering": ["-created_at"],
            },
        ),
    ]
