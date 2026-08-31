"""
Página pública de consulta de boletas.

Requisito de la declaración de cumplimiento del SII: un link donde el receptor
pueda verificar su boleta. Dos entradas:
- /boletas/consulta/            → formulario folio + monto
- /boletas/b/<token>/           → link directo (se adjuntará en el email al cliente)
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
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


@staff_member_required
def descargar_sobre_set(request):
    """Descarga el sobre del set de certificación, para subirlo A MANO al SII.

    El SII acepta el envío «UPLOAD, Web o automatizado». Nosotros lo mandamos
    por API y el resultado fue contradictorio: la recepción del SII acusa 5
    boletas aceptadas, pero el validador del set responde «El Documento no
    esta en el envio» para los cinco casos (trackId 32038620, set 4949774,
    dos veces seguidas). El validador del set es de la generación anterior
    («SET BOLETAS - Version 1»), así que puede estar mirando solo los envíos
    hechos por el formulario web.

    Esto entrega el mismo sobre como archivo, para probar esa vía sin
    depender de que el SII nos explique su lado.
    """
    from .services import simpleapi_client

    if not simpleapi_client.credenciales_listas():
        return HttpResponse('Faltan credenciales de facturación.', status=503)

    ultimas = {}
    for b in (BoletaElectronica.objects
              .filter(caso_set__startswith='CASO', ambiente='certificacion')
              .exclude(estado='error').order_by('folio')):
        ultimas[b.caso_set] = b          # la última de cada caso
    boletas = [ultimas[c] for c in sorted(ultimas)]
    if not boletas:
        return HttpResponse('No hay boletas del set.', status=404)

    config = ConfiguracionFacturacion.get()
    cert_bytes, cert_password = simpleapi_client.obtener_certificado()
    sobre = simpleapi_client.generar_sobre([b.xml_dte for b in boletas],
                                           cert_bytes, cert_password, config)
    folios = '-'.join(str(b.folio) for b in (boletas[0], boletas[-1]))
    resp = HttpResponse(sobre.encode('ISO-8859-1', errors='replace'),
                        content_type='application/xml')
    resp['Content-Disposition'] = (
        f'attachment; filename="set_boletas_folios_{folios}.xml"')
    return resp
