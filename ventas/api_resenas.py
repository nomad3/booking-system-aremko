"""API de reseñas externas — para que Datamatic Hospitality (Telar) cite a
clientes reales en el contenido, en vez de que el modelo invente la frase.

    GET /marketing/api/resenas/     — las publicables, en JSON.

Auth: header `X-API-KEY == settings.AUTOMATION_API_KEY` (mismo patrón que
`/marketing/api/catalogo/`, que ya se usó para migrar las 265 fotos).

Solo salen las **publicables**, y el filtro es parte del contrato, no una
comodidad del consumidor:

- **Con texto.** Las de solo estrellas no tienen nada que citar.
- **4 o 5 estrellas.** Las de 1 a 3 sirven para arreglar el negocio, no para
  publicarlo, y no tienen por qué salir de acá.
- **En español.** Traducir una cita la deja de ser textual, y una cita alterada
  es una frase puesta en la boca de una persona real.

Y del autor sale **solo el primer nombre**: que un apellido esté en Google no
autoriza a republicarlo en una historia de Instagram. Se recorta ACÁ, en el
origen, para que el apellido no salga nunca de este sistema.
"""
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Review

logger = logging.getLogger(__name__)

RATING_MINIMO = 4
TOPE = 200


def _api_key_ok(request) -> bool:
    esperada = getattr(settings, 'AUTOMATION_API_KEY', '') or ''
    return bool(esperada) and request.headers.get('X-API-KEY', '') == esperada


def _primer_nombre(autor: str) -> str:
    """«María José Pérez» → «María José»… no: → «María».

    Un solo token. Con dos nombres compuestos ya se empieza a poder identificar
    a alguien, y para citar basta el primero.
    """
    return (autor or '').strip().split(' ')[0][:60]


@require_http_methods(['GET'])
def resenas_lista(request):
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)

    qs = (Review.objects
          .exclude(texto='')
          .filter(rating__gte=RATING_MINIMO, idioma='es')
          .order_by('-fecha_review', '-created_at'))

    fuente = request.GET.get('fuente')
    if fuente in dict(Review.FUENTE_CHOICES):
        qs = qs.filter(fuente=fuente)

    resenas = [{
        'id': r.id,
        'fuente': r.get_fuente_display(),
        'fecha': r.fecha_review.isoformat() if r.fecha_review else None,
        'autor': _primer_nombre(r.autor),
        'rating': r.rating,
        'texto': r.texto.strip(),
    } for r in qs[:TOPE]]

    return JsonResponse({'total': len(resenas), 'resenas': resenas})
