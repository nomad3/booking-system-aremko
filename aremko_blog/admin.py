"""Admin del blog editorial Aremko."""
from __future__ import annotations

from django.contrib import admin

from .models import BlogPost


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    """Mirror del BlogPostAdmin DPV con fieldset CTA propio.

    `save_on_top=True` y "Publicación" en primer lugar — lección 2026-04-30
    sobre admin con muchos fieldsets (botón Save lejos del scroll).
    """

    list_display = (
        "title",
        "slug",
        "cluster",
        "keyword_root",
        "is_published",
        "published_at",
        "updated_at",
    )
    list_filter = ("is_published", "cluster")
    search_fields = ("title", "slug", "keyword_root", "intro")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "published_at"
    save_on_top = True
    fieldsets = (
        ("Publicación", {
            "fields": ("is_published", "published_at"),
            "description": (
                "is_published=True + published_at ≤ ahora → aparece en /blog/ y sitemap. "
                "Si solo seteas is_published=True sin fecha, no aparece hasta llenar published_at."
            ),
        }),
        ("Identidad", {
            "fields": ("title", "slug", "cluster"),
        }),
        ("SEO", {
            "fields": ("keyword_root", "meta_description"),
            "description": (
                "Meta description ≤160 chars (Google la trunca). "
                "Si la dejas vacía, el sitio toma los primeros 160 chars del intro."
            ),
        }),
        ("Contenido", {
            "fields": ("intro", "body_md"),
            "description": (
                "Intro 80-120 palabras (visible en listado) — humor + voz "
                "anfitrión en primeras 50 palabras (decisión #7). "
                "Body en Markdown — H2/H3 estructuran el outline."
            ),
        }),
        ("Hero", {
            "fields": ("hero_image", "hero_image_credit"),
        }),
        ("CTA comercial (opcional)", {
            "fields": ("cta_text", "cta_url"),
            "description": (
                "Soft CTA al final del post. Ej: 'Reserva tu cabaña con tina' → /tinas/. "
                "Si ambos campos vacíos, no se renderiza CTA. Mantener tono editorial: "
                "el CTA va al final, no en H2/H3."
            ),
        }),
        ("Schema FAQ (opcional)", {
            "classes": ("collapse",),
            "fields": ("faq_schema_json",),
            "description": (
                "Pegar JSON-LD FAQPage si el post incluye FAQ. "
                "Se inyecta tal cual en <script type='application/ld+json'>."
            ),
        }),
        ("Auditoría", {
            "classes": ("collapse",),
            "fields": ("created_at", "updated_at"),
        }),
    )
