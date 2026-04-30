"""Sitemaps para destinopuertovaras.cl.

Trabajo DPV-SEO-001 #1: el URLConf de DPV antes reusaba los sitemaps de
Aremko (HomepageSitemap, MainPagesSitemap, etc.), que apuntan a URL names
que no existen en el namespace público de DPV. Eso causaba NoReverseMatch
y HTTP 500 en /sitemap.xml.

Estos sitemaps usan exclusivamente URLs del namespace
`destino_puerto_varas_public`.
"""
from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.db import models
from django.db.models import Count
from django.urls import reverse

from .models import BlogPost, Circuit, Place


class DPVHomeSitemap(Sitemap):
    """Página principal del listado de circuitos."""

    changefreq = "daily"
    priority = 1.0

    def items(self):
        return ["destino_puerto_varas_public:circuit-list"]

    def location(self, item):
        return reverse(item)


class CircuitSitemap(Sitemap):
    """Detalle de cada circuito publicado con itinerario armado.

    Mismo filtro que CircuitListPublicView: published=True y al menos un
    CircuitDay. Los stubs (sin días) quedan fuera del sitemap.
    """

    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return (
            Circuit.objects.filter(published=True)
            .annotate(days_count=Count("days"))
            .filter(days_count__gt=0)
            .order_by("sort_order", "number")
        )

    def lastmod(self, obj: Circuit):
        return obj.updated_at

    def location(self, obj: Circuit):
        return reverse(
            "destino_puerto_varas_public:circuit-detail",
            kwargs={"slug": obj.slug},
        )


class PlaceSitemap(Sitemap):
    """Páginas de Place que califican como SEO-ready (DPV-SEO-001 #8 Opción A).

    Filtros:
    - Solo atractivos públicos (ATTRACTION, VIEWPOINT, PARK, MUSEUM, THEATER,
      CHURCH, CULTURAL_CENTER) o propiedades de Aremko (OWNED).
    - long_description ≥ 200 caracteres.
    - ≥ 1 foto.
    - ≥ 2 datos prácticos llenos.

    Comercios de terceros (RESTAURANT, CAFE, LODGING no-OWNED, etc.) NO entran
    al sitemap para evitar pasar autoridad SEO a competencia indirecta.
    """

    changefreq = "monthly"
    priority = 0.6

    def items(self):
        # Pre-filtro barato a nivel SQL; la regla completa la decide is_seo_ready.
        qs = (
            Place.objects.filter(published=True)
            .filter(
                models.Q(place_type__in=Place.SEO_INDEXABLE_PLACE_TYPES)
                | models.Q(partnership_level="OWNED")
            )
            .prefetch_related("photos")
        )
        return [p for p in qs if p.is_seo_ready]

    def lastmod(self, obj: Place):
        return obj.updated_at

    def location(self, obj: Place):
        return reverse(
            "destino_puerto_varas_public:place-detail",
            kwargs={"slug": obj.slug},
        )


class BlogPostSitemap(Sitemap):
    """Posts del blog publicados (DPV-SEO-002 Tactic A)."""

    changefreq = "weekly"
    priority = 0.7

    def items(self):
        from django.utils import timezone

        return (
            BlogPost.objects.filter(
                is_published=True,
                published_at__lte=timezone.now(),
            )
            .order_by("-published_at")
        )

    def lastmod(self, obj: BlogPost):
        return obj.updated_at

    def location(self, obj: BlogPost):
        return reverse(
            "destino_puerto_varas_public:blog-detail",
            kwargs={"slug": obj.slug},
        )


class BlogIndexSitemap(Sitemap):
    """Index del blog /blog/."""

    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return ["destino_puerto_varas_public:blog-list"]

    def location(self, item):
        return reverse(item)
