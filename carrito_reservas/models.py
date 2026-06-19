"""
Modelo de CarritoReserva para H-029 FASE 2.

Un carrito por conversación, acumula servicios + productos, calcula descuentos dinámicamente.
"""

from django.db import models
from django.utils import timezone
from decimal import Decimal


class CarritoReserva(models.Model):
    """Carrito de reservas para Luna (WhatsApp, Instagram, Messenger).

    Una conversación = un carrito. Acumula servicios (tina, masaje, cabaña) + productos (queso, jugos).
    Calcula descuentos dinámicamente usando PackDescuentoService.
    """

    # Identidad de la conversación
    canal = models.CharField(
        max_length=20,
        choices=[
            ('whatsapp', 'WhatsApp'),
            ('instagram', 'Instagram'),
            ('messenger', 'Messenger'),
        ],
        help_text='Canal de comunicación'
    )
    external_id = models.CharField(
        max_length=100,
        help_text='Teléfono (WA), IGSID (IG), o PSID (Messenger)'
    )

    # Items: servicios + productos
    items = models.JSONField(
        default=list,
        blank=True,
        help_text='''Lista de items en el carrito. Cada item es un dict:
        {
            "tipo": "servicio" | "producto",
            "id": int,
            "nombre": str,
            "precio_unitario": float,
            "subtotal": float,

            // Si tipo="servicio":
            "fecha": "YYYY-MM-DD",
            "hora": "HH:MM",
            "cantidad_personas": int,

            // Si tipo="producto":
            "cantidad": int
        }'''
    )

    # Totales (se recalculan cada vez que cambia el carrito)
    subtotal_servicios = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Suma de precios de servicios'
    )
    subtotal_productos = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Suma de precios de productos'
    )
    descuento_combo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Descuento por PackDescuento aplicado'
    )
    packs_aplicados = models.JSONField(
        default=list,
        blank=True,
        help_text='IDs de packs que se aplicaron: [{"pack_id": 1, "nombre": "...", "descuento": 30000}, ...]'
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='subtotal_servicios + subtotal_productos - descuento_combo'
    )

    # Estado
    ESTADO_CHOICES = [
        ('activo', 'Carrito activo'),
        ('checkout', 'En proceso de checkout'),
        ('creado', 'Convertido a reserva'),
    ]
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='activo',
        help_text='Estado del carrito'
    )

    # FK a la reserva creada (si aplica)
    venta_reserva = models.OneToOneField(
        'ventas.VentaReserva',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text='Reserva creada a partir de este carrito (FASE 2→checkout)'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Carrito expira si no hay actividad (ej. 24h sin cambios)'
    )

    class Meta:
        db_table = 'carrito_reservas_carrioreserva'
        unique_together = [('canal', 'external_id')]
        indexes = [
            models.Index(fields=['canal', 'external_id']),
            models.Index(fields=['estado']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'Carrito {self.canal} {self.external_id} (estado={self.estado})'

    @classmethod
    def obtener_o_crear(cls, canal, external_id):
        """Obtiene o crea un carrito para una conversación."""
        carrito, creado = cls.objects.get_or_create(
            canal=canal,
            external_id=external_id,
            defaults={'estado': 'activo'}
        )
        return carrito

    def esta_vigente(self):
        """Verifica si el carrito sigue vigente (no expirado)."""
        if not self.expires_at:
            return True
        return timezone.now() < self.expires_at

    def marcar_como_checkout(self):
        """Marca el carrito como en proceso de checkout."""
        self.estado = 'checkout'
        self.save(update_fields=['estado', 'updated_at'])

    def marcar_como_creado(self, venta_reserva):
        """Marca el carrito como convertido a reserva."""
        self.estado = 'creado'
        self.venta_reserva = venta_reserva
        self.save(update_fields=['estado', 'venta_reserva', 'updated_at'])

    def contar_items(self):
        """Cuenta el total de items (servicios + productos)."""
        return len(self.items)

    def contar_servicios(self):
        """Cuenta solo servicios."""
        return sum(1 for item in self.items if item.get('tipo') == 'servicio')

    def contar_productos(self):
        """Cuenta solo productos."""
        return sum(1 for item in self.items if item.get('tipo') == 'producto')
