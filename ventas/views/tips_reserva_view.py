"""
Vista para generar tips de reserva (post-pago)
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from datetime import datetime
from ..models import VentaReserva, ConfiguracionTips


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
    }

    return render(request, 'ventas/tips_postpago.html', context)


def _generar_texto_tips(reserva, config):
    """
    Genera el texto de tips según los servicios contratados.

    Args:
        reserva: Instancia de VentaReserva
        config: Instancia de ConfiguracionTips

    Returns:
        str: Texto de tips formateado
    """
    lineas = []

    # Detectar tipo de reserva
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

    # Determinar qué cabañas específicas tiene
    cabanas_contratadas = set()
    if tiene_alojamiento:
        for s in servicios:
            if s.servicio.tipo_servicio == 'cabana':
                nombre_lower = s.servicio.nombre.lower()
                for cabana in CABANAS_REALES:
                    if cabana in nombre_lower:
                        cabanas_contratadas.add(cabana)

    # Encabezado
    if config.encabezado:
        lineas.append(config.encabezado)
        lineas.append("")

    if config.intro:
        lineas.append(config.intro)
        lineas.append("")

    lineas.append("━" * 60)
    lineas.append("")

    # ========== SECCIÓN WIFI ==========
    if tiene_alojamiento or tiene_tinas or tiene_masajes:
        lineas.append("📶 CONEXIÓN WIFI")
        lineas.append("")

        # WiFi de cabañas específicas
        if tiene_alojamiento:
            if 'torre' in cabanas_contratadas and config.wifi_torre:
                lineas.append(f"• Cabaña Torre: {config.wifi_torre}")
            if 'tepa' in cabanas_contratadas and config.wifi_tepa:
                lineas.append(f"• Cabaña Tepa: {config.wifi_tepa}")
            if 'acantilado' in cabanas_contratadas and config.wifi_acantilado:
                lineas.append(f"• Cabaña Acantilado: {config.wifi_acantilado}")
            if 'laurel' in cabanas_contratadas and config.wifi_laurel:
                lineas.append(f"• Cabaña Laurel: {config.wifi_laurel}")
            if 'arrayan' in cabanas_contratadas and config.wifi_arrayan:
                lineas.append(f"• Cabaña Arrayan: {config.wifi_arrayan}")
            lineas.append("")

        # WiFi de otras áreas
        if (tiene_tinas or tiene_masajes):
            lineas.append("Otras áreas:")
            if tiene_tinas and config.wifi_tinas:
                lineas.append(f"• Sector Tinas: {config.wifi_tinas}")
            if tiene_tinas and config.wifi_tinajas:
                lineas.append(f"• Tinajas: {config.wifi_tinajas}")
            if tiene_masajes and config.wifi_masajes:
                lineas.append(f"• Sala de Masajes: {config.wifi_masajes}")

        lineas.append("")
        lineas.append("━" * 60)
        lineas.append("")

    # ========== NORMAS (solo para alojamiento) ==========
    if tiene_alojamiento:
        lineas.append("🚫 NORMAS IMPORTANTES")
        lineas.append("")

        if config.norma_mascotas:
            lineas.append(config.norma_mascotas)
            lineas.append("")

        if config.norma_cocinar:
            lineas.append(config.norma_cocinar)
            lineas.append("")

        if config.norma_fumar:
            lineas.append(config.norma_fumar)
            lineas.append("")

        if config.norma_danos:
            lineas.append(config.norma_danos)

        lineas.append("")
        lineas.append("━" * 60)
        lineas.append("")

    # ========== TINAS (si aplica) ==========
    if tiene_tinas:
        lineas.append("♨️ TINAS DE AGUA CALIENTE")
        lineas.append("")

        if config.uso_tinas_alternancia:
            lineas.append(config.uso_tinas_alternancia)
            lineas.append("")

        if config.uso_tinas_prohibiciones:
            lineas.append(config.uso_tinas_prohibiciones)
            lineas.append("")

        if config.recordatorio_toallas:
            lineas.append(f"🧺 Toallas:")
            lineas.append(config.recordatorio_toallas)

        lineas.append("")
        lineas.append("━" * 60)
        lineas.append("")

    # ========== RECOMENDACIONES ADICIONALES ==========
    if tiene_tinas or tiene_masajes:
        lineas.append("💡 RECOMENDACIONES")
        lineas.append("")

        if tiene_masajes and config.recomendacion_ducha_masaje:
            lineas.append(f"• {config.recomendacion_ducha_masaje}")

        if tiene_tinas and config.prohibicion_vasos:
            lineas.append(f"• {config.prohibicion_vasos}")

        if not tiene_alojamiento and config.tip_puntualidad:
            lineas.append(f"• {config.tip_puntualidad}")

        if config.info_vestidores:
            lineas.append(f"• {config.info_vestidores}")

        if tiene_masajes and config.ropa_masaje:
            lineas.append(f"• {config.ropa_masaje}")

        if config.menores_edad:
            lineas.append(f"• {config.menores_edad}")

        lineas.append("")
        lineas.append("━" * 60)
        lineas.append("")

    # ========== CHECK-OUT (solo para alojamiento) ==========
    if tiene_alojamiento:
        lineas.append("🚪 CHECK-OUT")
        lineas.append("")

        if config.checkout_semana:
            lineas.append(config.checkout_semana)
            lineas.append("")

        if config.checkout_finde:
            lineas.append(config.checkout_finde)

        lineas.append("")
        lineas.append("━" * 60)
        lineas.append("")

    # ========== SEGURIDAD EN PASARELAS (siempre) ==========
    if config.seguridad_pasarelas:
        lineas.append(config.seguridad_pasarelas)
        lineas.append("")
        lineas.append("━" * 60)
        lineas.append("")

    # ========== HORARIOS ==========
    lineas.append("🕐 HORARIOS")
    lineas.append("")

    lineas.append("Portón de acceso:")
    if config.horario_porton_semana:
        lineas.append(f"• {config.horario_porton_semana}")
    if config.horario_porton_finde:
        lineas.append(f"• {config.horario_porton_finde}")
    if config.telefono_porton:
        lineas.append(f"Fuera de horario: {config.telefono_porton}")
    lineas.append("")

    if tiene_alojamiento:
        lineas.append("Recepción:")
        if config.horario_recepcion_semana:
            lineas.append(f"• {config.horario_recepcion_semana}")
        if config.horario_recepcion_finde:
            lineas.append(f"• {config.horario_recepcion_finde}")
        if config.horario_recepcion_domingo:
            lineas.append(f"• {config.horario_recepcion_domingo}")
        lineas.append("")

    lineas.append("Cafetería:")
    if config.horario_cafeteria_semana:
        lineas.append(f"• {config.horario_cafeteria_semana}")
    if config.horario_cafeteria_finde:
        lineas.append(f"• {config.horario_cafeteria_finde}")

    lineas.append("")
    if config.productos_cafeteria:
        lineas.append(f"Disponemos de: {config.productos_cafeteria}")
    if config.menu_cafe:
        lineas.append(config.menu_cafe)

    lineas.append("")
    lineas.append("━" * 60)
    lineas.append("")

    # ========== UBICACIÓN ==========
    lineas.append("📍 CÓMO LLEGAR")
    lineas.append("")

    if config.direccion:
        lineas.append(f"Dirección: {config.direccion}")
        lineas.append("")

    if config.como_llegar:
        lineas.append(config.como_llegar)
        lineas.append("")

    if config.link_google_maps:
        lineas.append(f"Google Maps: {config.link_google_maps}")

    lineas.append("")
    lineas.append("━" * 60)
    lineas.append("")

    # ========== DESPEDIDA ==========
    if config.despedida:
        lineas.append(config.despedida)
        lineas.append("")

    if config.contacto_whatsapp:
        lineas.append(f"Cualquier consulta, escríbenos por WhatsApp: {config.contacto_whatsapp}")

    return '\n'.join(lineas)
