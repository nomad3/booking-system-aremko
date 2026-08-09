# -*- coding: utf-8 -*-
"""Catálogo de artesanías de la sala de ventas (2026-08-09).

Reemplaza la lista en papel y el truco de las «unidades de $1.000»: cada pieza
es ÚNICA, con su código del papel, precio real y estado. La venta crea una
línea normal en la reserva (ReservaProducto sobre UN producto genérico
«Artesanía (pieza única)» con precio_unitario_venta = precio de la pieza) —
así la lista de productos verdaderos no se contamina con 145 piezas únicas.

App aislada drift-safe: no toca modelos de ventas.
"""
from django.db import models


class ArtesaniaPieza(models.Model):
    ESTADOS = [
        ('disponible', 'Disponible en sala'),
        ('bodega', 'En bodega'),
        ('vendida', 'Vendida'),
        ('merma', 'Merma'),
        ('regalo', 'Regalo / entrega sin cobro'),
        ('baja', 'Baja'),
    ]
    # Estados que cuentan como inventario vivo (se pueden vender).
    VIVOS = ('disponible', 'bodega')

    codigo = models.CharField(
        max_length=10, unique=True, db_index=True,
        help_text='El código del papel (45, 58, … 1060). Único por pieza.')
    nombre = models.CharField(max_length=160)
    precio = models.DecimalField(
        max_digits=10, decimal_places=0,
        help_text='Precio de lista en pesos. Al vender se puede ajustar.')
    estado = models.CharField(max_length=12, choices=ESTADOS,
                              default='disponible', db_index=True)
    foto = models.ImageField(upload_to='artesanias/', blank=True, null=True,
                             help_text='Opcional: foto con el celular.')
    fecha_ingreso = models.DateField(null=True, blank=True)

    # Datos de la salida (venta, merma o regalo)
    venta_reserva = models.ForeignKey(
        'ventas.VentaReserva', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='artesanias_vendidas')
    # La LÍNEA exacta de la reserva que representa esta venta. Si esa línea
    # se elimina (o se borra la reserva), la señal pre_delete devuelve la
    # pieza a disponible AUTOMÁTICAMENTE — nadie tiene que acordarse de nada.
    venta_linea = models.OneToOneField(
        'ventas.ReservaProducto', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='artesania_pieza')
    venta_monto = models.DecimalField(max_digits=10, decimal_places=0,
                                      null=True, blank=True)
    venta_fecha = models.DateField(null=True, blank=True)
    venta_forma_pago = models.CharField(max_length=30, blank=True, default='')
    notas = models.CharField(max_length=255, blank=True, default='')

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pieza de artesanía'
        verbose_name_plural = 'Piezas de artesanía'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.codigo} · {self.nombre} (${int(self.precio):,})'.replace(',', '.')

    @property
    def viva(self):
        return self.estado in self.VIVOS

    @property
    def precio_fmt(self):
        return f'${int(self.precio):,}'.replace(',', '.')

    @staticmethod
    def siguiente_codigo():
        """El próximo código numérico libre (el papel quedó en 1060)."""
        numeros = [int(c) for c in ArtesaniaPieza.objects.values_list('codigo', flat=True)
                   if str(c).isdigit()]
        return str(max(numeros) + 1) if numeros else '1061'


NOMBRE_PRODUCTO_GENERICO = 'Artesanía (pieza única)'


def producto_generico():
    """El único Producto de ventas que representa a TODAS las piezas.

    Stock alto a propósito: el inventario real vive en las piezas; la señal
    de ventas descuenta 1 por línea y nunca debe bloquear.
    """
    from ventas.models import Producto
    prod, _ = Producto.objects.get_or_create(
        nombre=NOMBRE_PRODUCTO_GENERICO,
        defaults={'precio_base': 1000, 'cantidad_disponible': 9999})
    return prod
