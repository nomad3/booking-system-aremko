from datetime import timedelta, datetime
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
import random
import string
from django.db.models import Sum, F, DecimalField, FloatField # Added DecimalField, FloatField

class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    # Otros campos relevantes

    def __str__(self):
        return self.nombre


class CategoriaProducto(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    precio_base = models.DecimalField(max_digits=10, decimal_places=0)
    cantidad_disponible = models.PositiveIntegerField()
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True)
    categoria = models.ForeignKey(CategoriaProducto, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.nombre

    def reducir_inventario(self, cantidad):
        if self.cantidad_disponible >= cantidad:
            self.cantidad_disponible -= cantidad
            self.save()
        else:
            raise ValueError('No hay suficiente inventario disponible.')

    def incrementar_inventario(self, cantidad):
        self.cantidad_disponible += cantidad
        if self.cantidad_disponible < 0:
            raise ValueError('El inventario no puede ser negativo.')
        self.save()

class Compra(models.Model):
    METODOS_PAGO = [
        ('tarjeta', 'Tarjeta de Crédito/Débito'),
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia Bancaria'), # Added generic transfer option
        ('webpay', 'WebPay'),
        ('descuento', 'Descuento'),
        ('giftcard', 'GiftCard'),
        ('flow', 'FLOW'),
        ('mercadopago', 'MercadoPago'),
        ('scotiabank', 'Transferencia ScotiaBank'), # Keep specific ones for admin use
        ('bancoestado', 'Transferencia BancoEstado'),
        ('cuentarut', 'Transferencia CuentaRut'),
        ('machjorge', 'mach jorge'),
        ('machalda', 'mach alda'),
        ('bicegoalda', 'bicego alda'),
        ('bcialda', 'bci alda'),
        ('andesalda', 'andes alda'),
        ('mercadopagoaremko', 'mercadopago aremko'),
        ('scotiabankalda', 'scotiabank alda'),
        ('copecjorge', 'copec jorge'),
        ('copecalda', 'copec alda'),
        ('copecmartin', 'copec martin'),
    ]

    fecha_compra = models.DateField(default=timezone.now)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    metodo_pago = models.CharField(max_length=50, choices=METODOS_PAGO)
    numero_documento = models.CharField(max_length=100, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=0, default=0)


    def __str__(self):
        return f"Compra #{self.id} - {self.proveedor}"

    def calcular_total(self):
        total_detalles = self.detalles.aggregate(
            total=Sum(F('precio_unitario') * F('cantidad'), output_field=models.DecimalField())
        )['total'] or 0
        self.total = total_detalles

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # No llamamos a calcular_total aquí para evitar recursión

class GiftCard(models.Model):
    ESTADO_CHOICES = [
        ('por_cobrar', 'Por Cobrar'),
        ('cobrado', 'Cobrado'),
    ]

    codigo = models.CharField(max_length=12, unique=True, editable=False)
    monto_inicial = models.DecimalField(max_digits=10, decimal_places=0)
    monto_disponible = models.DecimalField(max_digits=10, decimal_places=0)
    fecha_emision = models.DateField(default=timezone.now)
    fecha_vencimiento = models.DateField()
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='por_cobrar')
    cliente_comprador = models.ForeignKey('Cliente', related_name='giftcards_compradas', on_delete=models.SET_NULL, null=True, blank=True)
    cliente_destinatario = models.ForeignKey('Cliente', related_name='giftcards_recibidas', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"GiftCard {self.codigo} - Saldo: {self.monto_disponible}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.generar_codigo_unico()
        if not self.monto_disponible:
            self.monto_disponible = self.monto_inicial
        super().save(*args, **kwargs)

    def generar_codigo_unico(self):
        while True:
            codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            if not GiftCard.objects.filter(codigo=codigo).exists():
                return codigo

    def usar(self, monto):
        if self.fecha_vencimiento < timezone.now().date():
            raise ValueError("La gift card ha expirado.")
        if self.monto_disponible >= monto:
            self.monto_disponible -= monto
            if self.monto_disponible == 0:
                self.estado = 'cobrado'
            self.save()
        else:
            raise ValueError("El monto excede el saldo disponible de la gift card.")

class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    descripcion = models.CharField(max_length=255)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=0)

    def __str__(self):
        return f"{self.descripcion} - {self.cantidad} x {self.precio_unitario}"

    def save(self, *args, **kwargs):
        cantidad_anterior = None
        if self.pk:
            cantidad_anterior = DetalleCompra.objects.get(pk=self.pk).cantidad

        super().save(*args, **kwargs)

        # Actualizar el stock del producto si está vinculado
        if self.producto:
            incremento = self.cantidad
            if cantidad_anterior is not None:
                incremento -= cantidad_anterior
            self.producto.incrementar_inventario(incremento)

    def delete(self, *args, **kwargs):
        # Al eliminar, restar la cantidad del inventario
        if self.producto:
            self.producto.incrementar_inventario(-self.cantidad)
        super().delete(*args, **kwargs)

