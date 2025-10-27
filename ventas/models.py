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
from solo.models import SingletonModel # Added import for django-solo

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
        ('mercadopago_link', 'Mercado Pago Link'),
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
    # Changed to ImageField to use Django's storage backend (GCS)
    imagen = models.ImageField(
        upload_to='categorias/', # Subdirectory within MEDIA_ROOT (GCS bucket)
        blank=True,
        null=True,
        help_text="Imagen representativa de la categoría."
    )

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
    # Changed to ImageField to use Django's storage backend (GCS)
    imagen = models.ImageField(
        upload_to='servicios/', # Subdirectory within MEDIA_ROOT (GCS bucket)
        blank=True,
        null=True,
        help_text="Imagen representativa del servicio."
    )
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

    def numero_visitas(self):
        """Calcula el número de visitas (VentaReserva) asociadas a este cliente."""
        return self.ventareserva_set.count() # Assumes default related_name

    def gasto_total(self):
        """Calcula el gasto total de este cliente basado en VentaReserva."""
        total = self.ventareserva_set.aggregate(total_gastado=Sum('total'))['total_gastado']
        return total or 0

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
        ('mercadopago_link', 'Mercado Pago Link'),
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
    # Targeting Criteria
    target_min_visits = models.PositiveIntegerField(null=True, blank=True, default=0, verbose_name="Visitas Mínimas Cliente")
    target_min_spend = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, default=0, verbose_name="Gasto Mínimo Cliente (CLP)")
    # Content Templates
    email_subject_template = models.CharField(max_length=255, blank=True, verbose_name="Plantilla Asunto Email")
    email_body_template = models.TextField(blank=True, verbose_name="Plantilla Cuerpo Email", help_text="Usar {nombre_cliente}, {apellido_cliente} como placeholders.")
    sms_template = models.TextField(blank=True, verbose_name="Plantilla SMS", help_text="Usar {nombre_cliente}, {apellido_cliente} como placeholders.")
    whatsapp_template = models.TextField(blank=True, verbose_name="Plantilla WhatsApp", help_text="Usar {nombre_cliente}, {apellido_cliente} como placeholders.")
    # Automation Notes
    automation_notes = models.TextField(blank=True, verbose_name="Notas de Automatización", help_text="Describe el flujo de n8n u otra automatización asociada (ej. 'Enviar SMS 3 días después', 'Llamada AI si no abre email').")


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

    def get_target_clientes(self):
        """
        Retorna un QuerySet de Clientes que cumplen los criterios de la campaña.
        """
        clientes_qs = Cliente.objects.annotate(
            num_visits=models.Count('ventareserva'),
            total_spend=Sum('ventareserva__total')
        )

        if self.target_min_visits is not None and self.target_min_visits > 0:
            clientes_qs = clientes_qs.filter(num_visits__gte=self.target_min_visits)

        if self.target_min_spend is not None and self.target_min_spend > 0:
            # Ensure total_spend is not null before filtering
            clientes_qs = clientes_qs.filter(total_spend__isnull=False, total_spend__gte=self.target_min_spend)

        return clientes_qs


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
    # Add campaign link to log which campaign triggered the activity
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities',
        verbose_name="Campaña Asociada"
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


# --- Singleton Model for Homepage Configuration ---

class HomepageConfig(SingletonModel):
    hero_background_image = models.ImageField(
        upload_to='homepage/',
        blank=True,
        null=True,
        help_text="Imagen de fondo para la sección principal (hero)."
    )
    philosophy_image = models.ImageField(
        upload_to='homepage/',
        blank=True,
        null=True,
        help_text="Imagen para la sección 'Vive la Experiencia Aremko'."
    )
    gallery_image_1 = models.ImageField(
        upload_to='homepage/gallery/',
        blank=True,
        null=True,
        help_text="Primera imagen para la galería 'Nuestros Espacios'."
    )
    gallery_image_2 = models.ImageField(
        upload_to='homepage/gallery/',
        blank=True,
        null=True,
        help_text="Segunda imagen para la galería 'Nuestros Espacios'."
    )
    gallery_image_3 = models.ImageField(
        upload_to='homepage/gallery/',
        blank=True,
        null=True,
        help_text="Tercera imagen para la galería 'Nuestros Espacios'."
    )

    def __str__(self):
        return "Configuración de la Página Principal"

    class Meta:
        verbose_name = "Configuración de la Página Principal"
        verbose_name_plural = "Configuración de la Página Principal"


# --- Model for Tracking Campaign Interactions ---

class CampaignInteraction(models.Model):
    INTERACTION_TYPES = [
        ('EMAIL_OPEN', 'Email Abierto'),
        ('EMAIL_CLICK', 'Email Click'),
        ('SMS_REPLY', 'Respuesta SMS'),
        ('WHATSAPP_REPLY', 'Respuesta WhatsApp'),
        ('CALL_ANSWERED', 'Llamada Contestada'),
        ('CALL_VOICEMAIL', 'Llamada a Buzón de Voz'),
        ('FORM_SUBMIT', 'Formulario Enviado'), # Example
        ('OTHER', 'Otro'),
    ]

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='interactions', verbose_name="Contacto")
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='interactions', verbose_name="Campaña")
    # Optional link back to the specific Activity that led to this interaction
    activity = models.ForeignKey(Activity, on_delete=models.SET_NULL, null=True, blank=True, related_name='interactions', verbose_name="Actividad Origen")
    interaction_type = models.CharField(max_length=50, choices=INTERACTION_TYPES, verbose_name="Tipo de Interacción")
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora")
    details = models.JSONField(null=True, blank=True, verbose_name="Detalles Adicionales", help_text="Ej: URL clickeada, contenido de respuesta SMS, etc.")

    class Meta:
        verbose_name = "Interacción de Campaña"
        verbose_name_plural = "Interacciones de Campaña"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_interaction_type_display()} de {self.contact} en Campaña '{self.campaign.name}' ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"

