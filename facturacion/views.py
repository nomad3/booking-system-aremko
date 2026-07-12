"""
Página pública de consulta de boletas.

Requisito de la declaración de cumplimiento del SII: un link donde el receptor
pueda verificar su boleta. Dos entradas:
- /boletas/consulta/            → formulario folio + monto
- /boletas/b/<token>/           → link directo (se adjuntará en el email al cliente)
"""
from django.shortcuts import render

from .models import BoletaElectronica


def _contexto_boleta(boleta):
    return {
        'boleta': boleta,
        'config_valida': boleta is not None,
    }


def consulta_boleta(request):
    folio = (request.GET.get('folio') or '').strip()
    monto = (request.GET.get('monto') or '').strip().replace('.', '').replace('$', '')
    boleta = None
    buscado = bool(folio and monto)
    if buscado and folio.isdigit() and monto.isdigit():
        boleta = (BoletaElectronica.objects
                  .filter(folio=int(folio), monto_total=int(monto))
                  .exclude(estado__in=('pendiente', 'error'))
                  .first())
    return render(request, 'facturacion/consulta_boleta.html', {
        'boleta': boleta,
        'buscado': buscado,
        'folio': folio,
        'monto': monto,
    })


def boleta_por_token(request, token):
    boleta = (BoletaElectronica.objects
              .filter(token_consulta=token)
              .exclude(estado__in=('pendiente', 'error'))
              .first())
    return render(request, 'facturacion/consulta_boleta.html', {
        'boleta': boleta,
        'buscado': True,
        'por_token': True,
    })
