"""Servicio de disponibilidad para el agente IA (H-011 / Fase A).

Función central que el agente consultará (vía tool-calling): dado tipo + fecha +
cantidad de personas, devuelve los servicios PUBLICADOS que admiten esa cantidad y
sus horarios libres ese día. REÚSA el motor de disponibilidad que ya existe (no
reinventa): slots por fecha + bloqueos de día/slot + capacidad + reservas del día.

Fuente de verdad de lo ofrecible: `publicado_web` + `activo` (decisión de Jorge),
igual que el grounding. Capacidad estricta por `capacidad_minima/maxima`.
"""

import logging
from datetime import datetime, timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

TIPOS_VALIDOS = {'tina', 'masaje', 'cabana', 'otro'}
# Servicios PRINCIPALES ofrecibles por Luna: SOLO tinas, masajes y alojamiento (cabañas).
# Todo lo demás (desayuno, decoraciones, adicionales) es complemento y NO se ofrece como
# principal, aunque esté publicado. Defensa en profundidad junto con ids_complementarios().
TIPOS_PRINCIPALES = {'tina', 'masaje', 'cabana'}

DIAS_SEMANA_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
MESES_ES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}

# Las masajistas vienen desde la ciudad (~1h). Para HOY, si todavía no hay masajistas
# trabajando, no se puede ofrecer un masaje antes de que alcancen a llegar.
TRAVEL_MASAJISTA_MIN = 60

# Horarios de masaje RESERVADOS al Programa Ritual/Refugio (Jorge, 2026-06-26). De todos los
# slots del Masaje, estos 4 quedan SOLO para el programa; el resto (11:45/13:00/14:15/16:45/
# 19:15...) queda para masaje solo o pack tina+masaje (ciudad). Por eso disponibilidad() los
# EXCLUYE por defecto en las ofertas de masaje; el programa pide incluir_slots_programa=True.
MASAJE_SLOTS_PROGRAMA = ('15:30', '18:00', '20:30', '21:45')
MASAJE_SLOTS_PROGRAMA_MIN = frozenset({15 * 60 + 30, 18 * 60, 20 * 60 + 30, 21 * 60 + 45})


def _parse_fecha(fecha):
    """Acepta date, 'YYYY-MM-DD', o una EXPRESIÓN del cliente ("próximo lunes",
    "el sábado", "25 de junio"). El texto se resuelve de forma DETERMINÍSTICA con
    `resolver_fecha` — NUNCA se deja que el LLM calcule el día. Devuelve date o None.
    """
    if hasattr(fecha, 'year') and hasattr(fecha, 'month'):
        return fecha
    s = str(fecha).strip()
    if not s:
        return None
    # 1) ISO directo
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        pass
    # 2) Expresión en lenguaje natural → resolver_fecha (determinístico)
    try:
        r = resolver_fecha(s)
        if r and r.get('fecha_iso'):
            return datetime.strptime(r['fecha_iso'], '%Y-%m-%d').date()
    except Exception:  # noqa: BLE001 — si no se puede resolver, devolver None
        pass
    return None


def _hhmm_min(s):
    """'14:30' -> 870 ; None/inválido -> None."""
    try:
        h, m = str(s).strip().split(':')
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _sin_acentos(s):
    """Quita tildes y baja a minúsculas, para matchear como escriben los clientes
    ("sabado", "miercoles") contra los nombres con tilde ("sábado", "miércoles")."""
    import unicodedata
    return unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()