class HomepageSettings(models.Model):
    """
    Stores settings specific to the homepage, like the hero image.
    Intended to have only one instance (singleton pattern).
    """
    hero_background_image = models.ImageField(
        upload_to='homepage/',
        blank=True,
        null=True,
        help_text="Imagen de fondo para la sección principal (hero) de la página de inicio."
    )
    # Add other homepage-specific fields here if needed later

    class Meta:
        verbose_name = "Configuración de Inicio"
        verbose_name_plural = "Configuraciones de Inicio"

    def __str__(self):
        return "Configuración de la Página de Inicio"

    # Optional: Enforce singleton pattern (only allow one instance)
    def save(self, *args, **kwargs):
        if not self.pk and HomepageSettings.objects.exists():
            # Prevent creation of a new instance if one already exists
            raise ValidationError('Solo puede existir una instancia de HomepageSettings.')
        return super().save(*args, **kwargs)


# --- Modelos para Comunicación Inteligente y Anti-Spam ---

class CommunicationLimit(models.Model):
    """
    Modelo para controlar los límites de comunicación por cliente
    y evitar spam según las reglas de negocio definidas
    """
    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name='communication_limit')
    
    # Contadores de SMS
    sms_count_daily = models.IntegerField(default=0, verbose_name="SMS enviados hoy")
    sms_count_monthly = models.IntegerField(default=0, verbose_name="SMS enviados este mes")
    last_sms_date = models.DateField(null=True, blank=True, verbose_name="Fecha último SMS")
    last_sms_reset_daily = models.DateField(auto_now_add=True, verbose_name="Última reset daily")
    last_sms_reset_monthly = models.DateField(auto_now_add=True, verbose_name="Última reset monthly")
    
    # Contadores de Email
    email_count_weekly = models.IntegerField(default=0, verbose_name="Emails enviados esta semana")
    email_count_monthly = models.IntegerField(default=0, verbose_name="Emails enviados este mes")
    last_email_date = models.DateTimeField(null=True, blank=True, verbose_name="Fecha último email")
    last_email_reset_weekly = models.DateField(auto_now_add=True, verbose_name="Última reset weekly")
    last_email_reset_monthly = models.DateField(auto_now_add=True, verbose_name="Última reset monthly")
    
    # Contadores especiales
    birthday_sms_sent_this_year = models.BooleanField(default=False, verbose_name="SMS cumpleaños enviado este año")
    last_birthday_sms_year = models.IntegerField(null=True, blank=True, verbose_name="Año último SMS cumpleaños")
    
    reactivation_emails_this_quarter = models.IntegerField(default=0, verbose_name="Emails reactivación este trimestre")
    last_reactivation_quarter = models.CharField(max_length=7, blank=True, verbose_name="Último trimestre reactivación (YYYY-Q)")
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Límite de Comunicación"
        verbose_name_plural = "Límites de Comunicación"
    
    def __str__(self):
        return f"Límites {self.cliente.nombre} - SMS: {self.sms_count_daily}/día, Email: {self.email_count_weekly}/semana"
    
    def can_send_sms(self):
        """
        Verifica si se puede enviar SMS según los límites configurados
        """
        from django.conf import settings
        
        daily_limit = getattr(settings, 'SMS_DAILY_LIMIT_PER_CLIENT', 2)
        monthly_limit = getattr(settings, 'SMS_MONTHLY_LIMIT_PER_CLIENT', 8)
        
        # Reset contadores si es necesario
        self._reset_counters_if_needed()
        
        return (self.sms_count_daily < daily_limit and 
                self.sms_count_monthly < monthly_limit)
    
    def can_send_email(self):
        """
        Verifica si se puede enviar email según los límites configurados
        """
        from django.conf import settings
        
        weekly_limit = getattr(settings, 'EMAIL_WEEKLY_LIMIT_PER_CLIENT', 1)
        monthly_limit = getattr(settings, 'EMAIL_MONTHLY_LIMIT_PER_CLIENT', 4)
        
        # Reset contadores si es necesario
        self._reset_counters_if_needed()
        
        return (self.email_count_weekly < weekly_limit and 
                self.email_count_monthly < monthly_limit)
    
    def can_send_birthday_sms(self):
        """
        Verifica si se puede enviar SMS de cumpleaños (máximo 1 por año)
        """
        current_year = timezone.now().year
        return not self.birthday_sms_sent_this_year or self.last_birthday_sms_year != current_year
    
    def can_send_reactivation_email(self):
        """
        Verifica si se puede enviar email de reactivación (máximo 1 por trimestre)
        """
        current_quarter = self._get_current_quarter()
        return (self.last_reactivation_quarter != current_quarter or 
                self.reactivation_emails_this_quarter == 0)
    
    def record_sms_sent(self):
        """
        Registra el envío de un SMS y actualiza contadores
        """
        self._reset_counters_if_needed()
        self.sms_count_daily += 1
        self.sms_count_monthly += 1
        self.last_sms_date = timezone.now().date()
        self.save()
    
    def record_email_sent(self):
        """
        Registra el envío de un email y actualiza contadores
        """
        self._reset_counters_if_needed()
        self.email_count_weekly += 1
        self.email_count_monthly += 1
        self.last_email_date = timezone.now()
        self.save()
    
    def record_birthday_sms_sent(self):
        """
        Registra el envío de SMS de cumpleaños
        """
        current_year = timezone.now().year
        self.birthday_sms_sent_this_year = True
        self.last_birthday_sms_year = current_year
        self.record_sms_sent()
    
    def record_reactivation_email_sent(self):
        """
        Registra el envío de email de reactivación
        """
        current_quarter = self._get_current_quarter()
        if self.last_reactivation_quarter != current_quarter:
            self.reactivation_emails_this_quarter = 0
        self.reactivation_emails_this_quarter += 1
        self.last_reactivation_quarter = current_quarter
        self.record_email_sent()
    
    def _reset_counters_if_needed(self):
        """
        Reset contadores según el período correspondiente
        """
        today = timezone.now().date()
        current_week_start = today - timezone.timedelta(days=today.weekday())
        current_month = today.replace(day=1)
        current_year = today.year
        
        # Reset diario SMS
        if self.last_sms_reset_daily != today:
            self.sms_count_daily = 0
            self.last_sms_reset_daily = today
        
        # Reset mensual SMS
        if self.last_sms_reset_monthly < current_month:
            self.sms_count_monthly = 0
            self.last_sms_reset_monthly = current_month
        
        # Reset semanal Email
        if self.last_email_reset_weekly < current_week_start:
            self.email_count_weekly = 0
            self.last_email_reset_weekly = current_week_start
        
        # Reset mensual Email
        if self.last_email_reset_monthly < current_month:
            self.email_count_monthly = 0
            self.last_email_reset_monthly = current_month
        
        # Reset anual cumpleaños
        if self.last_birthday_sms_year and self.last_birthday_sms_year < current_year:
            self.birthday_sms_sent_this_year = False
    
    def _get_current_quarter(self):
        """
        Obtiene el trimestre actual en formato YYYY-Q
        """
        now = timezone.now()
        quarter = (now.month - 1) // 3 + 1
        return f"{now.year}-{quarter}"


