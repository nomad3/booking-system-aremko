from datetime import timedelta, datetime
from typing import Optional
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import transaction
import random
import string
import re
from django.db.models import Sum, F, DecimalField, FloatField # Added DecimalField, FloatField
from django.db.models.functions import Coalesce # Coalesce es una función de DB
from solo.models import SingletonModel # Added import for django-solo
from cloudinary_storage.storage import VideoMediaCloudinaryStorage  # storage de video (resource_type=video) para FileField de video
from cloudinary_storage.storage import RawMediaCloudinaryStorage  # storage raw (resource_type=raw) para adjuntos WhatsApp (pdf/audio/imagen/video)

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
        help_text="Foto principal del producto para el catálogo web"
    )
    imagen_2 = models.ImageField(
        upload_to='productos/',
        blank=True,
        null=True,
        verbose_name="Imagen 2",
        help_text="Segunda foto del producto (opcional, aparece en el carousel)"
    )
    imagen_3 = models.ImageField(
        upload_to='productos/',
        blank=True,
        null=True,
        verbose_name="Imagen 3",
        help_text="Tercera foto del producto (opcional, aparece en el carousel)"
    )
    orden = models.IntegerField(
        default=0,
        verbose_name="Orden",
        help_text="Orden de visualización en el catálogo (menor número = primero)"
    )

    # Campos para sistema de comandas de clientes (vía WhatsApp)
    comanda_cliente = models.BooleanField(
        default=False,
        verbose_name="Disponible para Comanda de Cliente",
        help_text="Si está marcado, el cliente puede ver y seleccionar este producto desde su link de comanda vía WhatsApp"
    )
    orden_comanda = models.IntegerField(
        default=0,
        verbose_name="Orden en Menú de Comanda",
        help_text="Orden de visualización en el menú de comandas para clientes (menor número = primero)"
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
    permite_reserva_web = models.BooleanField(
        default=True,
        verbose_name="Permite Reserva Web Directa",
        help_text="Si está marcado, permite reserva directa por web. Si no, requiere contacto por WhatsApp."
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
        help_text="Imagen principal del servicio."
    )
    imagen_2 = models.ImageField(
        upload_to='servicios/',
        blank=True,
        null=True,
        help_text="Segunda imagen del servicio (opcional, aparece en el carousel de la card)."
    )
    imagen_3 = models.ImageField(
        upload_to='servicios/',
        blank=True,
        null=True,
        help_text="Tercera imagen del servicio (opcional, aparece en el carousel de la card)."
    )
    video = models.FileField(
        upload_to='servicios/videos/',
        storage=VideoMediaCloudinaryStorage(),
        max_length=255,
        blank=True,
        null=True,
        help_text="Video corto opcional subido desde tu computador (mp4/webm, idealmente <15 seg y liviano). Si se sube, se muestra en la card en lugar de las fotos. Para videos grandes ya hosteados, usa 'Video URL'."
    )
    video_url = models.URLField(
        max_length=500,
        blank=True,
        default='',
        help_text="Alternativa: URL de un video ya hosteado (mp4/webm directo, ej. Cloudinary). Se usa solo si NO subiste un archivo en 'Video'. Si ambos están vacíos, se muestran las fotos."
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
# MODELS DE GESTIÓN DE MASAJISTAS
# ============================================

class MasajistaEspecialidad(models.Model):
    """
    Define qué tipos de masajes puede realizar cada masajista.
    Permite control granular de especialidades por profesional.
    """
    masajista = models.ForeignKey(
        Proveedor,
        on_delete=models.CASCADE,
        limit_choices_to={'es_masajista': True},
        related_name='especialidades',
        verbose_name='Masajista'
    )
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        limit_choices_to={'tipo_servicio': 'masaje'},
        related_name='especialistas',
        verbose_name='Tipo de Masaje'
    )
    nivel_experiencia = models.CharField(
        max_length=20,
        choices=[
            ('basico', 'Básico'),
            ('intermedio', 'Intermedio'),
            ('avanzado', 'Avanzado'),
            ('experto', 'Experto'),
        ],
        default='intermedio',
        help_text='Nivel de experiencia del masajista en este tipo de masaje'
    )
    activo = models.BooleanField(
        default=True,
        help_text='Si el masajista está actualmente ofreciendo este servicio'
    )

    class Meta:
        unique_together = ['masajista', 'servicio']
        verbose_name = 'Especialidad de Masajista'
        verbose_name_plural = 'Especialidades de Masajistas'
        ordering = ['masajista__nombre', 'servicio__nombre']

    def __str__(self):
        return f"{self.masajista.nombre} - {self.servicio.nombre}"


class HorarioMasajista(models.Model):
    """
    Define la disponibilidad semanal de cada masajista.
    Permite configurar horarios diferentes por día de la semana.
    """
    DIAS_SEMANA = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]

    masajista = models.ForeignKey(
        Proveedor,
        on_delete=models.CASCADE,
        limit_choices_to={'es_masajista': True},
        related_name='horarios',
        verbose_name='Masajista'
    )
    dia_semana = models.IntegerField(
        choices=DIAS_SEMANA,
        verbose_name='Día de la Semana'
    )
    hora_inicio = models.TimeField(
        verbose_name='Hora de Inicio',
        help_text='Hora de inicio del turno'
    )
    hora_fin = models.TimeField(
        verbose_name='Hora de Fin',
        help_text='Hora de fin del turno'
    )
    disponible = models.BooleanField(
        default=True,
        help_text='Si el masajista está disponible este día'
    )

    class Meta:
        unique_together = ['masajista', 'dia_semana']
        verbose_name = 'Horario de Masajista'
        verbose_name_plural = 'Horarios de Masajistas'
        ordering = ['masajista__nombre', 'dia_semana']

    def __str__(self):
        return f"{self.masajista.nombre} - {self.get_dia_semana_display()}"


