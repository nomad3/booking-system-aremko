"""
Página pública de consulta de boletas.

Requisito de la declaración de cumplimiento del SII: un link donde el receptor
pueda verificar su boleta. Dos entradas:
- /boletas/consulta/            → formulario folio + monto
- /boletas/b/<token>/           → link directo (se adjuntará en el email al cliente)
"""
from django.shortcuts import render

from .models import BoletaElectronica, ConfiguracionFacturacion


def _publicables():
    """Solo boletas REALES.

    La página es pública: una boleta de certificación («SET SII CASO-1») o una
    simulada mostrada como «✔ Boleta encontrada» le miente al cliente que la
    consulta, y el SII revisa este enlace antes de autorizar. Solo el ambiente
    de producción tiene valor tributario.
    """
    return (BoletaElectronica.objects
            .filter(ambiente='produccion')
            .exclude(estado__in=('pendiente', 'error', 'simulada')))


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
        boleta = _publicables().filter(folio=int(folio),
                                       monto_total=int(monto)).first()
    return render(request, 'facturacion/consulta_boleta.html', {
        'boleta': boleta,
        'buscado': buscado,
        'folio': folio,
        'monto': monto,
        'config': ConfiguracionFacturacion.get(),
    })


def boleta_por_token(request, token):
    boleta = _publicables().filter(token_consulta=token).first()
    return render(request, 'facturacion/consulta_boleta.html', {
        'boleta': boleta,
        'buscado': True,
        'por_token': True,
        'config': ConfiguracionFacturacion.get(),
    })