class ClientPreferences(models.Model):
    """
    Preferencias de comunicación del cliente para opt-out granular
    """
    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name='preferences')
    
    # Preferencias generales
    accepts_sms = models.BooleanField(default=True, verbose_name="Acepta SMS")
    accepts_email = models.BooleanField(default=True, verbose_name="Acepta Email")
    accepts_whatsapp = models.BooleanField(default=True, verbose_name="Acepta WhatsApp")
    
    # Preferencias específicas
    accepts_booking_confirmations = models.BooleanField(default=True, verbose_name="Acepta confirmaciones de reserva")
    accepts_booking_reminders = models.BooleanField(default=True, verbose_name="Acepta recordatorios de cita")
    accepts_birthday_messages = models.BooleanField(default=True, verbose_name="Acepta mensajes de cumpleaños")
    accepts_promotional = models.BooleanField(default=True, verbose_name="Acepta mensajes promocionales")
    accepts_newsletters = models.BooleanField(default=True, verbose_name="Acepta newsletters")
    accepts_reactivation = models.BooleanField(default=True, verbose_name="Acepta mensajes de reactivación")
    
    # Preferencias de horario
    preferred_contact_hour_start = models.TimeField(default=timezone.datetime.strptime('09:00', '%H:%M').time(), verbose_name="Hora inicio contacto")
    preferred_contact_hour_end = models.TimeField(default=timezone.datetime.strptime('20:00', '%H:%M').time(), verbose_name="Hora fin contacto")
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    opt_out_date = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de opt-out general")
    
    class Meta:
        verbose_name = "Preferencia del Cliente"
        verbose_name_plural = "Preferencias de los Clientes"
    
    def __str__(self):
        status = "Activo" if self.accepts_sms or self.accepts_email else "Opt-out"
        return f"Preferencias {self.cliente.nombre} - {status}"
    
    def can_contact_now(self):
        """
        Verifica si se puede contactar al cliente en el horario actual
        """
        now = timezone.now().time()
        return self.preferred_contact_hour_start <= now <= self.preferred_contact_hour_end
    
    def set_opt_out_all(self):
        """
        Configura opt-out completo del cliente
        """
        self.accepts_sms = False
        self.accepts_email = False
        self.accepts_whatsapp = False
        self.accepts_promotional = False
        self.accepts_newsletters = False
        self.opt_out_date = timezone.now()
        self.save()


class CommunicationLog(models.Model):
    """
    Log detallado de todas las comunicaciones enviadas para auditoría y análisis
    """
    COMMUNICATION_TYPES = [
        ('SMS', 'SMS'),
        ('EMAIL', 'Email'),
        ('WHATSAPP', 'WhatsApp'),
        ('CALL', 'Llamada'),
    ]
    
    MESSAGE_TYPES = [
        ('BOOKING_CONFIRMATION', 'Confirmación de reserva'),
        ('BOOKING_REMINDER', 'Recordatorio de cita'),
        ('BIRTHDAY', 'Felicitación cumpleaños'),
        ('PROMOTIONAL', 'Promocional'),
        ('NEWSLETTER', 'Newsletter'),
        ('REACTIVATION', 'Reactivación'),
        ('FOLLOW_UP', 'Seguimiento'),
        ('SATISFACTION_SURVEY', 'Encuesta satisfacción'),
        ('OTHER', 'Otro'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('SENT', 'Enviado'),
        ('DELIVERED', 'Entregado'),
        ('READ', 'Leído'),
        ('REPLIED', 'Respondido'),
        ('FAILED', 'Falló'),
        ('BLOCKED', 'Bloqueado por límites'),
    ]
    
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='communication_logs')
    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='communication_logs')
    
    # Detalles del mensaje
    communication_type = models.CharField(max_length=20, choices=COMMUNICATION_TYPES, verbose_name="Tipo comunicación")
    message_type = models.CharField(max_length=30, choices=MESSAGE_TYPES, verbose_name="Tipo mensaje")
    subject = models.CharField(max_length=255, blank=True, verbose_name="Asunto")
    content = models.TextField(verbose_name="Contenido")
    destination = models.CharField(max_length=100, verbose_name="Destino (teléfono/email)")
    
    # Estado y tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Estado")
    external_id = models.CharField(max_length=100, blank=True, verbose_name="ID externo (batch_id, etc.)")
    
    # Metadatos
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Enviado en")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Entregado en")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Leído en")
    replied_at = models.DateTimeField(null=True, blank=True, verbose_name="Respondido en")
    
    cost = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Costo")
    
    # Contexto adicional
    booking_id = models.IntegerField(null=True, blank=True, verbose_name="ID Reserva relacionada")
    triggered_by = models.CharField(max_length=100, blank=True, verbose_name="Disparado por")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Log de Comunicación"
        verbose_name_plural = "Logs de Comunicación"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_communication_type_display()} a {self.cliente.nombre} - {self.get_status_display()}"
    
    def mark_as_sent(self, external_id=None):
        """
        Marca el mensaje como enviado
        """
        self.status = 'SENT'
        self.sent_at = timezone.now()
        if external_id:
            self.external_id = external_id
        self.save()
    
    def mark_as_delivered(self):
        """
        Marca el mensaje como entregado
        """
        self.status = 'DELIVERED'
        self.delivered_at = timezone.now()
        self.save()
    
    def mark_as_failed(self):
        """
        Marca el mensaje como fallido
        """
        self.status = 'FAILED'
        self.save()


