"""Conexión-Masajes — vistas públicas con token (mobile-first).

- masaje_ficha: cada participante completa su ficha de bienestar (una sola vez).
- masaje_registrar_acompanante: el comprador registra los datos de su acompañante.

Seguridad: acceso solo por token seguro (secrets.token_urlsafe), nunca por ID.
Registra fecha + texto exacto del consentimiento. Lenguaje de bienestar (no médico).
"""

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from ..models import ParticipanteMasajeReserva, BienestarMasajeFicha, Cliente

CONSENT_DATOS_TEXTO = (
    "Acepto que Aremko utilice esta información para adaptar mi experiencia de "
    "bienestar. Entiendo que no corresponde a una evaluación médica ni diagnóstico."
)
CONSENT_MKT_TEXTO = (
    "Acepto recibir recomendaciones, promociones y comunicaciones de Aremko por "
    "email o WhatsApp."
)


def _crear_o_actualizar_cliente(nombre, telefono, email):
    """Crea o actualiza Cliente usando el teléfono como identificador principal."""
    from ..services.cliente_service import ClienteService
    cliente, normalizado = ClienteService.buscar_cliente_por_telefono(telefono)
    if cliente:
        changed = False
        if not cliente.nombre and nombre:
            cliente.nombre = nombre[:100]; changed = True
        if not cliente.email and email:
            cliente.email = email[:254]; changed = True
        if changed:
            cliente.save()
        return cliente
    try:
        return Cliente.objects.create(
            nombre=nombre[:100],
            telefono=(normalizado or telefono)[:20],
            email=(email[:254] if email else None),
        )
    except Exception:
        # Carrera o teléfono duplicado: reintentar la búsqueda
        cliente, _ = ClienteService.buscar_cliente_por_telefono(telefono)
        return cliente


def masaje_ficha(request, token):
    """Ficha de bienestar individual del participante (se completa una sola vez)."""
    participante = get_object_or_404(ParticipanteMasajeReserva, token_formulario=token)
    ya_completada = bool(participante.ficha_bienestar_id) or participante.estado_contacto == 'ficha_completada'

    ctx = {
        'participante': participante,
        'objetivos': BienestarMasajeFicha.OBJETIVO_CHOICES,
        'intensidades': BienestarMasajeFicha.INTENSIDAD_CHOICES,
        'consent_datos_texto': CONSENT_DATOS_TEXTO,
        'consent_mkt_texto': CONSENT_MKT_TEXTO,
        'ya_completada': ya_completada,
    }

    if request.method != 'POST':
        # marcar como "abierto" si estaba pendiente
        if participante.estado_contacto == 'email_enviado':
            participante.estado_contacto = 'formulario_abierto'
            participante.save(update_fields=['estado_contacto', 'updated_at'])
        return render(request, 'ventas/masaje_ficha.html', ctx)

    if ya_completada:
        ctx['error'] = 'Esta ficha ya fue completada. Si necesitas corregir algo, escríbenos.'
        return render(request, 'ventas/masaje_ficha.html', ctx)

    nombre = (request.POST.get('nombre_completo') or participante.nombre or '').strip()
    telefono = (request.POST.get('telefono') or participante.telefono or '').strip()
    email = (request.POST.get('email') or '').strip()
    consent_datos = request.POST.get('consentimiento_datos') == 'on'
    consent_mkt = request.POST.get('consentimiento_marketing') == 'on'

    if not nombre or not telefono:
        ctx['error'] = 'Por favor completa tu nombre y teléfono.'
        return render(request, 'ventas/masaje_ficha.html', ctx)
    if not consent_datos:
        ctx['error'] = 'Para continuar debes aceptar el uso de tus datos para adaptar tu experiencia.'
        return render(request, 'ventas/masaje_ficha.html', ctx)

    cliente = _crear_o_actualizar_cliente(nombre, telefono, email)

    texto_consent = CONSENT_DATOS_TEXTO + ((" | " + CONSENT_MKT_TEXTO) if consent_mkt else "")
    ficha = BienestarMasajeFicha.objects.create(
        cliente=cliente,
        reserva=participante.reserva,
        nombre_completo=nombre[:160],
        telefono=telefono[:30],
        email=email[:254],
        objetivo_principal=(request.POST.get('objetivo_principal') or '')[:30],
        intensidad_preferida=(request.POST.get('intensidad_preferida') or '')[:10],
        zonas_tension=(request.POST.get('zonas_tension') or '')[:255],
        zonas_evitar=(request.POST.get('zonas_evitar') or '')[:255],
        observaciones_bienestar=(request.POST.get('observaciones_bienestar') or ''),
        condiciones_declaradas=(request.POST.get('condiciones_declaradas') or ''),
        consentimiento_datos=True,
        consentimiento_marketing=consent_mkt,
        fecha_consentimiento=timezone.now(),
        consentimiento_texto=texto_consent,
        origen=participante.tipo_participante,
        estado_ficha='completada',
    )

    participante.ficha_bienestar = ficha
    if cliente:
        participante.cliente = cliente
    if not participante.nombre:
        participante.nombre = nombre[:160]
    if not participante.telefono:
        participante.telefono = telefono[:30]
    if email and not participante.email:
        participante.email = email[:254]
    participante.estado_contacto = 'ficha_completada'
    participante.fecha_completado_formulario = timezone.now()
    participante.save()

    # F6: programar los emails de seguimiento post-visita (defensivo: nunca rompe
    # el guardado de la ficha si algo falla). El envío real va por cron y está
    # apagado por defecto (settings.MASAJE_SEGUIMIENTOS_ACTIVOS).
    try:
        from ..services.masaje_seguimiento_service import programar_seguimientos_masaje
        programar_seguimientos_masaje(participante)
    except Exception:
        pass

    ctx['exito'] = True
    ctx['ya_completada'] = True
    return render(request, 'ventas/masaje_ficha.html', ctx)


