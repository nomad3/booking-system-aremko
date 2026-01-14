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
import re
from django.db.models import Sum, F, DecimalField, FloatField # Added DecimalField, FloatField
from django.db.models.functions import Coalesce # Coalesce es una función de DB
from solo.models import SingletonModel # Added import for django-solo

class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    # Campos para sistema de pagos a masajistas
    porcentaje_comision = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=40.00,
        help_text='Porcentaje de comisión del proveedor (ej: 40.00 para 40%)',
        verbose_name='Porcentaje Comisión'
    )
    es_masajista = models.BooleanField(
        default=False,
        help_text='Indica si este proveedor es un masajista',
        verbose_name='Es Masajista'
    )
    rut = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        help_text='RUT del proveedor para efectos tributarios',
        verbose_name='RUT'
    )
    banco = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Banco para transferencias',
        verbose_name='Banco'
    )
    tipo_cuenta = models.CharField(
        max_length=20,
        choices=[
            ('corriente', 'Cuenta Corriente'),
            ('vista', 'Cuenta Vista'),
            ('ahorro', 'Cuenta de Ahorro'),
            ('rut', 'Cuenta RUT'),
        ],
        blank=True,
        null=True,
        verbose_name='Tipo de Cuenta'
    )
    numero_cuenta = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='Número de cuenta bancaria',
        verbose_name='Número de Cuenta'
    )

    def __str__(self):
        return self.nombre

    def get_servicios_pendientes_pago(self):
        """Obtiene los servicios pendientes de pago para este masajista"""
        # No necesitamos importar ReservaServicio porque está en el mismo archivo
        return self.reservas_asignadas.filter(
            venta_reserva__estado_pago='pagado',
            pagado_a_proveedor=False
        ).order_by('fecha_agendamiento')

    def calcular_monto_pendiente(self):
        """Calcula el monto total pendiente de pago (con retención aplicada)"""
        from decimal import Decimal
        servicios = self.get_servicios_pendientes_pago()
        total = Decimal('0')
        for servicio in servicios:
            precio_servicio = servicio.calcular_precio()
            monto_masajista = precio_servicio * (self.porcentaje_comision / 100)
            monto_con_retencion = monto_masajista * Decimal('0.855')  # Aplicar retención del 14.5%
            total += monto_con_retencion
        return total


class CategoriaProducto(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    # Campos existentes
    nombre = models.CharField(max_length=100)
    precio_base = models.DecimalField(max_digits=10, decimal_places=0)
    cantidad_disponible = models.PositiveIntegerField()
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True)
    categoria = models.ForeignKey(CategoriaProducto, on_delete=models.SET_NULL, null=True)

    # Campos para publicación web (todos opcionales para migración segura)
    publicado_web = models.BooleanField(
        default=False,
        verbose_name="Publicado en Web",
        help_text="Marcar para mostrar este producto en el catálogo web público"
    )
    descripcion_web = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción Web",
        help_text="Descripción detallada del producto para mostrar en la web (ingredientes, preparación, etc.)"
    )
    imagen = models.ImageField(
        upload_to='productos/',
        blank=True,
        null=True,
        verbose_name="Imagen",
        help_text="Foto del producto para el catálogo web"
    )
    orden = models.IntegerField(
        default=0,
        verbose_name="Orden",
        help_text="Orden de visualización en el catálogo (menor número = primero)"
    )

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

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
        ('booking', 'booking'),
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
    fecha_emision = models.DateField(default=timezone.now, db_index=True)
    fecha_vencimiento = models.DateField()
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='por_cobrar', db_index=True)
    cliente_comprador = models.ForeignKey('Cliente', related_name='giftcards_compradas', on_delete=models.SET_NULL, null=True, blank=True)
    cliente_destinatario = models.ForeignKey('Cliente', related_name='giftcards_recibidas', on_delete=models.SET_NULL, null=True, blank=True)

    # Relación con la venta/reserva donde se compró esta GiftCard
    venta_reserva = models.ForeignKey('VentaReserva', related_name='giftcards', on_delete=models.SET_NULL, null=True, blank=True)

    # Datos del comprador (campos directos para wizard - ahora opcionales ya que se capturan en checkout)
    comprador_nombre = models.CharField(max_length=255, null=True, blank=True)
    comprador_email = models.EmailField(null=True, blank=True)
    comprador_telefono = models.CharField(max_length=20, null=True, blank=True)

    # Datos del destinatario (para mensajes personalizados)
    destinatario_nombre = models.CharField(max_length=255, null=True, blank=True)
    destinatario_email = models.EmailField(null=True, blank=True)
    destinatario_telefono = models.CharField(max_length=20, null=True, blank=True)
    destinatario_relacion = models.CharField(max_length=100, null=True, blank=True)  # ej: "pareja", "amigo", "madre"
    detalle_especial = models.TextField(null=True, blank=True)

    # Configuración de mensaje IA
    tipo_mensaje = models.CharField(max_length=50, null=True, blank=True)  # ej: "romantico", "cumpleanos"
    mensaje_personalizado = models.TextField(null=True, blank=True)
    mensaje_alternativas = models.JSONField(default=list, null=True, blank=True)

    # Servicio asociado (opcional)
    servicio_asociado = models.CharField(max_length=100, null=True, blank=True)

    # Control de envío de comunicaciones
    enviado_email = models.BooleanField(default=False, null=True, blank=True)
    enviado_whatsapp = models.BooleanField(default=False, null=True, blank=True)

    def __str__(self):
        return f"GiftCard {self.codigo} - Saldo: {self.monto_disponible}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.generar_codigo_unico()
        # FIXED: Verificar si es None específicamente, no si es falsy
        # Esto permite guardar monto_disponible = 0 (GiftCard completamente usada)
        if self.monto_disponible is None:
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


class SEOContent(models.Model):
    """
    Modelo para gestionar contenido SEO para cada categoría de servicio.
    Incluye meta tags, contenido principal, FAQs y Schema.org data.
    """
    categoria = models.OneToOneField(
        CategoriaServicio,
        on_delete=models.CASCADE,
        related_name='seo_content'
    )

    # Meta tags SEO
    meta_title = models.CharField(
        max_length=70,
        help_text="Título SEO (máx. 70 caracteres)"
    )
    meta_description = models.CharField(
        max_length=160,
        help_text="Meta descripción SEO (máx. 160 caracteres)"
    )

    # Contenido principal de la página
    contenido_principal = models.TextField(
        help_text="Texto principal de la categoría (180-300 palabras)"
    )
    subtitulo_principal = models.CharField(
        max_length=200,
        blank=True,
        help_text="Subtítulo descriptivo para la categoría"
    )

    # Sección de beneficios/características
    beneficio_1_titulo = models.CharField(max_length=100, blank=True)
    beneficio_1_descripcion = models.TextField(blank=True)
    beneficio_2_titulo = models.CharField(max_length=100, blank=True)
    beneficio_2_descripcion = models.TextField(blank=True)
    beneficio_3_titulo = models.CharField(max_length=100, blank=True)
    beneficio_3_descripcion = models.TextField(blank=True)

    # FAQs (Preguntas frecuentes)
    faq_1_pregunta = models.CharField(max_length=200, blank=True)
    faq_1_respuesta = models.TextField(blank=True)
    faq_2_pregunta = models.CharField(max_length=200, blank=True)
    faq_2_respuesta = models.TextField(blank=True)
    faq_3_pregunta = models.CharField(max_length=200, blank=True)
    faq_3_respuesta = models.TextField(blank=True)
    faq_4_pregunta = models.CharField(max_length=200, blank=True)
    faq_4_respuesta = models.TextField(blank=True)
    faq_5_pregunta = models.CharField(max_length=200, blank=True)
    faq_5_respuesta = models.TextField(blank=True)
    faq_6_pregunta = models.CharField(max_length=200, blank=True)
    faq_6_respuesta = models.TextField(blank=True)

    # Keywords para Schema.org
    keywords = models.CharField(
        max_length=255,
        blank=True,
        help_text="Palabras clave separadas por comas"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contenido SEO"
        verbose_name_plural = "Contenidos SEO"

    def __str__(self):
        return f"SEO: {self.categoria.nombre}"

    def get_faqs(self):
        """Retorna las FAQs como una lista de diccionarios para facilitar el uso en templates."""
        faqs = []
        for i in range(1, 7):
            pregunta = getattr(self, f'faq_{i}_pregunta', '')
            respuesta = getattr(self, f'faq_{i}_respuesta', '')
            if pregunta and respuesta:
                faqs.append({
                    'pregunta': pregunta,
                    'respuesta': respuesta
                })
        return faqs

    def get_beneficios(self):
        """Retorna los beneficios como una lista de diccionarios."""
        beneficios = []
        for i in range(1, 4):
            titulo = getattr(self, f'beneficio_{i}_titulo', '')
            descripcion = getattr(self, f'beneficio_{i}_descripcion', '')
            if titulo and descripcion:
                beneficios.append({
                    'titulo': titulo,
                    'descripcion': descripcion
                })
        return beneficios

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
    max_servicios_simultaneos = models.PositiveIntegerField(
        default=1,
        verbose_name="Máximo de servicios simultáneos por slot",
        help_text="Cantidad máxima de veces que este servicio se puede reservar en el mismo horario (default: 1). Usar 2 para masajes que permiten reservas simultáneas."
    )
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
    visible_en_matriz = models.BooleanField(
        default=True,
        verbose_name="Visible en Calendario Matriz",
        help_text="Marcar si este servicio debe aparecer en el calendario matriz de disponibilidad."
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

    informacion_adicional = models.TextField(
        blank=True,
        verbose_name="Información Adicional para Resumen",
        help_text="Información específica del servicio que se incluirá en el resumen de reserva (ej: equipamiento de cabaña, características especiales)."
    )

    def __str__(self):
        return self.nombre

    def horario_valido(self, hora_propuesta):
        return hora_propuesta in self.slots_disponibles


# ============================================
# MODELS DE UBICACIÓN GEOGRÁFICA
# ============================================

class Region(models.Model):
    """
    Regiones oficiales de Chile.

    Chile tiene 16 regiones administrativas, cada una con un código romano
    y un nombre oficial.
    """
    codigo = models.CharField(
        max_length=10,
        unique=True,
        help_text="Código de la región (ej: 'RM', 'X', 'XIV')"
    )
    nombre = models.CharField(
        max_length=100,
        help_text="Nombre oficial de la región"
    )
    orden = models.PositiveIntegerField(
        default=0,
        help_text="Orden de visualización (de norte a sur)"
    )

    class Meta:
        ordering = ['orden']
        verbose_name = "Región"
        verbose_name_plural = "Regiones"

    def __str__(self):
        return f"{self.nombre}"


class Comuna(models.Model):
    """
    Comunas de Chile agrupadas por región.

    Chile tiene 346 comunas distribuidas en 16 regiones.
    """
    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name='comunas',
        help_text="Región a la que pertenece esta comuna"
    )
    nombre = models.CharField(
        max_length=100,
        help_text="Nombre oficial de la comuna"
    )
    codigo = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="Código de la comuna (opcional)"
    )

    class Meta:
        ordering = ['region__orden', 'nombre']
        verbose_name = "Comuna"
        verbose_name_plural = "Comunas"
        unique_together = [['region', 'nombre']]

    def __str__(self):
        return f"{self.nombre}, {self.region.nombre}"