class MailParaEnviar(models.Model):
    """
    Cola de emails para envío programado con control de horarios
    """
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('ENVIADO', 'Enviado'),
        ('FALLIDO', 'Fallido'),
        ('PAUSADO', 'Pausado'),
    ]
    
    # Datos del destinatario
    nombre = models.CharField(max_length=255, verbose_name="Nombre/Empresa")
    email = models.EmailField(verbose_name="Email")
    ciudad = models.CharField(max_length=100, blank=True, verbose_name="Ciudad")
    rubro = models.CharField(max_length=100, blank=True, verbose_name="Rubro")
    
    # Contenido del email
    asunto = models.CharField(max_length=255, verbose_name="Asunto")
    contenido_html = models.TextField(verbose_name="Contenido HTML")
    
    # Control de envío
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE', verbose_name="Estado")
    prioridad = models.IntegerField(default=1, verbose_name="Prioridad (1=alta, 5=baja)")
    
    # Timestamps
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")
    enviado_en = models.DateTimeField(null=True, blank=True, verbose_name="Enviado en")
    
    # Metadatos
    campana = models.CharField(max_length=100, blank=True, verbose_name="Campaña")
    notas = models.TextField(blank=True, verbose_name="Notas")
    
    class Meta:
        verbose_name = "Mail para Enviar"
        verbose_name_plural = "Mails para Enviar"
        ordering = ['prioridad', 'creado_en']
    
    def __str__(self):
        return f"{self.nombre} ({self.email}) - {self.estado}"
    
    def marcar_como_enviado(self):
        """Marca el email como enviado"""
        from django.utils import timezone
        self.estado = 'ENVIADO'
        self.enviado_en = timezone.now()
        self.save()
    
    def marcar_como_fallido(self):
        """Marca el email como fallido"""
        self.estado = 'FALLIDO'
        self.save()