def masaje_registrar_acompanante(request, token):
    """El comprador registra los datos de su acompañante para coordinar el masaje."""
    comprador = get_object_or_404(ParticipanteMasajeReserva, token_formulario=token)
    if comprador.tipo_participante != 'comprador':
        raise Http404("Enlace no válido.")

    acompanante = (
        comprador.reserva.participantes_masaje
        .filter(tipo_participante='acompanante')
        .order_by('id')
        .first()
    )

    ctx = {'comprador': comprador, 'acompanante': acompanante}

    if request.method != 'POST':
        return render(request, 'ventas/masaje_acompanante.html', ctx)

    if acompanante is None:
        ctx['error'] = 'No hay un acompañante por registrar en esta reserva.'
        return render(request, 'ventas/masaje_acompanante.html', ctx)

    nombre = (request.POST.get('nombre') or '').strip()
    telefono = (request.POST.get('telefono') or '').strip()
    email = (request.POST.get('email') or '').strip()
    autoriza = request.POST.get('autoriza') == 'on'

    if not nombre or not telefono:
        ctx['error'] = 'Por favor completa el nombre y WhatsApp de tu acompañante.'
        return render(request, 'ventas/masaje_acompanante.html', ctx)
    if not autoriza:
        ctx['error'] = 'Debes confirmar que cuentas con autorización para compartir estos datos.'
        return render(request, 'ventas/masaje_acompanante.html', ctx)

    cliente = _crear_o_actualizar_cliente(nombre, telefono, email)
    acompanante.nombre = nombre[:160]
    acompanante.telefono = telefono[:30]
    acompanante.email = email[:254]
    if cliente:
        acompanante.cliente = cliente
    acompanante.save()

    ctx['exito'] = True
    ctx['ficha_url'] = reverse('masaje_ficha', kwargs={'token': acompanante.token_formulario})
    return render(request, 'ventas/masaje_acompanante.html', ctx)
