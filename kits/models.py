"""Modelos para productos compuestos (kits).

Un Kit define un producto compuesto: la venta de ese producto dispara
el descuento automático del inventario de sus componentes.

Diseño v1:
- Kit es 1:1 con ventas.Producto (el producto que se vende al cliente).
- KitComponente lista los productos internos que conforman el kit.
- El producto compuesto en sí NO pierde stock relevante (se marca
  cantidad_disponible alta en el admin para no bloquear ventas).
- La fecha del movimiento es la fecha_entrega de la ReservaProducto
  asociada a la venta; no se persiste histórico en v1.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Kit(models.Model):
    """Marca a un Producto como producto compuesto con componentes internos."""

    producto_compuesto = models.OneToOneField(
        'ventas.Producto',
        on_delete=models.CASCADE,
        related_name='kit',
        verbose_name='Producto compuesto',
        help_text='El producto "kit" que se vende al cliente (ej: Tabla de Quesos).',
    )
    activo = models.BooleanField(
        default=True,
        help_text='Si está inactivo, no se descuentan componentes al venderlo.',
    )
    descontar_componentes_auto = models.BooleanField(
        default=True,
        verbose_name='Descontar componentes automáticamente',
        help_text='Si está activo, al vender este producto se descuentan automáticamente los componentes.',
    )
    notas = models.TextField(
        blank=True,
        help_text='Notas internas sobre la composición del kit (ingredientes, recetas, etc.).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kit'
        verbose_name_plural = 'Kits (productos compuestos)'
        ordering = ['producto_compuesto__nombre']

    def __str__(self):
        return f'Kit: {self.producto_compuesto.nombre}'


class KitComponente(models.Model):
    """Un componente interno que se descuenta del inventario al vender el kit."""

    kit = models.ForeignKey(
        Kit,
        on_delete=models.CASCADE,
        related_name='componentes',
    )
    producto_componente = models.ForeignKey(
        'ventas.Producto',
        on_delete=models.PROTECT,
        related_name='usado_en_kits',
        verbose_name='Producto componente',
        help_text='El producto interno que se descuenta del inventario.',
    )
    cantidad_por_unidad = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Cantidad del componente consumida por cada unidad vendida del kit.',
    )
    activo = models.BooleanField(default=True)
    notas = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'Componente del kit'
        verbose_name_plural = 'Componentes del kit'
        ordering = ['kit', 'producto_componente__nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['kit', 'producto_componente'],
                name='uq_kit_componente',
            ),
        ]

    def __str__(self):
        return f'{self.cantidad_por_unidad} x {self.producto_componente.nombre}'

    def cantidad_total_a_descontar(self, cantidad_kit_vendida: int) -> int:
        """Retorna la cantidad entera (redondeada hacia arriba) a descontar.
        reducir_inventario trabaja con enteros; componentes fraccionarios
        se redondean al entero más cercano hacia arriba para no perder stock."""
        from math import ceil
        total = self.cantidad_por_unidad * Decimal(cantidad_kit_vendida)
        return int(ceil(total))
