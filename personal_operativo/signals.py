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

# Áreas cuyas tareas se avisan al recepcionista de turno. "Todas al comienzo"
# (Recepción + Operación); más adelante se puede filtrar.
_SWIMLANES_AVISO = {'RX', 'OPS'}  # Recepción, Operación


@receiver(post_save, sender='control_gestion.Task', dispatch_uid='luna_interna_aviso_tarea')
def avisar_tarea_creada(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        swim = getattr(instance, 'swimlane', '') or ''
        if swim not in _SWIMLANES_AVISO:
            return
        from .services import receptores_avisos_operacion, texto_alerta_tarea, encolar_notificacion
        receptores = receptores_avisos_operacion()
        if not receptores:
            return
        texto = texto_alerta_tarea(instance)
        for persona in receptores:
            if not persona.telefono:
                continue
            encolar_notificacion(
                telefono=persona.telefono,
                texto=texto,
                dedup_key=f'task_creada:{instance.pk}:{persona.pk}',
                origen='task_creada',
                ref_tipo='task',
                ref_id=instance.pk,
            )
    except Exception:  # noqa: BLE001 — jamás romper la creación de la tarea
        logger.exception('Luna Interna: fallo encolando aviso de tarea %s', getattr(instance, 'pk', '?'))