def resolver_fecha(expresion_cliente):
    """Resuelve fecha de forma DETERMINÍSTICA (sin dejar al LLM calcular día de semana).

    Acepta: "el sábado", "25 de junio", "el 25", "25", "próximo sábado", "este domingo", etc.
    Devuelve: {
        'fecha_iso': '2026-06-25' (YYYY-MM-DD),
        'dia_semana': 'jueves' (minúscula),
        'dia_numero': 4 (0=lunes, 6=domingo),
        'ambiguo': False,
        'error': None,
    }

    Si hay inconsistencia (cliente dice "domingo 25" pero el 25 es lunes) → ambiguo=True.
    """
    from django.utils import timezone as tz
    from datetime import timedelta
    import re

    hoy = tz.localtime(tz.now()).date()
    hoy_numero = hoy.weekday()  # 0=lunes, 6=domingo

    expresion = (expresion_cliente or '').strip().lower()
    if not expresion:
        return {'error': 'expresión vacía', 'ambiguo': True}
    expr_norm = _sin_acentos(expresion)  # match insensible a tildes ("sabado" = "sábado")

    # PATRÓN 1: Nombre de día ("sábado", "el sábado", "próximo sábado", "este sábado")
    for i, dia_nombre in enumerate(DIAS_SEMANA_ES):
        if _sin_acentos(dia_nombre) in expr_norm:
            dias_adelante = (i - hoy_numero) % 7
            if dias_adelante == 0:
                dias_adelante = 7  # "sábado" = próximo sábado, no hoy
            fecha = hoy + timedelta(days=dias_adelante)
            return {
                'fecha_iso': fecha.isoformat(),
                'dia_semana': DIAS_SEMANA_ES[fecha.weekday()],
                'dia_numero': fecha.weekday(),
                'ambiguo': False,
                'error': None,
            }

    # PATRÓN 1.5: Expresiones relativas ("hoy", "mañana", "pasado mañana").
    # Van DESPUÉS de los nombres de día (para que "el sábado por la mañana" caiga en sábado)
    # y ANTES del patrón numérico (para que "hoy a las 8" no tome el 8 como día del mes).
    # "pasado mañana" se chequea antes que "mañana" porque lo contiene.
    for palabra, delta in (('pasado manana', 2), ('manana', 1), ('hoy', 0)):
        if palabra in expr_norm:
            fecha = hoy + timedelta(days=delta)
            return {
                'fecha_iso': fecha.isoformat(),
                'dia_semana': DIAS_SEMANA_ES[fecha.weekday()],
                'dia_numero': fecha.weekday(),
                'ambiguo': False,
                'error': None,
            }

    # PATRÓN 2: Número de día ("25", "el 25", "25 de junio")
    match_numero = re.search(r'\b(\d{1,2})\b', expr_norm)
    if match_numero:
        dia_numero = int(match_numero.group(1))

        # Si hay mes en la expresión, usarlo; si no, asumir mes actual
        mes_numero = hoy.month
        for mes_nombre, num_mes in MESES_ES.items():
            if _sin_acentos(mes_nombre) in expr_norm:
                mes_numero = num_mes
                break

        try:
            año = hoy.year if mes_numero >= hoy.month else hoy.year + 1
            fecha = datetime(año, mes_numero, dia_numero).date()

            # Validar que no esté en el pasado
            if fecha < hoy:
                fecha = datetime(hoy.year + 1, mes_numero, dia_numero).date()

            return {
                'fecha_iso': fecha.isoformat(),
                'dia_semana': DIAS_SEMANA_ES[fecha.weekday()],
                'dia_numero': fecha.weekday(),
                'ambiguo': False,
                'error': None,
            }
        except ValueError:
            return {'error': f'fecha inválida (día {dia_numero} en mes {mes_numero})', 'ambiguo': True}

    # Fallback: no se pudo resolver
    return {'error': f'no se pudo resolver la fecha: "{expresion_cliente}"', 'ambiguo': True}


