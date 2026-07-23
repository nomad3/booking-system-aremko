"""
Invitación sorpresa (Fase 1, Puerta B) — el documento que el comprador le envía a
su pareja.

Es una vista FILTRADA de la reserva: muestra solo los servicios principales
(tina, masaje, alojamiento), y esconde toda ambientación (categoría Ambientaciones)
y TODOS los valores. Así se mantiene la sorpresa: la pareja sabe que hay una
escapada, pero no la decoración ni cuánto costó.

Página HTML (mobile-first) para que el comprador la comparta por WhatsApp con un
screenshot o el link. Acceso por token firmado (mismo mecanismo no-adivinable de la
ficha de reserva; sin migración).
"""
from django.shortcuts import render

from .ficha_reserva_view import _venta_desde_token, token_para_reserva  # noqa: F401 (reexport)


CATEGORIA_SECRETA = 'ambientaciones'


def url_invitacion_sorpresa(venta_id):
    """URL pública completa de la invitación (para el comprador post-pago)."""
    from django.urls import reverse
    from django.conf import settings
    base = getattr(settings, 'COMANDA_PUBLIC_BASE_URL', 'https://www.aremko.cl')
    return f"{base}{reverse('invitacion_sorpresa', kwargs={'token': token_para_reserva(venta_id)})}"


def _servicios_visibles(venta):
    """
    Servicios principales para mostrarle a la pareja: tina / masaje / alojamiento.
    Excluye la categoría Ambientaciones (la sorpresa) y no expone precios.
    """
    visibles = []
    hay_secreto = False
    for rs in venta.reservaservicios.select_related('servicio', 'servicio__categoria').all():
        servicio = rs.servicio
        cat = (getattr(servicio.categoria, 'nombre', '') or '').lower()
        if cat == CATEGORIA_SECRETA:
            hay_secreto = True
            continue  # nunca aparece en la invitación
        visibles.append({
            'nombre': servicio.nombre,
            'tipo': servicio.tipo_servicio,
            'fecha': rs.fecha_agendamiento,
            'hora': rs.hora_inicio,
        })
    return visibles, hay_secreto


def _ocasion_de(venta):
    """Infiere romántica vs cumpleaños desde el SKU de ambientación de la reserva."""
    for rs in venta.reservaservicios.select_related('servicio').all():
        n = (rs.servicio.nombre or '').lower()
        if 'cumple' in n:
            return 'cumpleanos'
    return 'romantica'


def invitacion_sorpresa_view(request, token):
    venta = _venta_desde_token(token)
    servicios, hay_secreto = _servicios_visibles(venta)
    ocasion = _ocasion_de(venta)

    # Fecha/hora de referencia = la de la primera tina (o el primer servicio visible).
    fecha_ref = hora_ref = None
    for s in servicios:
        if s['tipo'] == 'tina':
            fecha_ref, hora_ref = s['fecha'], s['hora']
            break
    if fecha_ref is None and servicios:
        fecha_ref, hora_ref = servicios[0]['fecha'], servicios[0]['hora']

    context = {
        'de_nombre': (venta.cliente.nombre if venta.cliente_id else '') or '',
        'servicios': servicios,
        'ocasion': ocasion,
        'fecha_ref': fecha_ref,
        'hora_ref': hora_ref,
        'hay_sorpresa': hay_secreto,
    }
    return render(request, 'ventas/invitacion_sorpresa.html', context)
