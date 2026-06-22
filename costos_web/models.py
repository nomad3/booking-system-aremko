# -*- coding: utf-8 -*-
"""Tablero de costos de los servicios web que paga Aremko.

Objetivo: tener a la vista fechas de pago, montos, tarjeta (solo últimos 4) y
saldo (para los de uso/prepago) de TODOS los servicios — Render, Cloudinary,
GitHub, Claude, OpenAI, OpenRouter, etc. — para no quedar bloqueados por un
vencimiento o un saldo agotado.

⚠️ SEGURIDAD: este modelo guarda SOLO los últimos 4 dígitos de la tarjeta (dato
no sensible que sirve para identificarla). NUNCA el número completo, CVV ni
vencimiento, ni API keys/secretos (esos viven en variables de entorno).
"""
from datetime import date
from django.core.validators import RegexValidator
from django.db import models


class ServicioWeb(models.Model):
    CATEGORIAS = [
        ('infra', 'Infraestructura / Hosting'),
        ('ia', 'IA / LLM'),
        ('email', 'Email / Mensajería'),
        ('dominio', 'Dominio / DNS'),
        ('marketing', 'Marketing / Ads'),
        ('pagos', 'Pagos'),
        ('otro', 'Otro'),
    ]
    MODALIDADES = [
        ('suscripcion', 'Suscripción (monto fijo recurrente)'),
        ('uso', 'Uso / prepago (saldo)'),
    ]
    CICLOS = [
        ('mensual', 'Mensual'),
        ('anual', 'Anual'),
        ('uso', 'Por uso (sin ciclo fijo)'),
        ('otro', 'Otro'),
    ]
    MONEDAS = [('USD', 'USD'), ('CLP', 'CLP'), ('EUR', 'EUR')]

    nombre = models.CharField(max_length=120, help_text='Ej: Cloudinary, Render, Claude, OpenRouter.')
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='otro')
    modalidad = models.CharField(max_length=20, choices=MODALIDADES, default='suscripcion')
    activo = models.BooleanField(default=True)

    # Costo
    monto = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                help_text='Monto del ciclo (suscripción) o de la recarga típica (uso).')
    moneda = models.CharField(max_length=3, choices=MONEDAS, default='USD')
    ciclo = models.CharField(max_length=10, choices=CICLOS, default='mensual')
    proxima_fecha_pago = models.DateField(null=True, blank=True,
                                          help_text='Vencimiento / próxima renovación. Lo que ordena el tablero.')
    ultima_fecha_pago = models.DateField(null=True, blank=True)

    # Tarjeta — SOLO identificación (nunca el número completo)
    tarjeta_ultimos4 = models.CharField(
        max_length=4, blank=True, default='',
        validators=[RegexValidator(r'^\d{0,4}$', 'Solo los últimos 4 dígitos.')],
        help_text='Últimos 4 dígitos. NUNCA el número completo ni el CVV.')
    tarjeta_banco = models.CharField(max_length=80, blank=True, default='',
                                     help_text='Ej: Visa Santander, Mastercard.')

    # Saldo (solo para modalidad = uso/prepago)
    saldo_actual = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                       help_text='Saldo/crédito disponible (servicios de uso).')
    saldo_umbral_alerta = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                              help_text='Avisar cuando el saldo baje de este valor.')
    saldo_actualizado = models.DateField(null=True, blank=True, help_text='Fecha en que se revisó el saldo.')

    # Referencias
    url_facturacion = models.URLField(blank=True, default='', help_text='Panel de facturación del servicio.')
    responsable = models.CharField(max_length=80, blank=True, default='')
    notas = models.TextField(blank=True, default='')

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Servicio web (costo)'
        verbose_name_plural = 'Costos de Servicios Web'
        ordering = ['proxima_fecha_pago', 'nombre']

    def __str__(self):
        return self.nombre

    @property
    def dias_para_pago(self):
        """Días hasta el próximo pago (negativo = vencido). None si no hay fecha."""
        if not self.proxima_fecha_pago:
            return None
        return (self.proxima_fecha_pago - date.today()).days

    @property
    def estado_pago(self):
        """Semáforo del vencimiento: vencido / urgente / pronto / ok / sin_fecha."""
        d = self.dias_para_pago
        if d is None:
            return 'sin_fecha'
        if d < 0:
            return 'vencido'
        if d < 7:
            return 'urgente'
        if d < 15:
            return 'pronto'
        return 'ok'

    @property
    def saldo_bajo(self):
        """True si es de uso y el saldo está por debajo del umbral."""
        return (self.saldo_actual is not None
                and self.saldo_umbral_alerta is not None
                and self.saldo_actual < self.saldo_umbral_alerta)