def validar_hora_es_slot(servicio_id, fecha, hora):
    """Defensa en código contra horas ALUCINADAS por el modelo liviano.

    El modelo a veces propone una hora que NO existe como slot (ej. 16:30).
    Este validador comprueba que `hora` sea uno de los slots REALES configurados
    para ese servicio en esa fecha (reusa `extraer_slots_para_fecha`).

    Devuelve:
      - None  → la hora es válida, o no se puede validar (sin servicio, sin fecha
                resoluble, o sin slots configurados) → no bloquear.
      - dict  → {'error': 'hora_invalida', 'mensaje': ...} si la hora NO está
                entre los slots configurados → el handler debe abortar y pedir
                a Luna que ofrezca SOLO los horarios reales.
    """
    import datetime as _dt
    from ventas.models import Servicio
    from ventas.views.calendario_matriz_view import extraer_slots_para_fecha
    try:
        serv = Servicio.objects.filter(id=servicio_id).first()
        if serv is None:
            return None  # el servicio inexistente lo maneja otra validación

        f = (str(fecha) if fecha is not None else '').strip()
        fecha_date = None
        try:
            fecha_date = _dt.date.fromisoformat(f[:10])
        except ValueError:
            r = resolver_fecha(f)
            if r and r.get('fecha_iso'):
                try:
                    fecha_date = _dt.date.fromisoformat(r['fecha_iso'])
                except ValueError:
                    fecha_date = None
        if fecha_date is None:
            return None  # sin fecha resoluble no se puede validar el slot

        slots = extraer_slots_para_fecha(serv.slots_disponibles, fecha_date) or []
        slots_min = {_hhmm_min(x) for x in slots if _hhmm_min(x) is not None}
        if not slots_min:
            return None  # servicio sin slots configurados → no se valida acá

        if _hhmm_min(hora) in slots_min:
            return None  # OK: es un slot real

        slots_txt = ', '.join(sorted((str(x) for x in slots), key=lambda x: _hhmm_min(x) or 0))
        return {
            'error': 'hora_invalida',
            'mensaje': (
                f'La hora "{hora}" NO es un horario disponible para {serv.nombre}. '
                f'Los únicos horarios reales ese día son: {slots_txt}. '
                f'Ofrece SOLO esos horarios (usa consultar_disponibilidad) y NUNCA inventes una hora.'
            ),
        }
    except Exception:  # noqa: BLE001 — un error del validador no debe tumbar la reserva
        logger.exception('[validar_hora_es_slot] error validando %s %s %s', servicio_id, fecha, hora)
        return None


def _hay_masaje_agendado_hoy(f):
    """True si ya hay al menos un masaje agendado (no cancelado) ese día → masajistas en sitio."""
    from ventas.models import ReservaServicio
    return (ReservaServicio.objects
            .filter(servicio__tipo_servicio='masaje', fecha_agendamiento=f)
            .exclude(venta_reserva__estado_pago='cancelado')
            .exists())


def _es_masaje_agendable(servicio):
    """Solo el Masaje de Relajación/Descontracturante es auto-agendable por el agente.

    Los demás masajes (piedras calientes, drenaje linfático, etc.) están en la web pero son
    "consulta por WhatsApp" → NO se ofrecen para reservar; si el cliente los pide, el agente
    deriva a una persona (regla de prompt). Solo afecta a servicios tipo masaje.
    """
    if (servicio.tipo_servicio or '') != 'masaje':
        return True
    n = (servicio.nombre or '').lower()
    return 'relaj' in n or 'descontractura' in n


