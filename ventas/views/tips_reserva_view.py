"""
Vista para generar tips de reserva (post-pago)
"""

import re
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from datetime import datetime
from ..models import VentaReserva, ConfiguracionTips


# Límites de caracteres por canal (para el contador del editor de tips).
# Instagram y Messenger rechazan message[text] > 2000; WhatsApp aguanta 4096.
LIMITE_INSTAGRAM = 2000
LIMITE_MESSENGER = 2000
LIMITE_WHATSAPP = 4096


def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff"""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)


@staff_required
def generar_tips_postpago(request, reserva_id):
    """
    Vista para generar los tips post-pago.
    Muestra el texto generado en un textarea editable para copiar/enviar.
    """
    reserva = get_object_or_404(VentaReserva, id=reserva_id)
    config = ConfiguracionTips.get_solo()

    # Generar el texto de tips
    texto_tips = _generar_texto_tips(reserva, config)

    context = {
        'reserva': reserva,
        'texto_tips': texto_tips,
        'config': config,
        'largo_tips': len(texto_tips),
        'limite_instagram': LIMITE_INSTAGRAM,
        'limite_messenger': LIMITE_MESSENGER,
        'limite_whatsapp': LIMITE_WHATSAPP,
    }

    return render(request, 'ventas/tips_postpago.html', context)


def _primera_linea(texto):
    """Primera línea no vacía de un campo (para dejar una norma en 1 sola línea)."""
    for ln in str(texto or '').splitlines():
        if ln.strip():
            return ln.strip()
    return ''


def _una_linea(texto, sep=' · ', saltar_encabezados=True):
    """Colapsa un bloque multilínea (ej. seguridad en pasarelas) en UNA línea.

    Une las líneas con `sep`. Con `saltar_encabezados` descarta las líneas que son
    título (terminan en ':') o notas ("Nota: ...") para dejar solo el contenido útil.
    """
    partes = []
    for ln in str(texto or '').splitlines():
        s = ln.strip()
        if not s:
            continue
        if saltar_encabezados:
            letras = [c for c in s if c.isalpha()]
            es_titulo_mayus = bool(letras) and ''.join(letras).isupper()  # "SEGURIDAD EN PASARELAS..."
            if s.endswith(':') or s.lower().startswith('nota') or es_titulo_mayus:
                continue
        partes.append(s)
    return sep.join(partes)


def _generar_texto_tips(reserva, config):
    """Genera el texto de tips COMPACTO (≤2000 chars) para enviar por WhatsApp,
    Instagram y Messenger.

    Instagram y Messenger rechazan mensajes > 2000 caracteres; por eso esta versión
    prioriza lo esencial y compacta lo largo (normas a 1 línea c/u, seguridad de
    pasarelas en 1 línea) y NO incluye la prosa larga de "cómo llegar" (queda el link
    de Maps), los horarios de recepción/cafetería, el menú de café ni la info
    secundaria (vestidores/ropa de masaje/menores). Todo eso sigue en el admin
    (ConfiguracionTips); acá solo se arma el mensaje corto que se envía al cliente.
    """
    servicios = reserva.reservaservicios.all().select_related('servicio', 'servicio__categoria')

    # Lista de cabañas reales (alojamiento verdadero)
    CABANAS_REALES = ['torre', 'acantilado', 'laurel', 'tepa', 'arrayan']

    tiene_alojamiento = any(
        s.servicio.tipo_servicio == 'cabana' and
        any(cabana in s.servicio.nombre.lower() for cabana in CABANAS_REALES)
        for s in servicios
    )
    tiene_tinas = any(s.servicio.tipo_servicio == 'tina' for s in servicios)
    tiene_masajes = any(s.servicio.tipo_servicio == 'masaje' for s in servicios)

    # Qué cabañas específicas tiene (para su WiFi)
    cabanas_contratadas = set()
    if tiene_alojamiento:
        for s in servicios:
            if s.servicio.tipo_servicio == 'cabana':
                nombre_lower = s.servicio.nombre.lower()
                for cabana in CABANAS_REALES:
                    if cabana in nombre_lower:
                        cabanas_contratadas.add(cabana)

    bloques = []  # cada bloque ya viene compacto; se unen con doble salto de línea

    # ── Saludo ──
    if config.encabezado:
        bloques.append(config.encabezado.strip())

    # ── WiFi ──
    wifi = []
    if tiene_alojamiento:
        wifi_cabanas = [
            ('torre', config.wifi_torre), ('tepa', config.wifi_tepa),
            ('acantilado', config.wifi_acantilado), ('laurel', config.wifi_laurel),
            ('arrayan', config.wifi_arrayan),
        ]
        for clave, val in wifi_cabanas:
            if clave in cabanas_contratadas and val:
                wifi.append(f"• {clave.capitalize()}: {val}")
    if tiene_tinas and config.wifi_tinas:
        wifi.append(f"• Tinas: {config.wifi_tinas}")
    if tiene_tinas and config.wifi_tinajas:
        wifi.append(f"• Tinajas: {config.wifi_tinajas}")
    if tiene_masajes and config.wifi_masajes:
        wifi.append(f"• Masajes: {config.wifi_masajes}")
    if wifi:
        bloques.append("📶 WIFI\n" + "\n".join(wifi))

    # ── Llegada (portón + teléfono + dirección + Maps) ──
    llegada = []
    if config.horario_porton_semana:
        llegada.append(f"• Portón {config.horario_porton_semana}")
    if config.horario_porton_finde:
        llegada.append(f"• Portón {config.horario_porton_finde}")
    if config.telefono_porton:
        llegada.append(f"• Fuera de horario: {config.telefono_porton}")
    if config.direccion:
        llegada.append(f"• Dirección: {config.direccion}")
    if config.link_google_maps:
        llegada.append(f"• Maps: {config.link_google_maps}")
    if llegada:
        bloques.append("🕐 LLEGADA\n" + "\n".join(llegada))

    # ── Tinas (uso) ──
    if tiene_tinas:
        tinas = []
        if config.uso_tinas_alternancia:
            tinas.append(config.uso_tinas_alternancia.strip())
        if config.uso_tinas_prohibiciones:
            tinas.append(config.uso_tinas_prohibiciones.strip())
        if config.recordatorio_toallas:
            tinas.append(f"🧺 {config.recordatorio_toallas.strip()}")
        if tinas:
            bloques.append("♨️ TINAS\n" + "\n".join(tinas))

    # ── Recomendaciones (solo prácticas/seguridad) ──
    rec = []
    if tiene_masajes and config.recomendacion_ducha_masaje:
        rec.append(f"• {config.recomendacion_ducha_masaje.strip()}")
    if tiene_tinas and config.prohibicion_vasos:
        rec.append(f"• {config.prohibicion_vasos.strip()}")
    if not tiene_alojamiento and config.tip_puntualidad:
        rec.append(f"• {config.tip_puntualidad.strip()}")
    if rec:
        bloques.append("💡 RECOMENDACIONES\n" + "\n".join(rec))

    # ── Normas (1 línea c/u) — solo alojamiento ──
    if tiene_alojamiento:
        normas = [_primera_linea(x) for x in (
            config.norma_mascotas, config.norma_cocinar,
            config.norma_fumar, config.norma_danos,
        )]
        normas = [n for n in normas if n]
        if normas:
            bloques.append("🚫 NORMAS\n" + "\n".join(normas))

    # ── Check-out — solo alojamiento ──
    if tiene_alojamiento:
        checkout = []
        if config.checkout_semana:
            checkout.append(config.checkout_semana.strip())
        if config.checkout_finde:
            checkout.append(config.checkout_finde.strip())
        if checkout:
            bloques.append("🚪 CHECK-OUT\n" + "\n".join(checkout))

    # ── Seguridad en pasarelas (1 línea) ──
    if config.seguridad_pasarelas:
        resumen = _una_linea(config.seguridad_pasarelas)
        if resumen:
            bloques.append("⚠️ Pasarelas: " + resumen)

    # ── Cierre ──
    cierre = []
    if config.despedida:
        cierre.append(config.despedida.strip())
    if config.contacto_whatsapp:
        cierre.append(f"Consultas por WhatsApp: {config.contacto_whatsapp}")
    if cierre:
        bloques.append("\n".join(cierre))

    texto = "\n\n".join(b for b in bloques if b.strip())
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()