class SalaServicio(models.Model):
    """
    Define las salas disponibles para servicios (principalmente masajes).
    Cada sala puede tener múltiples camillas.
    """
    nombre = models.CharField(
        max_length=50,
        verbose_name='Nombre de la Sala',
        help_text='Ej: Sala 1, Sala Relax, etc.'
    )
    numero_camillas = models.PositiveIntegerField(
        default=2,
        verbose_name='Número de Camillas',
        help_text='Cantidad de camillas disponibles en esta sala'
    )
    permite_grupos_mixtos = models.BooleanField(
        default=False,
        verbose_name='Permite Grupos Mixtos',
        help_text='Si permite que personas no relacionadas compartan la sala'
    )
    activa = models.BooleanField(
        default=True,
        help_text='Si la sala está disponible para uso'
    )
    descripcion = models.TextField(
        blank=True,
        help_text='Descripción adicional de la sala'
    )

    class Meta:
        verbose_name = 'Sala de Servicio'
        verbose_name_plural = 'Salas de Servicio'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.numero_camillas} camillas)"


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

    # ───────────── Operación Vuelta a Casa (retención WhatsApp) ─────────────
    # Estos 3 campos controlan elegibilidad y cadencia de la bandeja diaria
    # del operador (cron generar_bandeja_whatsapp_diaria). Ver:
    # - ContactoWhatsApp para el log de cada intento
    # - ScriptWhatsApp para las plantillas
    opt_out_whatsapp = models.BooleanField(
        default=False,
        help_text="Cliente pidió no recibir más WhatsApp. Bloqueante permanente.",
    )
    proximo_contacto_no_antes_de = models.DateField(
        null=True, blank=True,
        help_text=(
            "No contactar antes de esta fecha. Usado para 'más adelante' "
            "y períodos de gracia (90 días tras 'no aplica')."
        ),
    )
    ultimo_contacto_outbound = models.DateField(
        null=True, blank=True,
        help_text=(
            "Última vez que enviamos WhatsApp outbound. "
            "Usado por la regla anti-saturación de 30 días."
        ),
    )

    # ───────────── Operación Vuelta a Casa · Etapa Geo.2 ─────────────
    # Categorización geográfica para personalizar mensajes WhatsApp según
    # cercanía a Puerto Varas. Se pobla con normalizar_ciudades_clientes
    # a partir de Cliente.ciudad (texto libre) y Cliente.comuna (FK).
    ciudad_normalizada = models.ForeignKey(
        'Ciudad',  # forward ref — Ciudad está definida más abajo en este archivo
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='clientes',
        help_text="Mapeo del texto libre 'ciudad' a una Ciudad canónica.",
    )
    region_geografica = models.CharField(
        max_length=20,
        choices=[
            ('sur', 'Sur (≤120 km)'),
            ('nacional', 'Resto de Chile'),
            ('extranjero', 'Extranjero'),
            ('sin_clasificar', 'Sin clasificar'),
        ],
        default='sin_clasificar',
        db_index=True,
        help_text="Categoría geográfica derivada. Define el tipo de mensaje WhatsApp.",
    )
    ciudad_normalizada_manual = models.BooleanField(
        default=False,
        help_text=(
            "True si el admin editó ciudad_normalizada/region_geografica "
            "manualmente. El comando normalizar_ciudades_clientes RESPETA "
            "estas ediciones y no las sobrescribe."
        ),
    )

    # ───── Cliente staff/proxy (Aremko, dueños, recepcionistas) ─────
    # Marcado por el operador desde la bandeja cuando aparece un cliente
    # interno (Jorge Aguilera, Deborah, Ernesto, etc.). Bloqueante
    # permanente para Operación Vuelta a Casa — el cron NO los selecciona
    # como candidatos. Decisión administrativa (no comercial como opt_out_whatsapp).
    es_staff_proxy = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "True si este registro es de personal Aremko o cuenta proxy del "
            "staff (no cliente real). Excluido de bandeja WhatsApp."
        ),
    )
    es_staff_proxy_razon = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Por qué se marcó como staff/proxy (auditoría).",
    )

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

    # ───────────── Ficha de Cliente 360 (Fase 1 fidelización) ─────────────
    # Properties que combinan VentaReserva + ServiceHistory para mostrar valor real
    # del cliente al equipo de Aremko. Cache Django con TTL 5min para no recalcular
    # en cada hit del admin.

    # Familias normalizadas para el desglose. Orden importa para visualización.
    FAMILIAS_FICHA = ('Tinas', 'Masajes', 'Cabañas', 'Ambientaciones', 'Otros', 'Productos')

    def _ficha_cache_key(self) -> str:
        return f'cliente_ficha_v1:{self.pk}'

    def ficha_360(self, force_refresh: bool = False) -> dict:
        """Devuelve la ficha 360 del cliente con desglose por familia.

        Estructura:
        {
            'total': float,
            'por_familia': {'Tinas': X, 'Masajes': Y, ...},
            'numero_visitas': int,
            'dias_desde_ultima_visita': int | None,
            'tramo_actual': int,
            'nivel': 'nuevo' | 'regular' | 'vip' | 'champion',
            'nunca_compro': ['Ambientaciones', ...],
        }
        """
        from django.core.cache import cache
        if not force_refresh:
            cached = cache.get(self._ficha_cache_key())
            if cached is not None:
                return cached

        ficha = self._calcular_ficha_360()
        cache.set(self._ficha_cache_key(), ficha, 300)  # 5min
        return ficha

    def _calcular_ficha_360(self) -> dict:
        from datetime import date
        from decimal import Decimal

        # Inicializar desglose
        por_familia = {f: Decimal(0) for f in self.FAMILIAS_FICHA}

        # 1) Ventas actuales (VentaReserva → ReservaServicio + ReservaProducto)
        ventas_pagadas = self.ventareserva_set.filter(
            estado_pago__in=['pagado', 'parcial']
        )

        # Servicios actuales: agrupar por categoria (más confiable que tipo_servicio
        # porque Ambientaciones tienen categoria propia pero tipo='otro').
        for rs in ReservaServicio.objects.filter(
            venta_reserva__in=ventas_pagadas,
        ).select_related('servicio__categoria'):
            servicio = rs.servicio
            if not servicio:
                continue
            precio_unit = rs.precio_unitario_venta or servicio.precio_base or 0
            subtotal = Decimal(precio_unit) * (rs.cantidad_personas or 1)
            familia = self._mapear_categoria_a_familia(
                getattr(servicio.categoria, 'nombre', '') if servicio.categoria else '',
                servicio.tipo_servicio or '',
            )
            por_familia[familia] += subtotal

        # Productos actuales (ReservaProducto)
        for rp in ReservaProducto.objects.filter(
            venta_reserva__in=ventas_pagadas,
        ).select_related('producto'):
            producto = rp.producto
            if not producto:
                continue
            # Fix: el campo se llama precio_unitario_venta (no precio_unitario).
            # Bug pre-existente que estaba enmascarado por el try/except del display.
            precio_unit = rp.precio_unitario_venta or producto.precio_base or 0
            subtotal = Decimal(precio_unit) * (rp.cantidad or 1)
            por_familia['Productos'] += subtotal

        # 2) Histórico CSV (ServiceHistory.service_type)
        try:
            from ventas.models import ServiceHistory
            for sh in ServiceHistory.objects.filter(
                cliente=self,
                service_date__gt='2021-01-01',
            ):
                familia = self._mapear_categoria_a_familia(sh.service_type or '', '')
                por_familia[familia] += Decimal(sh.price_paid or 0)
        except Exception:
            pass

        total = sum(por_familia.values(), Decimal(0))

        # 3) Recency (días desde la última visita pagada)
        ultima = ventas_pagadas.order_by('-fecha_reserva').values_list('fecha_reserva', flat=True).first()
        if ultima:
            dias_desde_ultima = (date.today() - (ultima.date() if hasattr(ultima, 'date') else ultima)).days
        else:
            # Si no hay venta actual, mirar ServiceHistory más reciente
            try:
                from ventas.models import ServiceHistory
                ult_csv = ServiceHistory.objects.filter(
                    cliente=self,
                    service_date__gt='2021-01-01',
                ).order_by('-service_date').values_list('service_date', flat=True).first()
                dias_desde_ultima = (date.today() - ult_csv).days if ult_csv else None
            except Exception:
                dias_desde_ultima = None

        # 4) Frequency (número de visitas)
        numero_visitas_actuales = ventas_pagadas.count()
        try:
            numero_visitas_csv = ServiceHistory.objects.filter(
                cliente=self,
                service_date__gt='2021-01-01',
            ).count()
        except Exception:
            numero_visitas_csv = 0
        numero_visitas = numero_visitas_actuales + numero_visitas_csv

        # 5) Tramo actual (TramoService)
        try:
            from ventas.services.tramo_service import TramoService
            tramo_actual = TramoService.calcular_tramo(float(total))
        except Exception:
            tramo_actual = 0

        # 6) Nivel del cliente (heurística R+F+M)
        nivel = self._calcular_nivel(numero_visitas, tramo_actual, dias_desde_ultima)

        # 7) Cross-sell: familias que el cliente nunca compró (excl. Productos)
        nunca_compro = [
            f for f in ('Tinas', 'Masajes', 'Cabañas', 'Ambientaciones')
            if por_familia[f] == 0
        ]

        return {
            'total': float(total),
            'por_familia': {f: float(v) for f, v in por_familia.items()},
            'numero_visitas': numero_visitas,
            'dias_desde_ultima_visita': dias_desde_ultima,
            'tramo_actual': tramo_actual,
            'nivel': nivel,
            'nunca_compro': nunca_compro,
        }

    @staticmethod
    def _mapear_categoria_a_familia(categoria_nombre: str, tipo_servicio: str = '') -> str:
        """Normaliza categoria.nombre o tipo_servicio a una de las 6 familias.

        Acepta texto de ServiceHistory (libre) y de CategoriaServicio.nombre.
        """
        c = (categoria_nombre or '').lower().strip()
        t = (tipo_servicio or '').lower().strip()

        # Prioridad: categoría (más específica) > tipo_servicio (fallback)
        if 'ambientac' in c or 'decora' in c:
            return 'Ambientaciones'
        if 'tina' in c or t == 'tina':
            return 'Tinas'
        if 'masaje' in c or t == 'masaje':
            return 'Masajes'
        if 'caba' in c or 'alojamient' in c or t == 'cabana':
            return 'Cabañas'
        return 'Otros'

    @staticmethod
    def _calcular_nivel(visitas: int, tramo: int, dias_desde_ultima) -> str:
        """Heurística R+F+M para clasificar al cliente.

        - champion: tramo>=5 (gasto>=$250K) Y visitas>=5 Y recency<180d
        - vip: tramo>=5 O visitas>=5 (pero menos recency)
        - regular: 2-4 visitas Y recency<365d
        - inactivo: alguna vez compró pero recency>=365d
        - nuevo: 0-1 visitas
        """
        if visitas == 0:
            return 'nuevo'
        if dias_desde_ultima is not None and dias_desde_ultima >= 365 and visitas >= 1:
            return 'inactivo'
        if tramo >= 5 and visitas >= 5 and (dias_desde_ultima is None or dias_desde_ultima < 180):
            return 'champion'
        if tramo >= 5 or visitas >= 5:
            return 'vip'
        if visitas >= 2:
            return 'regular'
        return 'nuevo'

    def invalidar_ficha_cache(self):
        """Invalida el cache de la ficha cliente (llamar después de nueva venta pagada)."""
        from django.core.cache import cache
        cache.delete(self._ficha_cache_key())


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

        # Para servicios: usar precio_unitario_venta si existe, sino precio_base.
        # El checkout fuerza cantidad_personas = capacidad_maxima para cabañas
        # y tinas de precio plano (AR-014 en add_to_cart), por lo que el total
        # es precio × cantidad_personas para todos los tipos sin excepción.
        total_servicios = self.reservaservicios.aggregate(
            total=models.Sum(
                Coalesce(models.F('precio_unitario_venta'), models.F('servicio__precio_base')) *
                models.F('cantidad_personas')
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
            # `add(through_defaults=...)` crea el ReservaProducto, lo que dispara
            # el signal post_save `actualizar_inventario` que YA descuenta el
            # stock. NO llamar a reducir_inventario aquí también: duplicaba el
            # descuento (mismo bug que en VentaReservaViewSet.create).
            self.productos.add(producto, through_defaults={'cantidad': cantidad})
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
        """Calcula el precio basado en el tipo de servicio.

        El checkout fuerza cantidad_personas = capacidad_maxima para cabañas
        y tinas de precio plano (ver AR-014 en checkout_views.add_to_cart),
        por lo que precio_base × cantidad_personas ya representa el precio
        plano total que paga el cliente. Mantener una regla distinta aquí
        provocaría reportar en el admin la mitad (u otra fracción) de lo
        realmente cobrado.
        """
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
        """Muestra el valor total calculado formateado.

        Para cabañas y tinas de precio plano el checkout guarda
        cantidad_personas = capacidad_maxima (AR-014), por lo que el total
        siempre es precio_unitario × cantidad_personas, sin excepciones.
        """
        if self.precio_unitario_venta:
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
# TAXONOMÍA MULTIDIMENSIONAL DE CLIENTES
# ============================================================================

class ClienteTaxonomia(models.Model):
    """
    Etiquetas multidimensionales + snapshot de features por cliente.

    Las 3 etiquetas (Valor + Estilo + Contexto) clasifican al cliente en una
    matriz multidimensional usada por dashboards, mini-ficha admin y campañas
    de marketing dirigidas. El snapshot evita recalcular en cada consulta.

    Se llena/refresca con el management command `recalcular_taxonomia_clientes`
    (Paso 2). Un cron nocturno (Paso 5) recalcula los clientes que tuvieron
    cambios en las últimas 24h.

    Diseño:
    - OneToOne con Cliente: 1 cliente = máximo 1 fila.
    - Las labels se guardan en español (mismo formato que el comando
      exploratorio v4) para compatibilidad directa con el CSV/MD.
    - meses_ventana = 24 hard-coded por ahora (futura ampliación: snapshots
      paralelos a 12m si se necesita).
    """

    # ----- Etiquetas (las 3 dimensiones) -----
    EJE_VALOR_CHOICES = [
        ('Campeón', 'Campeón'),
        ('Leal', 'Leal'),
        ('Gran Gastador Ocasional', 'Gran Gastador Ocasional'),
        ('Regular', 'Regular'),
        ('En Prueba', 'En Prueba'),
        ('En Riesgo', 'En Riesgo'),
        ('Dormido', 'Dormido'),
        ('Pre-sistema', 'Pre-sistema'),
    ]
    EJE_ESTILO_CHOICES = [
        ('Devoto del Masaje', 'Devoto del Masaje'),
        ('Amante de las Tinas', 'Amante de las Tinas'),
        ('Experiencia Completa', 'Experiencia Completa'),
        ('Buscador de Alojamiento', 'Buscador de Alojamiento'),
        ('Probador Esporádico', 'Probador Esporádico'),
        ('N/A (pre-sistema)', 'N/A (pre-sistema)'),
    ]
    EJE_CONTEXTO_CHOICES = [
        ('Pareja Romántica', 'Pareja Romántica'),
        ('Auto-cuidado Solo', 'Auto-cuidado Solo'),
        ('Grupo', 'Grupo'),
        ('Familiar', 'Familiar'),
        ('Turista Estacional', 'Turista Estacional'),
        ('Local Frecuente', 'Local Frecuente'),
        ('Visitante Solo', 'Visitante Solo'),
        ('Visitante Pareja', 'Visitante Pareja'),
        ('Visitante Grupal', 'Visitante Grupal'),
        ('Sin clasificar', 'Sin clasificar'),
        ('N/A (pre-sistema)', 'N/A (pre-sistema)'),
    ]

    cliente = models.OneToOneField(
        Cliente,
        on_delete=models.CASCADE,
        related_name='taxonomia',
        primary_key=False,
    )
    eje_valor = models.CharField(max_length=40, choices=EJE_VALOR_CHOICES, db_index=True)
    eje_estilo = models.CharField(max_length=40, choices=EJE_ESTILO_CHOICES, db_index=True)
    eje_contexto = models.CharField(max_length=40, choices=EJE_CONTEXTO_CHOICES, db_index=True)

    # ----- Metadatos del cálculo -----
    meses_ventana = models.PositiveSmallIntegerField(
        default=24,
        help_text="Horizonte (en meses) usado para computar este snapshot."
    )
    calculado_en = models.DateTimeField(
        auto_now=True, db_index=True,
        help_text="Última vez que se recalculó este snapshot."
    )

    # ----- Snapshot sistema actual -----
    total_visitas = models.IntegerField(default=0)
    gasto_total = models.IntegerField(default=0, help_text="CLP")
    ticket_promedio = models.IntegerField(default=0, help_text="CLP")
    primera_visita_actual = models.DateField(null=True, blank=True)
    ultima_visita = models.DateField(null=True, blank=True)
    dias_desde_ultima_visita = models.IntegerField(null=True, blank=True)
    dias_entre_visitas_avg = models.FloatField(null=True, blank=True)
    meses_relacion_actual = models.FloatField(default=0)

    # ----- Mix de servicios -----
    pct_tinas = models.FloatField(default=0)
    pct_masajes = models.FloatField(default=0)
    pct_cabanas = models.FloatField(default=0)
    pct_otros = models.FloatField(default=0)
    gasto_tinas = models.IntegerField(default=0, help_text="CLP")
    gasto_masajes = models.IntegerField(default=0, help_text="CLP")
    gasto_cabanas = models.IntegerField(default=0, help_text="CLP")
    gasto_otros = models.IntegerField(default=0, help_text="CLP")

    # ----- Patrón compañía -----
    avg_cantidad_personas = models.FloatField(null=True, blank=True)
    pct_reservas_bundle = models.FloatField(default=0)
    count_reservas_bundle = models.IntegerField(default=0)

    # ----- Patrón temporal -----
    pct_finde = models.FloatField(default=0)
    pct_verano = models.FloatField(default=0)
    pct_otono = models.FloatField(default=0)
    pct_invierno = models.FloatField(default=0)
    pct_primavera = models.FloatField(default=0)

    # ----- Historial pre-sistema -----
    tiene_historial_pre_sistema = models.BooleanField(default=False)
    visitas_history_count = models.IntegerField(default=0)
    primera_visita_global = models.DateField(null=True, blank=True)
    antiguedad_meses = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Taxonomía de Cliente"
        verbose_name_plural = "Taxonomías de Clientes"
        indexes = [
            # Cruces frecuentes para filtrado de cohortes
            models.Index(fields=['eje_valor', 'eje_estilo'], name='idx_taxo_val_est'),
            models.Index(fields=['eje_valor', 'eje_contexto'], name='idx_taxo_val_ctx'),
            models.Index(fields=['eje_estilo', 'eje_contexto'], name='idx_taxo_est_ctx'),
        ]

    def __str__(self):
        return f"Taxonomía de {self.cliente_id}: {self.eje_valor} × {self.eje_estilo} × {self.eje_contexto}"


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

    # Cotizaciones para empresas (defaults globales editables)
    cotizacion_frase_beneficios = models.TextField(
        blank=True,
        verbose_name="Cotización: frase de beneficios para el grupo",
        help_text=(
            "Frase formal sobre beneficios para el equipo/grupo. Aparece debajo de la tabla "
            "de servicios en el documento de cotización. Si se deja vacío, se usa el default "
            "del código. Cada cotización puede sobrescribir esta frase individualmente."
        ),
    )
    cotizacion_terminos = models.TextField(
        blank=True,
        verbose_name="Cotización: términos y condiciones",
        help_text="Términos legales/operativos. Validez, forma de pago, etc.",
    )
    cotizacion_cierre = models.TextField(
        blank=True,
        verbose_name="Cotización: cierre formal",
        help_text="Firma de cierre del documento (ej: 'Cordialmente, Equipo Aremko...').",
    )

    class Meta:
        verbose_name = "Configuración de Resumen de Reserva"
        verbose_name_plural = "Configuración de Resumen de Reserva"

    def __str__(self):
        return "Configuración de Resumen de Reserva"

    # Getters con fallback al default del código para que el modelo no quede vacío en ningún momento.
    def get_cotizacion_frase_beneficios(self) -> str:
        return self.cotizacion_frase_beneficios.strip() or COTIZACION_FRASE_BENEFICIOS_DEFAULT

    def get_cotizacion_terminos(self) -> str:
        return self.cotizacion_terminos.strip() or COTIZACION_TERMINOS_DEFAULT

    def get_cotizacion_cierre(self) -> str:
        return self.cotizacion_cierre.strip() or COTIZACION_CIERRE_DEFAULT


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


    """
    Características:
    - Solo 1 fecha (no rangos)
    - Solo 1 slot/horario
    - Solo se puede bloquear si el slot está disponible (sin reservas)
    - Si el día está bloqueado completamente, no se puede crear bloqueo de slot
    """
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name='bloqueos_slot',
        verbose_name='Servicio'
    )
    fecha = models.DateField(
        verbose_name='Fecha',
        help_text='Fecha específica del bloqueo'
    )
    hora_slot = models.CharField(
        max_length=10,
        verbose_name='Horario',
        help_text='Horario a bloquear (ej: 14:30)'
    )
    motivo = models.CharField(
        max_length=255,
        verbose_name='Motivo del Bloqueo',
        help_text='Ej: Limpieza, Mantenimiento, Setup'
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
        help_text='Desmarcar para desbloquear sin eliminar el registro'
    )
    notas = models.TextField(
        blank=True,
        verbose_name='Notas Adicionales',
        help_text='Información adicional sobre el bloqueo'
    )

    class Meta:
        app_label = 'ventas'
        verbose_name = 'Bloqueo de Slot'
        verbose_name_plural = 'Bloqueos de Slots'
        ordering = ['-fecha', '-hora_slot']
        indexes = [
            models.Index(fields=['servicio', 'fecha', 'hora_slot']),
            models.Index(fields=['activo']),
            models.Index(fields=['fecha']),
        ]
        # Prevenir duplicados: un servicio no puede tener el mismo slot bloqueado dos veces
        unique_together = [['servicio', 'fecha', 'hora_slot', 'activo']]

    def __str__(self):
        return f"{self.servicio.nombre} - {self.fecha.strftime('%d/%m/%Y')} a las {self.hora_slot}"

    def clean(self):
        """Validaciones del modelo"""
        from django.core.exceptions import ValidationError

        # Verificar que tenemos los campos necesarios antes de validar
        if not hasattr(self, 'fecha') or self.fecha is None:
            return  # No validar si no hay fecha

        # Validar que el slot no esté ya bloqueado por día completo
        if ServicioBloqueo.servicio_bloqueado_en_fecha(self.servicio_id, self.fecha):
            raise ValidationError({
                'fecha': 'Este servicio está bloqueado por día completo en esta fecha. No se pueden bloquear slots individuales.'
            })

        # Validar que el slot exista en la configuración del servicio
        from ventas.views.calendario_matriz_view import extraer_slots_para_fecha
        slots_disponibles_config = extraer_slots_para_fecha(
            self.servicio.slots_disponibles,
            self.fecha
        )



# ============================================================================
# SISTEMA DE COMANDAS
# ============================================================================

class Comanda(models.Model):
    """
    Comanda de productos para una reserva.
    Similar a una orden de restaurante - permite al personal tomar pedidos
    que aparecen en tiempo real en la cocina/bar.
    """
    ESTADO_CHOICES = [
        # Estados para comandas creadas por personal (flujo original)
        ('pendiente', 'Pendiente'),
        ('procesando', 'En Proceso'),
        ('entregada', 'Entregada'),
        ('cancelada', 'Cancelada'),

        # Estados para comandas creadas por clientes (vía WhatsApp)
        ('borrador', 'Borrador'),                    # Cliente está armando su pedido
        ('pendiente_pago', 'Pendiente de Pago'),     # Cliente finalizó pero no pagó
        ('pago_confirmado', 'Pago Confirmado'),      # Pago Flow confirmado
        ('pago_fallido', 'Pago Fallido'),            # Pago rechazado
    ]

    # Relaciones
    venta_reserva = models.ForeignKey(
        VentaReserva,
        on_delete=models.CASCADE,
        related_name='comandas',
        verbose_name='Reserva'
    )

    # Información temporal
    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora de Solicitud'
    )
    hora_solicitud = models.TimeField(
        auto_now_add=True,
        verbose_name='Hora de Solicitud',
        help_text='Hora específica para ordenamiento rápido'
    )

    # Estado y gestión
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado',
        db_index=True
    )

    # Notas generales de la comanda
    notas_generales = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas Generales',
        help_text='Indicaciones especiales para toda la comanda'
    )

    # Auditoría
    usuario_solicita = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='comandas_solicitadas',
        verbose_name='Usuario que Solicita'
    )

    usuario_procesa = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comandas_procesadas',
        verbose_name='Usuario que Procesa'
    )

    fecha_inicio_proceso = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Inicio de Proceso'
    )

    fecha_entrega = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Entrega'
    )

    fecha_entrega_objetivo = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha/Hora Entrega Objetivo',
        help_text='Para cuándo se necesita este pedido. Si es vacío, es para ahora (inmediato).',
        db_index=True
    )

    # Campos para sistema de comandas de clientes (vía WhatsApp)
    token_acceso = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Token de Acceso',
        help_text='Token único para acceso del cliente vía WhatsApp'
    )
    creada_por_cliente = models.BooleanField(
        default=False,
        verbose_name='Creada por Cliente',
        help_text='Indica si la comanda fue creada por el cliente vía link de WhatsApp',
        db_index=True
    )
    fecha_vencimiento_link = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Vencimiento del Link',
        help_text='Fecha límite para usar el link de comanda (24-48 horas típicamente)'
    )

    # Campos para integración con Flow (pagos)
    flow_order_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='Flow Order ID',
        help_text='ID de la orden en Flow'
    )
    flow_token = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Flow Token',
        help_text='Token de pago de Flow'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Comanda'
        verbose_name_plural = 'Comandas'
        ordering = ['-fecha_solicitud']
        indexes = [
            models.Index(fields=['estado', '-fecha_solicitud'], name='comanda_estado_fecha_idx'),
            models.Index(fields=['venta_reserva', 'estado'], name='comanda_reserva_estado_idx'),
        ]

    def __str__(self):
        cliente_nombre = self.venta_reserva.cliente.nombre if self.venta_reserva and self.venta_reserva.cliente else "Sin cliente"
        return f"Comanda #{self.id} - {cliente_nombre} - {self.get_estado_display()}"

    def tiempo_espera(self):
        """Calcula el tiempo de espera en minutos"""
        from django.utils import timezone
        if self.estado == 'entregada' and self.fecha_entrega:
            delta = self.fecha_entrega - self.fecha_solicitud
        elif self.estado == 'procesando' and self.fecha_inicio_proceso:
            delta = timezone.now() - self.fecha_solicitud
        else:
            delta = timezone.now() - self.fecha_solicitud
        return int(delta.total_seconds() / 60)

    def marcar_procesando(self, usuario):
        """Marca la comanda como en proceso"""
        from django.utils import timezone
        self.estado = 'procesando'
        self.usuario_procesa = usuario
        self.fecha_inicio_proceso = timezone.now()
        self.save()

    def marcar_entregada(self):
        """Marca la comanda como entregada"""
        from django.utils import timezone
        self.estado = 'entregada'
        self.fecha_entrega = timezone.now()
        self.save()

    @property
    def es_editable(self):
        """La comanda solo es editable si está pendiente"""
        return self.estado == 'pendiente'

    @property
    def puede_agregar_productos(self):
        """Solo se pueden agregar productos en estado pendiente"""
        return self.estado == 'pendiente'

    @property
    def total_items(self):
        """Retorna el total de items en la comanda"""
        try:
            return self.detalles.aggregate(total=models.Sum('cantidad'))['total'] or 0
        except:
            return 0

    @property
    def total_precio(self):
        """Calcula el precio total de la comanda"""
        try:
            from decimal import Decimal
            total = self.detalles.aggregate(
                total=models.Sum(models.F('cantidad') * models.F('precio_unitario'))
            )['total']
            return total or Decimal('0')
        except:
            return Decimal('0')

    @property
    def lugar_entrega(self):
        """Retorna el lugar de entrega basado en el servicio de la reserva"""
        try:
            if self.venta_reserva and self.venta_reserva.reserva_servicios.exists():
                # Si tiene servicios, usar la sala del primer servicio
                primer_servicio = self.venta_reserva.reserva_servicios.first()
                if primer_servicio and hasattr(primer_servicio, 'sala'):
                    return f"Sala: {primer_servicio.sala}"
            return "Cafetería"
        except:
            return "Cafetería"
    #     # TODO: Implementar lógica basada en servicios
    #     servicios = self.venta_reserva.reservaservicios.all()
    #     for servicio in servicios:
    #         nombre = servicio.servicio.nombre.lower()
    #         if 'tina' in nombre:
    #             return 'Tinas'
    #         elif 'cabaña' in nombre:
    #             return 'Cabaña'
    #         elif 'masaje' in nombre:
    #             return 'Sala de Masajes'
    #     return 'Cafetería'

    # @property
    # def es_urgente(self):
    #     """Determina si la comanda es urgente (más de 15 minutos esperando)"""
    #     return self.tiempo_espera() > 15 and self.estado == 'pendiente'

    @property
    def es_urgente(self):
        """Determina si la comanda es urgente (más de 15 minutos esperando)"""
        try:
            return self.tiempo_espera() > 15 and self.estado == 'pendiente'
        except:
            return False

    @property
    def notas(self):
        """Alias para notas_generales para compatibilidad"""
        return self.notas_generales or ""

    # ========================================
    # Métodos para sistema de comandas de clientes (vía WhatsApp)
    # ========================================

    def generar_token_acceso(self):
        """Genera un token único para acceso del cliente"""
        import secrets
        self.token_acceso = secrets.token_urlsafe(32)
        from django.utils import timezone
        from datetime import timedelta
        self.fecha_vencimiento_link = timezone.now() + timedelta(hours=48)
        self.save()
        return self.token_acceso

    def es_link_valido(self):
        """Verifica si el link aún es válido"""
        from django.utils import timezone
        if not self.fecha_vencimiento_link:
            return False
        return timezone.now() < self.fecha_vencimiento_link

    def obtener_url_cliente(self):
        """Obtiene la URL completa para el cliente."""
        from django.urls import reverse
        from django.conf import settings
        # Dominio de producción. Override con COMANDA_PUBLIC_BASE_URL si se necesita.
        site_url = getattr(settings, 'COMANDA_PUBLIC_BASE_URL', 'https://www.aremko.cl')
        path = reverse('ventas:comanda_cliente_api', kwargs={'token': self.token_acceso})
        return f"{site_url}{path}"

    def obtener_mensaje_whatsapp(self):
        """Genera el mensaje de WhatsApp con el link"""
        url_cliente = self.obtener_url_cliente()
        cliente = self.venta_reserva.cliente

        mensaje = f"""Hola {cliente.nombre}! 👋

Aquí está tu link para hacer tu pedido de cafetería/bar:

{url_cliente}

📱 Solo toca el link, selecciona lo que deseas y paga con tarjeta.
⏰ El link es válido por 48 horas.

¡Disfruta tu visita a Aremko! 🌿"""

        return mensaje.strip()

    def obtener_url_whatsapp(self):
        """Genera la URL de WhatsApp con el mensaje pre-cargado"""
        from urllib.parse import quote
        cliente = self.venta_reserva.cliente
        telefono = cliente.telefono.replace('+', '').replace(' ', '').replace('-', '')
        mensaje = self.obtener_mensaje_whatsapp()
        return f"https://wa.me/{telefono}?text={quote(mensaje)}"

    # ========================================
    # Fin métodos para comandas de clientes
    # ========================================

    def save(self, *args, **kwargs):
        """
        Guarda la comanda y auto-crea ReservaProducto para integración con facturación.

        La comanda es para seguimiento operativo (cocina/bar), mientras que
        ReservaProducto es para contabilidad y cobro. Este método mantiene ambos
        sistemas sincronizados automáticamente.

        NOTA: Cuando se crea desde el admin, la creación de ReservaProducto se hace
        en save_formset() después de guardar los detalles. Este método solo se usa
        para creación programática (API, scripts, etc.)
        """
        # Guardar la comanda primero
        is_new = self.pk is None

        # Detectar cambio de estado a 'entregada' para propagar fecha_entrega
        estado_anterior = None
        if not is_new:
            try:
                estado_anterior = Comanda.objects.filter(pk=self.pk).values_list('estado', flat=True).first()
            except Exception:
                pass

        super().save(*args, **kwargs)

        # Al pasar a 'entregada', descontar el inventario de sus productos.
        if self.estado == 'entregada' and estado_anterior and estado_anterior != 'entregada':
            self.entregar_inventario()

        # Auto-crear ReservaProducto por cada DetalleComanda (solo si es nueva comanda)
        # y NO viene del admin (el admin usa save_formset para esto).
        # IMPORTANTE: se crea con fecha_entrega=NULL (NO la fecha objetivo). El stock
        # NO se descuenta al crear la comanda: se descuenta recién cuando la comanda
        # se entrega (estado='entregada') o cuando llega la fecha objetivo (cron).
        # La fecha planificada vive en Comanda.fecha_entrega_objetivo.
        if is_new and not getattr(self, '_from_admin', False):
            for detalle in self.detalles.all():
                ReservaProducto.objects.get_or_create(
                    venta_reserva=self.venta_reserva,
                    producto=detalle.producto,
                    defaults={
                        'cantidad': detalle.cantidad,
                        'precio_unitario_venta': detalle.precio_unitario,
                        'fecha_entrega': None,  # se setea al entregar / al vencer objetivo
                    }
                )

    def entregar_inventario(self, fecha=None):
        """Marca como entregados (setea fecha_entrega) los ReservaProducto de esta
        comanda que aún no la tienen, lo que dispara el descuento de inventario vía
        el signal post_save. Idempotente: las líneas ya entregadas (con fecha) se
        omiten, así no hay doble descuento.

        Se llama desde dos lados:
          - al pasar la comanda a 'entregada' (entrega real anticipada o a tiempo),
          - desde el cron `procesar_entregas_comandas_vencidas` cuando llega la
            fecha objetivo sin que se haya marcado entregada.

        Devuelve la cantidad de líneas marcadas.
        """
        from django.utils import timezone
        if not self.venta_reserva:
            return 0
        if fecha is None:
            fecha = timezone.now().date()
        marcadas = 0
        for detalle in self.detalles.select_related('producto').all():
            for rp in ReservaProducto.objects.filter(
                venta_reserva=self.venta_reserva,
                producto=detalle.producto,
                fecha_entrega__isnull=True,
            ):
                rp.fecha_entrega = fecha
                rp.save(update_fields=['fecha_entrega'])  # dispara el descuento de stock
                marcadas += 1
        return marcadas