def disponibilidad(fecha=None, personas=1, tipo=None, limite=2, incluir_slots_programa=False):
    """Servicios publicados que admiten `personas`, con precio total y horarios libres (H-028 BUG FIX).

    Con `fecha` (YYYY-MM-DD O expresión como "el sábado") → calcula horarios libres ese día.
    Sin `fecha` → modo SOLO PRECIO: lista los servicios que aplican por capacidad.

    CAMBIO H-028: Si fecha es una expresión ("el sábado", "25 de junio"), resuelve internamente
    con resolver_fecha() antes de consultar. Luna hace 1 sola tool-call.

    Returns dict:
      { 'fecha', 'dia_semana', 'personas', 'tipo', 'solo_precio', 'servicios': [
            {nombre, precio_por_persona, es_por_persona, precio_total,
             capacidad_minima, capacidad_maxima, duracion_texto, slots_libres:[...]|null}
        ], 'error'? }
    """
    from ventas.models import Servicio, ServicioBloqueo, ServicioSlotBloqueo
    from ventas.calendar_utils import verificar_disponibilidad
    from ventas.views.calendario_matriz_view import extraer_slots_para_fecha

    from .grounding import formatear_duracion

    # H-028: Si fecha parece ser una expresión (no ISO), resolver primero
    f = None
    dia_semana_str = None
    if fecha not in (None, ''):
        f = _parse_fecha(fecha)
        if f is None:
            # No es formato ISO → intentar resolver como expresión ("el sábado", "25 de junio")
            resuelto = resolver_fecha(fecha)
            if resuelto.get('error'):
                return {'error': resuelto['error'], 'servicios': []}
            f = _parse_fecha(resuelto['fecha_iso'])
            dia_semana_str = resuelto.get('dia_semana')
            if resuelto.get('ambiguo'):
                return {'error': 'fecha ambigua — por favor especifica día y fecha (ej. "domingo 21 de junio")', 'servicios': []}

    if fecha not in (None, '') and f is None:
        return {'error': 'fecha inválida', 'servicios': []}

    try:
        personas = int(personas)
    except (TypeError, ValueError):
        personas = 1
    if personas < 1:
        personas = 1

    from .models import WhatsAppAgentConfig
    comp_ids = WhatsAppAgentConfig.get_solo().ids_complementarios()

    qs = Servicio.objects.filter(
        publicado_web=True, activo=True,
        tipo_servicio__in=TIPOS_PRINCIPALES,  # SOLO tina/masaje/cabana (no desayuno ni 'otro')
        capacidad_minima__lte=personas,
        capacidad_maxima__gte=personas,
    ).exclude(id__in=comp_ids)  # H-011: no ofrecer complementos como principales
    if tipo:
        tipo = str(tipo).strip().lower()
        if tipo in TIPOS_VALIDOS:
            qs = qs.filter(tipo_servicio=tipo)
    qs = qs.order_by('tipo_servicio', 'nombre')

    # Piso horario para HOY: nunca ofrecer horas pasadas. Se calcula una vez.
    ahora = timezone.localtime()
    es_hoy = (f == ahora.date()) if f is not None else False
    ahora_min = (ahora.hour * 60 + ahora.minute) if es_hoy else None
    # Para masajes hoy, si aún no hay masajistas en sitio, sumar el viaje (~1h).
    masaje_en_sitio = _hay_masaje_agendado_hoy(f) if es_hoy else False

    servicios = []
    for s in qs:
        if not _es_masaje_agendable(s):
            continue  # masaje no auto-agendable (consulta por WhatsApp) → no se ofrece
        libres = None
        if f is not None:
            # Modo disponibilidad: horarios libres ese día.
            if ServicioBloqueo.servicio_bloqueado_en_fecha(s.id, f):
                continue
            # Piso: hoy no se ofrecen horas pasadas; masaje sin masajistas en sitio
            # exige el tiempo de viaje (clientes vienen de otra ciudad).
            piso_min = None
            if es_hoy:
                piso_min = ahora_min
                if s.tipo_servicio == 'masaje' and not masaje_en_sitio:
                    piso_min = ahora_min + TRAVEL_MASAJISTA_MIN
            slots = extraer_slots_para_fecha(s.slots_disponibles, f) or []
            libres = []
            for hora in slots:
                if piso_min is not None:
                    hm = _hhmm_min(hora)
                    if hm is not None and hm < piso_min:
                        continue  # hora pasada (o sin margen de viaje) → no ofrecer
                if ServicioSlotBloqueo.slot_bloqueado(s.id, f, hora):
                    continue
                try:
                    if verificar_disponibilidad(s, f, hora, personas):
                        libres.append(hora)
                except Exception:  # noqa: BLE001 — un slot con error no debe tumbar la consulta
                    logger.exception('disponibilidad: error verificando %s %s %s', s.id, f, hora)
            # Los 4 horarios del Programa Ritual/Refugio quedan reservados: se excluyen de las
            # ofertas de masaje (solo/ciudad) salvo que el programa pida incluirlos explícitamente.
            if s.tipo_servicio == 'masaje' and not incluir_slots_programa:
                libres = [h for h in libres if _hhmm_min(h) not in MASAJE_SLOTS_PROGRAMA_MIN]
            if not libres:
                continue  # sin horarios ese día → no se ofrece

        # Precio POR PERSONA en TODOS los servicios (tina/masaje/cabaña): total = base × personas.
        precio_pp = int(s.precio_base)
        # Duración: cabañas se expresan "por noche", no en horas (H-011 refinamiento).
        duracion_texto = 'por noche' if s.tipo_servicio == 'cabana' else formatear_duracion(s.duracion)
        servicios.append({
            'nombre': s.nombre,
            'servicio_id': s.id,
            'precio_por_persona': precio_pp,
            'es_por_persona': True,
            'precio_total': precio_pp * personas,
            'capacidad_minima': s.capacidad_minima,
            'capacidad_maxima': s.capacidad_maxima,
            'duracion_texto': duracion_texto,
            'duracion_min': s.duracion or 0,
            'tipo': s.tipo_servicio,
            'slots_libres': libres,
        })

    # Limitar opciones para no abrumar al LLM, PERO con variedad de tipos:
    # - Si el cliente pidió un tipo concreto (ej. "una tina"): hasta `limite` de ese tipo.
    # - Si es consulta general: 1 representante de CADA tipo disponible (tina + masaje +
    #   cabaña), para no sesgar por orden alfabético (cabana<masaje<tina) y ofrecer las 3
    #   categorías cuando todas calzan con la cantidad de personas.
    # `limite=None` desactiva el tope (lo usa el Ritual para ver TODAS las cabañas libres y
    # poder elegir Torre como último recurso; con tope alfabético "Torre" nunca aparecía).
    if limite is None:
        pass  # sin tope: devolver todos los servicios que calzan
    elif tipo == 'tina':
        # Variedad de tina: ofrecer 1 SIN hidromasaje + 1 CON, para que el cliente elija
        # (estándar más económica vs hidromasaje premium). Si solo hay de un tipo, las 2 primeras.
        con_h = [s for s in servicios if 'hidromasaje' in (s.get('nombre') or '').lower()]
        sin_h = [s for s in servicios if 'hidromasaje' not in (s.get('nombre') or '').lower()]
        servicios = [sin_h[0], con_h[0]] if (con_h and sin_h) else servicios[:limite]
    elif tipo:
        servicios = servicios[:limite]
    else:
        vistos, diversos = set(), []
        for s in servicios:
            if s['tipo'] not in vistos:
                diversos.append(s)
                vistos.add(s['tipo'])
        servicios = diversos

    # Calcular dia_semana si no se había resuelto
    if f and not dia_semana_str:
        dia_semana_str = DIAS_SEMANA_ES[f.weekday()]

    return {
        'fecha': f.isoformat() if f else None,
        'dia_semana': dia_semana_str,  # H-028: devuelve el día calculado en código
        'personas': personas,
        'tipo': tipo or 'todos',
        'solo_precio': f is None,
        'servicios': servicios,
    }


