from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import CategoriaServicio

class StaticSitemap(Sitemap):
    changefreq = 'daily'
    priority = 1.0

    def items(self):
        return ['homepage']

    def location(self, item):
        return reverse(item)

class CategoriaSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return CategoriaServicio.objects.all()

    def location(self, obj):
        return reverse('ventas:categoria_detail', args=[obj.id])