class DetalleComanda(models.Model):
    """
    Detalle de productos en una comanda.
    Permite especificaciones individuales por producto (sabor, temperatura, etc.)
    """
    comanda = models.ForeignKey(
        Comanda,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Comanda'
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        verbose_name='Producto'
    )

    cantidad = models.PositiveIntegerField(
        default=1,
        verbose_name='Cantidad'
    )

    # Especificaciones del producto
    especificaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name='Especificaciones',
        help_text='Ej: Sabor frutilla, sin azúcar, con endulzante, bien frío, etc.'
    )

    # Precio al momento de la comanda (snapshot)
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name='Precio Unitario'
    )

    class Meta:
        verbose_name = 'Detalle de Comanda'
        verbose_name_plural = 'Detalles de Comanda'
        ordering = ['id']

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre}"

    @property
    def subtotal(self):
        """Calcula el subtotal de este item"""
        return self.cantidad * self.precio_unitario

    def save(self, *args, **kwargs):
        # Capturar precio actual del producto si no está definido
        if not self.precio_unitario:
            self.precio_unitario = self.producto.precio_base
        super().save(*args, **kwargs)


# ============================================================================
# MODELO: ServicioSlotBloqueo - Bloqueo de slots específicos
# ============================================================================

class ServicioSlotBloqueo(models.Model):
    """
    Bloquea UN slot específico (horario) de un servicio en una fecha determinada.
    """
    servicio = models.ForeignKey('Servicio', on_delete=models.CASCADE, related_name='slots_bloqueados')
    fecha = models.DateField()
    hora_slot = models.CharField(max_length=5)
    motivo = models.CharField(max_length=200)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notas = models.TextField(blank=True, null=True, verbose_name='Notas', help_text='Notas adicionales sobre el bloqueo')

    class Meta:
        verbose_name = 'Slot Bloqueado'
        verbose_name_plural = 'Slots Bloqueados'
        unique_together = ['servicio', 'fecha', 'hora_slot']
        ordering = ['fecha', 'hora_slot']

    def __str__(self):
        return f"{self.servicio.nombre} - {self.fecha} {self.hora_slot} - {self.motivo}"

    def save(self, *args, **kwargs):
        # Si estamos editando, permitir guardar el mismo slot (no es duplicado)
        if self.pk:
            # Es una edición, verificar cambios
            original = ServicioSlotBloqueo.objects.get(pk=self.pk)
            # Si no cambió nada relevante, permitir guardar
            if (original.servicio_id == self.servicio_id and
                original.fecha == self.fecha and
                original.hora_slot == self.hora_slot):
                # Aún así, guardar por si cambió el motivo o activo
                super().save(*args, **kwargs)
                return

        # Validar que no exista otro bloqueo activo para este mismo slot
        bloqueos_duplicados = ServicioSlotBloqueo.objects.filter(
            servicio=self.servicio,
            fecha=self.fecha,
            hora_slot=self.hora_slot,
            activo=True
        )

        if self.pk:
            bloqueos_duplicados = bloqueos_duplicados.exclude(pk=self.pk)

        if bloqueos_duplicados.exists():
            raise ValidationError({
                'hora_slot': f'Ya existe un bloqueo activo para {self.servicio.nombre} el {self.fecha.strftime("%d/%m/%Y")} a las {self.hora_slot}'
            })

        # IMPORTANTE: Guardar el objeto después de todas las validaciones
        super().save(*args, **kwargs)

    @classmethod
    def slot_bloqueado(cls, servicio_id, fecha, hora_slot):
        """
        Método de clase para verificar si un slot específico está bloqueado.

        Args:
            servicio_id: ID del servicio
            fecha: Fecha a verificar (date object)
            hora_slot: Horario a verificar (string, ej: "14:30")

        Returns:
            bool: True si está bloqueado, False si está disponible
        """
        return cls.objects.filter(
            servicio_id=servicio_id,
            fecha=fecha,
            hora_slot=hora_slot,
            activo=True
        ).exists()


# ============================================================================
# ENCUESTA DE SATISFACCIÓN — Sistema VoC integrado (Tarea 1.4 plan maestro)
# Reemplaza el Google Form externo con captura nativa a BD para análisis IA
# ============================================================================

CAL_1_5 = [MinValueValidator(1), MaxValueValidator(5)]
NPS_0_10 = [MinValueValidator(0), MaxValueValidator(10)]