class CategoriaServicio(models.Model):
    nombre = models.CharField(max_length=100)
    horarios = models.CharField(max_length=200, help_text="Ingresa los horarios disponibles separados por comas. Ejemplo: 14:00, 15:30, 17:00", blank=True)
    imagen = models.URLField(max_length=1024, blank=True, null=True, help_text="URL de la imagen externa (ej. Google Cloud Storage)") # Changed from ImageField

    def __str__(self):
        return self.nombre

class Servicio(models.Model):
    nombre = models.CharField(max_length=100)
    precio_base = models.DecimalField(max_digits=10, decimal_places=0)
    duracion = models.PositiveIntegerField(help_text="Duración en minutos")
    categoria = models.ForeignKey(CategoriaServicio, on_delete=models.SET_NULL, null=True)
    # Changed from ForeignKey to ManyToManyField
    proveedores = models.ManyToManyField(
        Proveedor,
        blank=True,
        related_name='servicios_ofrecidos',
        help_text="Selecciona los proveedores (ej. masajistas) que pueden realizar este servicio."
    )
    capacidad_minima = models.PositiveIntegerField(default=1, help_text="Mínimo de personas para reservar")
    capacidad_maxima = models.PositiveIntegerField(default=1, help_text="Máximo de personas permitidas")
    horario_apertura = models.TimeField(default='09:00')
    horario_cierre = models.TimeField(default='23:59')
    slots_disponibles = models.JSONField(default=list, help_text="Horarios disponibles en formato HH:MM")
    activo = models.BooleanField(
        default=True,
        help_text="Indica si el servicio está disponible para reservas (uso interno)"
    )
    publicado_web = models.BooleanField(
        default=True,
        help_text="Marcar si este servicio debe ser visible y reservable en la página web pública."
    )
    TIPO_SERVICIO_CHOICES = [
        ('tina', 'Tina'),
        ('masaje', 'Masaje'),
        ('cabana', 'Cabaña'),
        ('otro', 'Otro'),
    ]
    tipo_servicio = models.CharField(
        max_length=10,
        choices=TIPO_SERVICIO_CHOICES,
        default='otro',
        help_text="Tipo de servicio para aplicar lógicas específicas (ej. precios, horarios)."
    )
    imagen = models.URLField(max_length=1024, blank=True, null=True, help_text="URL de la imagen externa (ej. Google Cloud Storage)") # Changed from ImageField
    descripcion_web = models.TextField(
        blank=True,
        null=True,
        help_text="Descripción detallada para mostrar en la página web pública."
    )

    def __str__(self):
        return self.nombre

    def horario_valido(self, hora_propuesta):
        return hora_propuesta in self.slots_disponibles

class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True) # Allow blank email if phone is primary
    telefono = models.CharField(max_length=20, unique=True, help_text="Número de teléfono único (formato internacional preferido)") # Add unique=True
    documento_identidad = models.CharField(max_length=20, null=True, blank=True, verbose_name="ID/DNI/Passport/RUT")
    pais = models.CharField(max_length=100, null=True, blank=True)
    ciudad = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.nombre} - {self.telefono}"

