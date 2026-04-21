from .models import CategoriaServicio
from django.core.cache import cache

def categorias_processor(request):
    """
    Adds the list of all service categories to the template context.
    Usa caché para evitar queries repetidas en cada request.
    """
    # Intentar obtener del caché
    categorias = cache.get('categorias_menu')

    if categorias is None:
        # Si no está en caché, consultar BD y guardar por 1 hora
        categorias = list(CategoriaServicio.objects.all().order_by('nombre'))
        cache.set('categorias_menu', categorias, 3600)  # 1 hora

    return {'todas_las_categorias': categorias}
