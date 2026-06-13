"""Propaga el comentario de la VentaReserva al campo notas_generales de sus
comandas, dentro de un bloque delimitado idempotente que preserva el resto de
las notas. Parte de la funcionalidad "comentario de reserva → agenda + comanda"
(jun 2026): el operativo ve las instrucciones de la reserva también al preparar
la comanda de productos.

Diseño defensivo:
- Usa Comanda.objects.update() (NO instance.save()) para escribir, así NO vuelve
  a disparar el post_save de Comanda → cero recursión.
- El receiver de VentaReserva va envuelto en try/except: nunca puede romper el
  guardado de una reserva (ese save path es sensible).
"""

import logging
import re

from django.db.models.signals import post_save
from django.dispatch import receiver

from ..models import VentaReserva, Comanda

logger = logging.getLogger(__name__)

_MARCA_INI = "── Comentario de la reserva ──"
_MARCA_FIN = "──────────────────────────────"
_BLOQUE_RE = re.compile(
    re.escape(_MARCA_INI) + r".*?" + re.escape(_MARCA_FIN) + r"\n?",
    re.DOTALL,
)


def _notas_con_comentario(notas_actuales, comentario):
    """notas_generales con el bloque del comentario al inicio (o sin él si el
    comentario está vacío), preservando el resto del texto. Idempotente:
    primero quita el bloque previo y lo vuelve a poner actualizado."""
    base = _BLOQUE_RE.sub("", notas_actuales or "").lstrip("\n")
    comentario = (comentario or "").strip()
    if not comentario:
        return base
    bloque = f"{_MARCA_INI}\n{comentario}\n{_MARCA_FIN}\n"
    return bloque + base


def sincronizar_comanda(comanda):
    """Deja el comentario de la reserva al inicio de notas_generales de la comanda.
    No escribe si no hay cambios (evita writes innecesarios)."""
    reserva = comanda.venta_reserva if comanda.venta_reserva_id else None
    comentario = reserva.comentarios if reserva else ""
    nuevas = _notas_con_comentario(comanda.notas_generales, comentario)
    if nuevas != (comanda.notas_generales or ""):
        # update() en vez de save(): no dispara post_save → sin recursión.
        Comanda.objects.filter(pk=comanda.pk).update(notas_generales=nuevas)


@receiver(post_save, sender=Comanda, dispatch_uid="comanda_hereda_comentario_reserva")
def comanda_hereda_comentario(sender, instance, **kwargs):
    """Al crear/guardar una comanda, hereda el comentario vigente de su reserva."""
    try:
        sincronizar_comanda(instance)
    except Exception:
        logger.warning("No se pudo sincronizar comentario en comanda %s",
                       getattr(instance, "pk", "?"), exc_info=True)


@receiver(post_save, sender=VentaReserva, dispatch_uid="reserva_propaga_comentario_comandas")
def reserva_propaga_comentario_a_comandas(sender, instance, **kwargs):
    """Si se edita el comentario de la reserva, lo refleja en sus comandas.
    Nunca propaga una excepción (no debe romper el guardado de la reserva)."""
    try:
        for comanda in instance.comandas.all():
            sincronizar_comanda(comanda)
    except Exception:
        logger.warning("No se pudo propagar comentario de reserva %s a sus comandas",
                       getattr(instance, "pk", "?"), exc_info=True)