class VentaReserva(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    productos = models.ManyToManyField(Producto, through='ReservaProducto')
    servicios = models.ManyToManyField(Servicio, through='ReservaServicio')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_reserva = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name='Fecha Venta Reserva'  # Agregar verbose_name
    )    
    total = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    pagado = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    saldo_pendiente = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    estado_pago = models.CharField(
        max_length=20,
        choices=[
            ('pendiente', 'Pendiente'),
            ('pagado', 'Pagado'),
            ('parcial', 'Parcialmente Pagado'),
            ('cancelado', 'Cancelado'),
        ],
        default='pendiente',
        verbose_name='Estado de Pago'
    )
    ESTADO_RESERVA_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('checkin', 'Check-in'),
        ('checkout', 'Check-out'),
    ]
    estado_reserva = models.CharField(
        max_length=10,
        choices=ESTADO_RESERVA_CHOICES,
        default='pendiente',
        verbose_name='Estado de Reserva'
    )
    codigo_giftcard = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name='Código GiftCard'
    )
    cobrado = models.BooleanField(
        default=False, 
        verbose_name='Cobrado'
    )
    numero_documento_fiscal = models.CharField(max_length=100, null=True, blank=True)
    comentarios = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Venta/Reserva #{self.id} de {self.cliente}"

    def calcular_total(self):
        total_productos = self.reservaproductos.aggregate(total=models.Sum(models.F('producto__precio_base') * models.F('cantidad')))['total'] or 0
        total_servicios = self.reservaservicios.aggregate(total=models.Sum(models.F('servicio__precio_base') * models.F('cantidad_personas')))['total'] or 0
        total_pagos_descuentos = self.pagos.filter(metodo_pago='descuento').aggregate(total=models.Sum('monto'))['total'] or 0  # Considerar descuentos como pagos negativos

        self.total = total_productos + total_servicios - total_pagos_descuentos
        self.save()
        self.actualizar_saldo()  # Llama a actualizar_saldo después de calcular_total

    def actualizar_saldo(self):
        total_pagos = self.pagos.exclude(metodo_pago='descuento').aggregate(total=models.Sum('monto'))['total'] or 0
        self.pagado = total_pagos
        self.saldo_pendiente = self.total - self.pagado
        if self.saldo_pendiente <= 0:
            self.estado_pago = 'pagado'
        elif self.pagado > 0:
            self.estado_pago = 'parcial'
        else:
            self.estado_pago = 'pendiente'
        self.save()

    def actualizar_total(self):
        self.calcular_total()

    def registrar_pago(self, monto, metodo_pago):
        if metodo_pago == 'descuento' and monto > self.total:
            raise ValidationError("El descuento no puede ser mayor al total de la venta.")  # Validación descuento
            
        Pago.objects.create(venta_reserva=self, monto=monto, metodo_pago=metodo_pago)
        self.calcular_total() # Recalcula el total después de cada pago, incluyendo descuentos.

    def agregar_producto(self, producto, cantidad):
        with transaction.atomic():  # Asegura la consistencia de los datos
            if cantidad > producto.cantidad_disponible:
                raise ValueError("No hay suficiente inventario disponible para este producto.")
            self.productos.add(producto, through_defaults={'cantidad': cantidad})
            producto.reducir_inventario(cantidad)
            self.calcular_total()  # <-- Llama a calcular_total aquí

    @property
    def total_servicios(self):
        total = self.reservaservicios.aggregate(
            total=models.Sum(
                models.F('servicio__precio_base') * models.F('cantidad_personas')
            )
        )['total'] or 0
        return total

    @property
    def total_productos(self):
        total = self.reservaproductos.aggregate(
            total=models.Sum(
                models.F('producto__precio_base') * models.F('cantidad')
            )
        )['total'] or 0
        return total

    def agregar_servicio(self, servicio, fecha_agendamiento, cantidad_personas=1):
        with transaction.atomic():
            duracion_servicio = servicio.duracion
            fecha_fin = fecha_agendamiento + duracion_servicio

            if ReservaServicio.objects.filter(servicio=servicio).filter(
                fecha_agendamiento__lt=fecha_fin,
                fecha_agendamiento__gte=fecha_agendamiento - timedelta(hours=duracion_servicio.total_seconds() / 3600)
            ).exists():
                raise ValidationError(f"El servicio {servicio.nombre} ya está reservado entre {fecha_agendamiento} y {fecha_fin}. Por favor, elige otro horario.")

            self.servicios.add(servicio, through_defaults={
                'fecha_agendamiento': fecha_agendamiento,
                'cantidad_personas': cantidad_personas
            })
            self.calcular_total() # <-- Llama a calcular_total aquí