class Cliente(models.Model):
    nombre = models.CharField(max_length=100, db_index=True)
    email = models.EmailField(blank=True, null=True, db_index=True) # Allow blank email if phone is primary
    telefono = models.CharField(max_length=20, unique=True, help_text="Número de teléfono único (formato internacional preferido)") # Add unique=True
    documento_identidad = models.CharField(max_length=100, null=True, blank=True, verbose_name="ID/DNI/Passport/RUT")
    pais = models.CharField(max_length=100, null=True, blank=True)

    # Ubicación (campos legacy y nuevos)
    ciudad = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Campo legacy de ciudad (texto libre). Se recomienda usar región + comuna."
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clientes',
        help_text="Región de Chile"
    )
    comuna = models.ForeignKey(
        Comuna,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clientes',
        help_text="Comuna de Chile"
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    @staticmethod
    def normalize_phone(phone_str):
        """
        Normaliza número de teléfono usando servicio centralizado
        Mantiene compatibilidad con código existente
        """
        from .services.phone_service import PhoneService
        return PhoneService.normalize_phone(phone_str)

    def save(self, *args, **kwargs):
        """
        Override save para normalizar teléfono antes de guardar
        """
        if self.telefono:
            normalized = self.normalize_phone(self.telefono)
            if normalized:
                self.telefono = normalized
            else:
                raise ValidationError(f"Formato de teléfono inválido: {self.telefono}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} - {self.telefono}"

    def numero_visitas(self):
        """Calcula el número de visitas (VentaReserva) asociadas a este cliente."""
        return self.ventareserva_set.count() # Assumes default related_name

    def gasto_total(self):
        """
        Calcula el gasto total de este cliente basado en VentaReserva + ServiceHistory.
        Solo cuenta ventas con estado_pago 'pagado' o 'parcial' para consistencia
        con la segmentación de clientes.
        Incluye servicios históricos importados desde CSV.
        """
        # Gasto actual (ventas del sistema)
        gasto_actual = self.ventareserva_set.filter(
            estado_pago__in=['pagado', 'parcial']
        ).aggregate(total_gastado=Sum('total'))['total_gastado'] or 0
        
        # Gasto histórico (servicios importados)
        try:
            from ventas.models import ServiceHistory
            gasto_historico = ServiceHistory.objects.filter(
                cliente=self,
                service_date__gt='2021-01-01'  # Excluir placeholder dates
            ).aggregate(total_gastado=Sum('price_paid'))['total_gastado'] or 0
        except Exception:
            # Si la tabla no existe o hay error, solo usar gasto actual
            gasto_historico = 0
        
        return float(gasto_actual) + float(gasto_historico)


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
        # OPTIMIZACIÓN: Usar precios congelados (precio_unitario_venta) si existen,
        # sino usar precio actual del catálogo (precio_base) como fallback

        # Para productos: usar precio_unitario_venta si existe, sino precio_base
        total_productos = self.reservaproductos.aggregate(
            total=models.Sum(
                Coalesce(models.F('precio_unitario_venta'), models.F('producto__precio_base')) * models.F('cantidad')
            )
        )['total'] or 0

        # Para servicios: usar precio_unitario_venta si existe, sino precio_base
        # IMPORTANTE: Las cabañas tienen precio fijo (no se multiplican por cantidad_personas)
        # Otros servicios (tinas, masajes) sí se multiplican por cantidad_personas
        from django.db.models import Case, When, Value, IntegerField

        total_servicios = self.reservaservicios.aggregate(
            total=models.Sum(
                Coalesce(models.F('precio_unitario_venta'), models.F('servicio__precio_base')) *
                Case(
                    # Si es cabaña, multiplicar por 1 (precio fijo)
                    When(servicio__tipo_servicio='cabana', then=Value(1)),
                    # Si no es cabaña, multiplicar por cantidad_personas
                    default=models.F('cantidad_personas'),
                    output_field=IntegerField()
                )
            )
        )['total'] or 0

        total_giftcards = self.giftcards.aggregate(total=models.Sum('monto_inicial'))['total'] or 0
        total_pagos_descuentos = self.pagos.filter(metodo_pago='descuento').aggregate(total=models.Sum('monto'))['total'] or 0

        self.total = total_productos + total_servicios + total_giftcards - total_pagos_descuentos
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
        # Usar precio congelado si existe, sino precio actual del catálogo
        # IMPORTANTE: Las cabañas tienen precio fijo (no se multiplican por cantidad_personas)
        from django.db.models import Case, When, Value, IntegerField

        total = self.reservaservicios.aggregate(
            total=models.Sum(
                Coalesce(models.F('precio_unitario_venta'), models.F('servicio__precio_base')) *
                Case(
                    # Si es cabaña, multiplicar por 1 (precio fijo)
                    When(servicio__tipo_servicio='cabana', then=Value(1)),
                    # Si no es cabaña, multiplicar por cantidad_personas
                    default=models.F('cantidad_personas'),
                    output_field=IntegerField()
                )
            )
        )['total'] or 0
        return total

    @property
    def total_productos(self):
        # Usar precio congelado si existe, sino precio actual del catálogo
        total = self.reservaproductos.aggregate(
            total=models.Sum(
                Coalesce(models.F('precio_unitario_venta'), models.F('producto__precio_base')) * models.F('cantidad')
            )
        )['total'] or 0
        return total

    @property
    def total_giftcards(self):
        total = self.giftcards.aggregate(
            total=models.Sum('monto_inicial')
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
        ('booking', 'booking'),
    ]

    venta_reserva = models.ForeignKey(VentaReserva, related_name='pagos', on_delete=models.CASCADE)
    fecha_pago = models.DateTimeField(default=timezone.now)
    monto = models.DecimalField(max_digits=10, decimal_places=0)
    metodo_pago = models.CharField(max_length=100, choices=METODOS_PAGO, db_index=True)
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
    fecha_entrega = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Entrega",
        help_text="Fecha en que el producto fue/será entregado al cliente. Si está vacío, se asume la fecha del primer servicio de la reserva."
    )
    precio_unitario_venta = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Precio Unitario de Venta",
        help_text="Precio del producto al momento de agregarlo a la reserva. Si está vacío, se usa el precio_base actual del producto."
    )

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} en Venta/Reserva #{self.venta_reserva.id}"

    def mostrar_valor_unitario(self):
        """Muestra el valor unitario del producto formateado."""
        # Usar precio congelado si existe, sino usar precio actual del catálogo
        valor = self.precio_unitario_venta if self.precio_unitario_venta else self.producto.precio_base
        return f"${valor:,.0f}".replace(',', '.')
    mostrar_valor_unitario.short_description = 'Valor Unitario'

    def mostrar_valor_total(self):
        """Muestra el valor total calculado formateado."""
        # Usar precio congelado si existe, sino usar precio actual del catálogo
        precio = self.precio_unitario_venta if self.precio_unitario_venta else self.producto.precio_base
        valor = precio * self.cantidad
        return f"${valor:,.0f}".replace(',', '.')
    mostrar_valor_total.short_description = 'Valor Total'

