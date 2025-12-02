# -*- coding: utf-8 -*-
"""
Modelos para el sistema de campañas de email visual.

Este archivo contiene modelos adicionales para gestionar campañas de marketing
por email de manera visual, incluyendo templates, segmentación y estadísticas.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError


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
    
    # Usuario que creo la campaña
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
