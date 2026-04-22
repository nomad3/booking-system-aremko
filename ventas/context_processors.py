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
    'ta_url': 'https://www.tripadvisor.com/Hotel_Review-d7138437',
    'ta_travellers_choice_year': 2024,
    'google_rating': '4.5',
    'google_reviews': 660,
    'google_url': 'https://www.google.com/search?q=Aremko+Aguas+Calientes+Puerto+Varas+rese%C3%B1as',
}


def social_proof_processor(request):
    """Inyecta cifras de reseñas externas para la franja AR-028."""
    return {'social_proof': _SOCIAL_PROOF}