class ReservaServicio(models.Model):
    venta_reserva = models.ForeignKey(VentaReserva, on_delete=models.CASCADE, related_name='reservaservicios')
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    fecha_agendamiento = models.DateField()
    hora_inicio = models.CharField(max_length=5)
    # Default to 1, but enforce max 2 for cabins during booking if needed
    cantidad_personas = models.PositiveIntegerField(
        default=1,
        verbose_name='Cantidad',
        help_text='Para cabañas: cantidad de cabañas (siempre 1). Para tinas: cantidad de personas.'
    )
    # Add field to link specific provider for this instance (e.g., masseuse)
    proveedor_asignado = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservas_asignadas',
        help_text="Proveedor específico asignado para esta reserva (ej. masajista)."
    )
    precio_unitario_venta = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Precio Unitario de Venta",
        help_text="Precio del servicio al momento de agregarlo a la reserva. Si está vacío, se usa el precio_base actual del servicio."
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

    def mostrar_valor_unitario(self):
        """Muestra el valor unitario del servicio formateado."""
        # Usar precio congelado si existe, sino usar precio actual del catálogo
        valor = self.precio_unitario_venta if self.precio_unitario_venta else self.servicio.precio_base
        return f"${valor:,.0f}".replace(',', '.')
    mostrar_valor_unitario.short_description = 'Valor Unitario'

    def mostrar_valor_total(self):
        """Muestra el valor total calculado formateado."""
        # Usar precio congelado si existe, sino calcular con precio actual
        if self.precio_unitario_venta:
            # Usar precio congelado
            if self.servicio.tipo_servicio == 'cabana':
                valor = self.precio_unitario_venta  # Precio fijo para cabañas
            else:
                valor = self.precio_unitario_venta * self.cantidad_personas
        else:
            # Fallback: calcular con precio actual del catálogo
            valor = self.calcular_precio()
        return f"${valor:,.0f}".replace(',', '.')
    mostrar_valor_total.short_description = 'Valor Total'

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

    # Campos para sistema de pagos a masajistas
    pagado_a_proveedor = models.BooleanField(
        default=False,
        verbose_name='Pagado al Proveedor',
        help_text='Indica si el servicio ya fue pagado al proveedor/masajista'
    )
    pago_proveedor = models.ForeignKey(
        'PagoMasajista',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='servicios_incluidos',
        verbose_name='Pago Asociado',
        help_text='Pago en el que se incluyó este servicio'
    )

    # Consider adding validation in save() as well if needed, clean() isn't called automatically everywhere.


# --- Modelos para Sistema de Pagos a Masajistas ---

class PagoMasajista(models.Model):
    """Registro de pagos realizados a masajistas"""
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.CASCADE,
        related_name='pagos',
        verbose_name='Masajista'
    )
    fecha_pago = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Pago'
    )
    periodo_inicio = models.DateField(
        verbose_name='Periodo Inicio',
        help_text='Fecha inicio del periodo a pagar'
    )
    periodo_fin = models.DateField(
        verbose_name='Periodo Fin',
        help_text='Fecha fin del periodo a pagar'
    )
    monto_bruto = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name='Monto Bruto',
        help_text='Total antes de descuentos'
    )
    porcentaje_retencion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=14.5,
        verbose_name='% Retención',
        help_text='Porcentaje de retención de impuestos'
    )
    monto_retencion = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name='Monto Retención',
        help_text='Monto retenido por impuestos'
    )
    monto_neto = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name='Monto Neto',
        help_text='Monto pagado al masajista'
    )
    comprobante = models.ImageField(
        upload_to='pagos_masajistas/',
        verbose_name='Comprobante de Transferencia',
        help_text='Imagen del comprobante bancario'
    )
    numero_transferencia = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Número de Transferencia'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones'
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Creado por'
    )

    class Meta:
        verbose_name = 'Pago a Masajista'
        verbose_name_plural = 'Pagos a Masajistas'
        ordering = ['-fecha_pago']

    def __str__(self):
        return f"Pago a {self.proveedor.nombre} - {self.fecha_pago.strftime('%d/%m/%Y')}"

    def calcular_montos(self):
        """Calcula los montos de retención y neto basados en el monto bruto"""
        self.monto_retencion = self.monto_bruto * (self.porcentaje_retencion / 100)
        self.monto_neto = self.monto_bruto - self.monto_retencion
        return self.monto_neto

    def save(self, *args, **kwargs):
        """Sobrescribe save para calcular montos automáticamente"""
        if not self.monto_retencion or not self.monto_neto:
            self.calcular_montos()
        super().save(*args, **kwargs)


class DetalleServicioPago(models.Model):
    """Detalle de cada servicio incluido en un pago a masajista"""
    pago = models.ForeignKey(
        PagoMasajista,
        on_delete=models.CASCADE,
        related_name='detalles'
    )
    reserva_servicio = models.ForeignKey(
        ReservaServicio,
        on_delete=models.CASCADE
    )
    monto_servicio = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name='Monto del Servicio'
    )
    porcentaje_masajista = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='% Comisión',
        help_text='Porcentaje que se le pagó al masajista'
    )
    monto_masajista = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name='Monto para Masajista',
        help_text='Monto correspondiente al masajista'
    )

    class Meta:
        verbose_name = 'Detalle de Servicio en Pago'
        verbose_name_plural = 'Detalles de Servicios en Pagos'

    def __str__(self):
        return f"{self.reserva_servicio.servicio.nombre} - ${self.monto_masajista}"

    def save(self, *args, **kwargs):
        """Calcula el monto del masajista basado en el porcentaje"""
        if self.monto_servicio and self.porcentaje_masajista:
            self.monto_masajista = self.monto_servicio * (self.porcentaje_masajista / 100)
        super().save(*args, **kwargs)


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

    # Campos de Texto Editables
    # Hero Section
    hero_title = models.CharField(max_length=255, default="Desconecta y Renueva Tus Sentidos en Aremko Spa", verbose_name="Título Hero")
    hero_subtitle = models.TextField(default="Sumérgete en un oasis de tranquilidad en Puerto Varas. Descubre experiencias únicas de masajes, tinas calientes y alojamiento diseñadas para tu bienestar total.", verbose_name="Subtítulo Hero")
    hero_cta_text = models.CharField(max_length=50, default="Descubre Tu Experiencia Ideal", verbose_name="Texto Botón Hero")
    hero_cta_link = models.CharField(max_length=255, default="#servicios", verbose_name="Enlace Botón Hero")

    # Philosophy Section
    philosophy_title = models.CharField(max_length=255, default="Vive la Experiencia Aremko", verbose_name="Título Filosofía")
    philosophy_text_1 = models.TextField(default="Más que un spa, somos un refugio para el alma. En Aremko, creemos en el poder sanador de la naturaleza y la desconexión. Nuestra filosofía se centra en ofrecerte un espacio de paz donde puedas renovar tu energía, cuidar tu cuerpo y calmar tu mente.", verbose_name="Texto Filosofía 1")
    philosophy_text_2 = models.TextField(default="Desde masajes terapéuticos hasta la inmersión en nuestras tinajas calientes bajo las estrellas, cada detalle está pensado para tu máximo bienestar. Ven y descubre por qué nuestros visitantes nos eligen como su escape perfecto en Puerto Varas.", verbose_name="Texto Filosofía 2")
    philosophy_cta_text = models.CharField(max_length=50, default="Explora Nuestros Servicios", verbose_name="Texto Botón Filosofía")

    # CTA Section
    cta_title = models.CharField(max_length=255, default="¿Listo para Vivir la Experiencia Aremko?", verbose_name="Título CTA Final")
    cta_subtitle = models.TextField(default="Regálate el descanso que mereces. Elige tu masaje ideal, sumérgete en nuestras tinajas o planifica tu estancia completa. ¡Tu momento de paz te espera!", verbose_name="Subtítulo CTA Final")
    cta_button_text = models.CharField(max_length=50, default="Reservar Mi Experiencia Ahora", verbose_name="Texto Botón CTA Final")

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