def disponibilidad_alojamiento_multinoche(fecha_llegada, personas=1, noches=None, fecha_salida=None):
    """Disponibilidad de cabañas para estadías multi-noche (H-027).

    Parámetros:
    - fecha_llegada: YYYY-MM-DD (check-in). REQUERIDO.
    - personas: 1-2 (default 1).
    - noches: entero ≥1. Si se pasa, calcula salida = llegada + noches días. PREFERIDO.
    - fecha_salida: YYYY-MM-DD (alternativa si no se pasa noches). Si ambos, noches tiene precedencia.

    Solo cabañas: publicadas, activas, capacidad 1-2 personas, NO complementos.
    Devuelve cabañas LIBRES en TODAS las noches del rango.

    Respuesta: {'noches', 'fecha_llegada', 'fecha_salida', 'personas', 'cabanas': [
        {nombre, total_por_noche, noches, total_estadia}  (SIN precio_por_persona)
    ], 'error'?}
    """
    try:
        from datetime import timedelta
        from ventas.models import Servicio, ReservaServicio
        from .models import WhatsAppAgentConfig

        f_llegada = _parse_fecha(fecha_llegada)
        if f_llegada is None:
            return {'error': 'fecha_llegada inválida (usa formato YYYY-MM-DD)', 'cabanas': []}

        # Calcular fecha de salida: preferir noches, fallback a fecha_salida
        if noches is not None:
            try:
                noches = int(noches)
                if noches < 1:
                    return {'error': 'noches debe ser ≥1', 'cabanas': []}
                f_salida = f_llegada + timedelta(days=noches)
            except (TypeError, ValueError):
                return {'error': 'noches inválido (usa un número entero)', 'cabanas': []}
        else:
            f_salida = _parse_fecha(fecha_salida)
            if f_salida is None:
                return {'error': 'fecha_salida inválida (usa formato YYYY-MM-DD) o pasa noches', 'cabanas': []}
            if f_salida <= f_llegada:
                return {'error': 'fecha de salida debe ser posterior a llegada', 'cabanas': []}

        try:
            personas = int(personas)
        except (TypeError, ValueError):
            personas = 1
        if personas < 1 or personas > 2:
            return {'error': 'máximo 2 personas por cabaña', 'cabanas': []}

        # Calcular noches del rango
        delta = f_salida - f_llegada
        noches = delta.days

        # Obtener todas las cabañas candidatas
        comp_ids = WhatsAppAgentConfig.get_solo().ids_complementarios()

        cabanas = Servicio.objects.filter(
            tipo_servicio='cabana',
            publicado_web=True,
            activo=True,
            capacidad_minima__lte=personas,
            capacidad_maxima__gte=personas,
        ).exclude(id__in=comp_ids).order_by('nombre')

        # Para cada cabaña, verificar si está libre en TODAS las noches
        resultado = []
        for cabana in cabanas:
            # Contar ocupaciones en cualquiera de las noches del rango
            ocupadas_en_rango = ReservaServicio.objects.filter(
                servicio=cabana,
                fecha_agendamiento__gte=f_llegada,
                fecha_agendamiento__lt=f_salida,
            ).count()

            # Si está ocupada en alguna noche del rango, excluir
            if ocupadas_en_rango > 0:
                continue

            # Cabaña libre: calcular precio
            precio_base = float(cabana.precio_base)
            total_por_noche = precio_base * personas
            total_estadia = total_por_noche * noches

            resultado.append({
                'nombre': cabana.nombre,
                'total_por_noche': int(total_por_noche) if total_por_noche == int(total_por_noche) else total_por_noche,
                'noches': noches,
                'total_estadia': int(total_estadia) if total_estadia == int(total_estadia) else total_estadia,
            })

        # Ordenar por precio y guardar el total ANTES de limitar
        resultado_ordenado = sorted(resultado, key=lambda x: x['total_estadia'])
        total_disponibles = len(resultado_ordenado)

        # Limitar a máximo 2 cabañas (las 2 más económicas, por total_estadia)
        resultado = resultado_ordenado[:2]

        return {
            'fecha_llegada': f_llegada.isoformat(),
            'fecha_salida': f_salida.isoformat(),
            'noches': noches,
            'personas': personas,
            'cabanas': resultado,
            'total_disponibles': total_disponibles,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception('Agente WA: error en disponibilidad_alojamiento_multinoche: %s', exc)
        return {'error': f'Error al consultar disponibilidad: {str(exc)[:100]}', 'cabanas': []}
