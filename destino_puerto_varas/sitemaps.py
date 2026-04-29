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
from django.db.models import Count
from django.urls import reverse

from .models import Circuit


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