class CampaignEmailTemplate(models.Model):
    """Template reutilizable para emails de campañas de marketing"""

    name = models.CharField(max_length=200, verbose_name="Nombre del template")
    description = models.TextField(blank=True, verbose_name="Descripción")

    # Contenido del template
    subject_template = models.CharField(max_length=500, verbose_name="Asunto (template)",
                                       help_text="Puedes usar {nombre_cliente} y {gasto_total}")
    body_template = models.TextField(verbose_name="Cuerpo HTML (template)",
                                     help_text="Puedes usar {nombre_cliente} y {gasto_total}")

    # Configuración
    is_default = models.BooleanField(default=False, verbose_name="Template por defecto",
                                     help_text="Solo puede haber un template por defecto")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado el")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado el")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='campaign_email_templates_created', verbose_name="Creado por")

    class Meta:
        verbose_name = "Template de Campaña Email"
        verbose_name_plural = "Templates de Campaña Email"
        ordering = ['-is_default', '-updated_at']

    def __str__(self):
        default_marker = " [POR DEFECTO]" if self.is_default else ""
        return f"{self.name}{default_marker}"

    def save(self, *args, **kwargs):
        # Si este template se marca como default, desmarcar los demás
        if self.is_default:
            CampaignEmailTemplate.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


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
        default="📱 Reservar por WhatsApp"
    )

    call_to_action_url = models.URLField(
        max_length=500,
        verbose_name="URL del Botón CTA",
        default="https://wa.me/56957902525?text=Hola%2C%20me%20gustar%C3%ADa%20reservar",
        help_text="URL completa del botón. Ej: https://wa.me/56957902525?text=..."
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
                    <a href="{self.call_to_action_url}" style="display: inline-block; background-color: #25d366; color: white; padding: 14px 40px; text-decoration: none; border-radius: 25px; font-size: 16px; font-weight: 500;">{self.call_to_action_texto}</a>
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


# ============================================================================
# SISTEMA DE TRAMOS Y PREMIOS
# ============================================================================

class Premio(models.Model):
    """
    Modelo para definir los premios disponibles en el sistema de fidelización
    """
    TIPO_CHOICES = [
        ('descuento_bienvenida', 'Descuento Bienvenida'),
        ('tinas_gratis', 'Tinas Gratis con Masajes'),
        ('noche_gratis', 'Noche de Alojamiento'),
    ]
    
    nombre = models.CharField(max_length=200, help_text="Nombre del premio")
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    descripcion_corta = models.TextField(help_text="Descripción para mostrar en emails")
    descripcion_legal = models.TextField(help_text="Términos y condiciones detallados")
    
    # Valores
    porcentaje_descuento_tinas = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="% descuento en tinas/cabañas"
    )
    porcentaje_descuento_masajes = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="% descuento en masajes"
    )
    valor_monetario = models.DecimalField(
        max_digits=10, 
        decimal_places=0, 
        null=True, 
        blank=True,
        help_text="Valor en pesos del premio (ej: vale $60,000)"
    )
    
    # Configuración
    dias_validez = models.IntegerField(default=30, help_text="Días de validez del premio")
    tramo_hito = models.IntegerField(
        null=True,
        blank=True,
        help_text="DEPRECATED: Usar tramos_validos. Tramo único antiguo"
    )
    tramos_validos = models.JSONField(
        default=list,
        blank=True,
        help_text='Lista de tramos donde aplica este premio. Ej: [5,6,7,8] para premio de tramos 5-8'
    )
    restricciones = models.JSONField(
        default=dict,
        blank=True,
        help_text='Restricciones en JSON. Ej: {"no_sabados": true, "no_acumulable": true}'
    )

    # Metadata
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Premio"
        verbose_name_plural = "Premios"
        ordering = ['tipo', 'nombre']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.nombre}"

    def obtener_rango_tramo(self):
        """
        Retorna el rango de gasto del tramo asociado a este premio
        """
        if not self.tramo_hito:
            return None, None

        from ventas.services.tramo_service import TramoService
        return TramoService.obtener_rango_tramo(self.tramo_hito)

    def descripcion_tramo(self):
        """
        Retorna descripción legible del tramo
        """
        if not self.tramo_hito:
            return "No asignado a tramo"

        min_gasto, max_gasto = self.obtener_rango_tramo()
        return f"Tramo {self.tramo_hito} (${min_gasto:,} - ${max_gasto:,})"

    def get_tramos_list(self):
        """
        Obtiene la lista de tramos válidos para este premio
        Mantiene compatibilidad con tramo_hito antiguo
        """
        if self.tramos_validos:
            return self.tramos_validos
        elif self.tramo_hito:
            return [self.tramo_hito]
        return []

    def aplica_para_tramo(self, tramo):
        """
        Verifica si este premio aplica para un tramo específico
        """
        return tramo in self.get_tramos_list()

    def descripcion_tramos_validos(self):
        """
        Retorna descripción legible de los tramos válidos
        """
        tramos = self.get_tramos_list()
        if not tramos:
            return "No asignado a tramos"

        if len(tramos) == 1:
            return f"Tramo {tramos[0]}"

        # Agrupar tramos consecutivos
        tramos_sorted = sorted(tramos)
        if tramos_sorted == list(range(tramos_sorted[0], tramos_sorted[-1] + 1)):
            return f"Tramos {tramos_sorted[0]} al {tramos_sorted[-1]}"
        else:
            return f"Tramos {', '.join(map(str, tramos_sorted))}"


class ClientePremio(models.Model):
    """
    Modelo para tracking de premios asignados a clientes
    """
    ESTADO_CHOICES = [
        ('pendiente_aprobacion', 'Pendiente Aprobación'),
        ('aprobado', 'Aprobado'),
        ('enviado', 'Email Enviado'),
        ('usado', 'Premio Usado'),
        ('expirado', 'Expirado'),
        ('cancelado', 'Cancelado'),
    ]
    
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, related_name='premios')
    premio = models.ForeignKey(Premio, on_delete=models.PROTECT)
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='pendiente_aprobacion')
    
    # Fechas
    fecha_ganado = models.DateTimeField(auto_now_add=True)
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    fecha_enviado = models.DateTimeField(null=True, blank=True)
    fecha_envio_whatsapp = models.DateTimeField(null=True, blank=True, help_text="Fecha cuando se envió por WhatsApp")
    fecha_expiracion = models.DateTimeField(help_text="Calculado automáticamente basado en días de validez")
    fecha_uso = models.DateTimeField(null=True, blank=True)
    
    # Tracking del contexto
    tramo_al_ganar = models.IntegerField(help_text="Tramo del cliente al momento de ganar el premio")
    gasto_total_al_ganar = models.DecimalField(
        max_digits=12, 
        decimal_places=0,
        help_text="Gasto total acumulado al momento de ganar"
    )
    tramo_anterior = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Tramo anterior (solo si el premio es por subida de tramo)"
    )
    
    # Email
    asunto_email = models.CharField(max_length=200, blank=True)
    cuerpo_email = models.TextField(blank=True)
    
    # Código único para validar uso
    codigo_unico = models.CharField(
        max_length=50, 
        unique=True, 
        blank=True,
        help_text="Código único para validar el uso del premio"
    )
    
    # Relación con venta donde se usó
    venta_donde_uso = models.ForeignKey(
        'VentaReserva', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='premios_usados'
    )
    
    # Notas administrativas
    notas_admin = models.TextField(blank=True, help_text="Notas internas para administración")
    
    class Meta:
        verbose_name = "Premio de Cliente"
        verbose_name_plural = "Premios de Clientes"
        ordering = ['-fecha_ganado']
        indexes = [
            models.Index(fields=['estado', 'fecha_aprobacion']),
            models.Index(fields=['cliente', 'estado']),
            models.Index(fields=['codigo_unico']),
        ]
    
    def __str__(self):
        return f"{self.cliente.nombre} - {self.premio.nombre} ({self.get_estado_display()})"
    
    def save(self, *args, **kwargs):
        # Generar código único si no existe
        if not self.codigo_unico:
            self.codigo_unico = self._generar_codigo_unico()
        
        # Calcular fecha de expiración si no existe
        if not self.fecha_expiracion and self.fecha_ganado:
            self.fecha_expiracion = self.fecha_ganado + timedelta(days=self.premio.dias_validez)
        
        super().save(*args, **kwargs)
    
    def _generar_codigo_unico(self):
        """Genera un código único alfanumérico de 12 caracteres"""
        while True:
            codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            if not ClientePremio.objects.filter(codigo_unico=codigo).exists():
                return codigo
    
    def marcar_como_usado(self, venta=None):
        """Marca el premio como usado"""
        self.estado = 'usado'
        self.fecha_uso = timezone.now()
        if venta:
            self.venta_donde_uso = venta
        self.save()
    
    def esta_vigente(self):
        """Verifica si el premio está vigente"""
        if self.estado not in ['aprobado', 'enviado']:
            return False
        if timezone.now() > self.fecha_expiracion:
            return False
        return True


class HistorialTramo(models.Model):
    """
    Modelo para tracking histórico de cambios de tramo de clientes
    """
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, related_name='historial_tramos')
    tramo_desde = models.IntegerField(help_text="Tramo anterior")
    tramo_hasta = models.IntegerField(help_text="Nuevo tramo")
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    gasto_en_momento = models.DecimalField(
        max_digits=12, 
        decimal_places=0,
        help_text="Gasto total al momento del cambio"
    )
    premio_generado = models.ForeignKey(
        ClientePremio, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Premio generado por este cambio de tramo"
    )
    
    class Meta:
        verbose_name = "Historial de Tramo"
        verbose_name_plural = "Historial de Tramos"
        ordering = ['-fecha_cambio']
        indexes = [
            models.Index(fields=['cliente', '-fecha_cambio']),
        ]
    
    def __str__(self):
        return f"{self.cliente.nombre}: Tramo {self.tramo_desde} → {self.tramo_hasta}"