class EncuestaSatisfaccion(models.Model):
    """Respuesta a la encuesta de satisfacción enviada D+1 vía email.

    Reemplaza el Google Form histórico (datos importados con origen='legacy_google_form').
    Cada respuesta se vincula opcionalmente a un Cliente y a una VentaReserva específica
    para poder cruzar con métricas operativas y comerciales.
    """

    ORIGEN_CHOICES = [
        ('formulario_web', 'Formulario web Aremko'),
        ('legacy_google_form', 'Google Form (legacy)'),
        ('manual', 'Ingreso manual'),
    ]

    COMO_SE_ENTERO_CHOICES = [
        ('soy_cliente', 'Soy cliente recurrente'),
        ('recomendacion', 'Recomendación de conocido'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('google', 'Google / búsqueda'),
        ('blog', 'Blog Aremko'),
        ('publicidad', 'Publicidad'),
        ('otro', 'Otro'),
    ]

    OCASION_CHOICES = [
        ('pareja', 'Escapada en pareja'),
        ('cumpleanos', 'Cumpleaños'),
        ('aniversario', 'Aniversario'),
        ('amigos', 'Amigos'),
        ('familia', 'Familia'),
        ('trabajo', 'Trabajo / empresa'),
        ('solo', 'Solo / sola'),
        ('otro', 'Otro'),
    ]

    INTENCION_VOLVER_CHOICES = [
        ('si_6m', 'Sí, en menos de 6 meses'),
        ('si_12m', 'Sí, en 6-12 meses'),
        ('si_mas_1a', 'Sí, en más de 1 año'),
        ('no_seguro', 'No estoy seguro/a'),
        ('probablemente_no', 'Probablemente no'),
    ]

    # === Metadata ===
    cliente = models.ForeignKey(
        'Cliente', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='encuestas_satisfaccion'
    )
    venta_reserva = models.ForeignKey(
        'VentaReserva', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='encuestas_satisfaccion',
        help_text='Reserva específica que motivó esta encuesta'
    )
    fecha_respuesta = models.DateTimeField(default=timezone.now, db_index=True)
    fecha_visita = models.DateField(null=True, blank=True, help_text='Fecha de la visita evaluada')
    origen = models.CharField(max_length=30, choices=ORIGEN_CHOICES, default='formulario_web')

    # Datos de contacto (si no hay Cliente vinculado, ej. encuestas anónimas legacy)
    contacto_nombre = models.CharField(max_length=200, blank=True)
    contacto_email = models.EmailField(blank=True)
    contacto_telefono = models.CharField(
        max_length=30, blank=True,
        help_text='Teléfono opcional para contacto si requiere follow-up. '
                  'Si la encuesta viene vinculada a un Cliente, se prellena con su teléfono.'
    )

    # === Servicios contratados (multiselect persistido como lista) ===
    servicios_contratados = models.JSONField(
        default=list, blank=True,
        help_text='Lista: tina_hidromasaje, tina_sin_hidromasaje, masaje, alojamiento'
    )

    # === Calificaciones operativas (1-5, opcionales según servicio) ===
    cal_temperatura_tina = models.PositiveSmallIntegerField(null=True, blank=True, validators=CAL_1_5)
    cal_transparencia_agua = models.PositiveSmallIntegerField(null=True, blank=True, validators=CAL_1_5)
    cal_limpieza_tinas = models.PositiveSmallIntegerField(null=True, blank=True, validators=CAL_1_5)
    cal_limpieza_cabana = models.PositiveSmallIntegerField(null=True, blank=True, validators=CAL_1_5)
    cal_temperatura_cabana = models.PositiveSmallIntegerField(null=True, blank=True, validators=CAL_1_5)
    cal_limpieza_sala_masajes = models.PositiveSmallIntegerField(null=True, blank=True, validators=CAL_1_5)
    cal_servicio_masajes = models.PositiveSmallIntegerField(null=True, blank=True, validators=CAL_1_5)

    # === Calificaciones comerciales (1-5) ===
    cal_calidad_precio = models.PositiveSmallIntegerField(null=True, blank=True, validators=CAL_1_5)
    cal_atencion_ventas = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=CAL_1_5,
        help_text='Atención por WhatsApp/Instagram/Facebook'
    )
    cal_compra_web = models.PositiveSmallIntegerField(null=True, blank=True, validators=CAL_1_5)
    cal_atencion_visita = models.PositiveSmallIntegerField(null=True, blank=True, validators=CAL_1_5)

    # === Experiencia general + NPS ===
    cal_experiencia_general = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=CAL_1_5,
        help_text='Calificación global de la experiencia'
    )
    nps_score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=NPS_0_10,
        help_text='0-10. Promotores: 9-10. Pasivos: 7-8. Detractores: 0-6'
    )

    # === Texto libre (input para análisis IA cualitativo) ===
    lo_que_mas_gusto = models.TextField(blank=True)
    sugerencias = models.TextField(blank=True)
    decepcion = models.TextField(blank=True, help_text='¿Hubo algo que te decepcionó?')

    # === Comercial / segmentación ===
    como_se_entero = models.CharField(max_length=30, choices=COMO_SE_ENTERO_CHOICES, blank=True)
    como_se_entero_otro = models.CharField(max_length=200, blank=True)
    ocasion_visita = models.CharField(max_length=30, choices=OCASION_CHOICES, blank=True)
    intencion_volver = models.CharField(max_length=30, choices=INTENCION_VOLVER_CHOICES, blank=True)

    # === Permisos ===
    permite_uso_comentarios_redes = models.BooleanField(
        null=True, blank=True,
        help_text='¿Podemos usar tus comentarios anónimos en redes sociales?'
    )
    quiere_newsletter = models.BooleanField(null=True, blank=True)
    permite_seguimiento = models.BooleanField(
        null=True, blank=True,
        help_text='¿Podemos contactarte si necesitamos más información?'
    )

    # === Análisis IA (cache de procesamiento semanal) ===
    analisis_ia = models.JSONField(
        null=True, blank=True,
        help_text='Análisis automático: sentiment, temas, urgencia detectados'
    )

    # === Follow-up operativo ===
    requiere_followup = models.BooleanField(
        default=False,
        help_text='Marcado cuando NPS<=5 o califica 1-2 en alguna dimensión crítica'
    )
    followup_completado = models.BooleanField(default=False)
    followup_notas = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Encuesta de satisfacción'
        verbose_name_plural = 'Encuestas de satisfacción'
        ordering = ['-fecha_respuesta']
        indexes = [
            models.Index(fields=['-fecha_respuesta']),
            models.Index(fields=['cliente']),
            models.Index(fields=['nps_score']),
            models.Index(fields=['requiere_followup', 'followup_completado']),
            models.Index(fields=['origen']),
        ]

    def __str__(self):
        nombre = self.contacto_nombre or (self.cliente.nombre if self.cliente else 'Anónimo')
        fecha = self.fecha_respuesta.strftime('%Y-%m-%d') if self.fecha_respuesta else '?'
        nps = f' NPS={self.nps_score}' if self.nps_score is not None else ''
        return f'Encuesta {fecha} · {nombre}{nps}'

    @property
    def nps_categoria(self):
        if self.nps_score is None:
            return None
        if self.nps_score >= 9:
            return 'promotor'
        if self.nps_score >= 7:
            return 'pasivo'
        return 'detractor'

    @property
    def califica_para_review_publico(self):
        """Retorna True si el cliente reportó experiencia muy positiva (4-5⭐ o NPS>=7).

        Usado por la página de "Gracias" para mostrar/ocultar el funnel a Google Reviews.
        Filosofía: solo invitamos a reseña pública a clientes contentos. Ético + estratégico.
        """
        if self.cal_experiencia_general is not None and self.cal_experiencia_general >= 4:
            return True
        if self.nps_score is not None and self.nps_score >= 7:
            return True
        return False

    def evaluar_followup(self):
        """Determina si esta encuesta requiere follow-up urgente.

        Criterios:
        - NPS detractor (<=6)
        - Cualquier calificación 1-2 en dimensiones operativas críticas
        - Texto en 'decepcion' o 'sugerencias' marcado por IA como urgente
        """
        if self.nps_score is not None and self.nps_score <= 6:
            return True
        criticas = [
            self.cal_temperatura_tina, self.cal_atencion_visita,
            self.cal_servicio_masajes, self.cal_experiencia_general,
            self.cal_limpieza_tinas, self.cal_limpieza_cabana,
        ]
        if any(c is not None and c <= 2 for c in criticas):
            return True
        if self.analisis_ia and self.analisis_ia.get('urgencia') == 'alta':
            return True
        return False

    def save(self, *args, **kwargs):
        # Auto-marcar follow-up si aplica
        if not self.followup_completado:
            self.requiere_followup = self.evaluar_followup()
        super().save(*args, **kwargs)


class ReviewSnapshot(models.Model):
    """Snapshot semanal manual de reviews externas (Google + TripAdvisor).

    Cada lunes Jorge entra al admin e ingresa 4 números (rating + total de cada plataforma).
    El servicio de análisis IA cruza esto con NPS interno para detectar gaps:
    p.ej. NPS interno alto pero rating Google bajando → revisar review reciente negativa.

    Tarea 2.8 plan maestro.
    """
    fecha = models.DateField(
        unique=True, db_index=True, default=timezone.localdate,
        help_text='Lunes de la semana del snapshot. Solo 1 por fecha.'
    )

    # Google Reviews
    google_rating = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True,
        help_text='Rating promedio Google (1.00 - 5.00)'
    )
    google_total = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Total de reviews acumuladas en Google'
    )
    google_url = models.URLField(
        max_length=500, blank=True,
        help_text='URL del perfil de Google Maps (autocompletada desde el último snapshot)'
    )

    # TripAdvisor
    tripadvisor_rating = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True,
        help_text='Rating promedio TripAdvisor (1.00 - 5.00)'
    )
    tripadvisor_total = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Total de reviews acumuladas en TripAdvisor'
    )
    tripadvisor_url = models.URLField(
        max_length=500, blank=True,
        help_text='URL del perfil de TripAdvisor (autocompletada desde el último snapshot)'
    )

    # Notas operativas (opcional)
    notas = models.TextField(
        blank=True,
        help_text='Cualquier observación relevante: review reciente notable, '
                  'cambio de rating, comentarios destacados...'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Snapshot de reviews externas'
        verbose_name_plural = 'Snapshots de reviews externas'
        ordering = ['-fecha']

    def __str__(self):
        partes = [f'Reviews {self.fecha.strftime("%d/%m/%Y")}']
        if self.google_rating is not None:
            partes.append(f'Google {self.google_rating}★ ({self.google_total or 0})')
        if self.tripadvisor_rating is not None:
            partes.append(f'TA {self.tripadvisor_rating}★ ({self.tripadvisor_total or 0})')
        return ' · '.join(partes)

    def get_previous(self):
        """Snapshot anterior (por fecha), para calcular deltas."""
        return ReviewSnapshot.objects.filter(fecha__lt=self.fecha).order_by('-fecha').first()

    def deltas(self):
        """Diferencias vs snapshot anterior. None si es el primero."""
        prev = self.get_previous()
        if not prev:
            return None
        def _diff(curr, prev):
            if curr is None or prev is None:
                return None
            return float(curr) - float(prev)
        return {
            'google_rating_delta': _diff(self.google_rating, prev.google_rating),
            'google_total_delta': _diff(self.google_total, prev.google_total),
            'tripadvisor_rating_delta': _diff(self.tripadvisor_rating, prev.tripadvisor_rating),
            'tripadvisor_total_delta': _diff(self.tripadvisor_total, prev.tripadvisor_total),
            'fecha_anterior': prev.fecha,
        }

    def save(self, *args, **kwargs):
        # Heredar URLs del snapshot más reciente si quedaron vacías
        if not self.google_url or not self.tripadvisor_url:
            latest = ReviewSnapshot.objects.exclude(pk=self.pk).order_by('-fecha').first()
            if latest:
                if not self.google_url:
                    self.google_url = latest.google_url
                if not self.tripadvisor_url:
                    self.tripadvisor_url = latest.tripadvisor_url
        super().save(*args, **kwargs)


class Review(models.Model):
    """Review individual de Google Maps o TripAdvisor capturado vía screenshot.

    Workflow:
    1. Jorge sube el screenshot + selecciona la fuente
    2. Click "Extraer con IA" → autocompleta autor, fecha, rating, texto, idioma
    3. Click "Generar respuesta" → propone respuesta lista para copiar/pegar
    4. Jorge edita si hace falta, copia, publica en la plataforma externa
    5. Marca como "respondida" en el admin

    El análisis IA semanal lee texto completo de cada review nueva para
    cruzar con NPS interno y detectar temas recurrentes.
    """

    FUENTE_CHOICES = [
        ('google', 'Google Maps'),
        ('tripadvisor', 'TripAdvisor'),
    ]
    IDIOMA_CHOICES = [
        ('es', 'Español'),
        ('en', 'Inglés'),
        ('pt', 'Portugués'),
        ('otro', 'Otro'),
    ]
    SENTIMIENTO_CHOICES = [
        ('positivo', 'Positivo'),
        ('neutro', 'Neutro'),
        ('negativo', 'Negativo'),
    ]

    # Origen
    fuente = models.CharField(max_length=20, choices=FUENTE_CHOICES, db_index=True)
    screenshot = models.ImageField(
        upload_to='reviews/%Y/%m/', blank=True, null=True,
        help_text='Captura de pantalla del review para extracción con IA',
    )

    # Datos extraídos (editables por Jorge si la IA se equivocó)
    fecha_review = models.DateField(null=True, blank=True, db_index=True)
    autor = models.CharField(max_length=200, blank=True)
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='1-5 estrellas',
    )
    texto = models.TextField(
        blank=True,
        help_text='Vacío si el cliente solo dejó estrellas sin comentario',
    )
    idioma = models.CharField(max_length=10, choices=IDIOMA_CHOICES, default='es')

    # Procesamiento IA
    extraccion_completada = models.BooleanField(
        default=False,
        help_text='True cuando la IA ya procesó el screenshot',
    )

    # Respuesta de Aremko
    respuesta_sugerida = models.TextField(
        blank=True,
        help_text='Respuesta generada por IA, lista para copiar/pegar',
    )
    respuesta_publicada = models.BooleanField(default=False)
    respuesta_publicada_at = models.DateTimeField(null=True, blank=True)

    # Análisis (auto-poblado en futuro)
    sentimiento = models.CharField(
        max_length=15, choices=SENTIMIENTO_CHOICES, blank=True,
        help_text='Auto-derivado del rating (1-3 negativo, 4 neutro, 5 positivo)',
    )
    temas_detectados = models.JSONField(
        default=list, blank=True,
        help_text='Lista de temas mencionados (ej. ["temperatura_tina", "limpieza"])',
    )

    # Metadata
    notas_internas = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Review externo'
        verbose_name_plural = 'Reviews externos'
        ordering = ['-fecha_review', '-created_at']

    def __str__(self):
        partes = [self.get_fuente_display()]
        if self.fecha_review:
            partes.append(self.fecha_review.strftime('%d/%m/%Y'))
        if self.rating:
            partes.append(f'{self.rating}★')
        if self.autor:
            partes.append(self.autor[:30])
        return ' · '.join(partes)

    def auto_sentimiento(self):
        """Deriva sentimiento del rating si no está seteado manualmente."""
        if self.rating is None:
            return ''
        if self.rating <= 3:
            return 'negativo'
        if self.rating == 4:
            return 'neutro'
        return 'positivo'

    def save(self, *args, **kwargs):
        if self.rating is not None and not self.sentimiento:
            self.sentimiento = self.auto_sentimiento()
        super().save(*args, **kwargs)


class PendingReservation(models.Model):
    """Reserva tentativa antes de confirmacion de pago Flow.

    Se crea cuando el cliente envia el checkout con metodo_pago='flow'.
    No genera VentaReserva ni ReservaServicio hasta que Flow confirme el pago
    via webhook. Si el cliente abandona, queda como 'iniciado' y un cleanup
    periodico la marca 'expirado'.
    """
    ESTADO_CHOICES = [
        ('iniciado', 'Iniciado (esperando pago Flow)'),
        ('confirmado', 'Confirmado (VentaReserva creada)'),
        ('rechazado', 'Rechazado por Flow'),
        ('cancelado', 'Cancelado por usuario'),
        ('expirado', 'Expirado por timeout'),
        ('slot_perdido', 'Slot tomado mientras se pagaba (requiere reembolso manual)'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='pending_reservations')
    cart_data = models.JSONField(help_text='Snapshot del carrito: servicios, giftcards, totales, descuentos')
    metodo_pago = models.CharField(max_length=20, default='flow')
    monto = models.IntegerField(help_text='Total en CLP al momento del checkout')

    flow_token = models.CharField(max_length=100, blank=True, db_index=True)
    flow_url = models.URLField(max_length=500, blank=True)

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='iniciado', db_index=True)
    venta_reserva = models.OneToOneField(
        'VentaReserva', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pending_origin'
    )

    notas = models.TextField(blank=True, help_text='Mensajes de error o notas operativas')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = 'Reserva pendiente (pre-pago Flow)'
        verbose_name_plural = 'Reservas pendientes (pre-pago Flow)'
        ordering = ['-created_at']

    def __str__(self):
        return f'Pending #{self.id} {self.cliente.nombre} ${self.monto:,} [{self.estado}]'

    def is_expired(self):
        return timezone.now() > self.expires_at

    def marcar_confirmado(self, venta_reserva):
        self.estado = 'confirmado'
        self.venta_reserva = venta_reserva
        self.save(update_fields=['estado', 'venta_reserva', 'updated_at'])

    def marcar_slot_perdido(self, detalle=''):
        self.estado = 'slot_perdido'
        self.notas = (self.notas + '\n' + detalle).strip()
        self.save(update_fields=['estado', 'notas', 'updated_at'])


