"""Vista del documento formal de cotización para empresas.

Renderiza un HTML con look corporativo (imprimible / convertible a PDF
desde el browser) + versión texto plano embedded para copiar y enviar
por WhatsApp/email.
"""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render

from ..models import CotizacionEmpresa, ConfiguracionResumen


def _staff_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_staff)(view_func))


def _construir_texto_plano(cotizacion: CotizacionEmpresa, frase_beneficios: str, terminos: str, cierre: str) -> str:
    """Versión texto plano del documento, lista para copiar a WhatsApp/email."""
    lineas = []
    lineas.append('═══════════════════════════════════════════')
    lineas.append('  AREMKO HOTEL SPA')
    lineas.append('  Puerto Varas · Chile')
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
        CotizacionEmpresa.objects.prefetch_related('items__servicio', 'items__producto'),
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
