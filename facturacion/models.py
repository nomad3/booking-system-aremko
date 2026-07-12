"""
Facturación electrónica SII — P-16.

App AISLADA drift-safe (mismo criterio que conciliacion/): no toca ningún modelo
de `ventas`; la relación con Pago es un OneToOne declarado DESDE acá.

Alcance tributario (confirmado por Jorge 2026-07-11):
- Solo generan boleta los pagos por transferencia/efectivo (incluida la
  transferencia directa a la Cuenta Vista de Mercado Pago). Tarjeta, links de
  pago y Flow los informa el recaudador al SII (el voucher reemplaza la boleta).
- La venta de una giftcard NO boletea por sí misma: es un producto más (como
  una tabla de quesos) — boletea o no según el MEDIO con que se pagó esa
  compra. El canje (metodo_pago='giftcard') nunca boletea.
- Una boleta por cada pago (el IVA en servicios se devenga al percibir).

Los secretos NUNCA van en estos modelos: SIMPLEAPI_API_KEY, SII_CERT_B64 y
SII_CERT_PASSWORD viven en variables de entorno (Render).
"""
import uuid

from django.db import models, transaction


def nuevo_token_consulta():
    """Token opaco para la página pública de consulta de boletas."""
    return uuid.uuid4().hex


class MedioPago(models.Model):
    """Espejo configurable de los códigos de Pago.metodo_pago (ventas).

    Pedido por Jorge (2026-07-11): un switch por medio de pago que diga si
    genera boleta, para evitar dobles boleteos con lo que ya informa el
    recaudador (SumUp/MP/Flow). Se siembra con `sembrar_medios_pago`.
    """

    codigo = models.CharField(
        max_length=100, unique=True,
        help_text="Debe calzar EXACTO con Pago.metodo_pago (ventas).")
    nombre = models.CharField(max_length=150)
    genera_boleta = models.BooleanField(
        default=False, db_index=True,
        help_text="ON: cada pago con este medio genera boleta electrónica. "
                  "OFF: el recaudador informa al SII (voucher = boleta) o no es plata real.")
    nota = models.CharField(max_length=255, blank=True, default='')
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Medio de pago (boleteo)'
        verbose_name_plural = 'Medios de pago (boleteo)'
        ordering = ['-genera_boleta', 'codigo']

    def __str__(self):
        return f"{self.codigo} ({'boletea' if self.genera_boleta else 'no boletea'})"


