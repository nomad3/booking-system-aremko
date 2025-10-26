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
    philosophy_image_url = None # Add variable for philosophy image
    gallery_image_1_url = None  # Add variable for gallery image 1
    gallery_image_2_url = None  # Add variable for gallery image 2
    gallery_image_3_url = None  # Add variable for gallery image 3

    try:
        # HomepageConfig is a singleton, get the instance
        config = HomepageConfig.get_solo()
        # Get hero image URL
        if config.hero_background_image:
            hero_image_url = config.hero_background_image.url
        # Get philosophy image URL
        if config.philosophy_image:
            philosophy_image_url = config.philosophy_image.url
        # Get gallery image URLs
        if config.gallery_image_1:
            gallery_image_1_url = config.gallery_image_1.url
        if config.gallery_image_2:
            gallery_image_2_url = config.gallery_image_2.url
        if config.gallery_image_3:
            gallery_image_3_url = config.gallery_image_3.url

    except HomepageConfig.DoesNotExist:
        # Handle case where the config hasn't been created yet
        pass
    # --- End Fetch Homepage Config ---

    # Canonical URL for SEO (build safely)
    try:
        canonical_url = request.build_absolute_uri(request.path)
    except Exception:
        canonical_url = request.path

    context = {
        'servicios': servicios,
        'categorias': categorias,
        'cart': cart,
        'hero_image_url': hero_image_url,
        'philosophy_image_url': philosophy_image_url, # Add philosophy URL to context
        'gallery_image_1_url': gallery_image_1_url,   # Add gallery 1 URL to context
        'gallery_image_2_url': gallery_image_2_url,   # Add gallery 2 URL to context
        'gallery_image_3_url': gallery_image_3_url,   # Add gallery 3 URL to context
        'canonical_url': canonical_url,
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

    # Build canonical URL safely
    try:
        canonical_url = request.build_absolute_uri(request.path)
    except Exception:
        canonical_url = request.path
    
    category_hero_image = categoria.imagen.url if categoria.imagen else None

    context = {
        'categoria_actual': categoria,
        'servicios': servicios,
        'categorias': categorias,
        'cart': request.session.get('cart', {'servicios': [], 'total': 0}), # Include cart context
        'canonical_url': canonical_url,
        'category_hero_image': category_hero_image,
    }
    return render(request, 'ventas/category_detail.html', context)


def empresas_view(request):
    """
    Vista para la landing page de servicios empresariales
    """
    context = {
        'page_title': 'Reuniones con Resultados: Productividad + Bienestar',
        'meta_description': 'Espacios únicos para reuniones empresariales en Puerto Varas. Sala de reuniones, desayuno sureño y tinas calientes para tu equipo.',
    }
    return render(request, 'ventas/empresas.html', context)