class MetaSnapshot(models.Model):
    """Snapshot consolidado de Meta (Facebook + Instagram + Ads).

    Cada snapshot es una foto en el tiempo de las metricas organicas y de
    paid ads de Aremko. Se generan:
    - Manualmente desde el admin Django (botones de diagnostico)
    - Automaticamente cada lunes 10am (integrado al brief semanal)

    El campo `datos` guarda el JSON completo devuelto por meta_reporter.py
    (ver `get_full_snapshot()`). El analisis IA opcional se cachea en
    `analisis_ia` para no re-llamar al LLM.
    """
    TIPO_CHOICES = [
        ('full', 'Completo (FB + IG + Ads)'),
        ('facebook', 'Solo Facebook'),
        ('instagram', 'Solo Instagram'),
        ('ads', 'Solo Ads (paid)'),
    ]
    GENERADO_POR_CHOICES = [
        ('admin_manual', 'Admin Django (manual)'),
        ('cron_weekly', 'Cron semanal (lunes)'),
        ('management_command', 'Comando manual desde shell'),
        ('api', 'API endpoint'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='full', db_index=True)
    period_days = models.PositiveIntegerField(
        default=28,
        help_text='Ventana de dias del snapshot (28 default para tendencia mensual)',
    )
    datos = models.JSONField(help_text='JSON completo devuelto por meta_reporter')
    analisis_ia = models.TextField(
        blank=True,
        help_text='Analisis IA del snapshot (cache, opcional)',
    )
    generado_por = models.CharField(
        max_length=30, choices=GENERADO_POR_CHOICES, default='admin_manual', db_index=True,
    )
    error = models.TextField(blank=True, help_text='Mensajes de error si la captura fue parcial')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Snapshot Meta (FB + IG + Ads)'
        verbose_name_plural = 'Snapshots Meta'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['tipo', '-created_at']),
        ]

    def __str__(self):
        fecha = self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '?'
        return f'Meta snapshot {self.tipo} {fecha} ({self.period_days}d)'

    @property
    def fb_fan_count(self) -> int:
        try:
            return self.datos.get('facebook', {}).get('overview', {}).get('fan_count') or 0
        except (AttributeError, TypeError):
            return 0

    @property
    def ig_followers(self) -> int:
        try:
            return self.datos.get('instagram', {}).get('overview', {}).get('followers_count') or 0
        except (AttributeError, TypeError):
            return 0

    @property
    def ads_spend_period(self) -> float:
        """Suma del gasto del periodo en TODAS las cuentas publicitarias accesibles."""
        try:
            total = 0.0
            # Formato nuevo: lista ads_accounts con multiples cuentas
            for acct in (self.datos.get('ads_accounts') or []):
                try:
                    total += float(acct.get('insights_period', {}).get('spend') or 0)
                except (TypeError, ValueError):
                    pass
            # Compat con formato antiguo (snapshots anteriores con ads_principal)
            if not self.datos.get('ads_accounts'):
                total = float(self.datos.get('ads_principal', {}).get('insights', {}).get('spend') or 0)
            return total
        except (AttributeError, TypeError, ValueError):
            return 0.0


class WeeklySurveyAnalysis(models.Model):
    """Cache del analisis IA semanal de encuestas de satisfaccion.

    Se persiste cada lunes 9 AM cuando corre `analyze_surveys_weekly`.
    El brief semanal de las 10 AM lee el ultimo registro para incluir
    insights operativos de encuestas en el contexto del LLM.

    Resuelve gap del brief: antes get_alertas_analisis_ia_anterior() retornaba
    None y el brief perdia informacion cualitativa critica.
    """
    semana_inicio = models.DateField(
        db_index=True,
        help_text='Lunes de la semana que se analizo',
    )
    semana_fin = models.DateField(help_text='Domingo de la semana que se analizo')
    encuestas_count = models.PositiveIntegerField(default=0)
    nps_promedio = models.FloatField(null=True, blank=True)
    datos = models.JSONField(
        help_text='Output completo del LLM: resumen, alertas, oportunidades, ideas marketing, follow-ups urgentes',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Analisis IA encuestas semanal'
        verbose_name_plural = 'Analisis IA encuestas semanales'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['-semana_inicio']),
        ]

    def __str__(self):
        return f'Analisis encuestas semana {self.semana_inicio} ({self.encuestas_count} encuestas)'


class WeeklyObjective(models.Model):
    """Objetivo de marketing/comercial para una semana especifica.

    Jorge edita este registro cada domingo (o el lunes muy temprano antes
    del cron de las 10 AM) para indicar que quiere priorizar esa semana.
    Ejemplos:
    - "Esta semana foco en empresarial — viene grupo de Datamatic miercoles"
    - "Vender 5 cabañas para Dia del Padre, todavia hay disponibilidad"
    - "Bajar engagement caro: pausar boost del Reel descontracturante y crear uno nuevo"

    El brief lee el objetivo de la semana actual (o del fin de semana anterior si
    todavia no se actualizo) y lo usa como input central para guiar al LLM.
    """
    semana_inicio = models.DateField(
        unique=True, db_index=True,
        help_text='Lunes de la semana a la que aplica este objetivo',
    )
    objetivo = models.TextField(
        help_text='Texto libre. 2-3 parrafos. Que se quiere priorizar esta semana, '
                  'que evitar, que metricas mover, fechas clave del periodo.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Objetivo semanal'
        verbose_name_plural = 'Objetivos semanales'
        ordering = ['-semana_inicio']

    def __str__(self):
        return f'Objetivo semana {self.semana_inicio.strftime("%d-%m-%Y")}'


# ============================================================================
# COMPETITOR ANALYSIS MODELS
# ============================================================================

class Competitor(models.Model):
    """Registro maestro de cada competidor a monitorear."""
    
    nombre = models.CharField(max_length=200, unique=True, db_index=True)
    website = models.URLField(help_text='URL principal del sitio web')
    activo = models.BooleanField(
        default=True,
        help_text='Si está activo para scraping automático'
    )
    
    # Redes sociales
    facebook_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)
    
    # Metadata
    notas = models.TextField(blank=True, help_text='Notas internas sobre el competidor')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Competidor'
        verbose_name_plural = 'Competidores'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class CompetitorSnapshot(models.Model):
    """Snapshot periódico de datos scrapeados del sitio web del competidor."""
    
    competitor = models.ForeignKey(
        Competitor,
        on_delete=models.CASCADE,
        related_name='snapshots'
    )
    fecha_captura = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Datos extraídos del sitio
    precio_entrada_adulto = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        null=True,
        blank=True,
        help_text='Precio de entrada general adulto en CLP'
    )
    precio_entrada_nino = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        null=True,
        blank=True,
        help_text='Precio entrada niño en CLP'
    )
    
    # Servicios detectados (checkboxes básicos)
    tiene_piscinas_termales = models.BooleanField(default=False)
    tiene_masajes = models.BooleanField(default=False)
    tiene_restaurant = models.BooleanField(default=False)
    tiene_alojamiento = models.BooleanField(default=False)
    
    # Horarios
    horario_texto = models.CharField(
        max_length=500,
        blank=True,
        help_text='Horario de atención extraído del sitio'
    )
    
    # Promociones activas
    promociones = models.TextField(
        blank=True,
        help_text='Texto de promociones activas encontradas'
    )
    
    # Meta tags
    meta_description = models.TextField(
        blank=True,
        help_text='Meta description del sitio (propuesta de valor)'
    )
    
    # Datos raw para debugging
    datos_raw = models.JSONField(
        null=True,
        blank=True,
        help_text='Datos crudos extraídos del scraping para debugging'
    )
    
    # Estado del scraping
    scraping_exitoso = models.BooleanField(default=True)
    error_mensaje = models.TextField(blank=True, help_text='Mensaje de error si el scraping falló')
    
    class Meta:
        verbose_name = 'Snapshot de competidor'
        verbose_name_plural = 'Snapshots de competidores'
        ordering = ['-fecha_captura']
        indexes = [
            models.Index(fields=['competitor', '-fecha_captura']),
        ]
    
    def __str__(self):
        return f'{self.competitor.nombre} - {self.fecha_captura.strftime("%Y-%m-%d %H:%M")}'


class CompetitorSocialMedia(models.Model):
    """Métricas de redes sociales del competidor."""
    
    competitor = models.ForeignKey(
        Competitor,
        on_delete=models.CASCADE,
        related_name='social_media_metrics'
    )
    fecha_captura = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Facebook
    facebook_seguidores = models.IntegerField(null=True, blank=True)
    facebook_me_gusta = models.IntegerField(null=True, blank=True)
    
    # Instagram
    instagram_seguidores = models.IntegerField(null=True, blank=True)
    instagram_publicaciones_count = models.IntegerField(
        null=True,
        blank=True,
        help_text='Cantidad de posts totales'
    )
    
    # Engagement estimado (likes+comments de últimos posts)
    engagement_rate = models.FloatField(
        null=True,
        blank=True,
        help_text='(likes+comments)/followers promedio últimos posts'
    )
    
    # Frecuencia de publicación
    posts_ultima_semana = models.IntegerField(
        null=True,
        blank=True,
        help_text='Cantidad de posts en los últimos 7 días'
    )
    
    # Metadata
    notas = models.TextField(
        blank=True,
        help_text='Observaciones sobre la estrategia de contenido'
    )
    datos_raw = models.JSONField(
        null=True,
        blank=True,
        help_text='Datos crudos para análisis posterior'
    )
    
    class Meta:
        verbose_name = 'Métricas de redes sociales de competidor'
        verbose_name_plural = 'Métricas de redes sociales de competidores'
        ordering = ['-fecha_captura']
        indexes = [
            models.Index(fields=['competitor', '-fecha_captura']),
        ]
    
    def __str__(self):
        return f'{self.competitor.nombre} - Social Media - {self.fecha_captura.strftime("%Y-%m-%d")}'


class GA4Snapshot(models.Model):
    """Snapshot semanal de Google Analytics 4 para series historicas.

    El brief semanal hoy consulta GA4 en vivo y pierde el dato. Este modelo
    congela el estado cada lunes para permitir comparaciones semana-vs-semana
    y mes-vs-mes a futuro (8-12 semanas para tener series utiles).

    `datos` guarda el dict completo de ga4_reporter.get_full_snapshot(). Los
    campos planos del overview last_7d se materializan para queries rapidas
    sin parsear el JSON.
    """
    GENERADO_POR_CHOICES = [
        ('cron_weekly', 'Cron semanal (lunes)'),
        ('management_command', 'Comando manual desde shell'),
        ('admin_manual', 'Admin Django (manual)'),
    ]

    fecha_snapshot = models.DateField(
        db_index=True,
        help_text='Fecha del snapshot (tipicamente lunes de la semana)',
    )
    datos = models.JSONField(help_text='JSON completo de ga4_reporter.get_full_snapshot()')

    # Overview last_7d — materializado para queries y tendencias
    sessions = models.PositiveIntegerField(default=0)
    total_users = models.PositiveIntegerField(default=0)
    new_users = models.PositiveIntegerField(default=0)
    engaged_sessions = models.PositiveIntegerField(default=0)
    avg_session_duration = models.FloatField(default=0, help_text='Segundos promedio por sesion')
    screen_page_views = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)

    # Eventos custom Aremko (Tarea 2.2)
    whatsapp_clicks = models.PositiveIntegerField(default=0)
    phone_clicks = models.PositiveIntegerField(default=0)
    cta_blog_clicks = models.PositiveIntegerField(default=0)
    reservation_started = models.PositiveIntegerField(default=0)
    reservation_completed = models.PositiveIntegerField(default=0)

    generado_por = models.CharField(
        max_length=30, choices=GENERADO_POR_CHOICES, default='cron_weekly', db_index=True,
    )
    error = models.TextField(blank=True, help_text='Errores parciales si los hubo')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Snapshot GA4 (semanal)'
        verbose_name_plural = 'Snapshots GA4 (semanales)'
        ordering = ['-fecha_snapshot', '-created_at']
        indexes = [
            models.Index(fields=['-fecha_snapshot']),
        ]

    def __str__(self):
        return f'GA4 snapshot {self.fecha_snapshot} ({self.sessions} sesiones)'


class SearchConsoleSnapshot(models.Model):
    """Snapshot semanal de Google Search Console para series historicas.

    Mismo patron que GA4Snapshot. Permite ver evolucion de visibilidad SEO
    (impresiones, clicks, CTR, posicion) semana a semana.
    """
    GENERADO_POR_CHOICES = GA4Snapshot.GENERADO_POR_CHOICES

    fecha_snapshot = models.DateField(
        db_index=True,
        help_text='Fecha del snapshot (tipicamente lunes de la semana)',
    )
    datos = models.JSONField(help_text='JSON completo de gsc_reporter.get_full_snapshot()')

    # Overview last_7d — materializado
    clicks = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    ctr = models.FloatField(default=0, help_text='Click-through rate %, 0-100')
    position = models.FloatField(default=0, help_text='Posicion promedio ponderada por impresiones')

    generado_por = models.CharField(
        max_length=30, choices=GENERADO_POR_CHOICES, default='cron_weekly', db_index=True,
    )
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Snapshot Search Console (semanal)'
        verbose_name_plural = 'Snapshots Search Console (semanales)'
        ordering = ['-fecha_snapshot', '-created_at']
        indexes = [
            models.Index(fields=['-fecha_snapshot']),
        ]

    def __str__(self):
        return f'GSC snapshot {self.fecha_snapshot} ({self.clicks} clicks, pos {self.position:.1f})'


# ────────────── Cotizaciones para empresas ──────────────

COTIZACION_FRASE_BENEFICIOS_DEFAULT = (
    "Invertir en el bienestar del equipo es una de las mejores decisiones que una "
    "organización puede tomar. En Aremko Spa Boutique, su grupo encontrará un espacio único de "
    "desconexión junto al río Pescado, rodeado de bosque nativo: tinas calientes, masajes "
    "restauradores y la calma del sur de Chile. Una experiencia privada, cálida y memorable "
    "que fortalece vínculos, reduce el estrés acumulado y deja a cada persona con energía "
    "renovada para volver al trabajo."
)

COTIZACION_TERMINOS_DEFAULT = (
    "Términos y condiciones:\n"
    "• Esta cotización tiene una validez de 30 días desde la fecha de emisión.\n"
    "• Los precios incluyen IVA y están expresados en pesos chilenos (CLP).\n"
    "• La reserva se confirma con el 100% del pago anticipado mediante transferencia a:\n"
    "    Aremko Hotel Spa · RUT 76.485.192-7\n"
    "    Mercado Pago Cuenta Vista 1016006859\n"
    "    Enviar comprobante a ventas@aremko.cl indicando N° de cotización.\n"
    "• Coordinación de fechas y horarios se realiza una vez confirmada la aceptación de la cotización."
)

