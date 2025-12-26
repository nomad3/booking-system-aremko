from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import CategoriaServicio


class HomepageSitemap(Sitemap):
    """Sitemap para la página principal"""
    changefreq = 'daily'
    priority = 1.0

    def items(self):
        return ['homepage']

    def location(self, item):
        return reverse(item)


class MainPagesSitemap(Sitemap):
    """Sitemap para páginas principales de servicios"""
    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        # URLs principales de categorías de servicios
        return [
            'masajes',      # Página de masajes
            'tinas',        # Página de tinas
            'alojamientos', # Página de cabañas/alojamientos
            'productos',    # Página de productos/giftcards
        ]

    def location(self, item):
        return reverse(item)


class CorporatePagesSitemap(Sitemap):
    """Sitemap para páginas corporativas y empresas"""
    changefreq = 'monthly'
    priority = 0.7

    def items(self):
        return [
            'empresas',  # Landing page empresarial
        ]

    def location(self, item):
        return reverse(item)


class CategoriaSitemap(Sitemap):
    """Sitemap dinámico para categorías de servicios individuales"""
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return CategoriaServicio.objects.filter(activo=True)

    def location(self, obj):
        return reverse('ventas:categoria_detail', args=[obj.id])


# TODO: Agregar cuando exista el blog
# class BlogSitemap(Sitemap):
#     """Sitemap para artículos del blog"""
#     changefreq = 'weekly'
#     priority = 0.6
#
#     def items(self):
#         return BlogPost.objects.filter(publicado=True).order_by('-fecha_publicacion')
#
#     def lastmod(self, obj):
#         return obj.fecha_actualizacion
#
#     def location(self, obj):
#         return reverse('blog:post_detail', args=[obj.slug])
