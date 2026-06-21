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


# AR-028 — Social proof estático (TripAdvisor + Google). Sin queries, sin I/O.
# Actualizar manualmente las cifras cuando suban las reseñas.
_SOCIAL_PROOF = {
    'ta_rating': '4.4',
    'ta_reviews': 258,
    'ta_ranking_pos': 1,
    'ta_ranking_total': 14,
    'ta_ranking_city': 'Puerto Varas',
    'ta_url': 'https://www.tripadvisor.com.ar/Hotel_Review-g294299-d7138437-Reviews-Aremko_Aguas_Calientes_Spa-Puerto_Varas_Los_Lagos_Region.html',
    'ta_travellers_choice_year': 2024,
    'google_rating': '4.5',
    'google_reviews': 660,
    'google_url': 'https://www.google.cl/travel/hotels/entity/ChoIspWGrpvPlLD_ARoNL2cvMTFidG1yZzV3bBAB/reviews',
}


def social_proof_processor(request):
    """Inyecta cifras de reseñas externas para la franja AR-028."""
    return {'social_proof': _SOCIAL_PROOF}


def meta_pixel_processor(request):
    """Inyecta META_PIXEL_ID en el contexto para base_public.html y descendientes."""
    from django.conf import settings
    return {'META_PIXEL_ID': getattr(settings, 'META_PIXEL_ID', '')}


def ritual_rio_processor(request):
    """Expone los interruptores de publicación de la landing del Ritual del Río
    a TODAS las plantillas (para el enlace del menú y el botón del home).
    Tolerante a fallos: si algo falla, no muestra nada (no rompe el sitio)."""
    try:
        from .models import RitualRioLandingConfig
        cfg = RitualRioLandingConfig.get_solo()
        return {
            'ritual_rio_en_menu': bool(cfg.mostrar_en_menu),
            'ritual_rio_en_home': bool(cfg.mostrar_en_home),
        }
    except Exception:
        return {'ritual_rio_en_menu': False, 'ritual_rio_en_home': False}
