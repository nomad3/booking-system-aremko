"""Add BlogPost model (DPV-SEO-002 Tactic A · capa editorial).

Drift-safe: nuevo modelo aislado, sin tocar Circuit/Place/etc.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("destino_puerto_varas", "0019_strengthen_tool_call_rule"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlogPost",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slug", models.SlugField(max_length=220, unique=True)),
                (
                    "title",
                    models.CharField(
                        max_length=200,
                        help_text="H1 del post. Claro, no clickbait. Idealmente con keyword raíz.",
                    ),
                ),
                (
                    "meta_description",
                    models.CharField(
                        max_length=160,
                        blank=True,
                        help_text="Meta description (≤160 chars). Si vacía se autogenera del intro.",
                    ),
                ),
                (
                    "keyword_root",
                    models.CharField(
                        max_length=120,
                        blank=True,
                        help_text="Keyword principal del post (de la sesión Fase 1 keyword research).",
                    ),
                ),
                (
                    "cluster",
                    models.CharField(
                        max_length=30,
                        blank=True,
                        db_index=True,
                        choices=[
                            ("GUIDES", "Guías y planificación"),
                            ("COMPARISONS", "Comparativas"),
                            ("ITINERARIES", "Itinerarios"),
                            ("HOWTOS", "Cómo hacer"),
                            ("SEASONS", "Épocas y clima"),
                            ("FAMILY", "Viaje familiar"),
                            ("ROMANCE", "Escapada romántica"),
                            ("GASTRONOMY", "Gastronomía"),
                            ("CULTURE", "Cultura y patrimonio"),
                            ("NATURE", "Naturaleza"),
                        ],
                        help_text="Cluster editorial. Sirve para filtro UI + internal linking entre posts.",
                    ),
                ),
                (
                    "intro",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "Intro 80-120 palabras (con keyword en primeras 100 palabras). "
                            "Se muestra en el listado /blog/ y en og:description."
                        ),
                    ),
                ),
                (
                    "body_md",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "Cuerpo del post en Markdown. H2/H3 mapean al outline del cluster. "
                            "Se renderiza a HTML server-side (sin sanitizar — solo edita admin)."
                        ),
                    ),
                ),
                (
                    "hero_image",
                    models.ImageField(
                        upload_to="dpv/blog/",
                        blank=True,
                        null=True,
                        help_text="Imagen hero (acuarela DPV recomendado, ~1200×675).",
                    ),
                ),
                ("hero_image_credit", models.CharField(max_length=200, blank=True)),
                (
                    "faq_schema_json",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "JSON-LD FAQPage opcional (si el post incluye sección FAQ). "
                            "Se inyecta tal cual en <script type=application/ld+json>."
                        ),
                    ),
                ),
                ("is_published", models.BooleanField(default=False, db_index=True)),
                ("published_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Post de blog",
                "verbose_name_plural": "Posts de blog",
                "ordering": ["-published_at", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="blogpost",
            index=models.Index(
                fields=["is_published", "-published_at"],
                name="dpv_blogpos_is_publ_idx",
            ),
        ),
    ]