COTIZACION_CIERRE_DEFAULT = (
    "Cordialmente,\n"
    "Equipo Aremko Spa Boutique\n"
    "ventas@aremko.cl  ·  +56 9 7666 8080  ·  Puerto Varas, Chile"
)


class CotizacionFormal(models.Model):
    """Cotización formal para empresas (documento numerado desde 321).

    No es una reserva: no tiene fechas de servicio. Solo lista servicios + productos
    con cantidades y precios, para enviar como documento formal y eventualmente
    convertirse en reserva manual cuando la empresa acepte.

    NO confundir con CotizacionEmpresa (existente), que es el formulario de
    solicitudes desde el landing /empresas/.
    """

    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviada', 'Enviada'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada'),
        ('expirada', 'Expirada'),
    ]

    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='borrador', db_index=True,
    )
    fecha_emision = models.DateField(auto_now_add=True, db_index=True)
    validez_dias = models.PositiveIntegerField(
        default=30,
        help_text='Días de validez de la cotización desde la emisión',
    )

    # Datos de la empresa receptora
    empresa_razon_social = models.CharField(max_length=200)
    empresa_rut = models.CharField(max_length=20, blank=True)
    empresa_giro = models.CharField(max_length=200, blank=True, help_text='Giro comercial (opcional)')
    contacto_nombre = models.CharField(max_length=120)
    contacto_email = models.EmailField(blank=True)
    contacto_telefono = models.CharField(max_length=20, blank=True)

    # Personalización del documento (si está vacío usa los defaults de ConfiguracionResumen)
    frase_beneficios = models.TextField(
        blank=True,
        help_text='Si vacío, usa la frase global desde ConfiguracionResumen.cotizacion_frase_beneficios.',
    )

    # Notas internas (no se muestran en el documento al cliente)
    notas = models.TextField(blank=True, help_text='Notas internas, no visibles para el cliente.')

    # Tracking de estados
    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_aceptacion = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cotizaciones_creadas',
    )

    class Meta:
        verbose_name = 'Cotización Formal (documento)'
        verbose_name_plural = 'Cotizaciones Formales (documentos)'
        ordering = ['-fecha_emision', '-id']
        indexes = [
            models.Index(fields=['-fecha_emision']),
            models.Index(fields=['estado', '-fecha_emision']),
        ]

    @property
    def numero(self) -> Optional[int]:
        """Número del documento. Empieza en 321 (id + 320)."""
        return (self.id + 320) if self.id else None

    @property
    def fecha_validez(self):
        if not self.fecha_emision:
            return None
        return self.fecha_emision + timedelta(days=self.validez_dias)

    @property
    def esta_vencida(self) -> bool:
        if self.estado in ('aceptada', 'rechazada'):
            return False
        if not self.fecha_validez:
            return False
        return timezone.now().date() > self.fecha_validez

    @property
    def total(self):
        from decimal import Decimal
        return sum((item.subtotal for item in self.items.all()), Decimal(0))

    def __str__(self):
        return f'Cotización N° {self.numero or "?"} — {self.empresa_razon_social}'


class CotizacionItem(models.Model):
    """Línea individual de una cotización (servicio, producto, o item custom)."""

    cotizacion = models.ForeignKey(
        CotizacionFormal, related_name='items', on_delete=models.CASCADE,
    )
    servicio = models.ForeignKey(
        Servicio, on_delete=models.SET_NULL, null=True, blank=True,
        help_text='Si es un servicio del catálogo.',
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.SET_NULL, null=True, blank=True,
        help_text='Si es un producto del catálogo.',
    )
    descripcion_custom = models.CharField(
        max_length=200, blank=True,
        help_text='Para items que no están en el catálogo (servicio/producto a medida).',
    )
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(
        max_digits=10, decimal_places=0,
        help_text='Snapshot del precio al momento de cotizar (CLP, sin decimales).',
    )
    orden = models.PositiveIntegerField(default=0, help_text='Orden de aparición en el documento')

    class Meta:
        verbose_name = 'Ítem de cotización'
        verbose_name_plural = 'Ítems de cotización'
        ordering = ['orden', 'id']

    @property
    def descripcion(self) -> str:
        if self.servicio_id:
            return self.servicio.nombre
        if self.producto_id:
            return self.producto.nombre
        return self.descripcion_custom or '(sin descripción)'

    @property
    def subtotal(self):
        from decimal import Decimal
        return Decimal(self.cantidad) * (self.precio_unitario or Decimal(0))

    def __str__(self):
        return f'{self.descripcion} × {self.cantidad}'


# ────────────── Contexto Operativo (para inyectar en análisis IA) ──────────────

class ContextoOperativo(SingletonModel):
    """Contexto operativo de Aremko inyectable al system prompt de análisis IA.

    Se compone de:
    - seccion_automatica_cache: introspección del código (templates, packs, signals,
      tareas cron, etc). Se regenera periódicamente cada hora vía el endpoint.
    - seccion_manual: markdown editable a mano por Jorge (campañas de marketing,
      alianzas, procesos operativos que no están en código).

    El endpoint /api/aremko-cli/operating-context/ concatena ambas.
    """
    seccion_manual = models.TextField(
        blank=True,
        verbose_name="Sección manual (markdown editable)",
        help_text=(
            "Markdown editable. Información que NO está en código pero el LLM debería saber: "
            "campañas de marketing activas, decisiones de management, alianzas vigentes, "
            "iniciativas externas, etc."
        ),
    )
    seccion_automatica_cache = models.TextField(
        blank=True,
        editable=False,
        verbose_name="Sección automática (caché)",
        help_text="Generada automáticamente desde el código. No editar manualmente.",
    )
    seccion_automatica_actualizada_en = models.DateTimeField(
        null=True, blank=True, editable=False,
        verbose_name="Última regeneración automática",
    )

    class Meta:
        verbose_name = "Contexto Operativo"
        verbose_name_plural = "Contexto Operativo"

    def __str__(self):
        return "Contexto Operativo Aremko"


class DocumentoSistemaCache(SingletonModel):
    """Cache de la narrativa generada por LLM del Documento Maestro del Sistema.

    El documento maestro combina:
    - Narrativa (resumen ejecutivo, descripciones de dominio, valor diferenciador)
      generada por Claude Sonnet vía OpenRouter. Se cachea aquí.
    - Inventarios técnicos (modelos, endpoints, commands, etc.) introspectados en
      vivo al momento de descargar el PDF. NO se cachean acá.

    El usuario regenera la narrativa explícitamente desde el botón en admin cuando
    haga cambios significativos al sistema.
    """
    narrativa_md = models.TextField(
        blank=True,
        verbose_name="Narrativa cacheada (markdown)",
        help_text="Cuerpo narrativo del documento maestro, generado por LLM. Se combina con inventarios live al descargar el PDF.",
    )
    actualizado_en = models.DateTimeField(null=True, blank=True, editable=False)
    generado_por_modelo = models.CharField(
        max_length=100, blank=True, editable=False,
        verbose_name="Modelo LLM usado",
    )
    tokens_input = models.IntegerField(default=0, editable=False)
    tokens_output = models.IntegerField(default=0, editable=False)
    costo_usd_aprox = models.DecimalField(
        max_digits=8, decimal_places=4, default=0, editable=False,
        verbose_name="Costo estimado USD",
    )
    introspect_snapshot = models.JSONField(
        default=dict, blank=True, editable=False,
        help_text="Snapshot del estado del sistema al momento de generar (modelos, endpoints, etc.)",
    )

    class Meta:
        verbose_name = "Documento del Sistema (cache)"
        verbose_name_plural = "Documento del Sistema (cache)"

    def __str__(self):
        return f"Documento Sistema (actualizado: {self.actualizado_en or '(nunca)'})"


# ============================================================================
# OPERACIÓN VUELTA A CASA — Sistema de retención vía WhatsApp manual
# ============================================================================
# Plan junio-diciembre 2026: Deborah envía 50 WhatsApp manuales por día a
# clientes seleccionados según su ciclo de vida (taxonomía Valor × Estilo ×
# Contexto). Estos modelos soportan la operación completa:
#
#   ScriptWhatsApp      — catálogo editable de plantillas por cohorte
#   ContactoWhatsApp    — log de cada intento de contacto (1 fila por
#                         cliente-día sugerido)
#   TaxonomiaMovimiento — bitácora viva de cambios de tramo en cualquier eje
#   EventoCelebracion   — hitos que merecen mensaje de agradecimiento
#
# Flujo diario:
#   05:30 — cron recalcular_taxonomia_clientes refresca ClienteTaxonomia
#   06:00 — cron generar_bandeja_whatsapp_diaria crea ~50 ContactoWhatsApp
#   día   — Deborah procesa bandeja vía aremko-cli, marca enviados/respuestas
#   23:30 — cron cruzar_reservas_contactos_whatsapp atribuye conversiones
# ============================================================================


class ScriptWhatsApp(models.Model):
    """Plantillas editables de mensajes WhatsApp por cohorte + estado + salva.

    Convención de script_id:
        Letra = grupo por estado de valor target (A=En Riesgo, B=Dormido, …)
        Número = variante por cohorte estilo/contexto/salva
        Ej: "A.1", "B.2", "C.3"

    Matching de candidatos (en generar_bandeja_whatsapp_diaria):
        1. estado_valor_target debe coincidir EXACTO con el eje_valor del cliente
        2. cohorte_estilo:    si vacío aplica a cualquier estilo; si tiene valor
                              debe coincidir
        3. cohorte_contexto:  idem
        4. salva:             1ª contacto, 2ª si no respondió, 3ª y última
        5. Se prefieren matches específicos (estilo+contexto) sobre genéricos.
    """

    # Reutilizo los choices de ClienteTaxonomia para garantizar consistencia:
    # si alguien cambia una etiqueta en un lado, se actualiza en ambos.

    script_id = models.CharField(
        max_length=30, unique=True, db_index=True,
        help_text="Convención: 'A.1', 'B.2', 'B.refugio-N', etc. Letra=grupo, sufijo opcional.",
    )
    nombre = models.CharField(
        max_length=120,
        help_text="Ej: 'En Riesgo · Amante Tinas × Pareja · 1ª salva'",
    )
    estado_valor_target = models.CharField(
        max_length=40,
        choices=ClienteTaxonomia.EJE_VALOR_CHOICES,
        db_index=True,
        help_text="Estado de valor del cliente al que va dirigido este script.",
    )
    cohorte_estilo = models.CharField(
        max_length=40, blank=True,
        choices=[('', '— Cualquier estilo —')] + ClienteTaxonomia.EJE_ESTILO_CHOICES,
        help_text="Vacío = aplica a cualquier estilo.",
    )
    cohorte_contexto = models.CharField(
        max_length=40, blank=True,
        choices=[('', '— Cualquier contexto —')] + ClienteTaxonomia.EJE_CONTEXTO_CHOICES,
        help_text="Vacío = aplica a cualquier contexto.",
    )
    salva = models.PositiveSmallIntegerField(
        choices=[(1, '1ª salva'), (2, '2ª salva'), (3, '3ª salva')],
        default=1,
        help_text="1 = primer contacto, 2 = si no respondió a la 1, 3 = última.",
    )
    plantilla_texto = models.TextField(
        help_text=(
            "Texto con placeholders: {nombre}, {ultima_visita_humanizada}, "
            "{dias_sin_venir}, {ultimo_servicio}, {compania_habitual}, "
            "{servicio_recomendado}, {sugerencia_dia}, {sugerencia_hora}, "
            "{cupon_codigo}, {mes_proximo}, {fecha_limite}."
        ),
    )
    activo = models.BooleanField(
        default=True,
        help_text="Permite desactivar plantilla sin borrarla (A/B testing futuro).",
    )

    # ───── Etapa Geo.3 — target geográfico ─────
    # Cuando vacío ('') = plantilla aplica a cualquier región. Las 17 plantillas
    # iniciales (Geo.1/Etapa 2) quedaron con '' → sirven como fallback para 'sur'.
    # Las plantillas nuevas de Geo.3 (nacional + sin_clasificar) llevan el sufijo.
    # 'extranjero' NO está como choice porque el cron excluye esos clientes.
    region_geografica_target = models.CharField(
        max_length=20,
        blank=True, default='',
        choices=[
            ('', 'Cualquier región'),
            ('sur', 'Sur'),
            ('nacional', 'Resto de Chile'),
            ('sin_clasificar', 'Sin clasificar'),
        ],
        help_text=(
            "Región geográfica del cliente a la que aplica esta plantilla. "
            "Vacío = aplica a cualquier región (fallback). "
            "'sur'/'nacional'/'sin_clasificar' = plantilla específica."
        ),
    )

    # ───── Cloud API: mapeo a plantilla aprobada por Meta ─────
    # Lo llena Jorge cuando diseña/aprueba la plantilla en la WABA. Si
    # meta_template_name está vacío → el script NO es elegible para envío
    # automático (solo bandeja manual). Solo aplica a salva 1.
    meta_template_name = models.CharField(
        max_length=100, blank=True,
        help_text="Nombre de la plantilla aprobada en Meta (ej. 'vuelta_en_riesgo_1'). Vacío = no se envía automático.",
    )
    meta_language = models.CharField(
        max_length=10, default='es',
        help_text="Código de idioma de la plantilla en Meta (ej. 'es'). Meta no tiene es_CL.",
    )
    meta_variables_orden = models.JSONField(
        default=list, blank=True,
        help_text=(
            "Lista ordenada de placeholders que mapean a {{1}},{{2}}… de la plantilla Meta. "
            'Ej: ["nombre", "ultima_visita_humanizada"]. Vacío = plantilla sin variables.'
        ),
    )

    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Script WhatsApp"
        verbose_name_plural = "Scripts WhatsApp"
        ordering = ['script_id']
        indexes = [
            models.Index(
                fields=['estado_valor_target', 'cohorte_estilo', 'cohorte_contexto', 'salva'],
                name='idx_script_match',
            ),
            models.Index(
                fields=['estado_valor_target', 'activo'],
                name='idx_script_estado_activo',
            ),
            # Geo.3: índice para lookup eficiente con región
            models.Index(
                fields=['region_geografica_target', 'estado_valor_target', 'salva'],
                name='idx_script_region_match',
            ),
        ]

    def __str__(self):
        return f"[{self.script_id}] {self.nombre}"


