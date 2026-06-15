"""
bandeja_whatsapp_service
========================

Lógica de soporte para el comando `generar_bandeja_whatsapp_diaria`
(Operación Vuelta a Casa, Etapa 3).

Separado del Command para que sea:
- Testeable unitariamente sin levantar Django runner pesado
- Reutilizable desde el admin si más adelante queremos un botón
  "generar bandeja ad-hoc para cliente X"

Contiene:
    SafeDict                 — dict tolerante a placeholders faltantes
    DIAS_ES, MESES_ES        — localizaciones manuales (es_CL no garantizado)
    humanize_ultima_visita   — "en febrero" / "hace 4 meses"
    mes_proximo_nombre       — "mayo"
    compania_habitual        — "tu pareja" / "solos" / "con tu grupo"
    calcular_prioridad       — 0 a 6 o None (no califica)
    buscar_script_cascada    — match en 5 niveles (más específico → más genérico)
    calcular_servicio_recomendado — cruce tinas/masajes/cabañas
    calcular_sugerencia_dia_hora  — moda histórica del cliente
    obtener_ultimo_servicio_nombre
    build_render_context     — arma dict de variables para .format_map(SafeDict)
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import date, timedelta
from typing import Optional, Sequence, Tuple


# ============================================================================
# Localización manual (no depender de locale del sistema)
# ============================================================================

MESES_ES = [
    '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

# datetime.date.weekday(): lunes=0, ..., domingo=6
DIAS_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


# ============================================================================
# SafeDict: tolerante a placeholders faltantes en .format_map()
# ============================================================================

class SafeDict(dict):
    """Devuelve cadena vacía si la key no existe, en lugar de KeyError.

    Permite que una plantilla con {servicio_recomendado} no crashee si no
    pudimos calcular esa variable para un cliente específico.

    >>> "Hola {nombre}, te {accion_faltante} algo.".format_map(SafeDict(nombre='María'))
    'Hola María, te  algo.'
    """

    def __missing__(self, key):
        return ''


# ============================================================================
# Helpers de humanización (puros, sin DB)
# ============================================================================

def humanize_ultima_visita(fecha: Optional[date], hoy: date) -> str:
    """Convierte una fecha a frase humana:
       - <= 6 meses: 'en febrero' / 'en mayo'
       - > 6 meses: 'hace N meses'
       - None: 'hace un buen rato'
    """
    if fecha is None:
        return 'hace un buen rato'

    delta_dias = (hoy - fecha).days
    if delta_dias < 0:
        # Fecha futura — raro pero no crashear
        return 'en próximos días'

    meses_aprox = delta_dias // 30
    if meses_aprox <= 6:
        return f'en {MESES_ES[fecha.month]}'
    return f'hace {meses_aprox} meses'


def mes_proximo_nombre(hoy: date) -> str:
    """'mayo' si hoy es 23-abril."""
    siguiente = (hoy.month % 12) + 1
    return MESES_ES[siguiente]


def compania_habitual(eje_contexto: str) -> str:
    """Frase natural según el contexto dominante del cliente."""
    mapeo = {
        'Visitante Pareja': 'tu pareja',
        'Pareja Romántica': 'tu pareja',
        'Visitante Solo': 'solo',
        'Auto-cuidado Solo': 'solo',
        'Visitante Grupal': 'tu grupo',
        'Grupo': 'tu grupo',
        'Familiar': 'tu familia',
    }
    return mapeo.get(eje_contexto, '')


# ============================================================================
# Cálculo de prioridad (1 = más urgente, 6 = menos; 0 = mesa chica VIP)
# ============================================================================

def calcular_prioridad(
    eje_valor: str,
    dias_desde_ultima_visita: Optional[int],
    primera_visita_actual: Optional[date],
    dias_entre_visitas_avg: Optional[float],
    ultimo_contacto_outbound: Optional[date],
    hoy: date,
) -> Optional[int]:
    """Asigna prioridad 0-6 al cliente, o None si no califica para la bandeja.

    Reglas (en orden de evaluación, primera que matchea gana):

        FILTRO PREVIO — días mínimos desde última visita
            Si el cliente vino hace menos del mínimo configurado en
            settings.OVC_DIAS_MINIMO_DESDE_ULTIMA_VISITA[eje_valor], retorna
            None ANTES de evaluar cualquier P. Esto evita que un Campeón con
            visita hace 4 días reciba "te echamos de menos" porque no había
            ultimo_contacto_outbound aún.

            Valores configurados (settings):
                Campeón=45, Leal=60, Regular=30, Gran Gastador Ocasional=45.
                En Riesgo/Dormido/En Prueba/Pre-sistema=0 (las heurísticas
                P1-P3 ya tienen su propio chequeo de inactividad).

        P0  Leal / Campeón          ultimo_contacto_outbound es NULL
                                    o (hoy - ultimo_contacto_outbound).days > 30
                                    → mesa chica, toque mensual

        P1  En Riesgo               días_sin_venir ∈ [95, 105]
                                    → momento óptimo para reactivar

        P2  En Prueba               días_desde_primera_visita ∈
                                    {28-32, 58-62, 78-82}
                                    → momento clave de consolidación

        P3  Dormido                 días_sin_venir ∈ [180, 230]
                                    → ventana ~6-7.5 meses (segunda chance);
                                    ampliada 2026-05-27 para garantizar
                                    volumen diario en bandeja sin entrar a
                                    zonas radicalmente distintas (200 vs 230
                                    días psicológicamente similar)

        P4  Regular atrasado        días_sin_venir > 60 AND
                                    dias_entre_visitas_avg < 45
                                    → cliente regular que está atrasado

        P5  En Riesgo (resto)       cualquier otro 'En Riesgo'

        P6  Dormido (resto)         cualquier otro 'Dormido'

        None — no encaja en ninguna regla anterior
              (clientes Regular dentro de cadencia, Pre-sistema,
              Gran Gastador Ocasional sin atrasos, etc.)
    """
    # ---------- Filtro previo: días mínimos desde última visita ----------
    # Bloquea entrada a bandeja si el cliente vino hace muy poco para su
    # clasificación. Lazy import de settings para mantener el módulo testeable
    # sin Django runtime cuando se importan otros helpers (humanize_*, etc.).
    from django.conf import settings
    dias_minimo_map = getattr(settings, 'OVC_DIAS_MINIMO_DESDE_ULTIMA_VISITA', {})
    dias_minimo = dias_minimo_map.get(eje_valor, 0)
    if dias_minimo > 0:
        # Caso 1: dato presente y dentro del rango bloqueado.
        if dias_desde_ultima_visita is not None and dias_desde_ultima_visita < dias_minimo:
            return None
        # Caso 2: dias_desde_ultima_visita es None pero el segmento (Campeón/Leal/
        # Regular/GG Ocasional) implica historial real. None aquí significa
        # taxonomía stale o race condition (cron taxonomía aún no procesó al
        # cliente). Más seguro saltar al cliente hoy que arriesgar "te echamos
        # de menos" a alguien que vino ayer. Bugfix 2026-05-27: cliente
        # Campeón con visita 10d entró a bandeja porque snapshot fue None.
        if dias_desde_ultima_visita is None and eje_valor in (
            'Campeón', 'Leal', 'Regular', 'Gran Gastador Ocasional',
        ):
            return None

    # ---------- P0: Mesa chica (Leal + Campeón, contacto mensual) ----------
    if eje_valor in ('Leal', 'Campeón'):
        if ultimo_contacto_outbound is None:
            return 0
        if (hoy - ultimo_contacto_outbound).days > 30:
            return 0
        return None  # contactado hace <=30d, esperar siguiente ciclo

    # ---------- P1: En Riesgo en ventana óptima [95-105] ----------
    if eje_valor == 'En Riesgo':
        if dias_desde_ultima_visita is not None and 95 <= dias_desde_ultima_visita <= 105:
            return 1

    # ---------- P2: En Prueba en momentos clave ----------
    if eje_valor == 'En Prueba' and primera_visita_actual is not None:
        d = (hoy - primera_visita_actual).days
        if 28 <= d <= 32 or 58 <= d <= 62 or 78 <= d <= 82:
            return 2

    # ---------- P3: Dormido en ventana segunda chance [180-230] ----------
    if eje_valor == 'Dormido':
        if dias_desde_ultima_visita is not None and 180 <= dias_desde_ultima_visita <= 230:
            return 3

    # ---------- P4: Regular atrasado (avg < 45d, no viene hace >60d) ----------
    if eje_valor == 'Regular':
        if (dias_desde_ultima_visita is not None and dias_desde_ultima_visita > 60
                and dias_entre_visitas_avg is not None and dias_entre_visitas_avg < 45):
            return 4

    # ---------- P5: En Riesgo (resto) ----------
    if eje_valor == 'En Riesgo':
        return 5

    # ---------- P6: Dormido (resto) ----------
    if eje_valor == 'Dormido':
        return 6

    return None


# ============================================================================
# Búsqueda de script en cascada (5 niveles)
# ============================================================================

def buscar_script_cascada(
    scripts_qs, estado_valor: str, estilo: str, contexto: str, salva: int,
    region: str = '',
):
    """Busca el ScriptWhatsApp más específico aplicable a este cliente.

    Cascada extendida (Etapa Geo.3) — la región es la dimensión PRIORITARIA.

    Para un cliente con region=X y resto de parámetros:
        Bloque "región específica" (region=X):
          1. estado + estilo + contexto + salva + region=X
          2. estado + estilo + salva + region=X         (cualquier contexto)
          3. estado + contexto + salva + region=X       (cualquier estilo)
          4. estado + salva + region=X                  (genérico de región)

        Fallback a plantillas region='' (backward-compat):
          - Si region='sur' o region='' (caller no pasó): permitir caer a
            niveles 5-8 con region='' (las 17 plantillas iniciales sirven
            como fallback para sur).
          - Si region='nacional' o region='sin_clasificar': NO permitir
            fallback. Los textos region='' asumen sur y dirían frases tipo
            "esta semana" que suenan desubicadas para Santiago. Mejor
            retornar None y que el caller loguee warning + salte cliente.

        Niveles fallback (solo si se permite):
          5. estado + estilo + contexto + salva + region=''
          6. estado + estilo + salva + region=''
          7. estado + contexto + salva + region=''
          8. estado + salva + region=''                 (genérico universal)

    Args:
        scripts_qs: queryset base de ScriptWhatsApp (caller lo prepara)
        estado_valor: ej. 'En Riesgo', 'Dormido', 'Leal'
        estilo: ej. 'Amante de las Tinas' (vacío = sin estilo específico)
        contexto: ej. 'Visitante Pareja' (vacío = sin contexto específico)
        salva: 1, 2 o 3
        region: 'sur', 'nacional', 'sin_clasificar' o '' (default = '' = sur o no clasificado).
                NUNCA 'extranjero' (esos clientes no llegan acá).

    Returns:
        ScriptWhatsApp instance o None si no hay match aceptable.

    Notas:
        - Backward compatibility total: callers que no pasen `region`
          obtienen el comportamiento original (cascada de 4 niveles sobre
          region='').
        - Para region 'sur' explícito: si no hay específica, cae al fallback
          region='' (los textos actuales sirven).
        - Para region 'nacional' o 'sin_clasificar': si no hay específica,
          retorna None (mejor no enviar que enviar mensaje desubicado).
    """
    base = scripts_qs.filter(
        estado_valor_target=estado_valor,
        salva=salva,
        activo=True,
    )

    def _buscar_en_bloque(region_target: str):
        """4 niveles de cascada dentro de una región fija."""
        bloque = base.filter(region_geografica_target=region_target)
        # Nivel 1: exacto
        s = bloque.filter(cohorte_estilo=estilo, cohorte_contexto=contexto).first()
        if s:
            return s
        # Nivel 2: estilo + cualquier contexto
        s = bloque.filter(cohorte_estilo=estilo, cohorte_contexto='').first()
        if s:
            return s
        # Nivel 3: cualquier estilo + contexto
        s = bloque.filter(cohorte_estilo='', cohorte_contexto=contexto).first()
        if s:
            return s
        # Nivel 4: genérico
        return bloque.filter(cohorte_estilo='', cohorte_contexto='').first()

    # Si caller NO pasó región (compat), comportamiento original sobre region=''
    if not region:
        return _buscar_en_bloque('')

    # Bloque específico de la región solicitada
    s = _buscar_en_bloque(region)
    if s:
        return s

    # Fallback a region='' SOLO para 'sur' — los textos universales sirven
    if region == 'sur':
        return _buscar_en_bloque('')

    # Para 'nacional' / 'sin_clasificar': mejor None que enviar mensaje
    # desubicado. El caller loguea warning y salta el cliente.
    return None


# ============================================================================
# Helpers que SÍ tocan DB (separados para poder testearlos con DB de test)
# ============================================================================

# ─────────────────────────────────────────────────────────────────────
#  Programa Refugio Aremko (Jorge 2026-05-27 PM)
#  ─────────────────────────────────────────────────────────────────
#  Refugio REEMPLAZA la cascada normal cuando el cliente califica:
#      - region in (nacional, sin_clasificar) — NO sur
#      - eje_valor in (En Riesgo, Dormido)
#      - salva == 1 (solo primera oportunidad)
#      - anti-saturación: no recibió Refugio en últimos 60 días
#  Si NO califica → cascada normal sin cambios.
# ─────────────────────────────────────────────────────────────────────

REFUGIO_VENTANA_SATURACION_DIAS = 60
REFUGIO_REGIONES_ELEGIBLES = ('nacional', 'sin_clasificar')
REFUGIO_ESTADOS_ELEGIBLES = ('En Riesgo', 'Dormido')


def califica_refugio(cliente, eje_valor: str, salva: int, hoy=None) -> bool:
    """Decide si este cliente recibe plantilla Refugio en vez de la normal.

    Args:
        cliente: instancia Cliente con region_geografica
        eje_valor: 'En Riesgo' / 'Dormido' / etc. (de ClienteTaxonomia)
        salva: 1, 2 o 3
        hoy: date opcional para tests (default: timezone.now().date())

    Returns:
        True si califica para recibir un B.refugio-*.
    """
    from datetime import date, timedelta
    from django.utils import timezone
    from ventas.models import ContactoWhatsApp

    if cliente.region_geografica not in REFUGIO_REGIONES_ELEGIBLES:
        return False
    if eje_valor not in REFUGIO_ESTADOS_ELEGIBLES:
        return False
    if salva != 1:
        return False

    # Anti-saturación: si recibió un Refugio enviado en los últimos 60 días, skip
    if hoy is None:
        hoy = timezone.now().date()
    desde = hoy - timedelta(days=REFUGIO_VENTANA_SATURACION_DIAS)
    ya_recibio = ContactoWhatsApp.objects.filter(
        cliente_id=cliente.id,
        script__script_id__startswith='B.refugio',
        estado='enviado',
        fecha_envio__date__gte=desde,
    ).exists()
    return not ya_recibio


def buscar_script_refugio(cliente, eje_valor: str):
    """Devuelve el ScriptWhatsApp Refugio según estado + región del cliente.

    Args:
        cliente: instancia Cliente con region_geografica ya validada
        eje_valor: 'En Riesgo' o 'Dormido' (ya validado)

    Returns:
        ScriptWhatsApp o None si no se encuentra la plantilla esperada
        (no debería pasar si la migración 0115 fue aplicada).
    """
    from ventas.models import ScriptWhatsApp

    region_suffix = 'N' if cliente.region_geografica == 'nacional' else 'SC'
    if eje_valor == 'Dormido':
        script_id = f'B.refugio-DOR-{region_suffix}'
    else:  # En Riesgo
        script_id = f'B.refugio-{region_suffix}'
    return ScriptWhatsApp.objects.filter(script_id=script_id, activo=True).first()


def obtener_ultimo_servicio_nombre(cliente_id: int) -> str:
    """Nombre del último servicio reservado por el cliente.

    Devuelve string vacío si no encuentra reservas (cliente Pre-sistema sin
    VentaReserva); el SafeDict lo render como ''.
    """
    from ventas.models import ReservaServicio

    # H-014: el último servicio del mensaje debe ser el PRINCIPAL, nunca un
    # complemento (tina de niño, tina fría, decoración). Excluye la lista de
    # complementos del agente (M2M de whatsapp_agent; sin tocar Servicio).
    from whatsapp_agent.models import WhatsAppAgentConfig
    comp = WhatsAppAgentConfig.get_solo().ids_complementarios()

    rs = (
        ReservaServicio.objects
        .filter(venta_reserva__cliente_id=cliente_id)
        .exclude(servicio_id__in=comp)
        .select_related('servicio')
        .order_by('-fecha_agendamiento', '-id')
        .first()
    )
    if rs and rs.servicio:
        return rs.servicio.nombre or ''
    return ''


def calcular_servicio_recomendado(pct_tinas: float, pct_masajes: float, pct_cabanas: float) -> str:
    """Heurística de recomendación cruzada basada en el mix histórico del cliente.

    Filosofía: invitarle a probar lo que NO ha probado mucho, pero solo si
    realmente ya conoce la casa por otro lado. Si no conoce nada bien,
    mensaje suave y genérico.

    Umbral de "ya probó esta familia": UMBRAL = 20% del gasto histórico.

    Matriz de decisión (en orden de evaluación, primer match gana):

        ┌─────────┬────────┬─────────┬──────────────────────────────────┐
        │ Tinas   │ Masaje │ Cabañas │ Recomendación                    │
        ├─────────┼────────┼─────────┼──────────────────────────────────┤
        │ ≥20%    │ ≥20%   │ <20%    │ 'una cabaña con tina privada'    │
        │ ≥20%    │ <20%   │ -       │ 'un masaje relajante'            │
        │ <20%    │ ≥20%   │ -       │ 'una tina caliente con vista'    │
        │ -       │ -      │ ≥20%    │ 'un día spa completo'            │
        │ <20%    │ <20%   │ <20%    │ 'una experiencia nueva'          │
        └─────────┴────────┴─────────┴──────────────────────────────────┘

    Los % vienen de ClienteTaxonomia (calculados por recalcular_taxonomia_clientes).

    Si en producción vemos que la recomendación queda fea para algún caso
    específico (ej: alguien con 19% en tinas que técnicamente "ya probó"),
    bajamos UMBRAL a 15% o agregamos casos.
    """
    UMBRAL = 0.20  # 20% mínimo para considerar "ya probó"

    probo_tinas = pct_tinas >= UMBRAL
    probo_masaje = pct_masajes >= UMBRAL
    probo_cabana = pct_cabanas >= UMBRAL

    if probo_tinas and probo_masaje and not probo_cabana:
        return 'una cabaña con tina privada'
    if probo_tinas and not probo_masaje:
        return 'un masaje relajante'
    if probo_masaje and not probo_tinas:
        return 'una tina caliente con vista'
    if probo_cabana and not (probo_tinas and probo_masaje):
        # vino a cabaña pero no exploró todo
        return 'un día spa completo'
    return 'una experiencia nueva'


def calcular_sugerencia_dia_hora(cliente_id: int) -> Tuple[str, str, bool]:
    """Devuelve (día_semana_es, hora_HH:MM, es_patron_real).

    es_patron_real = True  → el patrón viene de ≥2 reservas históricas del cliente
                            → el render puede decir "el viernes a las 17:00"
    es_patron_real = False → cliente con <2 reservas, no hay señal real
                            → el render usa lenguaje suave ("un día de semana en la tarde")
                              para NO inventar precisiones falsas.

    Devolvemos los strings default igual que antes para compatibilidad
    retroactiva con cualquier caller que ignore el flag, pero los nuevos
    callers (build_render_context) consultan es_patron_real y eligen la
    frase apropiada.
    """
    from ventas.models import ReservaServicio

    reservas = list(
        ReservaServicio.objects
        .filter(venta_reserva__cliente_id=cliente_id)
        .values_list('fecha_agendamiento', 'hora_inicio')
    )

    if len(reservas) < 2:
        return ('viernes', '17:00', False)

    dias_counter: Counter = Counter()
    horas_counter: Counter = Counter()
    for fecha, hora in reservas:
        if fecha is not None:
            dias_counter[fecha.weekday()] += 1
        if hora:
            horas_counter[hora] += 1

    # Tomar el más frecuente con tie-breaker estable
    if dias_counter:
        dia_idx = max(dias_counter.items(), key=lambda kv: (kv[1], -kv[0]))[0]
        dia_str = DIAS_ES[dia_idx]
    else:
        dia_str = 'viernes'

    if horas_counter:
        hora_str = max(horas_counter.items(), key=lambda kv: kv[1])[0]
    else:
        hora_str = '17:00'

    return (dia_str, hora_str, True)


# ============================================================================
# Cupón determinístico para tracking de atribución
# ============================================================================

def generar_cupon_codigo(cliente_id: int) -> str:
    """Genera un código de cupón determinístico por cliente: 'VUELVE-XXXX'.

    Determinístico = mismo cliente siempre obtiene el mismo código. Esto
    permite:
      - Detectar cuándo un cliente menciona "el código" en su respuesta
      - Atribuir conversiones sin necesidad de un sistema de cupones real
      - Cuando construyamos cupones reales más adelante, el código ya existe
        y solo hay que registrarlo en la tabla de cupones (no romper códigos
        ya circulando entre clientes).

    Usamos MD5 (rápido, no crypto-sensitive) y tomamos los primeros 4
    caracteres hex (16⁴ = 65.536 combinaciones). Con 14K clientes,
    probabilidad de colisión ~1.5% por pares — aceptable para tracking
    informal (un cupón duplicado no rompe nada, solo crea ambigüedad rara
    de atribución entre 2 clientes simultáneos).
    """
    hash_corto = hashlib.md5(f"{cliente_id}".encode()).hexdigest()[:4].upper()
    return f"VUELVE-{hash_corto}"


def fecha_limite_natural(hoy: date, dias_validez: int = 15) -> str:
    """Devuelve fecha límite en formato natural en español: '8 de junio'.

    Default 15 días = urgencia razonable sin presionar (más corto que un mes
    típico de promoción, lo suficiente para sentir que es "esta semana o la
    próxima"). Si en logs vemos que 15 días no convierte mejor que 30,
    ajustamos.
    """
    fecha = hoy + timedelta(days=dias_validez)
    return f"{fecha.day} de {MESES_ES[fecha.month]}"


# ============================================================================
# Contexto de renderizado completo
# ============================================================================

def build_render_context(cliente, cliente_tax, hoy: date) -> SafeDict:
    """Construye el dict de variables para inyectar en plantilla_texto.

    Args:
        cliente: instancia de Cliente
        cliente_tax: instancia de ClienteTaxonomia (puede ser None para Pre-sistema)
        hoy: fecha de referencia (inyectada para testabilidad)

    Returns:
        SafeDict con todas las keys que pueden aparecer en plantillas.
        Las keys que no se pudieron calcular quedan en '' (SafeDict las render como '').

    Keys producidas:
        nombre, ultima_visita_humanizada, dias_sin_venir, ultimo_servicio,
        compania_habitual, servicio_recomendado,
        sugerencia_dia, sugerencia_hora, sugerencia_franja,
        cupon_codigo, mes_proximo, fecha_limite

    Sobre los placeholders de día/hora:
        - Cuando el cliente tiene >=2 reservas (patrón real):
            sugerencia_dia    = "viernes"
            sugerencia_hora   = "17:00"
            sugerencia_franja = "el viernes a las 17:00"
        - Cuando no hay patrón (cliente Pre-sistema o 1 sola reserva):
            sugerencia_dia    = "días de semana"
            sugerencia_hora   = "en la tarde"
            sugerencia_franja = "un día de semana en la tarde"
        Esto evita inventar precisiones falsas. Las plantillas viejas que
        usan {sugerencia_dia} y {sugerencia_hora} por separado siguen
        funcionando, y las plantillas nuevas pueden usar {sugerencia_franja}
        para garantizar gramática limpia.
    """
    nombre = (cliente.nombre or '').strip().split(' ')[0] or 'amigo/a'

    if cliente_tax is None:
        # Cliente Pre-sistema, sin features → defaults seguros sin invenciones
        return SafeDict(
            nombre=nombre,
            ultima_visita_humanizada='hace un buen rato',
            dias_sin_venir='',
            ultimo_servicio='',
            compania_habitual='',
            servicio_recomendado='nuestros servicios',
            sugerencia_dia='días de semana',
            sugerencia_hora='en la tarde',
            sugerencia_franja='un día de semana en la tarde',
            cupon_codigo=generar_cupon_codigo(cliente.id),
            mes_proximo=mes_proximo_nombre(hoy),
            fecha_limite=fecha_limite_natural(hoy),
        )

    dia, hora, es_patron_real = calcular_sugerencia_dia_hora(cliente.id)
    if es_patron_real:
        sugerencia_dia_val = dia
        sugerencia_hora_val = hora
        sugerencia_franja_val = f"el {dia} a las {hora}"
    else:
        sugerencia_dia_val = 'días de semana'
        sugerencia_hora_val = 'en la tarde'
        sugerencia_franja_val = 'un día de semana en la tarde'

    servicio_rec = calcular_servicio_recomendado(
        cliente_tax.pct_tinas or 0.0,
        cliente_tax.pct_masajes or 0.0,
        cliente_tax.pct_cabanas or 0.0,
    )

    return SafeDict(
        nombre=nombre,
        ultima_visita_humanizada=humanize_ultima_visita(cliente_tax.ultima_visita, hoy),
        dias_sin_venir=(
            str(cliente_tax.dias_desde_ultima_visita)
            if cliente_tax.dias_desde_ultima_visita is not None else ''
        ),
        ultimo_servicio=obtener_ultimo_servicio_nombre(cliente.id),
        compania_habitual=compania_habitual(cliente_tax.eje_contexto),
        servicio_recomendado=servicio_rec,
        sugerencia_dia=sugerencia_dia_val,
        sugerencia_hora=sugerencia_hora_val,
        sugerencia_franja=sugerencia_franja_val,
        cupon_codigo=generar_cupon_codigo(cliente.id),
        mes_proximo=mes_proximo_nombre(hoy),
        fecha_limite=fecha_limite_natural(hoy),
    )