class ConfiguracionFacturacion(models.Model):
    """Singleton (pk=1) con los datos del emisor y el ambiente activo."""

    AMBIENTES = [
        ('simulado', 'Simulado (sin API, para probar la plomería)'),
        ('certificacion', 'Certificación SII (set de pruebas)'),
        ('produccion', 'Producción SII'),
    ]

    ambiente = models.CharField(max_length=20, choices=AMBIENTES, default='simulado')
    emision_automatica = models.BooleanField(
        default=False,
        help_text="F2: al registrarse un pago boleteable se encola la emisión sola. "
                  "En F1 déjalo apagado (emisión solo manual desde el admin).")

    # Datos del emisor (van en cada DTE)
    rut_emisor = models.CharField(
        max_length=12, blank=True, default='',
        help_text="RUT de la empresa, con guión y dígito verificador (ej: 76123456-7).")
    razon_social = models.CharField(max_length=100, blank=True, default='')
    giro_boleta = models.CharField(
        max_length=80, blank=True, default='',
        help_text="Glosa corta del giro para la boleta (máx 80).")
    direccion = models.CharField(max_length=70, blank=True, default='')
    comuna = models.CharField(max_length=20, blank=True, default='Puerto Varas')
    indicador_servicio = models.PositiveSmallIntegerField(
        default=3, help_text="3 = ventas y servicios (boleta). No cambiar sin razón.")
    rut_firmante = models.CharField(
        max_length=12, blank=True, default='',
        help_text="RUT del dueño del certificado digital (representante legal), con guión.")

    # Carátula del sobre de envío (para certificación: fecha de la postulación
    # aceptada y resolución 0; para producción: los datos de la autorización).
    fecha_resolucion = models.DateField(
        null=True, blank=True,
        help_text="Fecha de resolución que autoriza a emitir (cert: fecha de postulación).")
    numero_resolucion = models.PositiveIntegerField(
        default=0, help_text="Número de resolución (0 en certificación).")

    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de facturación'
        verbose_name_plural = 'Configuración de facturación'

    def __str__(self):
        return f"Configuración facturación ({self.get_ambiente_display()})"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class RangoFolios(models.Model):
    """Un archivo CAF del SII = un rango de folios autorizados para un tipo de DTE.

    El XML del CAF (incluye la firma del SII) se guarda acá para adjuntarlo en
    cada generación vía SimpleAPI. Los folios de certificación no tienen valor
    tributario; los de producción sí — pedir rangos chicos (500-1000).
    """

    tipo_dte = models.PositiveSmallIntegerField(default=39, db_index=True)
    ambiente = models.CharField(max_length=20, choices=ConfiguracionFacturacion.AMBIENTES[1:])
    folio_desde = models.PositiveIntegerField()
    folio_hasta = models.PositiveIntegerField()
    folio_siguiente = models.PositiveIntegerField(
        help_text="Próximo folio a usar. Se avanza solo; no editar a mano salvo rescate.")
    caf_xml = models.TextField(help_text="Contenido íntegro del archivo CAF (.xml) del SII.")
    activo = models.BooleanField(default=True, db_index=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Rango de folios (CAF)'
        verbose_name_plural = 'Rangos de folios (CAF)'
        ordering = ['tipo_dte', 'folio_desde']
        constraints = [
            models.UniqueConstraint(
                fields=['tipo_dte', 'ambiente', 'folio_desde'],
                name='unique_caf_por_rango'),
        ]

    def __str__(self):
        return f"CAF {self.tipo_dte} [{self.folio_desde}-{self.folio_hasta}] {self.ambiente}"

    @property
    def restantes(self):
        return max(0, self.folio_hasta - self.folio_siguiente + 1)

    @classmethod
    def asignar_folio(cls, tipo_dte, ambiente):
        """Entrega el próximo folio disponible y avanza el contador (atómico).

        Devuelve (folio, rango) o (None, None) si no quedan folios activos.
        """
        with transaction.atomic():
            rango = (cls.objects.select_for_update()
                     .filter(tipo_dte=tipo_dte, ambiente=ambiente, activo=True,
                             folio_siguiente__lte=models.F('folio_hasta'))
                     .order_by('folio_desde').first())
            if not rango:
                return None, None
            folio = rango.folio_siguiente
            rango.folio_siguiente = folio + 1
            rango.save(update_fields=['folio_siguiente'])
            return folio, rango


class BoletaElectronica(models.Model):
    """Una boleta electrónica por pago (candado OneToOne = imposible duplicar).

    on_delete=PROTECT en ambas FK: un pago con boleta emitida NO se puede borrar
    del admin — corresponde nota de crédito (F3). Para deshacer una boleta
    simulada o con error, se borra la boleta primero.
    """

    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('simulada', 'Simulada (sin valor tributario)'),
        ('generada', 'Generada y timbrada'),
        ('enviada', 'Enviada al SII'),
        ('aceptada', 'Aceptada por el SII'),
        ('rechazada', 'Rechazada por el SII'),
        ('error', 'Error de emisión'),
        ('anulada', 'Anulada (nota de crédito)'),
    ]

    # Nullable SOLO para las boletas del set de pruebas de certificación
    # (no nacen de un pago real). Toda boleta operativa lleva su pago.
    pago = models.OneToOneField(
        'ventas.Pago', on_delete=models.PROTECT, related_name='boleta_electronica',
        null=True, blank=True)
    venta_reserva = models.ForeignKey(
        'ventas.VentaReserva', on_delete=models.PROTECT,
        related_name='boletas_electronicas', null=True, blank=True)
    caso_set = models.CharField(
        max_length=12, blank=True, default='', db_index=True,
        help_text="Solo certificación: CASO-N del set de pruebas del SII.")

    tipo_dte = models.PositiveSmallIntegerField(default=39)
    ambiente = models.CharField(max_length=20, default='simulado')
    folio = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    monto_total = models.DecimalField(max_digits=10, decimal_places=0)
    monto_neto = models.DecimalField(max_digits=10, decimal_places=0)
    monto_iva = models.DecimalField(max_digits=10, decimal_places=0)
    glosa = models.CharField(max_length=200, blank=True, default='')

    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente', db_index=True)
    track_id = models.CharField(max_length=60, blank=True, default='')
    xml_dte = models.TextField(blank=True, default='')
    error_mensaje = models.TextField(blank=True, default='')
    intentos = models.PositiveSmallIntegerField(default=0)

    token_consulta = models.CharField(
        max_length=32, unique=True, default=nuevo_token_consulta,
        help_text="Token de la página pública de verificación.")

    creada_at = models.DateTimeField(auto_now_add=True)
    emitida_at = models.DateTimeField(null=True, blank=True)
    actualizada_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Boleta electrónica'
        verbose_name_plural = 'Boletas electrónicas'
        ordering = ['-creada_at']

    def __str__(self):
        etiqueta = f"folio {self.folio}" if self.folio else f"interna #{self.pk}"
        return f"Boleta {etiqueta} (${self.monto_total:,.0f})".replace(',', '.')

    @property
    def es_definitiva(self):
        return self.estado in ('generada', 'enviada', 'aceptada')
