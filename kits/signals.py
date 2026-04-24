"""Signals que descuentan/restauran componentes de kits automáticamente.

Hooks sobre ventas.ReservaProducto:
- post_save (created=True): si el producto vendido es un Kit activo con
  descuento_auto, reducir inventario de cada componente.
- post_save (update, cantidad cambió): ajustar delta proporcional.
- post_delete: restaurar inventario de componentes.

El signal existente de ventas (actualizar_inventario en
ventas/signals/main_signals.py) sigue corriendo sobre el producto
compuesto mismo — por eso la recomendación operativa es setear
cantidad_disponible muy alta en el producto kit (decisión Opción B).

IMPORTANTE: estos signals NO reemplazan los de ventas; son ADITIVOS.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from ventas.models import Producto, ReservaProducto

from .models import Kit

logger = logging.getLogger(__name__)


def _get_kit_activo_para_producto(producto: Producto) -> Kit | None:
    """Retorna el Kit activo con descuento_auto asociado al producto, o None."""
    if producto is None:
        return None
    try:
        kit = producto.kit  # OneToOne related_name='kit'
    except Kit.DoesNotExist:
        return None
    if not kit.activo or not kit.descontar_componentes_auto:
        return None
    return kit


def _descontar_componentes(kit: Kit, cantidad_kit: int, origen_pk: int | None) -> None:
    """Descuenta del inventario los componentes de un kit (lock-safe)."""
    componentes = kit.componentes.filter(activo=True).select_related('producto_componente')
    for comp in componentes:
        a_descontar = comp.cantidad_total_a_descontar(cantidad_kit)
        if a_descontar <= 0:
            continue
        with transaction.atomic():
            prod_locked = Producto.objects.select_for_update().get(
                pk=comp.producto_componente_id
            )
            prod_locked.reducir_inventario(a_descontar)
        logger.info(
            "kits: descontadas %s unidades de %s por ReservaProducto %s (kit=%s)",
            a_descontar, prod_locked.nombre, origen_pk, kit.pk,
        )


def _restaurar_componentes(kit: Kit, cantidad_kit: int, origen_pk: int | None) -> None:
    """Restaura inventario de los componentes (lock-safe)."""
    componentes = kit.componentes.filter(activo=True).select_related('producto_componente')
    for comp in componentes:
        a_restaurar = comp.cantidad_total_a_descontar(cantidad_kit)
        if a_restaurar <= 0:
            continue
        with transaction.atomic():
            prod_locked = Producto.objects.select_for_update().get(
                pk=comp.producto_componente_id
            )
            prod_locked.incrementar_inventario(a_restaurar)
        logger.info(
            "kits: restauradas %s unidades de %s por ReservaProducto %s (kit=%s)",
            a_restaurar, prod_locked.nombre, origen_pk, kit.pk,
        )


@receiver(pre_save, sender=ReservaProducto)
def kits_guardar_cantidad_anterior(sender, instance, **kwargs):
    """Guarda la cantidad previa para poder calcular el delta en post_save."""
    if instance.pk:
        try:
            prev = ReservaProducto.objects.get(pk=instance.pk)
            instance._kits_cantidad_anterior = prev.cantidad
            instance._kits_producto_id_anterior = prev.producto_id
        except ReservaProducto.DoesNotExist:
            instance._kits_cantidad_anterior = 0
            instance._kits_producto_id_anterior = None
    else:
        instance._kits_cantidad_anterior = 0
        instance._kits_producto_id_anterior = None


@receiver(post_save, sender=ReservaProducto)
def kits_actualizar_inventario_componentes(sender, instance, created, raw=False, **kwargs):
    """Descuenta/ajusta componentes del kit al vender o modificar una ReservaProducto."""
    if raw:
        return  # fixtures

    try:
        producto = instance.producto
        kit = _get_kit_activo_para_producto(producto)

        if created:
            if kit is not None:
                _descontar_componentes(kit, instance.cantidad, instance.pk)
            return

        # Update: calcular delta
        cant_anterior = getattr(instance, '_kits_cantidad_anterior', 0)
        prod_id_anterior = getattr(instance, '_kits_producto_id_anterior', None)

        # Si cambió el producto, tratamos como restauración del viejo + descuento del nuevo
        if prod_id_anterior and prod_id_anterior != producto.pk:
            try:
                prod_viejo = Producto.objects.get(pk=prod_id_anterior)
                kit_viejo = _get_kit_activo_para_producto(prod_viejo)
                if kit_viejo is not None:
                    _restaurar_componentes(kit_viejo, cant_anterior, instance.pk)
            except Producto.DoesNotExist:
                logger.warning("kits: producto anterior %s no existe", prod_id_anterior)
            if kit is not None:
                _descontar_componentes(kit, instance.cantidad, instance.pk)
            return

        # Mismo producto: ajustar por delta de cantidad
        if kit is None:
            return
        delta = instance.cantidad - cant_anterior
        if delta > 0:
            _descontar_componentes(kit, delta, instance.pk)
        elif delta < 0:
            _restaurar_componentes(kit, -delta, instance.pk)
    except Exception as e:
        logger.exception(
            "kits: error ajustando componentes en ReservaProducto %s: %s",
            instance.pk, e,
        )


@receiver(post_delete, sender=ReservaProducto)
def kits_restaurar_inventario_al_eliminar(sender, instance, **kwargs):
    """Restaura el inventario de los componentes cuando se elimina una ReservaProducto (anulación)."""
    try:
        producto = instance.producto
        kit = _get_kit_activo_para_producto(producto)
        if kit is None:
            return
        _restaurar_componentes(kit, instance.cantidad, instance.pk)
    except Exception as e:
        logger.exception(
            "kits: error restaurando componentes al eliminar ReservaProducto %s: %s",
            instance.pk, e,
        )
