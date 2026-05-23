"""
taxonomia_movimientos_service
=============================

Lógica de soporte para registrar movimientos de taxonomía (Bitácora Viva)
y disparar celebraciones cuando un cliente da un salto positivo notable.

Operación Vuelta a Casa, Etapa 5 — *sin tocar todavía el cron productivo*.

Etapa 5.1 (este commit): detectar_cambios + utilidades de normalización.
Etapa 5.2 (siguiente commit): generar_movimientos_y_celebraciones +
                              detectar_celebraciones + mensajes.
Etapa 5.3 (después del deploy validado): integración en
                              recalcular_taxonomia_clientes detrás de un
                              flag opt-in --registrar-movimientos.

Funciones puras (sin DB), testeable sin runner pesado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, List, Optional, Tuple


# ============================================================================
# Modelo de datos: un cambio detectado en un eje específico
# ============================================================================

@dataclass(frozen=True)
class Cambio:
    """Un cambio detectado entre dos snapshots de taxonomía.

    Attributes:
        eje: nombre del eje afectado: 'valor', 'estilo' o 'contexto'
        valor_antes: string del valor previo (puede ser '' para cliente nuevo)
        valor_despues: string del valor nuevo

    frozen=True → hashable, permite usar Cambio en sets/dicts si se necesita.
    """
    eje: str
    valor_antes: str
    valor_despues: str

    def __str__(self) -> str:
        antes_repr = self.valor_antes or '(sin clasificar)'
        return f"{self.eje}: {antes_repr} → {self.valor_despues}"


# Los 3 ejes que la taxonomía rastrea. Orden importa solo para
# determinismo de iteración en detectar_cambios y tests.
EJES = ('valor', 'estilo', 'contexto')


# ============================================================================
# Normalización: aceptamos dict, ClienteTaxonomia instance, o None
# ============================================================================

def taxonomia_a_dict(taxo: Any) -> dict:
    """Normaliza distintos formatos de taxonomía a un dict de 3 keys.

    Acepta:
      - None (cliente sin taxonomía previa) → {'eje_valor': '', ...}
      - dict con keys eje_valor/eje_estilo/eje_contexto
      - instancia con esos atributos (ClienteTaxonomia, mock, etc.)

    Devuelve dict con exactamente:
        {'eje_valor': str, 'eje_estilo': str, 'eje_contexto': str}

    Garantiza strings no-None (convierte None a '').
    """
    if taxo is None:
        return {'eje_valor': '', 'eje_estilo': '', 'eje_contexto': ''}

    if isinstance(taxo, dict):
        return {
            'eje_valor': str(taxo.get('eje_valor', '') or ''),
            'eje_estilo': str(taxo.get('eje_estilo', '') or ''),
            'eje_contexto': str(taxo.get('eje_contexto', '') or ''),
        }

    # Asumir objeto con atributos (ClienteTaxonomia instance, mock, etc.)
    return {
        'eje_valor': str(getattr(taxo, 'eje_valor', '') or ''),
        'eje_estilo': str(getattr(taxo, 'eje_estilo', '') or ''),
        'eje_contexto': str(getattr(taxo, 'eje_contexto', '') or ''),
    }


# ============================================================================
# Detección de cambios
# ============================================================================

def detectar_cambios(taxo_anterior: Any, taxo_nuevo: Any) -> List[Cambio]:
    """Compara dos snapshots de taxonomía y devuelve los cambios por eje.

    Args:
        taxo_anterior: estado previo del cliente (None / dict / modelo)
        taxo_nuevo:    estado nuevo del cliente (None / dict / modelo)

    Returns:
        Lista de Cambio (puede ser vacía si no hay diferencias).
        Si taxo_anterior es None y taxo_nuevo tiene valores, devuelve un
        Cambio por cada eje con valor_antes='' (cliente recién clasificado).

    No tiene side effects — pura comparación.

    Edge cases:
      - Ambos None → []
      - Mismos valores en todos los ejes → []
      - Un eje cambia → [1 Cambio]
      - Los 3 ejes cambian → [3 Cambios] (en orden EJES)
      - taxo_nuevo tiene valor None en un eje → trata como ''
    """
    antes = taxonomia_a_dict(taxo_anterior)
    nuevo = taxonomia_a_dict(taxo_nuevo)

    cambios: List[Cambio] = []
    for eje in EJES:
        key = f'eje_{eje}'
        v_antes = antes[key]
        v_despues = nuevo[key]
        if v_antes != v_despues:
            cambios.append(Cambio(
                eje=eje,
                valor_antes=v_antes,
                valor_despues=v_despues,
            ))
    return cambios


# ============================================================================
# Detección de celebraciones (Etapa 5.2)
# ============================================================================

# Valores de eje_valor considerados "mejoras" respecto a Dormido
# (cualquier tramo que represente actividad/relación viva con la marca).
VALORES_MEJORA_DESDE_DORMIDO = {
    'En Prueba', 'Regular', 'Gran Gastador Ocasional', 'Leal', 'Campeón',
}

# Estilos que indican que el cliente "se enganchó" con una experiencia
# concreta (dejó de ser probador esporádico).
ESTILOS_DEVOTO = {
    'Devoto del Masaje',
    'Amante de las Tinas',
    'Experiencia Completa',
    'Buscador de Alojamiento',
}

# Contextos de "venir solo".
CONTEXTOS_SOLO = {'Visitante Solo', 'Auto-cuidado Solo'}

# Contextos de "venir acompañado".
CONTEXTOS_ACOMPANADO = {
    'Visitante Pareja', 'Pareja Romántica',
    'Visitante Grupal', 'Grupo',
    'Familiar',
}


def detectar_celebraciones(taxo_anterior: Any, taxo_nuevo: Any) -> List[str]:
    """Detecta qué tipos de celebración aplican al cambio de taxonomía.

    A diferencia del helper original del brief (que devolvía 1 sola
    celebración con `return`), acá devolvemos **lista** porque un mismo
    movimiento puede disparar varias: ej. un cliente que pasa de
    Dormido a Leal cumple `recuperado_dormido` Y `subio_a_leal`.

    Tipos posibles (coinciden con EventoCelebracion.TIPO_CHOICES):
        - 'recuperado_dormido'
        - 'consolidacion_regular'
        - 'migracion_devoto'
        - 'trajo_acompanante'
        - 'subio_a_leal'
        - 'subio_a_campeon'

    Returns lista vacía si:
        - No hubo cambios relevantes
        - El cliente estaba sin clasificar previamente (antes='' o
          'Pre-sistema') — las celebraciones son "mejoras desde un estado
          conocido", no creaciones iniciales
    """
    antes = taxonomia_a_dict(taxo_anterior)
    nuevo = taxonomia_a_dict(taxo_nuevo)
    out: List[str] = []

    v_antes, v_despues = antes['eje_valor'], nuevo['eje_valor']
    s_antes, s_despues = antes['eje_estilo'], nuevo['eje_estilo']
    c_antes, c_despues = antes['eje_contexto'], nuevo['eje_contexto']

    # ── recuperado_dormido: Dormido → cualquier mejora ──
    if v_antes == 'Dormido' and v_despues in VALORES_MEJORA_DESDE_DORMIDO:
        out.append('recuperado_dormido')

    # ── consolidacion_regular: En Prueba → Regular ──
    if v_antes == 'En Prueba' and v_despues == 'Regular':
        out.append('consolidacion_regular')

    # ── migracion_devoto: Probador Esporádico → devoto/amante/buscador ──
    if s_antes == 'Probador Esporádico' and s_despues in ESTILOS_DEVOTO:
        out.append('migracion_devoto')

    # ── trajo_acompanante: solo → acompañado ──
    if c_antes in CONTEXTOS_SOLO and c_despues in CONTEXTOS_ACOMPANADO:
        out.append('trajo_acompanante')

    # ── subio_a_leal: Regular o GG Ocasional → Leal ──
    if v_antes in ('Regular', 'Gran Gastador Ocasional') and v_despues == 'Leal':
        out.append('subio_a_leal')

    # ── subio_a_campeon: Leal → Campeón ──
    if v_antes == 'Leal' and v_despues == 'Campeón':
        out.append('subio_a_campeon')

    return out


# ============================================================================
# Mensajes sugeridos para cada tipo de celebración
# ============================================================================
# Templates DEFAULT — el operador puede editar antes de enviar (la
# bandeja los muestra como "mensaje_sugerido", no como obligatorio).
# Si Jorge quiere editar estos templates sin tocar código en el futuro,
# se puede mover a un modelo CelebracionTemplate como ScriptWhatsApp.

CELEBRACION_TEMPLATES = {
    'recuperado_dormido':
        "¡Qué bueno tenerte de vuelta, {nombre}! Te extrañábamos por Aremko.",
    'consolidacion_regular':
        "¡{nombre}! Ya eres parte de la familia regular de Aremko, "
        "gracias por la confianza.",
    'migracion_devoto':
        "¡{nombre}! Nos encanta ver que estás explorando más experiencias "
        "con nosotros.",
    'trajo_acompanante':
        "¡{nombre}! Qué lindo que nos trajiste compañía — siempre es bueno "
        "compartir momentos.",
    'subio_a_leal':
        "¡{nombre}! Te subiste a nuestra mesa chica — un placer cuidarte "
        "cada visita.",
    'subio_a_campeon':
        "¡{nombre}! Eres un campeón — gracias por hacer de Aremko parte "
        "de tu vida.",
}


def generar_mensaje_celebracion(tipo: str, nombre: str) -> str:
    """Renderiza el template de celebración con el primer nombre del cliente.

    Si tipo no existe en CELEBRACION_TEMPLATES, devuelve string vacío
    (no crashea — caller decide si registrar igual o no).
    """
    template = CELEBRACION_TEMPLATES.get(tipo, '')
    if not template:
        return ''
    nombre_corto = ((nombre or '').strip().split(' ') or ['amigo/a'])[0] or 'amigo/a'
    return template.format(nombre=nombre_corto)


# ============================================================================
# Atribución a contacto WhatsApp previo
# ============================================================================

def _buscar_contacto_whatsapp_atribuible(cliente_id: int, hoy: Optional[date] = None):
    """Devuelve el último ContactoWhatsApp enviado al cliente en los
    últimos 30 días que aún NO tenga convirtio=True, o None.

    Diseño: solo nos importa atribuir UNA vez por contacto, así que
    excluimos los que ya convirtieron previamente (otra reserva los marcó).

    El cron nocturno `cruzar_reservas_contactos_whatsapp` (Etapa 6) usa
    una variante distinta de esta lógica enfocada en reservas concretas.
    Esta función es para atribuir MOVIMIENTOS DE TAXONOMÍA al WhatsApp
    que pudo haber gatillado el reactivar.
    """
    from django.utils import timezone

    from ventas.models import ContactoWhatsApp

    if hoy is None:
        hoy = timezone.now().date()

    corte = hoy - timedelta(days=30)
    return (
        ContactoWhatsApp.objects
        .filter(
            cliente_id=cliente_id,
            estado='enviado',
            fecha_envio__date__gte=corte,
            convirtio=False,
        )
        .order_by('-fecha_envio')
        .first()
    )


# ============================================================================
# Orquestador: genera movimiento + celebraciones
# ============================================================================

def generar_movimientos_y_celebraciones(
    cliente,
    taxo_anterior: Any,
    taxo_nuevo: Any,
    evento_origen: str,
    reserva_relacionada=None,
    hoy: Optional[date] = None,
) -> Tuple[Optional[Any], List[Any]]:
    """Persiste TaxonomiaMovimiento + EventoCelebracion si corresponde.

    Args:
        cliente: instancia de Cliente (necesaria para FK + nombre en mensajes)
        taxo_anterior: snapshot previo (None / dict / ClienteTaxonomia)
        taxo_nuevo: snapshot nuevo (idem)
        evento_origen: uno de TaxonomiaMovimiento.EVENTO_ORIGEN_CHOICES:
            'reserva' | 'paso_tiempo' | 'recalculo_features' | 'manual'
        reserva_relacionada: instancia de VentaReserva (opcional, solo si
            evento_origen='reserva')
        hoy: fecha de referencia (default = today, inyectable para testing)

    Returns:
        (movimiento, [celebraciones])
        - movimiento es la fila TaxonomiaMovimiento creada, o None si no
          hubo cambios.
        - celebraciones es la lista de filas EventoCelebracion creadas
          (puede ser vacía si no aplican).

    Side effects:
        - Crea 1 fila en TaxonomiaMovimiento (si hubo cambios)
        - Crea 0..N filas en EventoCelebracion
        - Busca contacto_whatsapp_atribuido para enlazar con el movimiento
          (la atribución a movimiento NO marca convirtio=True en el
          contacto — eso es responsabilidad del cron Etapa 6 cuando hay
          una RESERVA concreta. Acá solo enlazamos para reportes).

    Idempotencia: si llamas dos veces seguidas con los mismos snapshots,
        crearás 2 filas. La idempotencia es responsabilidad del caller
        (recalcular_taxonomia_clientes ya garantiza 1 corrida por cliente
        por ejecución).
    """
    from django.utils import timezone

    from ventas.models import EventoCelebracion, TaxonomiaMovimiento

    cambios = detectar_cambios(taxo_anterior, taxo_nuevo)
    if not cambios:
        return None, []

    if hoy is None:
        hoy = timezone.now().date()

    antes_dict = taxonomia_a_dict(taxo_anterior)
    nuevo_dict = taxonomia_a_dict(taxo_nuevo)

    contacto_atribuido = _buscar_contacto_whatsapp_atribuible(cliente.id, hoy)

    movimiento = TaxonomiaMovimiento.objects.create(
        cliente=cliente,
        fecha=hoy,
        eje_valor_antes=antes_dict['eje_valor'],
        eje_estilo_antes=antes_dict['eje_estilo'],
        eje_contexto_antes=antes_dict['eje_contexto'],
        eje_valor_despues=nuevo_dict['eje_valor'],
        eje_estilo_despues=nuevo_dict['eje_estilo'],
        eje_contexto_despues=nuevo_dict['eje_contexto'],
        evento_origen=evento_origen,
        reserva_relacionada=reserva_relacionada,
        contacto_whatsapp_atribuido=contacto_atribuido,
    )

    tipos_celebracion = detectar_celebraciones(taxo_anterior, taxo_nuevo)
    eventos: List[Any] = []
    for tipo in tipos_celebracion:
        evt = EventoCelebracion.objects.create(
            cliente=cliente,
            tipo=tipo,
            fecha=hoy,
            movimiento_relacionado=movimiento,
            mensaje_sugerido=generar_mensaje_celebracion(tipo, cliente.nombre),
        )
        eventos.append(evt)

    return movimiento, eventos