class ContactoWhatsApp(models.Model):
    """Cada fila es un intento de contacto sugerido a un cliente en un día.

    Flujo de estados:
        pendiente  → enviado              (operador hizo el envío manual)
                   → omitido              (operador lo saltó hoy, queda elegible mañana)
                   → no_aplica            (teléfono inválido, falleció, etc; 90 días gracia)
                   → descartado           (revalidación detectó cambio de estado del cliente)
                   → expirado_acumulacion (>OVC_DIAS_MAX_ACUMULACION sin acción del operador
                                           — el cron lo retira para que la bandeja no se
                                           atasque; el cliente podrá volver a entrar
                                           más adelante por su clasificación)

    Atribución de conversión:
        El cron nocturno `cruzar_reservas_contactos_whatsapp` busca VentaReserva
        creadas dentro de los 30 días posteriores al envío y marca convirtio=True
        + reserva_atribuida.
    """

    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('enviado', 'Enviado'),
        ('omitido', 'Omitido (sin enviar)'),
        ('no_aplica', 'No aplica'),
        ('descartado', 'Descartado por revalidación'),
        ('expirado_acumulacion', 'Expirado por acumulación (>7 días sin acción)'),
    ]
    TIPO_RESPUESTA_CHOICES = [
        ('reservo', 'Reservó'),
        ('interesado', 'Respondió interesada/o'),
        ('consulto_precio', 'Pidió precio'),
        ('mas_adelante', 'Más adelante'),
        ('rechazo', 'Rechazó'),
        ('opt_out', 'Pidió no escribir más'),
        ('sin_respuesta', 'Sin respuesta'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='contactos_whatsapp',
    )
    script = models.ForeignKey(
        ScriptWhatsApp,
        on_delete=models.PROTECT,
        related_name='contactos',
        help_text="PROTECT: no permitir borrar scripts con histórico de uso.",
    )

    # Snapshot del estado del cliente al momento de generar (auditoría)
    eje_valor_snapshot = models.CharField(max_length=40)
    eje_estilo_snapshot = models.CharField(max_length=40)
    eje_contexto_snapshot = models.CharField(max_length=40)
    dias_sin_venir_snapshot = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Null si el cliente nunca había venido (edge case Pre-sistema).",
    )
    gasto_historico_snapshot = models.IntegerField(
        default=0,
        help_text="CLP, sin decimales (consistente con ClienteTaxonomia.gasto_total).",
    )

    salva = models.PositiveSmallIntegerField(
        default=1,
        help_text="1, 2 o 3. Cuál intento es para este cliente.",
    )
    mensaje_renderizado = models.TextField(
        help_text="Texto YA con variables resueltas, listo para copiar/pegar.",
    )
    prioridad = models.PositiveSmallIntegerField(
        default=5,
        help_text="1-6. Define orden de aparición en la bandeja (1 = más urgente).",
    )
    fecha_sugerido = models.DateField(
        db_index=True,
        help_text="Día en que el cron lo agregó a la bandeja.",
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        db_index=True,
    )
    fecha_envio = models.DateTimeField(null=True, blank=True)
    operador = models.CharField(
        max_length=100, blank=True,
        help_text="Usuario que marcó como enviado (ej. 'deborah').",
    )
    mensaje_enviado_editado = models.TextField(
        blank=True,
        help_text=(
            "Si el operador editó el mensaje sugerido antes de enviar, "
            "guardar el real aquí. Vacío = se envió mensaje_renderizado tal cual."
        ),
    )

    # Tracking de respuesta del cliente
    respondio = models.BooleanField(default=False)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    tipo_respuesta = models.CharField(
        max_length=30,
        choices=TIPO_RESPUESTA_CHOICES,
        blank=True,
    )
    nota_operador = models.TextField(blank=True)

    # Atribución de conversión (poblada por cron cruzar_reservas_contactos_whatsapp)
    convirtio = models.BooleanField(default=False)
    reserva_atribuida = models.ForeignKey(
        VentaReserva,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='whatsapp_atribuidos',
        help_text="VentaReserva creada por el cliente dentro de los 30 días posteriores al envío.",
    )
    fecha_atribucion = models.DateTimeField(null=True, blank=True)

    creado = models.DateTimeField(auto_now_add=True)

    # Feature 2026-05-27: distinguir contactos óptimos (P0-P4) vs los que
    # entraron por fallback de OVC_TARGET_DIARIO (P5/P6 cuando los óptimos
    # no llenaron el cupo). Permite análisis diferenciado de conversión.
    es_relleno = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "True si entró por fallback target (P5/P6 que llenaron cupo). "
            "False si vino de prioridad óptima P0-P4 propia."
        ),
    )

    class Meta:
        verbose_name = "Contacto WhatsApp"
        verbose_name_plural = "Contactos WhatsApp"
        indexes = [
            models.Index(fields=['fecha_sugerido', 'estado'], name='idx_cwa_fecha_estado'),
            models.Index(fields=['cliente', 'fecha_envio'], name='idx_cwa_cliente_envio'),
            models.Index(fields=['estado', 'fecha_envio'], name='idx_cwa_estado_envio'),
            models.Index(fields=['convirtio', 'fecha_atribucion'], name='idx_cwa_conv_atrib'),
        ]
        constraints = [
            # Un cliente solo puede tener 1 contacto pendiente por día.
            # Permite generar para el mismo cliente en distintos días, y permite
            # múltiples enviados/omitidos en distintos días.
            models.UniqueConstraint(
                fields=['cliente', 'fecha_sugerido'],
                condition=models.Q(estado='pendiente'),
                name='unique_pendiente_por_cliente_dia',
            ),
        ]

    def __str__(self):
        return f"Contacto {self.cliente_id} ({self.fecha_sugerido}) [{self.estado}]"


class TaxonomiaMovimiento(models.Model):
    """Bitácora Viva: cada vez que un cliente cambia de tramo en cualquier eje.

    Lo escribe el comando `recalcular_taxonomia_clientes` (extendido) cuando
    detecta diferencia entre el estado anterior y el nuevo de un cliente.

    Habilita:
      - Reportes "qué se está moviendo este mes"
      - Atribución de conversiones a contactos WhatsApp previos
      - Disparo de EventoCelebracion para movimientos positivos relevantes
    """

    EVENTO_ORIGEN_CHOICES = [
        ('reserva', 'Nueva reserva'),
        ('paso_tiempo', 'Paso del tiempo sin venir'),
        ('recalculo_features', 'Recálculo features'),
        ('manual', 'Ajuste manual'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='movimientos_taxonomia',
    )
    fecha = models.DateField(db_index=True)

    # Estado anterior (antes del cambio)
    eje_valor_antes = models.CharField(max_length=40)
    eje_estilo_antes = models.CharField(max_length=40)
    eje_contexto_antes = models.CharField(max_length=40)

    # Estado nuevo (después del cambio)
    eje_valor_despues = models.CharField(max_length=40)
    eje_estilo_despues = models.CharField(max_length=40)
    eje_contexto_despues = models.CharField(max_length=40)

    evento_origen = models.CharField(
        max_length=20,
        choices=EVENTO_ORIGEN_CHOICES,
    )
    reserva_relacionada = models.ForeignKey(
        VentaReserva,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movimientos_taxonomia',
        help_text="Reserva que causó el movimiento (si evento_origen='reserva').",
    )
    contacto_whatsapp_atribuido = models.ForeignKey(
        ContactoWhatsApp,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movimientos_causados',
        help_text=(
            "Si hubo WhatsApp en los 30 días previos al movimiento positivo, "
            "atribuir al contacto más reciente."
        ),
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de Taxonomía"
        verbose_name_plural = "Movimientos de Taxonomía"
        indexes = [
            models.Index(
                fields=['fecha', 'eje_valor_antes', 'eje_valor_despues'],
                name='idx_tm_fecha_valor',
            ),
            models.Index(fields=['cliente', 'fecha'], name='idx_tm_cliente_fecha'),
        ]

    def __str__(self):
        return (
            f"Movimiento {self.cliente_id} ({self.fecha}): "
            f"{self.eje_valor_antes} → {self.eje_valor_despues}"
        )


class EventoCelebracion(models.Model):
    """Hitos para destacar en la bandeja del operador (mensajes de agradecimiento, no promo).

    Se generan automáticamente desde TaxonomiaMovimiento cuando se detecta un
    movimiento positivo notable (ver _detectar_celebracion en
    recalcular_taxonomia_clientes). Se muestran en la bandeja del aremko-cli
    antes de los contactos comerciales para que el operador empiece el día
    con tonelada positiva.
    """

    TIPO_CHOICES = [
        ('recuperado_dormido', 'Recuperado de Dormido'),
        ('consolidacion_regular', 'En Prueba → Regular'),
        ('migracion_devoto', 'Probador → Devoto/Amante'),
        ('trajo_acompanante', 'Solo → Pareja/Grupo'),
        ('subio_a_leal', 'Subió a Leal'),
        ('subio_a_campeon', 'Subió a Campeón'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='celebraciones',
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    fecha = models.DateField()
    movimiento_relacionado = models.ForeignKey(
        TaxonomiaMovimiento,
        on_delete=models.CASCADE,
        related_name='celebraciones',
    )
    mensaje_sugerido = models.TextField(
        blank=True,
        help_text="Mensaje de agradecimiento sugerido al operador.",
    )
    mostrado_en_bandeja = models.BooleanField(default=False)
    fecha_mostrado = models.DateTimeField(null=True, blank=True)

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento de Celebración"
        verbose_name_plural = "Eventos de Celebración"
        indexes = [
            models.Index(
                fields=['fecha', 'mostrado_en_bandeja'],
                name='idx_evt_fecha_mostrado',
            ),
            models.Index(fields=['cliente', 'fecha'], name='idx_evt_cliente_fecha'),
        ]

    def __str__(self):
        return f"Celebración {self.cliente_id} ({self.tipo}) {self.fecha}"


# ============================================================================
# Operación Vuelta a Casa · Etapa Geo.2 — Ciudad + región geográfica
# ============================================================================
# Eje geográfico para personalizar mensajes WhatsApp según si el cliente
# vive cerca (servicio puntual) o lejos (pack alojamiento). 4 categorías:
#   - sur: ≤120 km Puerto Varas — viene en el día
#   - nacional: resto de Chile — necesita alojamiento
#   - extranjero: no-Chile — excluir del cron
#   - sin_clasificar: sin info — captura inline en bandeja (Geo.4)


class Ciudad(models.Model):
    """Catálogo de ciudades con aliases para normalización + región geo.

    Diseño:
        - nombre_canonico: el nombre "oficial" que se muestra y se persiste
          en Cliente.ciudad_normalizada → ciudad.nombre_canonico
        - aliases: lista separada por `|` de variantes en minúscula que
          deben mapearse a este canónico. Ej: "puerto varas" tiene aliases
          "pto varas|pto. varas|p. varas|ptovaras|puert varas". El comando
          normalizar_ciudades_clientes hace lookup case-insensitive sobre
          esta lista.
        - region_geografica: clasificación operacional para el cron WhatsApp
        - pais: default Chile; permite filtrar extranjeros sin enumerar

    El admin permite agregar aliases sin tocar código — útil cuando aparece
    una variante nueva en la base.
    """
    REGION_CHOICES = [
        ('sur', 'Sur (≤120 km Puerto Varas)'),
        ('nacional', 'Resto de Chile'),
        ('extranjero', 'Extranjero'),
    ]

    nombre_canonico = models.CharField(
        max_length=100, unique=True, db_index=True,
        help_text="Nombre 'oficial' que se muestra (ej. 'Puerto Varas').",
    )
    aliases = models.TextField(
        blank=True,
        help_text=(
            "Aliases en minúscula separados por |. Ej: "
            "'puerto varas|pto varas|pto. varas|p. varas'. Lookup es "
            "case-insensitive y trim-aware."
        ),
    )
    region_geografica = models.CharField(
        max_length=20, choices=REGION_CHOICES, db_index=True,
    )
    pais = models.CharField(max_length=50, default='Chile')
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ciudad"
        verbose_name_plural = "Ciudades"
        ordering = ['region_geografica', 'nombre_canonico']
        indexes = [
            models.Index(fields=['region_geografica', 'activo'], name='idx_ciudad_region_activo'),
        ]

    def __str__(self):
        return f"{self.nombre_canonico} ({self.region_geografica})"

    def aliases_list(self):
        """Devuelve la lista de aliases como list[str] en minúscula y trimmed."""
        if not self.aliases:
            return []
        return [a.strip().lower() for a in self.aliases.split('|') if a.strip()]


# ──────────────────────────────────────────────────────────────────────
#  Landing "Refugio Aremko" (campaña 15-jun-2026)
#  ──────────────────────────────────────────────────────────────────
#  RefugioConfig: singleton editable desde admin (precio, textos, fechas)
#  RefugioImagen: galería ordenable, hasta N fotos
#  RefugioLead:   leads que llegan del formulario público con UTM tracking
# ──────────────────────────────────────────────────────────────────────


class RefugioConfig(SingletonModel):
    """Configuración editable desde admin de la landing /refugio/.

    Singleton: una sola fila en BD. Acceso vía RefugioConfig.get_solo().

    Paquete actual (Jorge 2026-05-27 PM): 3 días / 2 noches en cabaña,
    masaje en pareja (1 sesión), 2 sesiones de tinas, segunda noche
    cortesía. Lanzamiento 15-jun-2026.
    """

    # Hero
    hero_title = models.CharField(
        max_length=200,
        default="Tres días para volver a tu centro",
        verbose_name="Título Hero",
    )
    hero_subtitle = models.CharField(
        max_length=300,
        default="Refugio Aremko · 2 noches en cabaña con masajes y tinas calientes",
        verbose_name="Subtítulo Hero",
    )
    hero_cta_text = models.CharField(
        max_length=60,
        default="Reserva tu Refugio",
        verbose_name="Texto botón principal Hero",
    )

    # Oferta
    precio_clp = models.PositiveIntegerField(
        default=270000,
        verbose_name="Precio (CLP)",
        help_text="Precio total del paquete Refugio en pesos chilenos.",
    )
    paquete_titulo = models.CharField(
        max_length=120,
        default="Tu Refugio Incluye",
        verbose_name="Título sección paquete",
    )
    paquete_incluye = models.TextField(
        default=(
            "Dos noches en cabaña de naturaleza — Cabaña privada para 2 personas\n"
            "Masaje en pareja — Una sesión profesional, en simultáneo\n"
            "Tinas calientes en pareja — Dos tardes con vista al bosque\n"
            "🎁 Cortesía Aremko — La segunda noche, regalo nuestro"
        ),
        verbose_name="Lista 'Qué incluye' (una línea por item)",
        help_text=(
            "Una línea por ítem. Se renderizan como bullets en la landing. "
            "Para una línea con regalo/cortesía empezar con emoji 🎁."
        ),
    )

    # Disponibilidad
    fecha_limite_oferta = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha límite oferta",
        help_text="Si se completa, se muestra como urgencia en la landing.",
    )
    cupo_disponible_texto = models.CharField(
        max_length=120,
        default="Cupos limitados — 5 cabañas",
        blank=True,
        verbose_name="Texto urgencia/escasez",
    )

    # Por qué Aremko
    por_que_titulo = models.CharField(
        max_length=200,
        default="¿Por qué Aremko?",
        verbose_name="Título sección 'Por qué'",
    )
    por_que_texto = models.TextField(
        default=(
            "Llevamos años cuidando a quienes buscan desconectar. "
            "Tinajas calientes con vista al sur, masajes terapéuticos "
            "y un entorno pensado para que recuperes el ritmo."
        ),
        verbose_name="Texto 'Por qué Aremko'",
    )

    # Footer / CTA final
    cta_final_titulo = models.CharField(
        max_length=200,
        default="Reserva tu Refugio",
        verbose_name="Título CTA final",
    )
    cta_final_subtitulo = models.CharField(
        max_length=300,
        default="Te contactamos dentro de 24 horas para coordinar tu fecha.",
        verbose_name="Subtítulo CTA final",
    )

    # Detalles operativos ("Lo que debes saber")
    duracion_texto = models.CharField(
        max_length=300,
        default="Check-in en el día 1 · Check-out el día 3. Dos noches completas en cabaña.",
        verbose_name="Detalles · Duración",
    )
    restricciones_fechas_texto = models.TextField(
        default=(
            "Válido cualquier día durante el mes de lanzamiento "
            "(15-jun a 15-jul-2026). Desde el 16-jul en adelante, "
            "solo domingo a jueves."
        ),
        verbose_name="Detalles · Cuándo usarlo",
    )
    cancelacion_texto = models.CharField(
        max_length=300,
        default="Hasta 48 horas antes del check-in sin costo.",
        verbose_name="Detalles · Política de cancelación",
    )
    para_quien_texto = models.CharField(
        max_length=300,
        default="Pensado para parejas o adultos buscando una pausa profunda.",
        verbose_name="Detalles · Para quién",
    )
    como_llegar_texto = models.CharField(
        max_length=300,
        default="15 minutos en auto desde el centro de Puerto Varas.",
        verbose_name="Detalles · Cómo llegar",
    )

    # Garantía (subtítulo sutil al pie del precio)
    garantia_texto = models.CharField(
        max_length=200,
        default="Respaldado por la Garantía Aremko",
        blank=True,
        verbose_name="Garantía · texto sutil pie del precio",
        help_text="Línea pequeña debajo de 'por 2 personas, todo incluido'. Si está vacío, no se muestra.",
    )
    garantia_url = models.CharField(
        max_length=300,
        default="/garantia/",
        blank=True,
        verbose_name="Garantía · URL del link",
        help_text="Path relativo (ej. /garantia/) o URL absoluta. Si está vacío, el texto se muestra sin link.",
    )

    # SEO
    seo_title = models.CharField(
        max_length=120,
        default="Refugio Aremko · 3 días en Puerto Varas | Cabaña + masajes + tinas",
        verbose_name="SEO Title",
    )
    seo_description = models.CharField(
        max_length=300,
        default=(
            "Tres días para volver a tu centro. Cabaña en naturaleza, "
            "masaje en pareja, tinas calientes. La segunda noche, cortesía "
            "Aremko. $270.000 por 2 personas."
        ),
        verbose_name="SEO Meta Description",
    )
    og_image = models.ImageField(
        upload_to='refugio/',
        blank=True,
        null=True,
        verbose_name="Imagen Open Graph (1200x630)",
    )

    # Control
    activo = models.BooleanField(
        default=True,
        verbose_name="Landing activa",
        help_text="Si está desactivada, la URL /refugio/ devuelve 404.",
    )

    def __str__(self):
        return "Configuración Landing Refugio Aremko"

    def incluye_list(self):
        """Devuelve paquete_incluye como list[str], una línea por item."""
        if not self.paquete_incluye:
            return []
        return [linea.strip() for linea in self.paquete_incluye.splitlines() if linea.strip()]

    class Meta:
        verbose_name = "Configuración Landing Refugio"
        verbose_name_plural = "Configuración Landing Refugio"


class RefugioImagen(models.Model):
    """Galería de imágenes para la landing Refugio.

    Orden controlado por campo 'orden'. Solo se muestran las activas.
    """

    imagen = models.ImageField(
        upload_to='refugio/galeria/',
        verbose_name="Imagen",
    )
    alt_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Alt text (SEO/accesibilidad)",
        help_text="Descripción para lectores de pantalla y SEO.",
    )
    orden = models.PositiveIntegerField(
        default=10,
        verbose_name="Orden",
        help_text="Menor número = aparece primero.",
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Imagen Refugio"
        verbose_name_plural = "Galería Refugio"
        ordering = ['orden', 'id']

    def __str__(self):
        return f"Refugio · {self.alt_text or self.imagen.name} (orden={self.orden})"


class RefugioLead(models.Model):
    """Lead capturado por el formulario de la landing /refugio/.

    Separado del modelo Lead general porque:
        - Necesita campos específicos (fecha tentativa, num personas)
        - Tracking UTM persistente (source/medium/campaign)
        - No contamina el embudo B2B de Lead

    Email de notificación se envía a comunicaciones@aremko.cl + aremkospa@gmail.com
    al momento de crearse (signal post_save o explícito en view).
    """

    STATUS_CHOICES = [
        ('nuevo', 'Nuevo'),
        ('contactado', 'Contactado'),
        ('cotizado', 'Cotizado'),
        ('reservado', 'Reservado'),
        ('descartado', 'Descartado'),
    ]

    # Datos del lead
    nombre = models.CharField(max_length=120, verbose_name="Nombre")
    email = models.EmailField(verbose_name="Email")
    telefono = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Teléfono",
        help_text="Idealmente con +56. Si viene sin prefijo se acepta igual.",
    )
    fecha_tentativa = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha tentativa",
    )
    num_personas = models.PositiveSmallIntegerField(
        default=2,
        verbose_name="Número de personas",
    )
    ciudad_origen = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Ciudad de origen",
        help_text="De dónde viene el lead — útil para segmentar campañas.",
    )
    mensaje = models.TextField(
        blank=True,
        verbose_name="Mensaje libre",
    )

    # Tracking UTM
    utm_source = models.CharField(max_length=120, blank=True, verbose_name="utm_source")
    utm_medium = models.CharField(max_length=120, blank=True, verbose_name="utm_medium")
    utm_campaign = models.CharField(max_length=120, blank=True, verbose_name="utm_campaign")
    utm_content = models.CharField(max_length=120, blank=True, verbose_name="utm_content")
    utm_term = models.CharField(max_length=120, blank=True, verbose_name="utm_term")
    referer = models.CharField(max_length=500, blank=True, verbose_name="Referer")

    # Forense
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name="IP")
    user_agent = models.CharField(max_length=500, blank=True, verbose_name="User-Agent")

    # Workflow
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='nuevo',
        verbose_name="Estado",
    )
    notas_internas = models.TextField(
        blank=True,
        verbose_name="Notas internas",
        help_text="Notas del equipo de ventas. No se muestran al cliente.",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Recibido")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lead Refugio"
        verbose_name_plural = "Leads Refugio"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='idx_refugiolead_created'),
            models.Index(fields=['status', '-created_at'], name='idx_refugiolead_status'),
            models.Index(fields=['utm_campaign'], name='idx_refugiolead_utm_camp'),
        ]

    def __str__(self):
        return f"{self.nombre} · {self.email} · {self.created_at:%Y-%m-%d}"


