"""Sitemaps del blog editorial Aremko."""
from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import BlogPost


class AremkoBlogPostSitemap(Sitemap):
    """Posts publicados del blog Aremko."""

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
        return reverse("aremko_blog:blog-detail", kwargs={"slug": obj.slug})


class AremkoBlogIndexSitemap(Sitemap):
    """Index del blog /blog/."""

    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return ["aremko_blog:blog-list"]

    def location(self, item):
        return reverse(item)
