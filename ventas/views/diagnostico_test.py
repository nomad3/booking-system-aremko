# -*- coding: utf-8 -*-
"""
Vista de prueba simple para diagnóstico
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required


@staff_member_required
@require_http_methods(["GET"])
def diagnostico_test(request):
    """Vista de prueba simple"""
    return JsonResponse({
        'status': 'ok',
        'message': 'El endpoint funciona correctamente',
        'user': str(request.user),
        'is_staff': request.user.is_staff
    })
