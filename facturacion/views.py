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

from .models import (BoletaElectronica, ConfiguracionFacturacion,
                     MedioPago)


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


@staff_member_required
def descargar_cof_set(request):
    """Descarga el consumo de folios del día del set, para subirlo A MANO.

    El SII rechaza el set con «Valor del Monto Total no coinciden con el del
    COF» aunque cada boleta cuadre por dentro y el día tenga solo esas cinco
    (verificado el 02-09-2026 con folios 29-33, en un día limpio). El reparo
    cae siempre en el ÚLTIMO folio del lote: es el validador comparando contra
    un consumo de folios que nunca enviamos.

    Su propio correo lo dice: «se pretende verificar la capacidad de generación
    del RCOF». La API de SimpleAPI lo rechaza —«Impuestos Internos ya no admite
    este tipo de documento»—, pero la API también ignoraba el set y por el
    formulario web sí entró. Así que el archivo se genera acá y se sube a mano.
    """
    import datetime

    from django.utils import timezone

    from .services import rcof_builder, simpleapi_client

    if not simpleapi_client.credenciales_listas():
        return HttpResponse('Faltan credenciales de facturación.', status=503)

    crudo = (request.GET.get('fecha') or '').strip()
    try:
        fecha = datetime.date.fromisoformat(crudo) if crudo else timezone.localdate()
    except ValueError:
        return HttpResponse('Fecha inválida (usa AAAA-MM-DD).', status=400)

    boletas = [b for b in BoletaElectronica.objects
               .filter(ambiente='certificacion').exclude(estado='error')
               .order_by('folio')
               if b.xml_dte and f'<FchEmis>{fecha:%Y-%m-%d}</FchEmis>' in b.xml_dte]
    if not boletas:
        return HttpResponse(f'No hay boletas de certificación del {fecha}.', status=404)

    config = ConfiguracionFacturacion.get()
    cert_bytes, cert_password = simpleapi_client.obtener_certificado()
    sin_firma, doc_id = rcof_builder.construir_consumo_folios(
        config, fecha, boletas, secuencia=int(request.GET.get('secuencia') or 1),
        timestamp=timezone.localtime())
    xml = rcof_builder.firmar(sin_firma, doc_id, cert_bytes, cert_password)

    # La misma compuerta del sobre: no se entrega un XML que el esquema rechaza.
    from pathlib import Path

    from lxml import etree

    xsd = Path('/app/docs/certificacion_sii/ConsumoFolio_v10.xsd')
    if xsd.exists():
        schema = etree.XMLSchema(etree.parse(str(xsd)))
        if not schema.validate(etree.fromstring(xml.encode('ISO-8859-1', errors='replace'))):
            errores = '; '.join(e.message for e in schema.error_log)
            return HttpResponse(f'El consumo de folios no valida: {errores}', status=500)

    resp = HttpResponse(xml.encode('ISO-8859-1', errors='replace'),
                        content_type='application/xml')
    resp['Content-Disposition'] = (
        f'attachment; filename="consumo_folios_{fecha:%Y%m%d}.xml"')
    return resp


