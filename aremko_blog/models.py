"""Modelos del blog editorial de aremko.cl.

Diseño portable: NO importa de `ventas/` ni de `destino_puerto_varas/`.
El día que DPV se separe a otro Render service (cuando su tráfico amenace
la operación de aremko.cl, AR-030 / decisión owner 2026-04-30), este blog
queda en aremko sin tocar nada.

Mirror del patrón DPV-SEO-002 con clusters/voz propios:
- DPV blog (en `destino_puerto_varas.models.BlogPost`) = medio editorial neutral
- Aremko blog (este modelo) = voz "anfitrión" + soft CTA comercial
"""
from __future__ import annotations

from django.db import models


class BlogCluster(models.TextChoices):
    """Clusters editoriales de aremko.cl.

    Derivados de `ventas/data/aremko_keywords_phase1.md` (Fase 1 keyword
    research, 2026-04-30). NO solapan con clusters DPV (GUIDES, ITINERARIES,
    HOWTOS, NATURE, etc.) porque el intent es comercial-experiencial,
    no informacional-geográfico.
    """

    TINAS = "TINAS", "Tinas calientes / jacuzzi"
    MASAJES = "MASAJES", "Masajes"
    SPA = "SPA", "Spa y bienestar"
    ROMANCE = "ROMANCE", "Escapada parejas"
    RIO = "RIO", "Río y sensorial"
    BOUTIQUE = "BOUTIQUE", "Boutique / detrás del mostrador"


class BlogPost(models.Model):
    """Post del blog editorial de aremko.cl.

    Captura queries comerciales-experienciales (tinas, masajes, spa, escapada
    parejas) y construye topical authority. Diferencia clave vs blog DPV:
    permite soft CTA comercial al final (cta_text + cta_url).
    """

    slug = models.SlugField(max_length=220, unique=True)
    title = models.CharField(
        max_length=200,
        help_text="H1 del post. Claro, no clickbait. Idealmente con keyword raíz.",
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        help_text="Meta description (≤160 chars). Si vacía se autogenera del intro.",
    )
    keyword_root = models.CharField(
        max_length=120,
        blank=True,
        help_text="Keyword principal (de aremko_keywords_phase1.md).",
    )
    cluster = models.CharField(
        max_length=30,
        choices=BlogCluster.choices,
        blank=True,
        db_index=True,
        help_text="Cluster editorial. Sirve para filtro UI + internal linking.",
    )
    intro = models.TextField(
        blank=True,
        help_text=(
            "Intro 80-120 palabras (con keyword en primeras 100 palabras y "
            "humor + voz personal en primeras 50 — decisión #7 DPV-SEO-002, "
            "aplica también al blog Aremko). Se muestra en /blog/ y og:description."
        ),
    )
    body_md = models.TextField(
        blank=True,
        help_text=(
            "Cuerpo del post en Markdown. H2/H3 mapean al outline del cluster. "
            "Se renderiza a HTML server-side."
        ),
    )
    hero_image = models.ImageField(
        upload_to="aremko/blog/",
        blank=True,
        null=True,
        help_text="Imagen hero (~1200×675).",
    )
    hero_image_credit = models.CharField(max_length=200, blank=True)

    # Soft CTA comercial (NO existe en blog DPV — es donde divergen).
    cta_text = models.CharField(
        max_length=120,
        blank=True,
        help_text=(
            "Texto del botón CTA al final del post. Ej: 'Reserva tu cabaña con tina'. "
            "Si está vacío, no se renderiza CTA."
        ),
    )
    cta_url = models.CharField(
        max_length=300,
        blank=True,
        help_text=(
            "URL del CTA. Path relativo (ej: /tinas/) o URL absoluta. "
            "Si está vacío, no se renderiza CTA."
        ),
    )

    faq_schema_json = models.TextField(
        blank=True,
        help_text=(
            "JSON-LD FAQPage opcional (si el post incluye sección FAQ). "
            "Se inyecta tal cual en <script type=application/ld+json>."
        ),
    )
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name = "Post de blog Aremko"
        verbose_name_plural = "Posts de blog Aremko"
        indexes = [
            models.Index(fields=["is_published", "-published_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.slug})"

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("aremko_blog:blog-detail", kwargs={"slug": self.slug})
