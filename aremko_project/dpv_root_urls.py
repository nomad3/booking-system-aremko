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

from ventas.sitemaps import (
    CategoriaSitemap,
    CorporatePagesSitemap,
    HomepageSitemap,
    MainPagesSitemap,
)

sitemaps = {
    "homepage": HomepageSitemap,
    "main-pages": MainPagesSitemap,
    "corporate": CorporatePagesSitemap,
    "categorias": CategoriaSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),

    # API DPV (catálogo, conversación, webhooks)
    path("api/destino-puerto-varas/", include("destino_puerto_varas.api.urls")),

    # SEO
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps},
         name="django.contrib.sitemaps.views.sitemap"),
    path("robots.txt", TemplateView.as_view(
        template_name="seo/robots.txt", content_type="text/plain"
    ), name="robots_txt"),

    # DPV en root — catch-all al final
    path("", include("destino_puerto_varas.urls")),
]