# ===========================================================================
# Conexión-Masajes — Ficha de Bienestar para Masajes (v1: captura + ficha + admin)
# Lenguaje de BIENESTAR (nunca médico/clínico). Canal v1 = email; WhatsApp pendiente
# (Cloud API). Modelos nuevos (tablas nuevas) -> requieren migrate manual en Render.
# ===========================================================================

class BienestarMasajeFicha(models.Model):
    """Ficha de bienestar individual por persona que recibe masaje.
    NO es ficha clínica ni diagnóstico: solo preferencias/zonas de tensión para
    adaptar la experiencia."""

    OBJETIVO_CHOICES = [
        ('relajacion', 'Relajación'),
        ('reducir_estres', 'Reducir estrés'),
        ('aliviar_tension_muscular', 'Aliviar tensión muscular'),
        ('descanso', 'Descanso'),
        ('recuperacion_deportiva', 'Recuperación deportiva'),
        ('experiencia_pareja', 'Experiencia en pareja'),
        ('otro', 'Otro'),
    ]
    INTENSIDAD_CHOICES = [('suave', 'Suave'), ('media', 'Media'), ('firme', 'Firme')]
    ORIGEN_CHOICES = [
        ('comprador', 'Comprador'), ('acompanante', 'Acompañante'),
        ('recepcion', 'Recepción'), ('admin', 'Admin'),
    ]
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'), ('completada', 'Completada'), ('incompleta', 'Incompleta'),
    ]
    FRECUENCIA_CHOICES = [
        ('cada_15_dias', 'Cada 15 días'), ('mensual', 'Mensual'),
        ('cada_2_meses', 'Cada 2 meses'), ('ocasional', 'Ocasional'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True, related_name='fichas_bienestar')
    reserva = models.ForeignKey(VentaReserva, on_delete=models.CASCADE, related_name='fichas_bienestar')
    servicio_reservado = models.ForeignKey(ReservaServicio, on_delete=models.SET_NULL, null=True, blank=True, related_name='fichas_bienestar')

    # Datos de la persona
    nombre_completo = models.CharField(max_length=160)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    ciudad = models.CharField(max_length=120, blank=True)

    # Preferencias de bienestar (todas opcionales)
    objetivo_principal = models.CharField(max_length=30, choices=OBJETIVO_CHOICES, blank=True)
    intensidad_preferida = models.CharField(max_length=10, choices=INTENSIDAD_CHOICES, blank=True)
    zonas_tension = models.CharField(max_length=255, blank=True, verbose_name="Zonas de tensión")
    zonas_evitar = models.CharField(max_length=255, blank=True, verbose_name="Zonas que prefiere evitar")
    observaciones_bienestar = models.TextField(blank=True)
    condiciones_declaradas = models.TextField(
        blank=True,
        help_text="Esta información se usa solo para adaptar la experiencia de bienestar. No constituye evaluación médica ni diagnóstico.",
    )

    # Consentimientos (registro legal: fecha + texto exacto aceptado)
    consentimiento_datos = models.BooleanField(default=False)
    consentimiento_marketing = models.BooleanField(default=False)
    fecha_consentimiento = models.DateTimeField(null=True, blank=True)
    consentimiento_texto = models.TextField(blank=True, help_text="Texto exacto del consentimiento aceptado.")

    origen = models.CharField(max_length=12, choices=ORIGEN_CHOICES, default='acompanante')
    estado_ficha = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='pendiente', db_index=True)

    # Resumen del terapeuta (post-masaje, se llena en el Admin). Solo bienestar, no médico.
    obs_terapeuta = models.TextField(blank=True, verbose_name="Observaciones del terapeuta")
    zonas_trabajadas = models.CharField(max_length=255, blank=True)
    intensidad_aplicada = models.CharField(max_length=10, choices=INTENSIDAD_CHOICES, blank=True)
    sugerencia_frecuencia = models.CharField(max_length=15, choices=FRECUENCIA_CHOICES, blank=True)
    recomendacion_texto = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ficha de bienestar (masaje)"
        verbose_name_plural = "Fichas de bienestar (masajes)"
        ordering = ['-created_at']

    def __str__(self):
        return f"Ficha bienestar · {self.nombre_completo} · reserva {self.reserva_id}"


class ParticipanteMasajeReserva(models.Model):
    """Cada persona que recibe masaje en una reserva (comprador o acompañante)."""

    TIPO_CHOICES = [('comprador', 'Comprador'), ('acompanante', 'Acompañante')]
    ESTADO_CONTACTO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('email_enviado', 'Email enviado'),
        ('formulario_abierto', 'Formulario abierto'),
        ('ficha_completada', 'Ficha completada'),
        ('no_responde', 'No responde'),
    ]

    reserva = models.ForeignKey(VentaReserva, on_delete=models.CASCADE, related_name='participantes_masaje')
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name='participaciones_masaje')
    ficha_bienestar = models.OneToOneField(BienestarMasajeFicha, on_delete=models.SET_NULL, null=True, blank=True, related_name='participante')

    nombre = models.CharField(max_length=160, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    tipo_participante = models.CharField(max_length=12, choices=TIPO_CHOICES)
    estado_contacto = models.CharField(max_length=20, choices=ESTADO_CONTACTO_CHOICES, default='pendiente', db_index=True)

    # Token único y seguro para el formulario público (patrón secrets.token_urlsafe)
    token_formulario = models.CharField(max_length=64, unique=True, db_index=True, blank=True)
    # 'fecha_envio' generaliza el antiguo 'fecha_envio_whatsapp' (canal v1 = email)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_completado_formulario = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Participante de masaje"
        verbose_name_plural = "Participantes de masaje"
        ordering = ['reserva', 'tipo_participante']

    def save(self, *args, **kwargs):
        if not self.token_formulario:
            import secrets
            self.token_formulario = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_participante_display()} · {self.nombre or '(sin datos)'} · reserva {self.reserva_id}"


class SeguimientoBienestarMasaje(models.Model):
    """Email de seguimiento programado por participante (scaffolding v2 — el envío
    automatizado se implementa en v2; en v1 solo se crea el modelo)."""

    TIPO_EMAIL_CHOICES = [
        ('gracias_visita', 'Gracias por la visita'),
        ('encuesta_24h', 'Encuesta 24h'),
        ('seguimiento_7d', 'Seguimiento 7 días'),
        ('recomendacion_30d', 'Recomendación 30 días'),
        ('reactivacion_60d', 'Reactivación 60 días'),
        ('reactivacion_90d', 'Reactivación 90 días'),
    ]
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'), ('enviado', 'Enviado'),
        ('error', 'Error'), ('cancelado', 'Cancelado'),
    ]

    participante = models.ForeignKey(ParticipanteMasajeReserva, on_delete=models.CASCADE, related_name='seguimientos')
    reserva = models.ForeignKey(VentaReserva, on_delete=models.CASCADE, related_name='seguimientos_masaje')
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name='seguimientos_masaje')

    tipo_email = models.CharField(max_length=20, choices=TIPO_EMAIL_CHOICES)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='pendiente', db_index=True)
    fecha_programada = models.DateTimeField(db_index=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    asunto = models.CharField(max_length=255, blank=True)
    cuerpo = models.TextField(blank=True)
    error_log = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Seguimiento de bienestar (masaje)"
        verbose_name_plural = "Seguimientos de bienestar (masajes)"
        ordering = ['fecha_programada']

    def __str__(self):
        return f"{self.get_tipo_email_display()} · {self.estado} · {self.fecha_programada:%Y-%m-%d}"


# ===========================================================================
# WhatsApp Cloud API — persistencia de conversaciones (fuente de verdad en Django)
# Las recibe/envía aremko-cli (Go) vía Cloud API; aquí se guardan y se conectan a
# la bandeja OVC (ContactoWhatsApp). Tabla NUEVA -> migrate manual en Render.
# ===========================================================================

class WhatsAppMessage(models.Model):
    DIRECTION_CHOICES = [('in', 'Entrante'), ('out', 'Saliente')]
    STATUS_CHOICES = [
        ('sent', 'Enviado'), ('delivered', 'Entregado'), ('read', 'Leído'),
        ('received', 'Recibido'), ('failed', 'Error'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name='whatsapp_messages')
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES, db_index=True)
    wa_message_id = models.CharField(max_length=128, unique=True, db_index=True, help_text="ID del mensaje en Meta (idempotencia).")
    phone = models.CharField(max_length=20, db_index=True, help_text="Teléfono E.164 del cliente.")
    body = models.TextField(blank=True)
    msg_type = models.CharField(max_length=30, default='text', help_text="text, image, audio, etc.")
    timestamp = models.DateTimeField(db_index=True, help_text="Momento del mensaje (de Meta).")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, blank=True)
    contact_name = models.CharField(max_length=160, blank=True)
    # Adjuntos (foto/PDF/voz/video). aremko-cli descarga los bytes de la Cloud API
    # y los sube vía /api/whatsapp/inbound-media. Storage RAW (resource_type=raw)
    # para servir cualquier tipo (imagen, pdf, audio, video) tal cual.
    media_file = models.FileField(
        upload_to='whatsapp/', storage=RawMediaCloudinaryStorage(),
        null=True, blank=True, max_length=255,
        help_text="Adjunto del mensaje (comprobante, foto, audio, etc.). Nombre con UUID.",
    )
    mime_type = models.CharField(max_length=120, blank=True, help_text="Ej. image/jpeg, application/pdf, audio/ogg.")
    original_filename = models.CharField(max_length=255, blank=True, help_text="Nombre original del archivo (útil en documentos).")
    # Conexión con la conversación/bandeja OVC
    contacto_whatsapp = models.ForeignKey('ContactoWhatsApp', on_delete=models.SET_NULL, null=True, blank=True, related_name='mensajes_wa')
    requiere_atencion = models.BooleanField(default=False, db_index=True, help_text="Entrante sin atender por el operador.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mensaje WhatsApp"
        verbose_name_plural = "Mensajes WhatsApp"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['phone', 'timestamp'], name='idx_wamsg_phone_ts'),
        ]

    def __str__(self):
        return f"[{self.direction}] {self.phone} · {self.timestamp:%Y-%m-%d %H:%M}"
