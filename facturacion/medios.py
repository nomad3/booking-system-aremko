"""
Qué medios de pago se ofrecen al cobrar en el admin.

Jorge (2026-08-15): la lista de `Pago.METODOS_PAGO` acumuló 22 opciones —
cuentas personales, medios que ya no se usan— y elegir se volvió incómodo.
Ocultarlos NO es borrarlos: los pagos históricos conservan su medio y se siguen
mostrando; solo desaparecen del selector para cobros nuevos.

El switch vive en MedioPago.visible_al_cobrar (admin → «Medios de pago
(boleteo)»), así que se ajusta sin deploy.

Ante cualquier duda el sistema MUESTRA TODO: tabla sin sembrar, todos los
medios apagados, o la columna aún inexistente durante un deploy. Un selector de
cobro vacío deja a Aremko sin poder registrar pagos; una opción de más no le
hace daño a nadie.
"""
import logging

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save

logger = logging.getLogger(__name__)

CACHE_KEY = 'facturacion:medios_pago_visibles'
CACHE_TTL = 300  # segundos; el signal invalida antes si Jorge cambia una casilla
TODOS = '*'      # sentinela: no filtrar


def _leer_codigos_visibles():
    from facturacion.models import MedioPago
    try:
        if not MedioPago.objects.exists():
            return TODOS  # tabla sin sembrar (falta `sembrar_medios_pago`)
        codigos = list(
            MedioPago.objects
            .filter(visible_al_cobrar=True)
            .values_list('codigo', flat=True)
        )
        return codigos or TODOS  # nadie visible = configuración imposible de usar
    except Exception as exc:  # columna inexistente a mitad de deploy, BD caída…
        logger.warning("No se pudo leer MedioPago.visible_al_cobrar (%s); se muestran todos", exc)
        return TODOS


def codigos_visibles_al_cobrar():
    """Set de códigos ofrecibles, o None si no hay que filtrar."""
    valor = cache.get(CACHE_KEY)
    if valor is None:
        valor = _leer_codigos_visibles()
        cache.set(CACHE_KEY, valor, CACHE_TTL)
    return None if valor == TODOS else set(valor)


def filtrar_choices_pago(choices, valor_actual=None):
    """Deja solo los medios visibles, más `valor_actual`.

    `valor_actual` es el medio que ese pago YA tiene guardado: sin él, abrir un
    pago antiguo hecho por Mach Jorge lo mostraría en blanco y bastaría un
    'Guardar' distraído para perder el dato.
    """
    visibles = codigos_visibles_al_cobrar()
    choices = list(choices)
    if visibles is None:
        return choices
    return [
        (codigo, etiqueta) for codigo, etiqueta in choices
        if not codigo or codigo in visibles or codigo == valor_actual
    ]


def _invalidar_cache(sender, **kwargs):
    cache.delete(CACHE_KEY)


def conectar_signals():
    """Llamado desde FacturacionConfig.ready(): que un cambio en el admin se
    note al tiro y no en 5 minutos."""
    from facturacion.models import MedioPago
    post_save.connect(_invalidar_cache, sender=MedioPago, dispatch_uid='medios_pago_cache')
    post_delete.connect(_invalidar_cache, sender=MedioPago, dispatch_uid='medios_pago_cache')
