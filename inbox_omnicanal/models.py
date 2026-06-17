"""Persistencia de mensajes omnicanal (H-016+H-023).

App AISLADA drift-safe (patrón `whatsapp_agent`): tabla nueva propia, sin FK que
arrastre `ventas` (AR-034 deja `ventas` congelado). WhatsApp sigue viviendo en
`ventas.WhatsAppMessage`; aquí entra Instagram (H-016), Messenger (H-023) y futuros canales.
El read de la bandeja UNE todas las fuentes: /api/inbox/conversations lista unificado.

Identidad de la conversación: `(canal, external_id)`.
- Instagram   → external_id = IGSID del cliente (el que NO es la cuenta de Aremko).
- Messenger   → external_id = PSID del cliente (el que NO es la Página 555157687911449).
- WhatsApp    → external_id = teléfono (si algún día se migra acá).

El vínculo a `ventas.Cliente` es OPCIONAL y se guarda como id plano (sin FK) para no
crear dependencia de migración con `ventas`. Un DM de IG/Messenger puede no matchear cliente.
"""

from django.db import models
from cloudinary_storage.storage import RawMediaCloudinaryStorage  # storage raw para adjuntos IG (pdf/audio/imagen/video)


class ChannelMessage(models.Model):
    CANAL_CHOICES = [('whatsapp', 'WhatsApp'), ('instagram', 'Instagram'), ('messenger', 'Facebook Messenger')]
    DIRECTION_CHOICES = [('in', 'Entrante'), ('out', 'Saliente')]

    canal = models.CharField(max_length=20, choices=CANAL_CHOICES, db_index=True)
    external_id = models.CharField(
        max_length=120, db_index=True,
        help_text='Identidad de la conversación en el canal (IG: IGSID; WA: teléfono).')
    external_message_id = models.CharField(
        max_length=190, unique=True,
        help_text='ID del mensaje en el canal (idempotencia). IG: mid.')
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES, db_index=True)
    body = models.TextField(blank=True)
    msg_type = models.CharField(max_length=30, default='text', help_text='text, image, story, share, etc.')
    timestamp = models.DateTimeField(db_index=True, help_text='Momento del mensaje (del canal).')
    status = models.CharField(max_length=12, blank=True)
    contact_name = models.CharField(max_length=200, blank=True, help_text='@username o nombre resuelto por aremko-cli.')
    # ventas.Cliente.id si se resolvió (sin FK a propósito → app aislada, cero dependencia
    # de migración con ventas). IG empieza sin cliente; se enriquece después.
    cliente_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    requiere_atencion = models.BooleanField(default=False, db_index=True, help_text='Entrante sin atender por el operador.')
    # Adjuntos (Fase 5). aremko-cli descarga los bytes del media temporal de IG (con el
    # token) y los sube vía /api/instagram/inbound-media. Storage RAW (resource_type=raw)
    # para servir cualquier tipo (imagen, audio, video) tal cual, igual que WhatsApp.
    media_file = models.FileField(
        upload_to='instagram/', storage=RawMediaCloudinaryStorage(),
        null=True, blank=True, max_length=255,
        help_text='Adjunto del DM (foto/audio/video). Nombre con UUID.',
    )
    mime_type = models.CharField(max_length=120, blank=True, help_text='Ej. image/jpeg, audio/ogg.')
    original_filename = models.CharField(max_length=255, blank=True, help_text='Nombre original del archivo (si viene).')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mensaje omnicanal'
        verbose_name_plural = 'Mensajes omnicanal'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['canal', 'external_id', 'timestamp'], name='idx_chmsg_conv_ts'),
            models.Index(fields=['canal', 'requiere_atencion'], name='idx_chmsg_canal_req'),
        ]

    def __str__(self):
        return f'[{self.canal}/{self.direction}] {self.external_id} · {self.timestamp:%Y-%m-%d %H:%M}'
