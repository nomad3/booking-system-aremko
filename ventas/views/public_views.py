from django.shortcuts import render, get_object_or_404
from ..models import Servicio, CategoriaServicio, HomepageConfig # Relative import, ADD HomepageConfig

def homepage_view(request):
    """
    Vista que renderiza la página de inicio pública de Aremko.cl
    Muestra los servicios disponibles y permite realizar reservas.
    """
    # Obtener servicios activos Y publicados en la web
    servicios = Servicio.objects.filter(activo=True, publicado_web=True).select_related('categoria')
    categorias = CategoriaServicio.objects.all()

    # Obtener carrito de compras de la sesión o crear uno nuevo
    cart = request.session.get('cart', {'servicios': [], 'total': 0})

    # --- Fetch Homepage Config ---
    hero_image_url = None
    try:
        # HomepageConfig is a singleton, get the instance
        config = HomepageConfig.get_solo()
        if config.hero_background_image: # Check if an image is set
            hero_image_url = config.hero_background_image.url
    except HomepageConfig.DoesNotExist:
        # Handle case where the config hasn't been created yet
        pass
    # --- End Fetch Homepage Config ---

    context = {
        'servicios': servicios,
        'categorias': categorias,
        'cart': cart,
        'hero_image_url': hero_image_url, # Add the URL to the context
    }
    return render(request, 'ventas/homepage.html', context)

def categoria_detail_view(request, categoria_id):
    """
    Vista que muestra los servicios de una categoría específica.
    """
    categoria = get_object_or_404(CategoriaServicio, id=categoria_id)
    # Filter by category, active, AND published
    servicios = Servicio.objects.filter(categoria=categoria, activo=True, publicado_web=True)
    categorias = CategoriaServicio.objects.all() # For potential navigation/filtering

    context = {
        'categoria_actual': categoria,
        'servicios': servicios,
        'categorias': categorias,
        'cart': request.session.get('cart', {'servicios': [], 'total': 0}) # Include cart context
    }
    return render(request, 'ventas/category_detail.html', context)