class Pago(models.Model):
    METODOS_PAGO = [
        ('tarjeta', 'Tarjeta de Crédito/Débito'),
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia Bancaria'), # Added generic transfer option
        ('webpay', 'WebPay'),
        ('descuento', 'Descuento'),
        ('giftcard', 'GiftCard'),
        ('flow', 'FLOW'),
        ('mercadopago', 'MercadoPago'),
        ('scotiabank', 'Transferencia ScotiaBank'), # Keep specific ones for admin use
        ('bancoestado', 'Transferencia BancoEstado'),
        ('cuentarut', 'Transferencia CuentaRut'),
        ('machjorge', 'mach jorge'),
        ('machalda', 'mach alda'),
        ('bicegoalda', 'bicego alda'),
        ('bcialda', 'bci alda'),
        ('andesalda', 'andes alda'),
        ('mercadopagoaremko', 'mercadopago aremko'),
        ('scotiabankalda', 'scotiabank alda'),
        ('copecjorge', 'copec jorge'),
        ('copecalda', 'copec alda'),
        ('copecmartin', 'copec martin'),
    ]

    venta_reserva = models.ForeignKey(VentaReserva, related_name='pagos', on_delete=models.CASCADE)
    fecha_pago = models.DateTimeField(default=timezone.now)
    monto = models.DecimalField(max_digits=10, decimal_places=0)
    metodo_pago = models.CharField(max_length=100, choices=METODOS_PAGO)
    usuario = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='pagos')  # Permitir nulos
    giftcard = models.ForeignKey(GiftCard, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Pago de {self.monto} para {self.venta_reserva}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            # Validaciones y lógica para gift cards
            if self.metodo_pago == 'giftcard':
                if not self.giftcard:
                    raise ValidationError("Debe seleccionar una gift card para este método de pago.")
                if self.giftcard.fecha_vencimiento < timezone.now().date():
                    raise ValidationError("La gift card ha expirado.")
                if self.giftcard.monto_disponible < self.monto:
                    raise ValidationError("El monto excede el saldo disponible en la gift card.")
                # Descontar el monto de la gift card
                self.giftcard.usar(self.monto)
            else:
                if self.giftcard:
                    raise ValidationError("No debe seleccionar una gift card para este método de pago.")

            super().save(*args, **kwargs)
            self.venta_reserva.calcular_total()

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            if self.metodo_pago == 'giftcard' and self.giftcard:
                # Restaurar el monto a la gift card
                self.giftcard.monto_disponible += self.monto
                self.giftcard.estado = 'por_cobrar'
                self.giftcard.save()
            super().delete(*args, **kwargs)
            self.venta_reserva.calcular_total()

class MovimientoCliente(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    tipo_movimiento = models.CharField(max_length=50)
    fecha_movimiento = models.DateTimeField(auto_now_add=True)
    # Changed on_delete to SET_NULL to prevent IntegrityError during test teardown
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL, # Keep user info if possible, but allow deletion
        null=True, # Allow null values
        blank=True
    )
    comentarios = models.TextField(blank=True)
    venta_reserva = models.ForeignKey(
        VentaReserva, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.tipo_movimiento} - {self.cliente} - {self.fecha_movimiento}"

class ReservaProducto(models.Model):
    venta_reserva = models.ForeignKey(VentaReserva, on_delete=models.CASCADE, related_name='reservaproductos')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} en Venta/Reserva #{self.venta_reserva.id}"

class ReservaServicio(models.Model):
    venta_reserva = models.ForeignKey(VentaReserva, on_delete=models.CASCADE, related_name='reservaservicios')
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    fecha_agendamiento = models.DateField()
    hora_inicio = models.CharField(max_length=5)
    # Default to 1, but enforce max 2 for cabins during booking if needed
    cantidad_personas = models.PositiveIntegerField(default=1)
    # Add field to link specific provider for this instance (e.g., masseuse)
    proveedor_asignado = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservas_asignadas',
        help_text="Proveedor específico asignado para esta reserva (ej. masajista)."
    )

    @property
    def fecha_hora_completa(self):
        return timezone.make_aware(
            datetime.combine(self.fecha_agendamiento, datetime.strptime(self.hora_inicio, "%H:%M").time())
        )

    def __str__(self):
        return f"{self.servicio.nombre} reservado para {self.fecha_agendamiento} {self.hora_inicio}"

    def calcular_precio(self):
        """Calcula el precio basado en el tipo de servicio."""
        if self.servicio.tipo_servicio == 'cabana':
            # Precio fijo para cabañas, independientemente de las personas (max 2)
            return self.servicio.precio_base
        else:
            # Precio normal basado en personas para otros servicios
            return self.servicio.precio_base * self.cantidad_personas
    
    # Add subtotal property for consistency in templates if needed
    @property
    def subtotal(self):
        return self.calcular_precio()

    def clean(self):
        # Basic validation example: Ensure assigned provider is valid for the service type
        super().clean()
        if self.servicio and self.proveedor_asignado:
            if self.servicio.tipo_servicio == 'masaje':
                if not self.servicio.proveedores.filter(pk=self.proveedor_asignado.pk).exists():
                    raise ValidationError({
                        'proveedor_asignado': f"El proveedor '{self.proveedor_asignado}' no está habilitado para el servicio '{self.servicio}'."
                    })
            # Optional: Clear provider if service is not a massage type?
            # elif self.servicio.tipo_servicio != 'masaje':
            #     self.proveedor_asignado = None # Or raise validation error

    # Consider adding validation in save() as well if needed, clean() isn't called automatically everywhere.


