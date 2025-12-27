# -*- coding: utf-8 -*-
"""
Vista de diagnóstico simplificada para debugging
"""

from django.http import JsonResponse
from django.utils import timezone
import traceback
import time


def diagnostico_simple(request):
    """Vista de diagnóstico simplificada con manejo de errores"""

    # Verificar que es usuario staff
    if not request.user.is_staff:
        return JsonResponse({'error': 'No autorizado'}, status=403)

    try:
        from ..models import GiftCard, GiftCardExperiencia, VentaReserva, Pago

        inicio = time.time()

        # Test 1: Contar GiftCards
        total_giftcards = GiftCard.objects.count()
        tiempo_1 = (time.time() - inicio) * 1000

        # Test 2: Contar Experiencias
        inicio = time.time()
        total_experiencias = GiftCardExperiencia.objects.count()
        tiempo_2 = (time.time() - inicio) * 1000

        # Test 3: Contar Ventas con GiftCards
        inicio = time.time()
        ventas_con_giftcards = VentaReserva.objects.filter(giftcards__isnull=False).distinct().count()
        tiempo_3 = (time.time() - inicio) * 1000

        # Test 4: Contar Pagos con GiftCard
        inicio = time.time()
        pagos_giftcard = Pago.objects.filter(metodo_pago='giftcard').count()
        tiempo_4 = (time.time() - inicio) * 1000

        return JsonResponse({
            'status': 'ok',
            'timestamp': timezone.now().isoformat(),
            'metricas': {
                'total_giftcards': {
                    'valor': total_giftcards,
                    'tiempo_ms': round(tiempo_1, 2)
                },
                'total_experiencias': {
                    'valor': total_experiencias,
                    'tiempo_ms': round(tiempo_2, 2)
                },
                'ventas_con_giftcards': {
                    'valor': ventas_con_giftcards,
                    'tiempo_ms': round(tiempo_3, 2)
                },
                'pagos_giftcard': {
                    'valor': pagos_giftcard,
                    'tiempo_ms': round(tiempo_4, 2)
                }
            }
        })

    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }, status=500)