@staff_member_required
def pagos_sin_boleta(request):
    """Los pagos que SÍ correspondía boletear y no tienen boleta.

    La otra mitad del diseño de Jorge (02-09-2026): si al cobrar se puede
    responder «no», ese «no» tiene que quedar a la vista en alguna parte. Sin
    este listado, un pago sin boleta es indistinguible de un olvido — y el
    olvido solo aparecería cuando el SII pregunte.

    Se separan a propósito en dos grupos, porque significan cosas distintas:
    · DECIDIDOS: alguien miró y dijo que no. Hay nombre y hora.
    · SIN DECIDIR: nadie los miró. Estos son los que preocupan.
    """
    import datetime

    from django.utils import timezone

    from ventas.models import Pago

    from .models import BoletaElectronica, DecisionSinBoleta

    dias = 30
    try:
        dias = max(1, min(365, int(request.GET.get('dias') or 30)))
    except ValueError:
        pass
    desde = timezone.localdate() - datetime.timedelta(days=dias)

    codigos = list(MedioPago.objects.filter(genera_boleta=True)
                   .values_list('codigo', flat=True))
    con_boleta = set(BoletaElectronica.objects
                     .exclude(estado__in=('error', 'pendiente'))
                     .exclude(pago__isnull=True)
                     .values_list('pago_id', flat=True))
    decididos = {d.pago_id: d for d in DecisionSinBoleta.objects
                 .select_related('usuario', 'pago')}

    # Las devoluciones (monto <= 0) NO van acá. Una devolución no se boletea:
    # se anula con nota de crédito, y esas Jorge y Alda las emiten en el
    # sistema gratuito del SII, igual que las facturas (decisión 02-09-2026).
    # Sin este filtro el listado arrastraría 69 devoluciones históricas como
    # «nadie las ha mirado» — pendientes que nadie puede resolver nunca.
    pagos = (Pago.objects.filter(metodo_pago__in=codigos, fecha_pago__gte=desde,
                                 monto__gt=0)
             .exclude(id__in=con_boleta)
             .select_related('venta_reserva__cliente')
             .order_by('-fecha_pago'))

    sin_decidir, con_decision = [], []
    for p in pagos:
        fila = {'pago': p, 'decision': decididos.get(p.id)}
        (con_decision if fila['decision'] else sin_decidir).append(fila)

    # Un panel tiene que declarar lo que NO cuenta, o el total miente.
    devoluciones = Pago.objects.filter(metodo_pago__in=codigos,
                                       fecha_pago__gte=desde, monto__lte=0).count()

    return render(request, 'facturacion/pagos_sin_boleta.html', {
        'dias': dias,
        'devoluciones': devoluciones,
        'sin_decidir': sin_decidir,
        'con_decision': con_decision,
        'total_sin_decidir': sum(int(f['pago'].monto or 0) for f in sin_decidir),
        'total_con_decision': sum(int(f['pago'].monto or 0) for f in con_decision),
    })


def _pdf_boleta_impresa(boleta):
    """El PDF de la representación impresa, o (None, mensaje) si no se puede.

    Falla con mensaje y no con un 500: quien pide esto puede ser Deborah con
    un cliente al frente, o el cliente mismo desde su enlace.
    """
    from django.template.loader import render_to_string

    from .services import representacion_impresa

    try:
        datos = representacion_impresa.datos_para_impresion(boleta)
    except representacion_impresa.SinTimbre as exc:
        return None, str(exc)

    config = ConfiguracionFacturacion.get()
    html = render_to_string('facturacion/boleta_impresa.html', {
        'd': datos,
        # El recuadro rojo lleva la unidad del SII. Si nadie la configuró, la
        # comuna es lo más cercano y honesto -- no se inventa una regional.
        'unidad_sii': (config.unidad_sii or config.comuna or '').upper(),
        'url_verificacion': 'www.aremko.cl/boletas/consulta/',
    })

    from weasyprint import HTML
    return HTML(string=html).write_pdf(), ''


def _responder_pdf(boleta, request):
    pdf, error = _pdf_boleta_impresa(boleta)
    if pdf is None:
        return HttpResponse(f'No se puede imprimir esta boleta: {error}',
                            status=409, content_type='text/plain; charset=utf-8')
    respuesta = HttpResponse(pdf, content_type='application/pdf')
    # inline: se abre en el visor del teléfono en vez de bajar un archivo que
    # después hay que buscar. `descargar=1` fuerza la descarga.
    disposicion = 'attachment' if request.GET.get('descargar') else 'inline'
    respuesta['Content-Disposition'] = (
        f'{disposicion}; filename="boleta-{boleta.folio or boleta.pk}.pdf"')
    return respuesta


@staff_member_required
def boleta_impresa_staff(request, pk):
    """Reimprimir cualquier boleta desde el admin — incluidas las de
    certificación, que es como se generan las muestras impresas para el SII."""
    from django.shortcuts import get_object_or_404
    boleta = get_object_or_404(BoletaElectronica, pk=pk)
    return _responder_pdf(boleta, request)


def boleta_impresa_por_token(request, token):
    """La boleta impresa del cliente, desde el enlace que ya recibe.

    Misma regla que la consulta pública: solo boletas REALES. Una de
    certificación en manos de un cliente sería un documento sin valor
    presentado como si lo tuviera.
    """
    boleta = _publicables().filter(token_consulta=token).first()
    if boleta is None:
        return HttpResponse('Boleta no encontrada.', status=404,
                            content_type='text/plain; charset=utf-8')
    return _responder_pdf(boleta, request)