class PackDescuento(models.Model):
    """
    Modelo para gestionar descuentos por paquetes de servicios
    Ejemplo: Cabaña + Tinas de domingo a jueves = $45,000 de descuento
    """
    nombre = models.CharField(
        max_length=200,
        help_text="Nombre del pack, ej: Pack Escapada Semanal"
    )
    descripcion = models.TextField(
        help_text="Descripción detallada del pack y sus beneficios"
    )
    descuento = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        help_text="Monto de descuento en pesos chilenos"
    )

    # Servicios específicos del pack
    servicios_especificos = models.ManyToManyField(
        'Servicio',
        blank=True,
        related_name='packs_descuento',
        help_text="Servicios específicos que forman este pack (ej: Cabaña Torre, Tina Puyehue)"
    )

    # Mantener para compatibilidad y packs por tipo
    TIPO_SERVICIO_CHOICES = [
        ('ALOJAMIENTO', 'Alojamiento'),
        ('TINA', 'Tinas Calientes'),
        ('MASAJE', 'Masaje'),
        ('DECORACION', 'Decoración'),
    ]

    servicios_requeridos = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de tipos de servicios requeridos (usar solo si no se especifican servicios específicos)"
    )

    usa_servicios_especificos = models.BooleanField(
        default=False,
        help_text="Si está activo, usa servicios específicos en lugar de tipos"
    )

    # Días de la semana válidos (0=Domingo, 6=Sábado)
    dias_semana_validos = models.JSONField(
        default=list,
        help_text="Lista de días válidos (0-6), ej: [0,1,2,3,4] para Dom-Jue"
    )

    # Vigencia
    activo = models.BooleanField(default=True)
    fecha_inicio = models.DateField(
        help_text="Fecha desde cuando aplica el descuento"
    )
    fecha_fin = models.DateField(
        null=True,
        blank=True,
        help_text="Fecha hasta cuando aplica el descuento (opcional)"
    )

    # Prioridad
    prioridad = models.IntegerField(
        default=0,
        help_text="Mayor número = mayor prioridad. Se aplica el de mayor prioridad si hay múltiples"
    )

    # Restricciones adicionales
    cantidad_minima_noches = models.IntegerField(
        default=1,
        help_text="Cantidad mínima de noches para alojamiento"
    )

    # CAMPO PENDIENTE DE MIGRACIÓN 0066 - NO USAR HASTA APLICAR MIGRACIÓN
    # cantidad_minima_personas = models.IntegerField(
    #     default=1,
    #     help_text="Cantidad mínima de personas por servicio para aplicar el descuento"
    # )

    misma_fecha = models.BooleanField(
        default=True,
        help_text="¿Los servicios deben ser para la misma fecha?"
    )

    class Meta:
        verbose_name = "Pack de Descuento"
        verbose_name_plural = "Packs de Descuento"
        ordering = ['-prioridad', '-descuento']
        indexes = [
            models.Index(fields=['activo', '-prioridad']),
            models.Index(fields=['fecha_inicio', 'fecha_fin']),
        ]

    def __str__(self):
        return f"{self.nombre} - ${self.descuento:,.0f}"

    def aplica_para_fecha(self, fecha):
        """Verifica si el pack aplica para una fecha específica"""
        if not self.activo:
            return False

        # Verificar vigencia
        if fecha.date() < self.fecha_inicio:
            return False
        if self.fecha_fin and fecha.date() > self.fecha_fin:
            return False

        # Verificar día de la semana
        if self.dias_semana_validos:
            # En Python: 0=Lunes, 6=Domingo, ajustar a 0=Domingo, 6=Sábado
            dia_semana = (fecha.weekday() + 1) % 7
            if dia_semana not in self.dias_semana_validos:
                return False

        return True

    def get_dias_semana_display(self):
        """Retorna los días de la semana en formato legible"""
        dias_map = {
            0: 'Dom', 1: 'Lun', 2: 'Mar', 3: 'Mié',
            4: 'Jue', 5: 'Vie', 6: 'Sáb'
        }
        if not self.dias_semana_validos:
            return "Todos los días"
        return ', '.join([dias_map.get(d, '') for d in sorted(self.dias_semana_validos)])

    def get_dias_display(self):
        """Alias para get_dias_semana_display"""
        return self.get_dias_semana_display()

    def get_servicios_requeridos_display(self):
        """Retorna lista legible de servicios requeridos"""
        if hasattr(self, 'usa_servicios_especificos') and self.usa_servicios_especificos:
            return [s.nombre for s in self.servicios_especificos.all()]
        else:
            # Convertir tipos a nombres legibles
            tipos_display = []
            for tipo in self.servicios_requeridos if self.servicios_requeridos else []:
                for choice_value, choice_label in self.TIPO_SERVICIO_CHOICES:
                    if choice_value == tipo:
                        tipos_display.append(choice_label)
                        break
            return tipos_display


class GiftCardExperiencia(models.Model):
    """
    Modelo para las experiencias disponibles en las Gift Cards.
    Migrado desde el array hardcodeado en giftcard_views.py
    """

    CATEGORIA_CHOICES = [
        ('tinas', 'Tinas y Hidromasajes'),
        ('masajes', 'Masajes'),
        ('faciales', 'Faciales'),
        ('packs', 'Packs Spa'),
        ('valor', 'Tarjetas de Valor'),
    ]

    # Identificación
    id_experiencia = models.CharField(
        max_length=50,
        unique=True,
        help_text="ID único de la experiencia (ej: 'tinas', 'masaje_relajacion')"
    )
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        db_index=True
    )

    # Información básica
    nombre = models.CharField(max_length=200)
    descripcion = models.CharField(
        max_length=500,
        help_text="Descripción corta para menú"
    )
    descripcion_giftcard = models.TextField(
        help_text="Descripción detallada para la gift card"
    )

    # Imagen
    imagen = models.ImageField(
        upload_to='giftcards/experiencias/',
        help_text="Imagen de la experiencia (recomendado: 800x600px)"
    )

    # Precios
    monto_fijo = models.IntegerField(
        null=True,
        blank=True,
        help_text="Monto fijo si la experiencia tiene un precio único (ej: $50.000)"
    )
    montos_sugeridos = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de montos sugeridos para tarjetas de valor [30000, 50000, 75000]"
    )

    # Estado
    activo = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Si está inactivo, no aparece en el wizard"
    )
    orden = models.IntegerField(
        default=0,
        help_text="Orden de aparición en la lista (menor = primero)"
    )

    # Metadatos
    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Experiencia Gift Card"
        verbose_name_plural = "Experiencias Gift Cards"
        ordering = ['categoria', 'orden', 'nombre']
        indexes = [
            models.Index(fields=['categoria', 'activo']),
            models.Index(fields=['activo', 'orden']),
        ]

    def __str__(self):
        precio = f"${self.monto_fijo:,}" if self.monto_fijo else "Valor variable"
        return f"{self.nombre} ({self.get_categoria_display()}) - {precio}"

    def tiene_monto_fijo(self):
        """Retorna True si la experiencia tiene monto fijo"""
        return self.monto_fijo is not None and self.monto_fijo > 0

    def es_tarjeta_valor(self):
        """Retorna True si es una tarjeta de valor (montos sugeridos)"""
        return bool(self.montos_sugeridos)

    def get_precio_minimo(self):
        """Retorna el precio mínimo de la experiencia"""
        if self.monto_fijo:
            return self.monto_fijo
        elif self.montos_sugeridos:
            return min(self.montos_sugeridos)
        return 0

    def to_dict(self):
        """
        Convierte el modelo a diccionario compatible con el formato
        del array hardcodeado original en giftcard_views.py
        """
        return {
            'id': self.id_experiencia,
            'categoria': self.categoria,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'descripcion_giftcard': self.descripcion_giftcard,
            'imagen': self.imagen.url if self.imagen else '',
            'monto_fijo': float(self.monto_fijo) if self.monto_fijo else None,
            'montos_sugeridos': self.montos_sugeridos or []
        }


# =============================================================================
# MODELOS PARA COTIZACIONES EMPRESARIALES
# =============================================================================

class NewsletterSubscriber(models.Model):
    """
    Modelo para gestionar suscriptores del newsletter.
    Separado de Lead para tener una gestión dedicada de marketing por email.
    """
    email = models.EmailField(unique=True, verbose_name='Email')
    first_name = models.CharField(max_length=100, blank=True, verbose_name='Nombre')
    last_name = models.CharField(max_length=100, blank=True, verbose_name='Apellido')
    subscribed_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Suscripción')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    source = models.CharField(
        max_length=50,
        default='Website Footer',
        verbose_name='Fuente',
        help_text='De dónde proviene la suscripción'
    )
    notes = models.TextField(blank=True, verbose_name='Notas')
    
    # Campos de seguimiento
    last_email_sent = models.DateTimeField(null=True, blank=True, verbose_name='Último Email Enviado')
    email_open_count = models.IntegerField(default=0, verbose_name='Emails Abiertos')
    email_click_count = models.IntegerField(default=0, verbose_name='Clicks en Emails')
    
    class Meta:
        verbose_name = 'Suscriptor Newsletter'
        verbose_name_plural = 'Suscriptores Newsletter'
        ordering = ['-subscribed_at']
    
    def __str__(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name} ({self.email})"
        return self.email
    
    def get_full_name(self):
        """Retorna el nombre completo del suscriptor"""
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.email

class CotizacionEmpresa(models.Model):
    """
    Modelo para manejar solicitudes de cotización de servicios empresariales
    desde la landing page /empresas/
    """

    SERVICIOS_CHOICES = [
        ('experiencia_completa', 'Experiencia Completa (Desayuno + Reunión + Tinas)'),
        ('desayuno_relax', 'Desayuno & Relax (Desayuno + Tinas)'),
        ('solo_tinas', 'Solo Tinas (Team Building)'),
    ]

    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('contactado', 'Contactado'),
        ('cotizado', 'Cotizado'),
        ('convertido', 'Convertido a Reserva'),
        ('rechazado', 'Rechazado'),
    ]

    # Datos de la empresa
    nombre_empresa = models.CharField(
        max_length=200,
        verbose_name="Nombre de la Empresa"
    )
    nombre_contacto = models.CharField(
        max_length=200,
        verbose_name="Nombre del Contacto"
    )
    email = models.EmailField(
        verbose_name="Email Corporativo"
    )
    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono de Contacto"
    )

    # Detalles del servicio
    servicio_interes = models.CharField(
        max_length=50,
        choices=SERVICIOS_CHOICES,
        verbose_name="Servicio de Interés"
    )
    numero_personas = models.PositiveIntegerField(
        verbose_name="Número de Personas"
    )
    fecha_tentativa = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Tentativa"
    )
    mensaje_adicional = models.TextField(
        blank=True,
        verbose_name="Mensaje Adicional"
    )

    # Estado y seguimiento
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado de la Cotización"
    )
    notas_internas = models.TextField(
        blank=True,
        verbose_name="Notas Internas (uso del equipo)"
    )

    # Metadatos
    creado = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Solicitud"
    )
    actualizado = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Actualización"
    )
    atendido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Atendido Por"
    )

    class Meta:
        verbose_name = "Cotización Empresarial"
        verbose_name_plural = "Cotizaciones Empresariales"
        ordering = ['-creado']
        indexes = [
            models.Index(fields=['estado', '-creado']),
            models.Index(fields=['fecha_tentativa']),
        ]

    def __str__(self):
        return f"{self.nombre_empresa} - {self.get_servicio_interes_display()} ({self.numero_personas} pax)"

    def get_servicio_display_corto(self):
        """Retorna nombre corto del servicio"""
        mapping = {
            'experiencia_completa': 'Exp. Completa',
            'desayuno_relax': 'Desayuno & Relax',
            'solo_tinas': 'Solo Tinas',
        }
        return mapping.get(self.servicio_interes, self.servicio_interes)

    def dias_desde_solicitud(self):
        """Retorna días transcurridos desde la solicitud"""
        delta = timezone.now() - self.creado
        return delta.days

    def es_urgente(self):
        """Marca como urgente si lleva más de 2 días sin atender"""
        return self.estado == 'pendiente' and self.dias_desde_solicitud() > 2


