"""URLConf alternativo activado por host_routing.HostBasedURLConfMiddleware
cuando la request llega a destinopuertovaras.cl (o www.destinopuertovaras.cl).

Monta la app DPV en root, expone admin/API y delega sitemap/robots a las
mismas rutas SEO de Aremko.
"""
from __future__ import annotations

from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import TemplateView

from destino_puerto_varas.sitemaps import (
    BlogIndexSitemap,
    BlogPostSitemap,
    CircuitSitemap,
    DPVHomeSitemap,
    PlaceSitemap,
)

# DPV-SEO-001 #1: sitemaps propios de DPV. Antes se reusaban los de Aremko
# (HomepageSitemap, MainPagesSitemap…) cuyos reverse() fallaban en este
# URLConf, devolviendo HTTP 500.
# DPV-SEO-001 #8: PlaceSitemap filtra atractivos públicos SEO-ready; comercios fuera.
# DPV-SEO-002: BlogPostSitemap + BlogIndexSitemap para la capa editorial.
sitemaps = {
    "home": DPVHomeSitemap,
    "circuits": CircuitSitemap,
    "places": PlaceSitemap,
    "blog_index": BlogIndexSitemap,
    "blog_posts": BlogPostSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),

    # API DPV (catálogo, conversación, webhooks)
    path("api/destino-puerto-varas/", include("destino_puerto_varas.api.urls")),

    # SEO
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps},
         name="django.contrib.sitemaps.views.sitemap"),
    # DPV-SEO-001 #2: robots.txt propio de DPV (apunta al sitemap de
    # destinopuertovaras.cl, no al de aremko.cl; sin /ventas/...).
    path("robots.txt", TemplateView.as_view(
        template_name="seo/robots_dpv.txt", content_type="text/plain"
    ), name="robots_txt"),

    # DPV en root — catch-all al final
    path("", include("destino_puerto_varas.urls")),
]
