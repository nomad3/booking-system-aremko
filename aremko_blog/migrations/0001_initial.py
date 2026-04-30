"""Initial migration: BlogPost del blog editorial Aremko.

Drift-safe: app aislada `aremko_blog`, sin dependencias de `ventas/` ni de
`destino_puerto_varas/` (memoria AR-034 / makemigrations drift-safe).
Las tablas se crean con prefijo `aremko_blog_*` y no tocan ninguna tabla
existente. Si algún día se migra DPV a otro Render service, este blog
queda intacto.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BlogPost",
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
                        help_text="Keyword principal (de aremko_keywords_phase1.md).",
                    ),
                ),
                (
                    "cluster",
                    models.CharField(
                        max_length=30,
                        blank=True,
                        db_index=True,
                        choices=[
                            ("TINAS", "Tinas calientes / jacuzzi"),
                            ("MASAJES", "Masajes"),
                            ("SPA", "Spa y bienestar"),
                            ("ROMANCE", "Escapada parejas"),
                            ("RIO", "Río y sensorial"),
                            ("BOUTIQUE", "Boutique / detrás del mostrador"),
                        ],
                        help_text="Cluster editorial. Sirve para filtro UI + internal linking.",
                    ),
                ),
                (
                    "intro",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "Intro 80-120 palabras (con keyword en primeras 100 palabras y "
                            "humor + voz personal en primeras 50 — decisión #7 DPV-SEO-002, "
                            "aplica también al blog Aremko). Se muestra en /blog/ y og:description."
                        ),
                    ),
                ),
                (
                    "body_md",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "Cuerpo del post en Markdown. H2/H3 mapean al outline del cluster. "
                            "Se renderiza a HTML server-side."
                        ),
                    ),
                ),
                (
                    "hero_image",
                    models.ImageField(
                        upload_to="aremko/blog/",
                        blank=True,
                        null=True,
                        help_text="Imagen hero (~1200×675).",
                    ),
                ),
                ("hero_image_credit", models.CharField(max_length=200, blank=True)),
                (
                    "cta_text",
                    models.CharField(
                        max_length=120,
                        blank=True,
                        help_text=(
                            "Texto del botón CTA al final del post. Ej: 'Reserva tu cabaña con tina'. "
                            "Si está vacío, no se renderiza CTA."
                        ),
                    ),
                ),
                (
                    "cta_url",
                    models.CharField(
                        max_length=300,
                        blank=True,
                        help_text=(
                            "URL del CTA. Path relativo (ej: /tinas/) o URL absoluta. "
                            "Si está vacío, no se renderiza CTA."
                        ),
                    ),
                ),
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
                "verbose_name": "Post de blog Aremko",
                "verbose_name_plural": "Posts de blog Aremko",
                "ordering": ["-published_at", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="blogpost",
            index=models.Index(
                fields=["is_published", "-published_at"],
                name="aremko_blog_pub_pubat_idx",
            ),
        ),
    ]
