"""Conexión-Masajes — vistas públicas con token (mobile-first).

- masaje_ficha: cada participante completa su ficha de bienestar (una sola vez).
- masaje_registrar_acompanante: el comprador registra los datos de su acompañante.

Seguridad: acceso solo por token seguro (secrets.token_urlsafe), nunca por ID.
Registra fecha + texto exacto del consentimiento. Lenguaje de bienestar (no médico).
"""

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..models import ParticipanteMasajeReserva, BienestarMasajeFicha, Cliente, Comuna

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

    # Modo staff: si quien abre es la masajista (usuario logueado), NO puede ver ni
    # capturar teléfono/email del cliente — solo el resto de la ficha.
    modo_staff = request.user.is_authenticated and request.user.is_staff

    # Pedir teléfono/email SOLO al acompañante que llena su propia ficha: del
    # comprador ya tenemos esos datos (vinieron de la venta); del acompañante NO,
    # y los necesitamos para comunicación futura. La masajista (staff) nunca los pide.
    pedir_contacto = (not modo_staff) and (participante.tipo_participante == 'acompanante')

    ctx = {
        'participante': participante,
        'objetivos': BienestarMasajeFicha.OBJETIVO_CHOICES,
        'intensidades': BienestarMasajeFicha.INTENSIDAD_CHOICES,
        'consent_datos_texto': CONSENT_DATOS_TEXTO,
        'consent_mkt_texto': CONSENT_MKT_TEXTO,
        'ya_completada': ya_completada,
        'ocultar_contacto': modo_staff,
        'pedir_contacto': pedir_contacto,
    }

    # Plan Geo E3: se captura la comuna (la zona se deriva sola). El cliente la
    # indica (obligatoria); la masajista también puede ingresarla (opcional).
    ctx['comunas'] = Comuna.objects.select_related('region').order_by('nombre')

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
    if pedir_contacto:
        # Acompañante llenando su propia ficha: captura su teléfono y email.
        telefono = (request.POST.get('telefono') or participante.telefono or '').strip()
        email = (request.POST.get('email') or participante.email or '').strip()
    else:
        # Comprador o masajista: ya tenemos el contacto, no se vuelve a pedir.
        cli_prev = participante.cliente if participante.cliente_id else None
        telefono = (participante.telefono or (cli_prev.telefono if cli_prev else '') or '').strip()
        email = (participante.email or (cli_prev.email if cli_prev else '') or '').strip()
    consent_datos = request.POST.get('consentimiento_datos') == 'on'
    consent_mkt = request.POST.get('consentimiento_marketing') == 'on'
    comuna_val = (request.POST.get('comuna') or '').strip()

    if not nombre:
        ctx['error'] = 'Por favor completa el nombre.'
        return render(request, 'ventas/masaje_ficha.html', ctx)
    if pedir_contacto and (not telefono or not email):
        ctx['error'] = 'Por favor completa el teléfono y el email del acompañante.'
        return render(request, 'ventas/masaje_ficha.html', ctx)
    if not modo_staff and not comuna_val:
        ctx['error'] = 'Por favor indícanos tu comuna (o selecciona “Vengo del extranjero”).'
        return render(request, 'ventas/masaje_ficha.html', ctx)
    if not consent_datos:
        ctx['error'] = 'Para continuar debes aceptar el uso de los datos para adaptar la experiencia.'
        return render(request, 'ventas/masaje_ficha.html', ctx)

    cliente = _crear_o_actualizar_cliente(nombre, telefono, email) if telefono else participante.cliente

    # Plan Geo E3: aplicar la comuna/extranjero al cliente → la zona se deriva sola
    # (Cliente.save). Aplica también si la ingresa la masajista. Defensivo: nunca
    # rompe el guardado de la ficha.
    if cliente and comuna_val:
        try:
            if comuna_val == 'extranjero':
                cliente.pais = 'Extranjero'
                cliente.comuna = None
            elif comuna_val.isdigit():
                cm = Comuna.objects.filter(id=comuna_val).first()
                if cm:
                    cliente.comuna = cm
                    if not (cliente.pais or '').strip():
                        cliente.pais = 'Chile'
            cliente.save()
        except Exception:
            pass

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
        alergia_aceites=(request.POST.get('alergia_aceites') == 'on'),
        alergia_aceites_detalle=(request.POST.get('alergia_aceites_detalle') or '')[:255],
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


def _pagina_baja(titulo, mensaje, boton_confirmar=False):
    """HTML mobile-first de marca para la página de baja de comunicaciones."""
    boton = ''
    if boton_confirmar:
        boton = (
            '<form method="post" style="margin-top:22px;">'
            '<button type="submit" style="background:#b5651d;color:#fff;border:none;'
            'padding:14px 30px;border-radius:10px;font-weight:bold;font-size:16px;'
            'cursor:pointer;">Sí, darme de baja</button></form>'
        )
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{titulo}</title></head>'
        '<body style="margin:0;background:#faf6f0;font-family:Arial,Helvetica,sans-serif;">'
        '<div style="max-width:520px;margin:40px auto;background:#fff;border-radius:16px;'
        'overflow:hidden;border:1px solid #eee3d4;">'
        '<div style="background:#b5651d;padding:24px;text-align:center;">'
        '<div style="color:#fff;font-size:22px;font-weight:bold;">🌿 Aremko Spa Boutique</div>'
        '<div style="color:#f6e9da;font-size:13px;margin-top:2px;">Puerto Varas</div></div>'
        '<div style="padding:30px 26px;color:#3a3a3a;font-size:16px;line-height:1.6;text-align:center;">'
        f'<h2 style="color:#b5651d;margin-top:0;">{titulo}</h2><p>{mensaje}</p>{boton}'
        '</div></div></body></html>'
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def masaje_baja_comunicaciones(request, token):
    """Baja de comunicaciones (email + WhatsApp + promociones) desde el enlace de
    los correos de seguimiento. El token es firmado (codifica el id de cliente).
    GET muestra confirmación; POST ejecuta la baja (evita bajas accidentales por
    prefetch de los clientes de correo)."""
    from django.core import signing
    from ..models import ClientPreferences
    from ..services.masaje_seguimiento_service import BAJA_SALT

    try:
        cliente_id = signing.loads(token, salt=BAJA_SALT)
    except signing.BadSignature:
        return HttpResponse(_pagina_baja(
            "Enlace no válido",
            "Este enlace de baja no es válido o está incompleto."), status=400)

    cliente = Cliente.objects.filter(id=cliente_id).first()
    if cliente is None:
        return HttpResponse(_pagina_baja(
            "No encontrado",
            "No encontramos tu registro. Es posible que ya no estés en nuestra base."),
            status=404)

    if request.method == 'POST':
        prefs, _ = ClientPreferences.objects.get_or_create(cliente=cliente)
        prefs.set_opt_out_all()
        if not cliente.opt_out_whatsapp:
            cliente.opt_out_whatsapp = True
            cliente.save(update_fields=['opt_out_whatsapp'])
        return HttpResponse(_pagina_baja(
            "Listo, te diste de baja 🌿",
            "No volverás a recibir correos ni WhatsApp con información de Aremko Spa "
            "Boutique. Si cambias de opinión, escríbenos cuando quieras."))

    return HttpResponse(_pagina_baja(
        "¿Dar de baja tus comunicaciones?",
        "Si confirmas, dejarás de recibir correos y WhatsApp con información de "
        "bienestar y promociones de Aremko Spa Boutique.",
        boton_confirmar=True))
