"""Vista del documento formal de cotización para empresas.

Renderiza un HTML con look corporativo (imprimible / convertible a PDF
desde el browser) + versión texto plano embedded para copiar y enviar
por WhatsApp/email.
"""
import logging
import re
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from ..models import CotizacionFormal, ConfiguracionResumen

logger = logging.getLogger(__name__)


def _staff_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_staff)(view_func))


def _construir_texto_plano(cotizacion: CotizacionFormal, frase_beneficios: str, terminos: str, cierre: str) -> str:
    """Versión texto plano del documento, lista para copiar a WhatsApp/email."""
    lineas = []
    lineas.append('═══════════════════════════════════════════')
    lineas.append('  Aremko Spa Boutique')
    lineas.append('═══════════════════════════════════════════')
    lineas.append('')
    lineas.append(f'COTIZACIÓN N° {cotizacion.numero}')
    lineas.append(f'Fecha emisión: {cotizacion.fecha_emision.strftime("%d-%m-%Y") if cotizacion.fecha_emision else "(borrador)"}')
    if cotizacion.fecha_validez:
        lineas.append(f'Válida hasta:  {cotizacion.fecha_validez.strftime("%d-%m-%Y")} ({cotizacion.validez_dias} días)')
    lineas.append('')
    lineas.append('Para:')
    lineas.append(f'  Empresa:    {cotizacion.empresa_razon_social}')
    if cotizacion.empresa_rut:
        lineas.append(f'  RUT:        {cotizacion.empresa_rut}')
    if cotizacion.empresa_giro:
        lineas.append(f'  Giro:       {cotizacion.empresa_giro}')
    lineas.append(f'  Contacto:   {cotizacion.contacto_nombre}')
    if cotizacion.contacto_email:
        lineas.append(f'  Email:      {cotizacion.contacto_email}')
    if cotizacion.contacto_telefono:
        lineas.append(f'  Teléfono:   {cotizacion.contacto_telefono}')
    lineas.append('')
    lineas.append('Detalle de servicios y productos cotizados:')
    lineas.append('')
    items = list(cotizacion.items.all())
    # Cabecera de tabla en monospace
    lineas.append(f'  {"ITEM":<40}  {"CANT":>5}  {"PRECIO UNIT":>14}  {"SUBTOTAL":>14}')
    lineas.append(f'  {"-" * 40}  {"-" * 5}  {"-" * 14}  {"-" * 14}')
    for item in items:
        descr = item.descripcion[:40]
        precio = f'${int(item.precio_unitario):,}'.replace(',', '.')
        subtotal = f'${int(item.subtotal):,}'.replace(',', '.')
        lineas.append(f'  {descr:<40}  {item.cantidad:>5}  {precio:>14}  {subtotal:>14}')
    lineas.append(f'  {"-" * 40}  {"-" * 5}  {"-" * 14}  {"-" * 14}')
    total_str = f'${int(cotizacion.total):,}'.replace(',', '.')
    lineas.append(f'  {"TOTAL":<40}  {"":>5}  {"":>14}  {total_str:>14}')
    lineas.append('')
    lineas.append('')
    lineas.append(frase_beneficios)
    lineas.append('')
    lineas.append('')
    lineas.append(terminos)
    lineas.append('')
    lineas.append('')
    lineas.append(cierre)
    lineas.append('')
    lineas.append('═══════════════════════════════════════════')
    return '\n'.join(lineas)


@_staff_required
def cotizacion_formal_view(request, numero):
    """Renderiza el documento formal de una cotización.

    Args:
        numero: número del documento (321, 322, etc.). Se convierte a id (numero - 320).
    """
    try:
        cotizacion_id = int(numero) - 320
    except (TypeError, ValueError):
        cotizacion_id = -1

    cotizacion = get_object_or_404(
        CotizacionFormal.objects.prefetch_related('items__servicio', 'items__producto'),
        pk=cotizacion_id,
    )

    config = ConfiguracionResumen.get_solo()
    frase_beneficios = (cotizacion.frase_beneficios.strip()
                        or config.get_cotizacion_frase_beneficios())
    terminos = config.get_cotizacion_terminos()
    cierre = config.get_cotizacion_cierre()

    texto_plano = _construir_texto_plano(cotizacion, frase_beneficios, terminos, cierre)

    return render(request, 'ventas/cotizacion_formal.html', {
        'cotizacion': cotizacion,
        'items': cotizacion.items.all(),
        'frase_beneficios': frase_beneficios,
        'terminos': terminos,
        'cierre': cierre,
        'texto_plano': texto_plano,
    })


def _slugify_empresa(nombre: str) -> str:
    """Convierte 'Empresa de Prueba SpA' → 'Empresa_de_Prueba_SpA' para nombre de archivo."""
    limpio = re.sub(r'[^\w\s-]', '', nombre or 'empresa', flags=re.UNICODE)
    return re.sub(r'\s+', '_', limpio.strip())[:50] or 'empresa'


