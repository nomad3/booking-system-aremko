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

        P0  Leal / Campeón          ultimo_contacto_outbound es NULL
                                    o (hoy - ultimo_contacto_outbound).days > 30
                                    → mesa chica, toque mensual

        P1  En Riesgo               días_sin_venir ∈ [95, 105]
                                    → momento óptimo para reactivar

        P2  En Prueba               días_desde_primera_visita ∈
                                    {28-32, 58-62, 78-82}
                                    → momento clave de consolidación

        P3  Dormido                 días_sin_venir ∈ [195, 210]
                                    → ventana 6-7 meses (segunda chance)

        P4  Regular atrasado        días_sin_venir > 60 AND
                                    dias_entre_visitas_avg < 45
                                    → cliente regular que está atrasado

        P5  En Riesgo (resto)       cualquier otro 'En Riesgo'

        P6  Dormido (resto)         cualquier otro 'Dormido'

        None — no encaja en ninguna regla anterior
              (clientes Regular dentro de cadencia, Pre-sistema,
              Gran Gastador Ocasional sin atrasos, etc.)
    """
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

    # ---------- P3: Dormido en ventana segunda chance [195-210] ----------
    if eje_valor == 'Dormido':
        if dias_desde_ultima_visita is not None and 195 <= dias_desde_ultima_visita <= 210:
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

def buscar_script_cascada(scripts_qs, estado_valor: str, estilo: str, contexto: str, salva: int):
    """Busca el ScriptWhatsApp más específico aplicable a este cliente.

    Cascada (gana la primera que matchea):
        1. exacto:    estado_valor + estilo + contexto + salva
        2. parcial:   estado_valor + estilo + (contexto vacío) + salva
        3. parcial:   estado_valor + (estilo vacío) + contexto + salva
        4. genérico:  estado_valor + (estilo vacío) + (contexto vacío) + salva
        5. None — sin match, el caller debe loguear warning y saltar

    Notas:
        - scripts_qs debe ser un queryset filtrado por activo=True y la salva
          correspondiente (el caller lo prepara). Recibimos el queryset para
          poder testear con mocks/in-memory en los tests sin tocar DB.
        - El orden de evaluación es importante: si hay un script específico
          (nivel 1) Y un genérico (nivel 4) para el mismo target, gana el 1.
    """
    base = scripts_qs.filter(
        estado_valor_target=estado_valor,
        salva=salva,
        activo=True,
    )

    # Nivel 1: match exacto
    s = base.filter(cohorte_estilo=estilo, cohorte_contexto=contexto).first()
    if s:
        return s

    # Nivel 2: estilo + cualquier contexto
    s = base.filter(cohorte_estilo=estilo, cohorte_contexto='').first()
    if s:
        return s

    # Nivel 3: cualquier estilo + contexto
    s = base.filter(cohorte_estilo='', cohorte_contexto=contexto).first()
    if s:
        return s

    # Nivel 4: genérico (cualquier estilo + cualquier contexto)
    s = base.filter(cohorte_estilo='', cohorte_contexto='').first()
    return s  # puede ser None


# ============================================================================
# Helpers que SÍ tocan DB (separados para poder testearlos con DB de test)
# ============================================================================

def obtener_ultimo_servicio_nombre(cliente_id: int) -> str:
    """Nombre del último servicio reservado por el cliente.

    Devuelve string vacío si no encuentra reservas (cliente Pre-sistema sin
    VentaReserva); el SafeDict lo render como ''.
    """
    from ventas.models import ReservaServicio

    rs = (
        ReservaServicio.objects
        .filter(venta_reserva__cliente_id=cliente_id)
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