# --- Modelos CRM & Marketing ---

class Campaign(models.Model):
    STATUS_CHOICES = [
        ('Planning', 'Planificación'),
        ('Active', 'Activa'),
        ('Completed', 'Completada'),
        ('Cancelled', 'Cancelada'),
    ]
    name = models.CharField(max_length=255, unique=True, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    start_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Inicio")
    end_date = models.DateField(null=True, blank=True, verbose_name="Fecha de Fin")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Planning', verbose_name="Estado")
    goal = models.TextField(blank=True, verbose_name="Objetivo")
    budget = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Presupuesto")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")

    class Meta:
        verbose_name = "Campaña"
        verbose_name_plural = "Campañas"

    def __str__(self):
        return self.name

    # Placeholder for ROI calculation methods
    def get_associated_leads_count(self):
        return self.leads.count()

    def get_won_deals_count(self):
        return self.deals.filter(stage='Closed Won').count()

    def get_won_deals_value(self):
        return self.deals.filter(stage='Closed Won').aggregate(total_value=Sum('amount'))['total_value'] or 0


class Lead(models.Model):
    STATUS_CHOICES = [
        ('New', 'Nuevo'),
        ('Contacted', 'Contactado'),
        ('Qualified', 'Calificado'),
        ('Unqualified', 'No Calificado'),
        ('Converted', 'Convertido'),
    ]
    SOURCE_CHOICES = [
        ('Website Form', 'Formulario Web'),
        ('Referral', 'Referido'),
        ('Cold Call', 'Llamada en Frío'),
        ('Event', 'Evento'),
        ('Campaign', 'Campaña'),
        ('Other', 'Otro'),
    ]
    first_name = models.CharField(max_length=100, verbose_name="Nombre")
    last_name = models.CharField(max_length=100, verbose_name="Apellido")
    email = models.EmailField(unique=True, verbose_name="Correo Electrónico")
    phone = models.CharField(max_length=30, blank=True, null=True, verbose_name="Teléfono")
    company_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nombre Compañía")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='New', verbose_name="Estado")
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES, blank=True, null=True, verbose_name="Fuente")
    notes = models.TextField(blank=True, verbose_name="Notas")
    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='leads', verbose_name="Campaña")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")

    class Meta:
        verbose_name = "Lead (Prospecto)"
        verbose_name_plural = "Leads (Prospectos)"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"


class Company(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Nombre")
    website = models.URLField(blank=True, null=True, verbose_name="Sitio Web")
    address = models.TextField(blank=True, verbose_name="Dirección")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")

    class Meta:
        verbose_name = "Compañía"
        verbose_name_plural = "Compañías"

    def __str__(self):
        return self.name


class Contact(models.Model):
    first_name = models.CharField(max_length=100, verbose_name="Nombre")
    last_name = models.CharField(max_length=100, verbose_name="Apellido")
    email = models.EmailField(unique=True, verbose_name="Correo Electrónico")
    phone = models.CharField(max_length=30, blank=True, null=True, verbose_name="Teléfono")
    job_title = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cargo")
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='contacts', verbose_name="Compañía")
    # Link to Django's built-in User model
    linked_user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='crm_contact',
        verbose_name="Usuario Vinculado"
    )
    notes = models.TextField(blank=True, verbose_name="Notas")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")

    class Meta:
        verbose_name = "Contacto"
        verbose_name_plural = "Contactos"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"