@_staff_required
def cotizacion_pdf_view(request, numero):
    """Genera el PDF de la cotización y lo devuelve como descarga directa.

    Reusa el mismo HTML template (sin la toolbar) y lo convierte con WeasyPrint.
    El navegador descarga el archivo a la carpeta de Descargas por default.
    """
    try:
        cotizacion_id = int(numero) - 320
    except (TypeError, ValueError):
        cotizacion_id = -1

    cotizacion = get_object_or_404(
        CotizacionFormal.objects.prefetch_related('items__servicio', 'items__producto'),
        pk=cotizacion_id,
    )

    config = ConfiguracionResumen.get_solo()
    frase_beneficios = (cotizacion.frase_beneficios.strip()
                        or config.get_cotizacion_frase_beneficios())
    terminos = config.get_cotizacion_terminos()
    cierre = config.get_cotizacion_cierre()

    html_str = render_to_string('ventas/cotizacion_formal.html', {
        'cotizacion': cotizacion,
        'items': cotizacion.items.all(),
        'frase_beneficios': frase_beneficios,
        'terminos': terminos,
        'cierre': cierre,
        'texto_plano': '',  # no se usa en PDF
        'pdf_mode': True,   # bandera para que el template oculte toolbar
    })

    try:
        from weasyprint import HTML, CSS
        # Letter (8.5" x 11"), márgenes ajustados para que todo el contenido
        # entre en una sola página.
        pdf_bytes = HTML(string=html_str, base_url=request.build_absolute_uri('/')).write_pdf(
            stylesheets=[CSS(string='@page { size: Letter; margin: 1cm 1.5cm; }')],
        )
    except Exception as exc:
        logger.error(f'Error generando PDF de cotización {numero}: {exc}', exc_info=True)
        return HttpResponse(
            f'Error generando PDF: {exc}. Usa "Imprimir / Guardar PDF" del navegador como alternativa.',
            status=500,
        )

    filename = f'Cotizacion_{cotizacion.numero}_{_slugify_empresa(cotizacion.empresa_razon_social)}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@_staff_required
def sistema_documento_pdf_view(request):
    """Genera y descarga el PDF del documento maestro del Sistema Aremko.

    Lee docs/SISTEMA_AREMKO_COMPLETO.md desde el repositorio, lo convierte a HTML
    con estilos corporativos y lo entrega como PDF tamaño Letter via WeasyPrint.
    """
    import os
    from django.conf import settings as dj_settings

    try:
        import markdown
        from weasyprint import HTML, CSS
    except ImportError as exc:
        return HttpResponse(
            f'Falta dependencia para generar PDF: {exc}. '
            f'WeasyPrint y markdown deben estar instalados.',
            status=500,
        )

    md_path = os.path.join(
        getattr(dj_settings, 'BASE_DIR', os.getcwd()),
        'docs',
        'SISTEMA_AREMKO_COMPLETO.md',
    )
    if not os.path.exists(md_path):
        return HttpResponse(
            f'Documento maestro no encontrado en {md_path}. '
            f'Verifica que el archivo esté en docs/ del repositorio.',
            status=404,
        )

    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    html_body = markdown.markdown(
        md_text,
        extensions=['extra', 'tables', 'toc', 'sane_lists'],
    )

    css_styles = '''
        @page { size: Letter; margin: 1.5cm 2cm; }
        body { font-family: Helvetica, Arial, sans-serif; line-height: 1.5; color: #2a2a2a; }
        h1 { color: #2a2a2a; border-bottom: 3px solid #b78b5b; padding-bottom: 8px; margin-top: 40px; }
        h1:first-of-type { margin-top: 0; }
        h2 { color: #2a2a2a; border-bottom: 1px solid #b78b5b; padding-bottom: 4px; margin-top: 28px; }
        h3 { color: #b78b5b; margin-top: 22px; }
        h4 { color: #555; margin-top: 18px; }
        p, li { font-size: 12px; }
        table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 11px; }
        th { background: #faf6ee; color: #b78b5b; text-align: left; padding: 6px 8px; border-bottom: 2px solid #b78b5b; }
        td { padding: 6px 8px; border-bottom: 1px solid #eee; vertical-align: top; }
        code { background: #f5f5f5; padding: 1px 4px; border-radius: 3px; font-size: 10px; }
        pre { background: #fafafa; border-left: 3px solid #b78b5b; padding: 10px; font-size: 10px; line-height: 1.4; }
        hr { border: none; border-top: 1px solid #ddd; margin: 30px 0; }
        h1, h2, h3 { page-break-after: avoid; }
        table { page-break-inside: avoid; }
    '''

    html_str = f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Sistema Aremko</title></head><body>{html_body}</body></html>'

    pdf_bytes = HTML(string=html_str).write_pdf(stylesheets=[CSS(string=css_styles)])

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="Aremko_Sistema_Completo.pdf"'
    return response