# =============================================================================
# MODELOS PARA SISTEMA DE CAMPAÑAS DE EMAIL VISUAL
# =============================================================================

class EmailCampaignTemplate(models.Model):
    """
    Template de campaña de email que puede ser editado visualmente
    desde el dashboard de CRM.
    """
    
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('ready', 'Lista para Envío'),
        ('sending', 'Enviando'),
        ('paused', 'Pausada'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
    ]
    
    AUDIENCE_CHOICES = [
        ('all', 'Todos los suscriptores activos'),
        ('segment', 'Segmento personalizado'),
        ('manual', 'Lista manual'),
    ]
    
    # Información básica
    name = models.CharField(
        max_length=200,
        verbose_name='Nombre de la Campaña',
        help_text='Nombre interno para identificar la campaña'
    )
    subject = models.CharField(
        max_length=500,
        verbose_name='Asunto del Email',
        help_text='Asunto que verán los destinatarios'
    )
    
    # Contenido
    html_content = models.TextField(
        verbose_name='Contenido HTML',
        help_text='Contenido del email en formato HTML'
    )
    preview_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Texto de Preview',
        help_text='Texto que aparece en la vista previa del email'
    )
    
    # Variables disponibles para personalización
    uses_personalization = models.BooleanField(
        default=True,
        verbose_name='Usa Personalización',
        help_text='Si usa variables como {{nombre}}, {{email}}, etc.'
    )
    
    # Estado y control
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='Estado'
    )
    
    # Audiencia
    audience_type = models.CharField(
        max_length=20,
        choices=AUDIENCE_CHOICES,
        default='all',
        verbose_name='Tipo de Audiencia'
    )
    
    # Segmentación (JSON para flexibilidad)
    segment_filters = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Filtros de Segmentación',
        help_text='Criterios para filtrar destinatarios (JSON)'
    )
    
    # Configuración de envío
    batch_size = models.IntegerField(
        default=25,
        verbose_name='Emails por Lote',
        help_text='Cantidad de emails a enviar por lote'
    )
    batch_delay_minutes = models.IntegerField(
        default=15,
        verbose_name='Delay entre Lotes (minutos)',
        help_text='Tiempo de espera entre cada lote de envío'
    )
    
    # Programación
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Programado para',
        help_text='Fecha y hora para iniciar el envío (null = inmediato)'
    )
    
    # Estadísticas
    total_recipients = models.IntegerField(
        default=0,
        verbose_name='Total de Destinatarios',
        help_text='Número total de destinatarios objetivo'
    )
    emails_sent = models.IntegerField(
        default=0,
        verbose_name='Emails Enviados',
        help_text='Cantidad de emails enviados exitosamente'
    )
    emails_delivered = models.IntegerField(
        default=0,
        verbose_name='Emails Entregados',
        help_text='Cantidad de emails que llegaron a destino'
    )
    emails_opened = models.IntegerField(
        default=0,
        verbose_name='Emails Abiertos',
        help_text='Cantidad de emails que fueron abiertos'
    )
    emails_clicked = models.IntegerField(
        default=0,
        verbose_name='Clicks',
        help_text='Cantidad de clicks en links del email'
    )
    emails_bounced = models.IntegerField(
        default=0,
        verbose_name='Rebotes',
        help_text='Cantidad de emails que rebotaron'
    )
    spam_complaints = models.IntegerField(
        default=0,
        verbose_name='Quejas de Spam',
        help_text='Cantidad de reportes de spam'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado el'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizado el'
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Iniciado el'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Completado el'
    )
    
    # Usuario que creó la campaña
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Creado por'
    )
    
    class Meta:
        verbose_name = 'Plantilla de Campaña de Email'
        verbose_name_plural = 'Plantillas de Campañas de Email'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def progress_percent(self):
        """Retorna el porcentaje de progreso del envío"""
        if self.total_recipients == 0:
            return 0
        return int((self.emails_sent / self.total_recipients) * 100)
    
    @property
    def open_rate(self):
        """Retorna la tasa de apertura en porcentaje"""
        if self.emails_delivered == 0:
            return 0
        return round((self.emails_opened / self.emails_delivered) * 100, 2)
    
    @property
    def click_rate(self):
        """Retorna la tasa de clicks en porcentaje"""
        if self.emails_delivered == 0:
            return 0
        return round((self.emails_clicked / self.emails_delivered) * 100, 2)
    
    @property
    def bounce_rate(self):
        """Retorna la tasa de rebotes en porcentaje"""
        if self.emails_sent == 0:
            return 0
        return round((self.emails_bounced / self.emails_sent) * 100, 2)
    
    @property
    def status_color(self):
        """Retorna el color Bootstrap para el badge de estado"""
        colors = {
            'draft': 'secondary',
            'ready': 'info',
            'sending': 'primary',
            'paused': 'warning',
            'completed': 'success',
            'cancelled': 'danger',
        }
        return colors.get(self.status, 'secondary')
    
    def can_edit(self):
        """Verifica si la campaña puede ser editada"""
        return self.status in ['draft', 'ready', 'paused']
    
    def can_send(self):
        """Verifica si la campaña puede ser enviada"""
        return self.status in ['draft', 'ready', 'paused']
    
    def can_pause(self):
        """Verifica si la campaña puede ser pausada"""
        return self.status == 'sending'
    
    def clean(self):
        """Validaciones personalizadas"""
        from django.core.exceptions import ValidationError
        
        if self.batch_size < 1:
            raise ValidationError({'batch_size': 'El tamaño de lote debe ser mayor a 0'})
        
        if self.batch_delay_minutes < 1:
            raise ValidationError({'batch_delay_minutes': 'El delay debe ser mayor a 0'})
        
        # Validar que el HTML tenga el footer con unsubscribe
        if 'unsubscribe' not in self.html_content.lower():
            raise ValidationError({
                'html_content': 'El contenido debe incluir un enlace de unsubscribe'
            })


class CampaignSendLog(models.Model):
    """
    Log de envíos individuales de una campaña.
    Permite tracking detallado de cada email enviado.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('sending', 'Enviando'),
        ('sent', 'Enviado'),
        ('delivered', 'Entregado'),
        ('opened', 'Abierto'),
        ('clicked', 'Click realizado'),
        ('bounced', 'Rebotado'),
        ('failed', 'Fallido'),
        ('spam', 'Marcado como spam'),
    ]
    
    campaign = models.ForeignKey(
        EmailCampaignTemplate,
        on_delete=models.CASCADE,
        related_name='send_logs',
        verbose_name='Campaña'
    )
    
    recipient_email = models.EmailField(
        verbose_name='Email del Destinatario'
    )
    recipient_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Nombre del Destinatario'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Estado'
    )
    
    # Timestamps de eventos
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Enviado el'
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Entregado el'
    )
    opened_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Abierto el'
    )
    clicked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Click el'
    )
    
    # Información adicional
    error_message = models.TextField(
        blank=True,
        verbose_name='Mensaje de Error'
    )
    bounce_reason = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Razón del Rebote'
    )
    
    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado el'
    )
    
    class Meta:
        verbose_name = 'Log de Envío de Campaña'
        verbose_name_plural = 'Logs de Envío de Campañas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['recipient_email']),
        ]
    
    def __str__(self):
        return f"{self.campaign.name} → {self.recipient_email} ({self.get_status_display()})"


class ConfiguracionResumen(SingletonModel):
    """
    Configuración para generar resúmenes de reserva (pre-pago).
    Singleton: solo existe una instancia de configuración.
    """
    # Encabezado
    encabezado = models.TextField(
        default="Confirma tu Reserva en Aremko Spa",
        verbose_name="Encabezado",
        help_text="Título principal del resumen de reserva"
    )

    # Información de pago
    datos_transferencia = models.TextField(
        default="""Para confirmación reserva abonar 100% a:

Aremko Hotel Spa Rut 76.485.192-7
Mercado Pago Cta Vista 1016006859

Para confirmar su reserva nos debe llegar un correo de la entidad pagadora al realizar la transferencia ingrese el correo ventas@aremko.cl, indicando NRO Reserva y fecha de esta reserva.

La reserva se considerará confirmada únicamente una vez recibido el comprobante en el correo y también despachar imagen por este medio donde se especifica claramente detalles de la transferencia.""",
        verbose_name="Datos de Transferencia",
        help_text="Información completa para pago por transferencia bancaria"
    )

    link_pago_mercadopago = models.URLField(
        default="https://link.mercadopago.cl/aremko",
        verbose_name="Link Mercado Pago",
        help_text="URL para pago con tarjeta a través de Mercado Pago"
    )

    texto_link_pago = models.TextField(
        default="Ingresa al link, elige cómo pagar, ¡y listo!",
        verbose_name="Texto Link de Pago",
        help_text="Texto que acompaña al link de Mercado Pago"
    )

    # Cortesías y garantías generales
    tina_yate_texto = models.TextField(
        default="""Tina Yate agua fría (sin costo adicional)
