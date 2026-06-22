# -*- coding: utf-8 -*-
"""Luna Interna · Fase 2: cuando control_gestion crea una tarea de Recepción u
Operación, encola un aviso por WhatsApp al recepcionista de turno.

No toca control_gestion: escucha su post_save por referencia string. El envío
real lo hace aremko-cli drenando la cola NotificacionStaff.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Áreas cuyas tareas se avisan al recepcionista de turno (Recepción + Operación).
_SWIMLANES_AVISO = {'RX', 'OPS'}  # Recepción, Operación

# Líneas que NO se preparan (descuentos/ajustes/administrativas) → no se avisan.
# Como tipo_servicio solo distingue tina/masaje/cabaña/otro (desayuno y descuento
# son ambos "otro"), filtramos por nombre. Decisión de Jorge: "todo menos
# descuentos/admin". Agregar patrones acá si aparece más ruido.
_PATRONES_NO_PREPARABLES = ('descuento', 'ajuste', 'gift card', 'giftcard')


def _aviso_relevante(task):
    """False si la tarea es una línea no preparable (descuento/ajuste) → no se avisa."""
    import unicodedata
    t = unicodedata.normalize('NFKD', (getattr(task, 'title', '') or '').lower())
    t = t.encode('ascii', 'ignore').decode()
    return not any(p in t for p in _PATRONES_NO_PREPARABLES)


@receiver(post_save, sender='control_gestion.Task', dispatch_uid='luna_interna_aviso_tarea')
def avisar_tarea_creada(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        swim = getattr(instance, 'swimlane', '') or ''
        if swim not in _SWIMLANES_AVISO:
            return
        if not _aviso_relevante(instance):
            return
        from .services import receptores_avisos_operacion, texto_alerta_tarea, encolar_notificacion
        receptores = receptores_avisos_operacion()
        if not receptores:
            return
        texto = texto_alerta_tarea(instance)
        # Dedup por CONTENIDO (no por id de tarea): si control_gestion crea dos
        # tareas con el mismo título (ej. "Desayuno Tepa" repetido), sale un solo
        # aviso. El título ya incluye servicio + reserva, así que es estable.
        import hashlib
        clave = hashlib.md5(
            (getattr(instance, 'title', '') or str(instance.pk)).strip().lower().encode('utf-8')
        ).hexdigest()[:16]
        for persona in receptores:
            if not persona.telefono:
                continue
            encolar_notificacion(
                telefono=persona.telefono,
                texto=texto,
                dedup_key=f'aviso:{persona.pk}:{clave}',
                origen='task_creada',
                ref_tipo='task',
                ref_id=instance.pk,
            )
    except Exception:  # noqa: BLE001 — jamás romper la creación de la tarea
        logger.exception('Luna Interna: fallo encolando aviso de tarea %s', getattr(instance, 'pk', '?'))