class Deal(models.Model):
    STAGE_CHOICES = [
        ('Prospecting', 'Prospección'),
        ('Qualification', 'Calificación'),
        ('Proposal', 'Propuesta'),
        ('Negotiation', 'Negociación'),
        ('Closed Won', 'Cerrada Ganada'),
        ('Closed Lost', 'Cerrada Perdida'),
    ]
    name = models.CharField(max_length=255, verbose_name="Nombre Oportunidad")
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='deals', verbose_name="Contacto")
    stage = models.CharField(max_length=50, choices=STAGE_CHOICES, default='Prospecting', verbose_name="Etapa")
    expected_close_date = models.DateField(null=True, blank=True, verbose_name="Fecha Cierre Estimada")
    amount = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Monto")
    probability = FloatField(null=True, blank=True, help_text="Probabilidad de 0.0 a 1.0", verbose_name="Probabilidad")
    # Assuming 'ventas.VentaReserva' is your booking/purchase model as requested
    related_booking = models.ForeignKey(
        'ventas.VentaReserva', # Using the likely model name from your app
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='crm_deal',
        verbose_name="Reserva Vinculada"
    )
    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='deals', verbose_name="Campaña")
    notes = models.TextField(blank=True, verbose_name="Notas")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")

    class Meta:
        verbose_name = "Oportunidad (Deal)"
        verbose_name_plural = "Oportunidades (Deals)"

    def __str__(self):
        return f"Oportunidad: {self.name} para {self.contact}"


class Activity(models.Model):
    TYPE_CHOICES = [
        ('Call', 'Llamada'),
        ('Email Sent', 'Correo Enviado'),
        ('Email Received', 'Correo Recibido'),
        ('Meeting', 'Reunión'),
        ('Note Added', 'Nota Agregada'),
        ('Status Change', 'Cambio de Estado'),
        ('Other', 'Otro'),
    ]
    activity_type = models.CharField(max_length=50, choices=TYPE_CHOICES, verbose_name="Tipo de Actividad")
    subject = models.CharField(max_length=255, verbose_name="Asunto")
    notes = models.TextField(blank=True, verbose_name="Notas")
    activity_date = models.DateTimeField(default=timezone.now, verbose_name="Fecha Actividad")
    related_lead = models.ForeignKey(Lead, on_delete=models.CASCADE, null=True, blank=True, related_name='activities', verbose_name="Lead Relacionado")
    related_contact = models.ForeignKey(Contact, on_delete=models.CASCADE, null=True, blank=True, related_name='activities', verbose_name="Contacto Relacionado")
    related_deal = models.ForeignKey(Deal, on_delete=models.CASCADE, null=True, blank=True, related_name='activities', verbose_name="Oportunidad Relacionada")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_activities',
        verbose_name="Creado por"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")

    class Meta:
        verbose_name = "Actividad"
        verbose_name_plural = "Actividades"

    def __str__(self):
        related_object = self.related_lead or self.related_contact or self.related_deal or "Sistema"
        return f"{self.get_activity_type_display()}: {self.subject} ({related_object})"

    def clean(self):
        """Ensure only one related object (Lead, Contact, or Deal) is linked."""
        super().clean()
        related_objects = [self.related_lead, self.related_contact, self.related_deal]
        linked_count = sum(1 for obj in related_objects if obj is not None)
        if linked_count > 1:
            raise ValidationError("An activity can only be related to one Lead, Contact, OR Deal at a time.")
        # Optional: Ensure at least one is linked if required by your logic
        # if linked_count == 0:
        #     raise ValidationError("An activity must be related to a Lead, Contact, or Deal.")

    # Optional: Add a CheckConstraint for database-level validation (requires Django 3.0+)
    # class Meta:
    #     constraints = [
    #         models.CheckConstraint(
    #             check=(
    #                 models.Q(related_lead__isnull=False, related_contact__isnull=True, related_deal__isnull=True) |
    #                 models.Q(related_lead__isnull=True, related_contact__isnull=False, related_deal__isnull=True) |
    #                 models.Q(related_lead__isnull=True, related_contact__isnull=True, related_deal__isnull=False) |
    #                 # Optional: Allow activities not linked to any (e.g., general notes)
    #                 models.Q(related_lead__isnull=True, related_contact__isnull=True, related_deal__isnull=True)
    #             ),
    #             name='crm_activity_single_relation'
    #         )
    #     ]