Temperatura garantizada menos de 37°grados su tina es gratis
No incluye toallas o batas.""",
        verbose_name="Texto Tina Yate",
        help_text="Texto sobre tina yate y garantía de temperatura (se muestra cuando hay tinas)"
    )

    sauna_no_disponible = models.TextField(
        default="(Reserva no incluye sauna por que este no está disponible)",
        verbose_name="Texto Sauna No Disponible",
        help_text="Aclaración sobre sauna (se muestra cuando hay alojamiento)"
    )

    # Políticas de cancelación
    politica_alojamiento = models.TextField(
        default="""Alojamiento : Si nos avisa con más de 48hrs de anticipación antes de que inicie su reserva (16:00 hrs Check in), se puede pedir reembolso total o cambio de fecha sin penalidad. Si no se avisa con menos de 48hrs antes de su reserva, lamentablemente la has perdido.""",
        verbose_name="Política Alojamiento",
        help_text="Política de cancelación para servicios de alojamiento"
    )

    politica_tinas_masajes = models.TextField(
        default="""Tina / Masajes : Si nos avisa con más de 24hrs de anticipación antes de que inicie su reserva, se puede pedir reembolso total o cambio de fecha sin penalidad. Si no se avisa con menos de 24hrs antes de su reserva, lamentablemente la has perdido.""",
        verbose_name="Política Tinas/Masajes",
        help_text="Política de cancelación para tinas y masajes"
    )

    # Información adicional para alojamiento
    equipamiento_cabanas = models.TextField(
        default="""Cabaña equipada:*
Nuestras cabañas cuentan con todas las comodidades para que disfrutes al máximo: mini refrigerador, microondas, lavaplatos, tostadora, hervidor, loza, aire acondicionado, wifi y secador de pelo.""",
        verbose_name="Equipamiento Cabañas",
        help_text="Descripción del equipamiento general de las cabañas"
    )

    cortesias_alojamiento = models.TextField(
        default="""Detalle especial:
Te ofrecemos cortesías como té negro, infusiones especiales y té Twinings para endulzar naturalmente tus momentos de relax.""",
        verbose_name="Cortesías Alojamiento",
        help_text="Cortesías incluidas en el alojamiento"
    )

    seguridad_pasarela = models.TextField(
        default="""Pasarela:
Por tu seguridad, al transitar por las pasarelas, te pedimos usar zapatos cómodos y antideslizantes. El uso de pasamanos es obligatorio y las sandalias no están permitidas.""",
        verbose_name="Seguridad Pasarela",
        help_text="Recomendaciones de seguridad para pasarelas"
    )

    # Cortesías para tinas/masajes
    cortesias_generales = models.TextField(
        default="Cortesías: Durante tu estadía encontrarás en recepción un espacio de autoservicio de té e infusiones.",
        verbose_name="Cortesías Generales",
        help_text="Cortesías disponibles para servicios de tinas/masajes"
    )

    # Despedida
    despedida = models.TextField(
        default="""Estamos aquí para asegurarnos de que tengas una experiencia inolvidable. Si tienes dudas o necesitas algo más, no dudes en escribirnos.

Gracias por elegir Aremko Spa para tu relax.""",
        verbose_name="Despedida",
        help_text="Texto de despedida al final del resumen"
    )

    class Meta:
        verbose_name = "Configuración de Resumen de Reserva"
        verbose_name_plural = "Configuración de Resumen de Reserva"

    def __str__(self):
        return "Configuración de Resumen de Reserva"


class ConfiguracionTips(SingletonModel):
    """
    Configuración para generar tips post-pago (enviados después del pago).
    Singleton: solo existe una instancia de configuración.
    """
    # Encabezado general
    encabezado = models.TextField(
        default="Bienvenido a Aremko Spa 🌿",
        verbose_name="Encabezado",
        help_text="Título principal de los tips",
        blank=True
    )

    intro = models.TextField(
        default="Gracias por elegirnos para tu estadía. Aquí te compartimos información importante para que disfrutes al máximo tu experiencia:",
        verbose_name="Introducción",
        help_text="Texto introductorio",
        blank=True
    )

    # ========== TIPS ESPECÍFICOS PARA CABAÑAS ==========

    # WiFi Cabañas
    wifi_torre = models.CharField(
        max_length=200,
        default="Red: Torre / Clave: torre2021",
        verbose_name="WiFi Cabaña Torre",
        blank=True
    )

    wifi_tepa = models.CharField(
        max_length=200,
        default="Red: TP-Link_3B26 / Clave: 83718748",
        verbose_name="WiFi Cabaña Tepa",
        blank=True
    )

    wifi_acantilado = models.CharField(
        max_length=200,
        default="Red: Acantilado / Clave: acantilado",
        verbose_name="WiFi Cabaña Acantilado",
        blank=True
    )

    wifi_laurel = models.CharField(
        max_length=200,
        default="Red: Acantilado / Clave: acantilado",
        verbose_name="WiFi Cabaña Laurel",
        blank=True
    )

    wifi_arrayan = models.CharField(
        max_length=200,
        default="Red: tp-link_7e8a / Clave: 19146881",
        verbose_name="WiFi Cabaña Arrayan",
        blank=True
    )

    # Normas cabañas
    norma_mascotas = models.TextField(
        default="❌ Prohibido traer mascotas a Aremko",
        verbose_name="Norma: Mascotas",
        blank=True
    )

    norma_cocinar = models.TextField(
        default="❌ Prohibido cocinar y realizar asados (interior y exterior de cabañas)",
        verbose_name="Norma: Cocinar/Asados",
        blank=True
    )

    norma_fumar = models.TextField(
        default="""❌ AREMKO ES NO FUMADOR (Ley 20.660)
Fumar en lugares cerrados está prohibido por ley.
Multa: 2 UTM (~$70.000) + costo de limpieza profunda.
El cobro se realiza al momento del check-out.""",
        verbose_name="Norma: No Fumar",
        blank=True
    )

    norma_danos = models.TextField(
        default="""⚠️ Multas por daños o limpieza extraordinaria:
Se aplicarán cargos por daños, artículos faltantes o limpieza inesperada (manchas en sábanas, ropa de cama, toallas).
La cabaña será revisada por personal de Aremko al check-out.""",
        verbose_name="Norma: Daños y Limpieza",
        blank=True
    )

    # Check-out cabañas
    checkout_semana = models.TextField(
        default="""Domingo a Jueves (antes de 11:00 hrs):
→ Deja llaves y controles dentro de la cabaña
→ Asegúrate de apagar el aire acondicionado
→ Saldos pendientes: recibirás datos de pago por WhatsApp""",
        verbose_name="Check-out Domingo-Jueves",
        blank=True
    )

    checkout_finde = models.TextField(
        default="""Viernes y Sábado (desde 10:30 hrs):
→ Check-out presencial en recepción
→ Para abrir portón automático, solicitar por WhatsApp""",
        verbose_name="Check-out Viernes-Sábado",
        blank=True
    )

    # ========== TIPS ESPECÍFICOS PARA TINAS/MASAJES ==========

    recordatorio_toallas = models.TextField(
        default="Recuerde traer toallas. También tenemos toallas para arrendar ($3.000 c/u) o puede usar las de su cabaña si tiene alojamiento.",
        verbose_name="Recordatorio: Traer Toallas",
        blank=True
    )

    tip_puntualidad = models.TextField(
        default="En Puerto Varas a toda hora hay congestión vehicular. Intente llegar 15 minutos antes de su reserva.",
        verbose_name="Tip: Puntualidad",
        blank=True
    )

    info_vestidores = models.TextField(
        default="Cada tina tiene su vestidor y también hay vestidores en el spa si gusta utilizar.",
        verbose_name="Info: Vestidores",
        blank=True
    )

    ropa_masaje = models.TextField(
        default="Para pasajeros que sólo vengan a masaje, traer solamente ropa de interior, no traje de baño.",
        verbose_name="Info: Ropa para Masaje",
        blank=True
    )

    menores_edad = models.TextField(
        default="Los menores de edad en todo momento deben estar bajo el cuidado de los padres (desde 2 años si utiliza tina de agua caliente o fría, de ser con pañal de agua).",
        verbose_name="Info: Menores de Edad",
        blank=True
    )

    # ========== TIPS COMUNES (TINAS Y CABAÑAS) ==========

    # WiFi otras áreas
    wifi_tinas = models.CharField(
        max_length=200,
        default="Red: Tinas / Clave: 82551551",
        verbose_name="WiFi Sector Tinas",
        blank=True
    )

    wifi_tinajas = models.CharField(
        max_length=200,
        default="Red: wifi Tinajas / Clave: 12345678",
        verbose_name="WiFi Tinajas",
        blank=True
    )

    wifi_masajes = models.CharField(
        max_length=200,
        default="Red: domo / Clave: Tepa2021",
        verbose_name="WiFi Sala Masajes",
        blank=True
    )

    # Uso de tinas
    uso_tinas_alternancia = models.TextField(
        default="""✓ Alterna entre tina caliente y tina fría (Tina Yate - uso libre sin costo)
✓ Máximo 15 minutos por sesión en agua caliente
✓ Descansa al borde unos minutos entre sesiones
✓ Completa hasta 2 horas totales de baño""",
        verbose_name="Uso de Tinas: Alternancia",
        blank=True
    )

    uso_tinas_prohibiciones = models.TextField(
        default="""❌ NO usar shampoo, jabones, sales, hierbas ni flores
