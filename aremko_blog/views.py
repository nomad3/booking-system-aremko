"""Vistas públicas del blog editorial Aremko (aremko.cl/blog/)."""
from __future__ import annotations

from django.http import Http404
from django.shortcuts import render
from django.views.generic import View

from .models import BlogCluster, BlogPost


# Mapeo de slug de cluster (URL) → choice del modelo. (slug, code, label, icon).
BLOG_CLUSTER_LABELS = [
    ("tinas", "TINAS", "Tinas calientes", "🛁"),
    ("masajes", "MASAJES", "Masajes", "💆"),
    ("spa", "SPA", "Spa y bienestar", "🧖"),
    ("romance", "ROMANCE", "Escapada parejas", "💕"),
    ("rio", "RIO", "Río y sensorial", "🌊"),
    ("boutique", "BOUTIQUE", "Boutique", "✨"),
]
BLOG_CLUSTER_BY_SLUG = {slug: code for slug, code, _, _ in BLOG_CLUSTER_LABELS}


class BlogPostListPublicView(View):
    """Listado público del blog Aremko.

    Solo muestra is_published=True con published_at <= ahora.
    """

    template_name = "aremko_blog/blog_list.html"
    paginate_by = 12

    def get(self, request):
        from django.utils import timezone

        posts = BlogPost.objects.filter(
            is_published=True,
            published_at__lte=timezone.now(),
        ).order_by("-published_at")

        # Filtro por cluster (slug-friendly): /blog/?c=tinas
        cluster_slug = request.GET.get("c")
        cluster_code = BLOG_CLUSTER_BY_SLUG.get(cluster_slug) if cluster_slug else None
        if cluster_code:
            posts = posts.filter(cluster=cluster_code)

        # Clusters con al menos 1 post publicado (no mostrar chips vacíos).
        active_codes = set(
            BlogPost.objects.filter(is_published=True)
            .values_list("cluster", flat=True)
            .distinct()
        )
        clusters = [
            {"slug": s, "label": label, "icon": icon, "active": s == cluster_slug}
            for s, code, label, icon in BLOG_CLUSTER_LABELS
            if code in active_codes
        ]

        context = {
            "posts": list(posts[: self.paginate_by]),
            "clusters": clusters,
            "selected_cluster": cluster_slug or "",
            "any_filter_active": bool(cluster_code),
        }
        return render(request, self.template_name, context)


class BlogPostDetailPublicView(View):
    """Detalle de un post de blog Aremko."""

    template_name = "aremko_blog/blog_detail.html"

    def get(self, request, slug: str):
        from django.utils import timezone

        post = (
            BlogPost.objects.filter(
                slug=slug,
                is_published=True,
                published_at__lte=timezone.now(),
            )
            .first()
        )
        if post is None:
            raise Http404("Post no encontrado")

        body_html = _render_markdown(post.body_md or "")

        related = []
        if post.cluster:
            related = list(
                BlogPost.objects.filter(
                    is_published=True,
                    published_at__lte=timezone.now(),
                    cluster=post.cluster,
                )
                .exclude(pk=post.pk)
                .order_by("-published_at")[:3]
            )

        context = {
            "post": post,
            "body_html": body_html,
            "related_posts": related,
        }
        return render(request, self.template_name, context)


def _render_markdown(text: str) -> str:
    """Markdown → HTML. Si falta la lib, fallback defensivo a <p> escapado."""
    if not text:
        return ""
    try:
        import markdown as _md

        return _md.markdown(
            text,
            extensions=["extra", "sane_lists", "toc"],
            output_format="html5",
        )
    except ImportError:
        from django.utils.html import escape

        return f"<p>{escape(text).replace(chr(10), '<br>')}</p>"
