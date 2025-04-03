from .models import CategoriaServicio

def categorias_processor(request):
    """
    Adds the list of all service categories to the template context.
    """
    categorias = CategoriaServicio.objects.all().order_by('nombre')
    return {'todas_las_categorias': categorias}