❌ NO sumergir la cabeza - el agua está clorada (disposición sanitaria)""",
        verbose_name="Uso de Tinas: Prohibiciones",
        blank=True
    )

    recomendacion_ducha_masaje = models.TextField(
        default="Por recomendación de la masajista, ducharse después del masaje.",
        verbose_name="Recomendación: Ducha post-masaje",
        blank=True
    )

    prohibicion_vasos = models.TextField(
        default="NO transitar por pasarelas con copas o vasos. Si necesitas, solicita por WhatsApp y te facilitamos vasos para tu hora de tina.",
        verbose_name="Prohibición: Vasos en Pasarelas",
        blank=True
    )

    # Seguridad pasarelas
    seguridad_pasarelas = models.TextField(
        default="""⚠️ SEGURIDAD EN PASARELAS (OBLIGATORIO)

Por tu seguridad al transitar por las pasarelas:

✓ Usar zapatos cómodos y antideslizantes
✓ Uso de pasamanos OBLIGATORIO
❌ Prohibido: chalas, zapatos con taco o plataforma

Nota: Indicaciones de la autoridad sanitaria""",
        verbose_name="Seguridad en Pasarelas",
        blank=True
    )

    # Horarios
    horario_porton_semana = models.CharField(
        max_length=200,
        default="Domingo a Jueves: 09:00 - 22:00 hrs",
        verbose_name="Horario Portón (Dom-Jue)",
        blank=True
    )

    horario_porton_finde = models.CharField(
        max_length=200,
        default="Viernes y Sábado: 09:00 - 00:00 hrs",
        verbose_name="Horario Portón (Vie-Sáb)",
        blank=True
    )

    telefono_porton = models.CharField(
        max_length=50,
        default="+56 9 5336 1647",
        verbose_name="Teléfono para abrir portón",
        blank=True
    )

    horario_recepcion_semana = models.CharField(
        max_length=200,
        default="Lunes a Jueves: hasta 20:00 hrs",
        verbose_name="Horario Recepción (Lun-Jue)",
        blank=True
    )

    horario_recepcion_finde = models.CharField(
        max_length=200,
        default="Viernes y Sábado: hasta 23:30 hrs",
        verbose_name="Horario Recepción (Vie-Sáb)",
        blank=True
    )

    horario_recepcion_domingo = models.CharField(
        max_length=200,
        default="Domingo: hasta 19:30 hrs",
        verbose_name="Horario Recepción (Dom)",
        blank=True
    )

    horario_cafeteria_semana = models.CharField(
        max_length=200,
        default="Domingo a Jueves: hasta 20:00 hrs",
        verbose_name="Horario Cafetería (Dom-Jue)",
        blank=True
    )

    horario_cafeteria_finde = models.CharField(
        max_length=200,
        default="Viernes y Sábado: hasta 23:00 hrs",
        verbose_name="Horario Cafetería (Vie-Sáb)",
        blank=True
    )

    # Cafetería
    productos_cafeteria = models.TextField(
        default="Tablas de quesos, jugos naturales, agua con/sin gas, bebidas envasadas",
        verbose_name="Productos Cafetería",
        blank=True
    )

    menu_cafe = models.TextField(
        default="Café Marley: Capuccino, Mokaccino, Chocolate, Americano, Vainilla, Cortado",
        verbose_name="Menú de Café",
        blank=True
    )

    # Ubicación
    direccion = models.CharField(
        max_length=200,
        default="Río Pescado Km 4, Puerto Varas",
        verbose_name="Dirección",
        blank=True
    )

    como_llegar = models.TextField(
        default="""Desde Puerto Varas:
1. Tomar camino Ensenada hasta km 19 (carretera 255)
2. Encontrarás retén de Carabineros de Río Pescado (a tu derecha)
3. Frente al retén, tomar camino de tierra hacia Volcán Calbuco
   (ANTES del Puente Río Pescado - hay 2 retenes, nosotros estamos en el 1°)
4. Ingresar 4 km por ese camino
5. Aremko estará a tu izquierda""",
        verbose_name="Cómo Llegar",
        blank=True
    )

    link_google_maps = models.URLField(
        default="https://maps.google.com/maps?q=-41.2776517%2C-72.7685313&z=17&hl=es",
        verbose_name="Link Google Maps",
        blank=True
    )

    # Despedida
    despedida = models.TextField(
        default="¡Disfruta tu estadía en Aremko! 🌿✨",
        verbose_name="Despedida",
        blank=True
    )

    contacto_whatsapp = models.CharField(
        max_length=50,
        default="+56 9 5336 1647",
        verbose_name="WhatsApp de Contacto",
        blank=True
    )

    class Meta:
        verbose_name = "Configuración de Tips Post-Pago"
        verbose_name_plural = "Configuración de Tips Post-Pago"

    def __str__(self):
        return "Configuración de Tips Post-Pago"


# --- Sistema de Bloqueo de Servicios por Fecha ---

class ServicioBloqueo(models.Model):
    """
    Modelo para bloquear servicios en rangos de fechas específicos.
    Útil para mantenimiento, reparaciones, o cerrar servicios temporalmente.

    Ejemplos de uso:
    - Cerrar Cabaña Torre del 15-20 enero por mantenimiento
    - Cerrar Tina Hornopiren el 5 de febrero por reparación
    - Bloquear Masaje de Piedras Calientes una semana completa

    IMPORTANTE: Solo se puede bloquear si NO hay reservas existentes en el rango.
    """
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name='bloqueos',
        verbose_name='Servicio'
    )
    fecha_inicio = models.DateField(
        verbose_name='Fecha Inicio',
        help_text='Primer día del bloqueo (inclusive)'
    )
    fecha_fin = models.DateField(
        verbose_name='Fecha Fin',
        help_text='Último día del bloqueo (inclusive)'
    )
    motivo = models.CharField(
        max_length=255,
        verbose_name='Motivo del Bloqueo',
        help_text='Ej: Mantenimiento, Reparación, Fuera de temporada'
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Creado Por'
    )
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Desmarcar para desactivar el bloqueo sin eliminarlo'
    )
    notas = models.TextField(
        blank=True,
        verbose_name='Notas Adicionales',
        help_text='Información adicional sobre el bloqueo'
    )

    class Meta:
        app_label = 'ventas'
        verbose_name = 'Bloqueo de Servicio'
        verbose_name_plural = 'Bloqueos de Servicios'
        ordering = ['-fecha_inicio']
        indexes = [
            models.Index(fields=['servicio', 'fecha_inicio', 'fecha_fin']),
            models.Index(fields=['activo']),
        ]
        permissions = [
            ('can_manage_bloqueos', 'Puede gestionar bloqueos de servicios'),
        ]

    def __str__(self):
        if self.fecha_inicio == self.fecha_fin:
            return f"{self.servicio.nombre} - {self.fecha_inicio.strftime('%d/%m/%Y')}"
        return f"{self.servicio.nombre} - {self.fecha_inicio.strftime('%d/%m/%Y')} al {self.fecha_fin.strftime('%d/%m/%Y')}"

    def clean(self):
        """Validaciones del modelo"""
        from django.core.exceptions import ValidationError

        # Validar que fecha_fin >= fecha_inicio
        if self.fecha_fin < self.fecha_inicio:
            raise ValidationError({
                'fecha_fin': 'La fecha fin no puede ser anterior a la fecha inicio.'
            })

        # Validar que no haya reservas en el rango (solo si es un bloqueo nuevo o se cambió el rango)
        if self.pk:
            # Es una edición - verificar si cambió el rango de fechas
            original = ServicioBloqueo.objects.get(pk=self.pk)
            if (original.fecha_inicio != self.fecha_inicio or
                original.fecha_fin != self.fecha_fin or
                original.servicio_id != self.servicio_id):
                self._validar_sin_reservas()
        else:
            # Es un bloqueo nuevo
            self._validar_sin_reservas()

    def _validar_sin_reservas(self):
        """Verifica que no existan reservas en el rango de fechas"""
        from django.core.exceptions import ValidationError

        # Buscar reservas del servicio en el rango de fechas
        reservas_conflicto = ReservaServicio.objects.filter(
            servicio=self.servicio,
            fecha_agendamiento__gte=self.fecha_inicio,
            fecha_agendamiento__lte=self.fecha_fin
        ).exclude(
            venta_reserva__estado_reserva='cancelada'
        )

        if reservas_conflicto.exists():
            # Contar reservas por fecha
            fechas_con_reservas = reservas_conflicto.values_list('fecha_agendamiento', flat=True).distinct()
            fechas_str = ', '.join([f.strftime('%d/%m/%Y') for f in sorted(fechas_con_reservas)[:5]])

            if len(fechas_con_reservas) > 5:
                fechas_str += f' y {len(fechas_con_reservas) - 5} fechas más'

            raise ValidationError({
                'fecha_inicio': f'No se puede bloquear: existen {reservas_conflicto.count()} reservas en las fechas: {fechas_str}'
            })

    def save(self, *args, **kwargs):
        """Ejecutar validaciones antes de guardar"""
        self.full_clean()
        super().save(*args, **kwargs)

    def get_dias_bloqueados(self):
        """Retorna la cantidad de días bloqueados"""
        return (self.fecha_fin - self.fecha_inicio).days + 1

    def contiene_fecha(self, fecha):
        """Verifica si una fecha específica está dentro del bloqueo"""
        return self.activo and self.fecha_inicio <= fecha <= self.fecha_fin

    @classmethod
    def servicio_bloqueado_en_fecha(cls, servicio_id, fecha):
        """
        Método de clase para verificar si un servicio está bloqueado en una fecha.
        Útil para validaciones rápidas.

        Args:
            servicio_id: ID del servicio
            fecha: Fecha a verificar (date object)

        Returns:
            bool: True si está bloqueado, False si está disponible
        """
        return cls.objects.filter(
            servicio_id=servicio_id,
            fecha_inicio__lte=fecha,
            fecha_fin__gte=fecha,
            activo=True
        ).exists()