class SMSTemplate(models.Model):
    """
    Plantillas predefinidas para diferentes tipos de SMS
    """
    MESSAGE_TYPES = [
        ('BOOKING_CONFIRMATION', 'Confirmación de reserva'),
        ('BOOKING_REMINDER', 'Recordatorio de cita'),
        ('BIRTHDAY', 'Felicitación cumpleaños'),
        ('REACTIVATION', 'Reactivación'),
        ('SATISFACTION_SURVEY', 'Encuesta satisfacción'),
        ('PROMOTIONAL', 'Promocional'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Nombre plantilla")
    message_type = models.CharField(max_length=30, choices=MESSAGE_TYPES, verbose_name="Tipo mensaje")
    content = models.TextField(verbose_name="Contenido", help_text="Usar {nombre}, {apellido}, {servicio}, {fecha}, {hora} como variables")
    
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    requires_approval = models.BooleanField(default=False, verbose_name="Requiere aprobación")
    
    # Límites específicos de la plantilla
    max_uses_per_client_per_day = models.IntegerField(default=1, verbose_name="Máximo usos por cliente por día")
    max_uses_per_client_per_month = models.IntegerField(default=4, verbose_name="Máximo usos por cliente por mes")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Creado por")
    
    class Meta:
        verbose_name = "Plantilla SMS"
        verbose_name_plural = "Plantillas SMS"
        unique_together = ['name', 'message_type']
    
    def __str__(self):
        return f"{self.name} ({self.get_message_type_display()})"
    
    def render_message(self, cliente, **kwargs):
        """
        Renderiza la plantilla con los datos del cliente y contexto adicional
        """
        context = {
            'nombre': cliente.nombre,
            'apellido': getattr(cliente, 'apellido', ''),
            'telefono': cliente.telefono,
        }
        context.update(kwargs)
        
        try:
            return self.content.format(**context)
        except KeyError as e:
            logger.warning(f"Variable faltante en plantilla {self.name}: {e}")
            return self.content  # Devolver sin procesar si falta alguna variable


class EmailTemplate(models.Model):
    """Template personalizado de emails para campañas"""
    name = models.CharField(max_length=200, verbose_name="Nombre del Template")
    subject = models.CharField(max_length=500, verbose_name="Asunto")
    body_html = models.TextField(verbose_name="Cuerpo HTML")
    campaign_type = models.CharField(max_length=50, choices=[
        ('giftcard', 'Campaña Giftcard'),
        ('promocional', 'Promocional'),
        ('recordatorio', 'Recordatorio'),
    ], default='giftcard')
    year = models.IntegerField(verbose_name="Año", default=2025)
    month = models.IntegerField(verbose_name="Mes", default=1)
    giftcard_amount = models.IntegerField(verbose_name="Monto Giftcard", default=15000)
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Template de Email"
        verbose_name_plural = "Templates de Email"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.year}/{self.month:02d}"


# =============================================================================
# MODELOS PARA SISTEMA DE CAMPAÑAS AVANZADO
# =============================================================================

class EmailCampaign(models.Model):
    """Campaña de email marketing con criterios avanzados"""
    
    CAMPAIGN_STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('ready', 'Lista para envío'),
        ('sending', 'Enviando'),
        ('paused', 'Pausada'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
    ]
    
    # Información básica
    name = models.CharField(max_length=200, verbose_name="Nombre de la campaña")
    description = models.TextField(blank=True, verbose_name="Descripción")
    status = models.CharField(max_length=20, choices=CAMPAIGN_STATUS_CHOICES, default='draft', verbose_name="Estado")
    
    # Criterios de selección (almacenados en JSON)
    criteria = models.JSONField(default=dict, verbose_name="Criterios de selección")
    # Estructura del JSON criteria:
    # {
    #     "month": 1, "year": 2025,
    #     "spend_min": 50000, "spend_max": 100000,  # opcional
    #     "visit_count_min": 2, "visit_count_max": 10,  # opcional
    #     "cities": ["Puerto Varas", "Osorno"],  # opcional
    # }
    
    # Configuración de envío
    schedule_config = models.JSONField(default=dict, verbose_name="Configuración de horarios")
    # Estructura del JSON schedule_config:
    # {
    #     "start_time": "08:00", "end_time": "21:00",
    #     "batch_size": 1, "interval_minutes": 3,
    #     "timezone": "America/Santiago",
    #     "ai_enabled": true, "ai_timeout": 5
    # }
    
    # Template de email
    email_subject_template = models.CharField(max_length=500, verbose_name="Template de asunto")
    email_body_template = models.TextField(verbose_name="Template de cuerpo")
    
    # Configuración avanzada
    ai_variation_enabled = models.BooleanField(default=True, verbose_name="Usar IA para variar contenido")
    anti_spam_enabled = models.BooleanField(default=True, verbose_name="Medidas anti-spam activas")
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Creado por")
    
    # Estadísticas calculadas
    total_recipients = models.IntegerField(default=0, verbose_name="Total de destinatarios")
    emails_sent = models.IntegerField(default=0, verbose_name="Emails enviados")
    emails_delivered = models.IntegerField(default=0, verbose_name="Emails entregados")
    emails_opened = models.IntegerField(default=0, verbose_name="Emails abiertos")
    emails_clicked = models.IntegerField(default=0, verbose_name="Clicks en emails")
    emails_bounced = models.IntegerField(default=0, verbose_name="Emails rebotados")
    spam_complaints = models.IntegerField(default=0, verbose_name="Quejas de spam")
    
    class Meta:
        verbose_name = "Campaña de Email"
        verbose_name_plural = "Campañas de Email"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def progress_percentage(self):
        """Calcula el porcentaje de progreso de la campaña"""
        if self.total_recipients == 0:
            return 0
        return (self.emails_sent / self.total_recipients) * 100
    
    @property
    def delivery_rate(self):
        """Calcula la tasa de entrega"""
        if self.emails_sent == 0:
            return 0
        return (self.emails_delivered / self.emails_sent) * 100
    
    @property
    def open_rate(self):
        """Calcula la tasa de apertura"""
        if self.emails_delivered == 0:
            return 0
        return (self.emails_opened / self.emails_delivered) * 100
    
    @property
    def click_rate(self):
        """Calcula la tasa de clicks"""
        if self.emails_delivered == 0:
            return 0
        return (self.emails_clicked / self.emails_delivered) * 100


class EmailRecipient(models.Model):
    """Destinatario individual de una campaña con email personalizado"""
    
    RECIPIENT_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('sending', 'Enviando'),
        ('sent', 'Enviado'),
        ('delivered', 'Entregado'),
        ('opened', 'Abierto'),
        ('clicked', 'Click realizado'),
        ('bounced', 'Rebotado'),
        ('failed', 'Fallido'),
        ('spam_complaint', 'Queja de spam'),
        ('unsubscribed', 'Desuscrito'),
        ('excluded', 'Excluido'),
    ]
    
    # Relaciones
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name='recipients')
    client = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    
    # Información del destinatario
    email = models.EmailField(verbose_name="Email")
    name = models.CharField(max_length=200, verbose_name="Nombre")
    
    # Contenido personalizado (generado por IA o personalización)
    personalized_subject = models.CharField(max_length=500, verbose_name="Asunto personalizado")
    personalized_body = models.TextField(verbose_name="Cuerpo personalizado")
    
    # Control de envío
    send_enabled = models.BooleanField(default=True, verbose_name="Habilitado para envío")
    priority = models.IntegerField(default=1, verbose_name="Prioridad")
    
    # Estado y tracking
    status = models.CharField(max_length=20, choices=RECIPIENT_STATUS_CHOICES, default='pending', verbose_name="Estado")
    
    # Metadatos de envío
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name="Programado para")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Enviado en")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Entregado en")
    opened_at = models.DateTimeField(null=True, blank=True, verbose_name="Abierto en")
    clicked_at = models.DateTimeField(null=True, blank=True, verbose_name="Click en")
    
    # Información adicional
    error_message = models.TextField(blank=True, verbose_name="Mensaje de error")
    bounce_reason = models.CharField(max_length=200, blank=True, verbose_name="Razón del rebote")
    user_agent = models.CharField(max_length=500, blank=True, verbose_name="User Agent")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Address")
    
    # Datos del cliente para análisis
    client_total_spend = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Gasto total del cliente")
    client_visit_count = models.IntegerField(default=0, verbose_name="Número de visitas")
    client_last_visit = models.DateField(null=True, blank=True, verbose_name="Última visita")
    client_city = models.CharField(max_length=100, blank=True, verbose_name="Ciudad del cliente")
    
    class Meta:
        verbose_name = "Destinatario de Email"
        verbose_name_plural = "Destinatarios de Email"
        ordering = ['priority', 'scheduled_at', 'id']
        unique_together = ['campaign', 'email']  # Un email por campaña
    
    def __str__(self):
        return f"{self.name} ({self.email}) - {self.campaign.name}"
    
    def mark_as_sent(self):
        """Marca el email como enviado"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()
        
        # Actualizar estadísticas de la campaña
        self.campaign.emails_sent += 1
        self.campaign.save()
    
    def mark_as_delivered(self):
        """Marca el email como entregado"""
        if self.status == 'sent':
            self.status = 'delivered'
            self.delivered_at = timezone.now()
            self.save()
            
            # Actualizar estadísticas de la campaña
            self.campaign.emails_delivered += 1
            self.campaign.save()
    
    def mark_as_opened(self):
        """Marca el email como abierto"""
        if self.status in ['delivered', 'opened']:
            if self.status != 'opened':
                self.campaign.emails_opened += 1
            self.status = 'opened'
            self.opened_at = timezone.now()
            self.save()
            self.campaign.save()
    
    def mark_as_clicked(self):
        """Marca el email como clicked"""
        if self.status in ['delivered', 'opened', 'clicked']:
            if self.status != 'clicked':
                self.campaign.emails_clicked += 1
            self.status = 'clicked'
            self.clicked_at = timezone.now()
            self.save()
            self.campaign.save()


class EmailDeliveryLog(models.Model):
    """Log detallado de entregas de email para análisis y debugging"""
    
    LOG_TYPE_CHOICES = [
        ('send_attempt', 'Intento de envío'),
        ('delivery_success', 'Entrega exitosa'),
        ('delivery_failure', 'Falla en entrega'),
        ('bounce_hard', 'Rebote duro'),
        ('bounce_soft', 'Rebote suave'),
        ('spam_complaint', 'Queja de spam'),
        ('unsubscribe', 'Desuscripción'),
        ('open_tracking', 'Seguimiento de apertura'),
        ('click_tracking', 'Seguimiento de clicks'),
    ]
    
    # Relaciones
    recipient = models.ForeignKey(EmailRecipient, on_delete=models.CASCADE, related_name='delivery_logs')
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name='delivery_logs')
    
    # Información del log
    log_type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES, verbose_name="Tipo de log")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Timestamp")
    
    # Detalles técnicos
    smtp_response = models.TextField(blank=True, verbose_name="Respuesta SMTP")
    error_code = models.CharField(max_length=10, blank=True, verbose_name="Código de error")
    error_message = models.TextField(blank=True, verbose_name="Mensaje de error")
    
    # Información adicional
    user_agent = models.CharField(max_length=500, blank=True, verbose_name="User Agent")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Address")
    country_code = models.CharField(max_length=2, blank=True, verbose_name="Código de país")
    
    # Metadatos del servidor
    server_response_time = models.FloatField(null=True, blank=True, verbose_name="Tiempo de respuesta (ms)")
    retry_count = models.IntegerField(default=0, verbose_name="Número de reintentos")
    
    class Meta:
        verbose_name = "Log de Entrega de Email"
        verbose_name_plural = "Logs de Entrega de Email"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.get_log_type_display()} - {self.recipient.email} ({self.timestamp})"


class EmailBlacklist(models.Model):
    """Lista negra de emails para prevención de spam"""
    
    BLACKLIST_REASON_CHOICES = [
        ('hard_bounce', 'Rebote duro'),
        ('spam_complaint', 'Queja de spam'),
        ('unsubscribe', 'Desuscripción'),
        ('invalid_email', 'Email inválido'),
        ('domain_blocked', 'Dominio bloqueado'),
        ('manual_block', 'Bloqueo manual'),
        ('suspicious_activity', 'Actividad sospechosa'),
    ]
    
    email = models.EmailField(unique=True, verbose_name="Email")
    reason = models.CharField(max_length=20, choices=BLACKLIST_REASON_CHOICES, verbose_name="Razón del bloqueo")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Agregado en")
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Agregado por")
    
    # Información adicional
    notes = models.TextField(blank=True, verbose_name="Notas")
    domain = models.CharField(max_length=100, verbose_name="Dominio")
    
    # Control de reactivación
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Expira en")
    
    class Meta:
        verbose_name = "Email en Lista Negra"
        verbose_name_plural = "Emails en Lista Negra"
        ordering = ['-added_at']
    
    def __str__(self):
        return f"{self.email} ({self.get_reason_display()})"
    
    def save(self, *args, **kwargs):
        if '@' in self.email:
            self.domain = self.email.split('@')[1].lower()
        super().save(*args, **kwargs)


# ============================================================================
# MODELOS CRM - HISTORIAL DE SERVICIOS
# ============================================================================

class ServiceHistory(models.Model):
    """
    Historial de servicios históricos importados (2020-2024)
    Conecta con la tabla crm_service_history en la base de datos.
    """
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='historial_servicios',
        verbose_name="Cliente"
    )
    reserva_id = models.CharField(max_length=50, blank=True, verbose_name="ID Reserva")
    service_type = models.CharField(max_length=100, verbose_name="Tipo de Servicio")  # Tinas, Masajes, Cabañas
    service_name = models.CharField(max_length=200, verbose_name="Nombre del Servicio")
    service_date = models.DateField(verbose_name="Fecha del Servicio")
    quantity = models.IntegerField(default=1, verbose_name="Cantidad")
    price_paid = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio Pagado")
    season = models.CharField(max_length=50, blank=True, verbose_name="Estación")  # Verano, Otoño, Invierno, Primavera
    year = models.IntegerField(null=True, blank=True, verbose_name="Año")

    class Meta:
        db_table = 'crm_service_history'  # Usa la tabla existente
        managed = False  # Django no crea/modifica esta tabla
        ordering = ['-service_date']
        verbose_name = "Servicio Histórico"
        verbose_name_plural = "Servicios Históricos"

    def __str__(self):
        return f"{self.cliente.nombre} - {self.service_name} ({self.service_date})"

    def get_categoria_display(self):
        """Retorna categoría normalizada"""
        return self.service_type.title()

    @property
    def is_recent(self):
        """Verifica si el servicio es de los últimos 6 meses"""
        from datetime import datetime, timedelta
        six_months_ago = datetime.now().date() - timedelta(days=180)
        return self.service_date >= six_months_ago


# ============================================================================
# MODELOS CRM - ASUNTOS DE EMAIL VARIABLES
# ============================================================================

class EmailSubjectTemplate(models.Model):
    """
    Templates de asuntos para emails personalizados
    Permite variedad para evitar detección de spam
    """
    ESTILO_CHOICES = [
        ('formal', 'Formal/Profesional'),
        ('calido', 'Cálido/Emocional'),
        ('ambos', 'Ambos Estilos'),
    ]
    
    subject_template = models.CharField(
        max_length=200,
        verbose_name="Asunto del Email",
        help_text="Usa {nombre} para insertar el nombre del cliente. Ej: '{nombre}, tenemos algo especial para ti'"
    )
    estilo = models.CharField(
        max_length=10,
        choices=ESTILO_CHOICES,
        default='calido',
        verbose_name="Estilo de Email"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Desmarcar para desactivar este asunto temporalmente"
    )
    veces_usado = models.IntegerField(
        default=0,
        verbose_name="Veces Usado",
        help_text="Contador automático de cuántas veces se ha usado"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    
    class Meta:
        ordering = ['estilo', '-activo', 'veces_usado']
        verbose_name = "Asunto de Email"
        verbose_name_plural = "Asuntos de Email"
    
    def __str__(self):
        return f"{self.subject_template} ({self.get_estilo_display()})"
    
    @classmethod
    def get_random_subject(cls, estilo='calido', nombre_cliente=''):
        """
        Obtiene un asunto aleatorio para el estilo especificado
        
        Args:
            estilo: 'formal' o 'calido'
            nombre_cliente: Nombre del cliente para reemplazar {nombre}
        
        Returns:
            String con el asunto personalizado
        """
        # Buscar templates activos del estilo o que sirvan para ambos
        templates = cls.objects.filter(
            activo=True
        ).filter(
            models.Q(estilo=estilo) | models.Q(estilo='ambos')
        )
        
        if templates.exists():
            # Seleccionar uno al azar (priorizando los menos usados)
            # Ordenar por veces_usado y tomar uno de los 5 menos usados al azar
            least_used = list(templates.order_by('veces_usado')[:5])
            selected = random.choice(least_used)
            
            # Incrementar contador
            selected.veces_usado += 1
            selected.save(update_fields=['veces_usado'])
            
            # Reemplazar {nombre} con el nombre del cliente
            nombre = nombre_cliente.split()[0] if nombre_cliente else ''
            subject = selected.subject_template.replace('{nombre}', nombre)
            
            return subject
        else:
            # Fallback a asuntos default si no hay en la base de datos
            return cls._get_default_subject(estilo, nombre_cliente)
    
    @staticmethod
    def _get_default_subject(estilo='calido', nombre_cliente=''):
        """
        Asuntos default si no hay en la base de datos
        """
        nombre = nombre_cliente.split()[0] if nombre_cliente else 'amigo'
        
        if estilo == 'calido':
            subjects = [
                f"{nombre}, tenemos buenas noticias para ti",
                f"{nombre}, algo especial te espera en Aremko",
                f"Hola {nombre}, te extrañamos",
                f"{nombre}, un regalo especial para ti",
                f"¡{nombre}! Tu momento de relax te está esperando",
                f"{nombre}, vuelve a disfrutar de la naturaleza",
                f"Una sorpresa para ti, {nombre}",
                f"{nombre}, ¿cuándo vuelves a visitarnos?",
                f"Tenemos un detalle especial para ti, {nombre}",
                f"{nombre}, tu escape perfecto te espera",
                f"Hola {nombre}, reservamos algo para ti",
                f"{nombre}, es hora de relajarte de nuevo",
                f"¡{nombre}! Beneficios exclusivos para ti",
                f"{nombre}, te recordamos con cariño",
                f"Un mensaje especial para ti, {nombre}",
                f"{nombre}, ven a renovar tu energía",
                f"Hola {nombre}, te tenemos presente",
                f"{nombre}, vuelve a conectar con la naturaleza",
                f"Tu bienestar es importante, {nombre}",
                f"{nombre}, momentos únicos te esperan",
                f"¡{nombre}! Oferta especial solo para ti",
                f"Hola {nombre}, pensamos en ti",
                f"{nombre}, tu próxima aventura te llama",
                f"Un beneficio exclusivo para ti, {nombre}",
                f"{nombre}, te invitamos a desconectar",
                f"¡{nombre}! Descubre lo que preparamos para ti",
                f"Hola {nombre}, hora de mimarte",
                f"{nombre}, tu refugio natural te espera",
                f"Algo especial preparado para ti, {nombre}",
                f"{nombre}, vuelve a enamorarte de Aremko",
            ]
        else:  # formal
            subjects = [
                f"Propuesta Personalizada para {nombre}",
                f"Oferta Exclusiva - {nombre}",
                f"Recomendaciones Especiales - Aremko",
                f"Beneficios Personalizados para Usted",
                f"Su Próxima Experiencia en Aremko",
                f"Propuesta de Valor Especial",
                f"Servicios Recomendados - {nombre}",
                f"Oferta Limitada - Aremko Spa",
                f"Experiencia Premium Personalizada",
                f"Plan Especial para {nombre}",
            ]
        
        return random.choice(subjects)



# ============================================================================
# MODELOS CRM - TEMPLATES DE CONTENIDO DE EMAIL EDITABLES
# ============================================================================

class EmailContentTemplate(models.Model):
    """
    Templates editables para el contenido de los emails de propuestas
    Permite personalizar cada sección del email desde el admin
    """
    ESTILO_CHOICES = [
        ('formal', 'Formal/Profesional'),
        ('calido', 'Cálido/Emocional'),
    ]
    
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre del Template",
        help_text="Ej: 'Template Cálido Primavera 2025'"
    )
    estilo = models.CharField(
        max_length=10,
        choices=ESTILO_CHOICES,
        verbose_name="Estilo de Email"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Solo se usa el template activo de cada estilo"
    )
    
    # Estructura del email
    saludo = models.TextField(
        verbose_name="Saludo",
        help_text="Usa {nombre} para el nombre del cliente. Ej: 'Hola {nombre},'",
        default="Hola {nombre},"
    )
    
    introduccion = models.TextField(
        verbose_name="Introducción",
        help_text="Texto de apertura. Usa {servicios_narrativa} para la narrativa del historial.",
        default="Espero que te encuentres muy bien."
    )
    
    seccion_ofertas_titulo = models.CharField(
        max_length=200,
        verbose_name="Título de Ofertas",
        default="Oferta Especial"
    )
    
    seccion_ofertas_intro = models.TextField(
        verbose_name="Introducción de Ofertas",
        help_text="Texto antes de mostrar las ofertas. Usa {mes_actual} para el mes.",
        default="Este mes tenemos algo especial para ti:"
    )
    
    oferta_texto = models.TextField(
        verbose_name="Texto de Ofertas",
        help_text="Usa {oferta_porcentaje} y {oferta_servicios} para ofertas dinámicas.",
        default="{oferta_porcentaje} de descuento en {oferta_servicios}"
    )
    
    call_to_action_texto = models.CharField(
        max_length=200,
        verbose_name="Texto del Botón CTA",
        default="Reservar Ahora"
    )
    
    cierre = models.TextField(
        verbose_name="Cierre/Despedida",
        help_text="Texto de cierre del email.",
        default="¡Esperamos verte pronto!"
    )
    
    firma = models.TextField(
        verbose_name="Firma",
        default="Equipo Aremko\nPuerto Varas, Chile"
    )
    
    # Estilos CSS personalizables
    color_principal = models.CharField(
        max_length=7,
        verbose_name="Color Principal",
        default="#2c5530",
        help_text="Color hexadecimal (ej: #2c5530)"
    )
    
    color_secundario = models.CharField(
        max_length=7,
        verbose_name="Color Secundario",
        default="#8B7355",
        help_text="Color hexadecimal (ej: #8B7355)"
    )
    
    fuente_tipografia = models.CharField(
        max_length=100,
        verbose_name="Tipografía",
        default="Georgia, serif",
        help_text="Fuente CSS (ej: 'Georgia, serif' o 'Arial, sans-serif')"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Creado por"
    )
    
    class Meta:
        ordering = ['estilo', '-activo', '-updated_at']
        verbose_name = "Template de Email"
        verbose_name_plural = "Templates de Email"
    
    def __str__(self):
        return f"{self.nombre} ({self.get_estilo_display()}) {'✓' if self.activo else '✗'}"
    
    @classmethod
    def get_active_template(cls, estilo='calido'):
        """
        Obtiene el template activo para el estilo especificado
        """
        try:
            return cls.objects.filter(estilo=estilo, activo=True).latest('updated_at')
        except cls.DoesNotExist:
            return None
    
    def safe_format(self, text, context):
        """
        Reemplaza placeholders de forma segura, ignorando llaves que no son placeholders

        Args:
            text: Texto con posibles placeholders {variable}
            context: Dict con valores para reemplazar

        Returns:
            Texto con placeholders reemplazados, llaves no-placeholders intactas
        """
        import re

        # Solo reemplazar placeholders que existen en el context
        def replacer(match):
            key = match.group(1)
            return str(context.get(key, match.group(0)))

        # Buscar solo placeholders válidos (nombres de variables Python)
        pattern = r'\{(\w+)\}'
        return re.sub(pattern, replacer, text)

    def render_email(self, context):
        """
        Renderiza el email completo usando el template y el contexto

        Args:
            context: Dict con variables como:
                - nombre: Nombre del cliente
                - servicios_narrativa: Texto generado del historial
                - ofertas: Dict con porcentajes y servicios
                - mes_actual: Nombre del mes actual

        Returns:
            String con HTML completo del email
        """
        # Reemplazar placeholders en cada sección de forma segura
        saludo = self.safe_format(self.saludo, context)
        introduccion = self.safe_format(self.introduccion, context)
        ofertas_intro = self.safe_format(self.seccion_ofertas_intro, context)
        oferta_texto = self.safe_format(self.oferta_texto, context)
        cierre = self.safe_format(self.cierre, context)
        firma = self.firma
        
        # Construir HTML completo
        html = f"""
        <html>
        <body style="font-family: {self.fuente_tipografia}; line-height: 1.8; color: #333; background-color: #fafafa;">
            <div style="max-width: 600px; margin: 0 auto; padding: 30px 20px; background-color: #ffffff;">
                <h2 style="color: {self.color_principal}; font-weight: 400; margin-bottom: 20px;">{saludo}</h2>
                
                <p style="font-size: 16px; line-height: 1.8; margin-bottom: 20px;">
                    {introduccion}
                </p>
                
                <p style="font-size: 16px; line-height: 1.8; margin-bottom: 25px;">
                    {ofertas_intro}
                </p>
                
                <div style="background-color: #f8f5f0; border-left: 4px solid {self.color_secundario}; padding: 20px; margin: 25px 0;">
                    <p style="font-size: 16px; line-height: 1.8; margin: 0;">
                        {oferta_texto}
                    </p>
                </div>
                
                <div style="text-align: center; margin: 35px 0;">
                    <a href="https://www.aremko.cl" style="display: inline-block; background-color: {self.color_principal}; color: white; padding: 14px 40px; text-decoration: none; border-radius: 4px; font-size: 16px; font-weight: 500;">{self.call_to_action_texto}</a>
                </div>
                
                <p style="font-size: 16px; line-height: 1.8; margin-bottom: 25px;">
                    {cierre}
                </p>
                
                <p style="font-size: 15px; line-height: 1.7; color: #666; margin-top: 40px; border-top: 1px solid #e0e0e0; padding-top: 20px;">
                    {firma.replace(chr(10), '<br>')}
                </p>
            </div>
        </body>
        </html>
        """
        
        return html.strip()

