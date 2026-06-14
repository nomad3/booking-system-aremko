"""Modelos del Agente IA de WhatsApp (H-007).

DOS tablas NUEVAS y aisladas (app propia) → la migración es puramente aditiva
(CreateModel) y no arrastra el drift de `ventas`/`control_gestion` (AR-034).

- WhatsAppAgentConfig: singleton editable desde admin (on/off, modo, tono,
  modelo). Criterio de Jorge: las features de IA se controlan con formularios
  admin, no con variables de entorno.
- SugerenciaAgenteWhatsApp: el borrador generado para un entrante concreto
  (cache por wa_message_id + observabilidad de tokens/latencia/escalamiento).
"""

from django.db import models
from solo.models import SingletonModel


class WhatsAppAgentConfig(SingletonModel):
    """Configuración única del agente. `WhatsAppAgentConfig.get_solo()`."""

    MODO_CHOICES = [
        ('borrador', 'Borrador asistido (Fase 1) — genera sugerencia, humano envía'),
        ('auto_info', 'Auto solo informativo (Fase 2) — auto-envía info, escala lo transaccional'),
        ('auto', 'Auto completo (Fase 3) — responde dentro de alcance'),
    ]

    activo = models.BooleanField(
        default=False,
        verbose_name='Agente activo',
        help_text='Interruptor general. Si está apagado, no se genera ninguna sugerencia.',
    )
    modo = models.CharField(
        max_length=20, choices=MODO_CHOICES, default='borrador',
        help_text='Fase 1 = borrador (recomendado para empezar). El auto-envío llega en fases 2-3.',
    )
    persona_tono = models.TextField(
        default=(
            'Eres el asistente virtual de Aremko Spa Boutique, en Puerto Varas, Chile '
            '("aguas calientes junto al río"). Hablas en español de Chile, cálido y cercano, '
            'breve, con buena onda y sin sonar robótico. Representas a un spa boutique de '
            'cabañas y tinas calientes junto al río.'
        ),
        help_text='Voz de marca / personalidad. Es el bloque 1 del system prompt (editable sin redeploy).',
    )
    conocimiento = models.TextField(
        blank=True, default='',
        verbose_name='Conocimiento y correcciones',
        help_text='Reglas y correcciones que el agente debe respetar SIEMPRE (autoridad máxima, por '
                  'sobre el catálogo). Una regla por línea. Ej: "Las tinas se cobran POR PERSONA, '
                  'capacidad 1 a 4." / "No ofrecer el producto Cacao por este chat." Editable sin redeploy.',
    )
    link_reserva = models.URLField(
        max_length=300, default='https://www.aremko.cl/',
        help_text='Link oficial de reservas al que el agente deriva (nunca confirma reservas él mismo).',
    )

    # Modelo en la config (no en env) — alineado con el patrón DPV (AgentPromptTemplate).
    model_name = models.CharField(
        max_length=120, blank=True, default='',
        help_text='ID OpenRouter (ej. anthropic/claude-haiku-4.5). Vacío = usa DPV_LLM_MODEL de env.',
    )
    temperature = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.40,
        help_text='Creatividad del modelo. Bajo (0.2-0.5) = más preciso y predecible (recomendado).',
    )
    max_tokens = models.PositiveSmallIntegerField(
        default=350,
        help_text='Tope de tokens de salida. WhatsApp quiere respuestas cortas.',
    )
    history_window = models.PositiveSmallIntegerField(
        default=6,
        help_text='Cuántos mensajes recientes de la conversación se le pasan como contexto.',
    )
    pausa_horas_tras_humano = models.PositiveSmallIntegerField(
        default=12,
        help_text='Horas que el agente se calla en un chat después de que un humano respondió ahí.',
    )

    # --- Mensaje de ausencia (H-008) — independiente del agente IA ---
    ausencia_activa = models.BooleanField(
        default=False,
        verbose_name='Mensaje de ausencia activo',
        help_text='Si está activo, a cada cliente que escribe se le responde una frase fija '
                  'y NO se genera borrador del agente (la ausencia tiene precedencia).',
    )
    ausencia_mensaje = models.TextField(
        default=(
            '¡Hola! 🌿 Gracias por escribir a Aremko Spa Boutique. En este momento no estamos '
            'atendiendo por este chat. Puedes reservar y pagar online —masajes, tinas calientes '
            'y alojamiento— en www.aremko.cl, disponible las 24 horas. Apenas retomemos la '
            'atención te respondemos por aquí. ¡Gracias por tu paciencia! 🙏'
        ),
        help_text='Frase fija que se auto-responde cuando la ausencia está activa.',
    )
    ausencia_anti_spam_horas = models.PositiveSmallIntegerField(
        default=6,
        help_text='No repetir la frase de ausencia a la misma conversación dentro de estas horas '
                  '(0 = responder a cada mensaje).',
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración Agente WhatsApp'

    def __str__(self):
        estado = 'ON' if self.activo else 'OFF'
        return f'Agente WhatsApp [{estado} · {self.modo}]'


class SugerenciaAgenteWhatsApp(models.Model):
    """Borrador generado por el agente para un entrante concreto.

    Cache por `wa_message_id`: una sugerencia por mensaje entrante respondido,
    así abrir la conversación varias veces no regenera (ni recobra al LLM).
    """

    wa_message_id = models.CharField(
        max_length=128, unique=True, db_index=True,
        help_text='ID Meta del entrante que esta sugerencia responde (idempotencia/cache).',
    )
    phone = models.CharField(max_length=20, db_index=True)

    texto = models.TextField(blank=True, help_text='Borrador sugerido (vacío si escala a humano).')
    escalar = models.BooleanField(default=False, help_text='True = derivar a persona; no se sugiere texto.')
    motivo_escalar = models.CharField(max_length=200, blank=True)

    modo = models.CharField(max_length=20, blank=True)
    modelo = models.CharField(max_length=120, blank=True)
    error = models.CharField(max_length=200, blank=True, help_text='Si el LLM falló; activa el fallback seguro.')

    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)

    enviada = models.BooleanField(
        default=False,
        help_text='True cuando el borrador se usó para responder (lo marcará el outbound en fases 2-3).',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sugerencia Agente WhatsApp'
        verbose_name_plural = 'Sugerencias Agente WhatsApp'
        ordering = ['-created_at']

    def __str__(self):
        tag = 'ESCALAR' if self.escalar else 'BORRADOR'
        return f'[{tag}] {self.phone} · {self.created_at:%Y-%m-%d %H:%M}'


class AgenteFeedback(models.Model):
    """Delta entre el borrador propuesto por el agente y lo que Deborah envió (H-010 parte 1).

    Base del motor de aprendizaje: si `editado=True`, la corrección alimenta la
    clasificación (parte 2) y las métricas de evolución (parte 3, `pct_sin_editar`).
    Fire-and-forget: lo reporta aremko-cli tras un envío que tenía borrador.
    """

    phone = models.CharField(max_length=20, db_index=True)
    wa_message_id = models.CharField(
        max_length=128, db_index=True, blank=True,
        help_text='Referencia del mensaje/borrador (el entrante que se respondía).',
    )
    borrador = models.TextField(blank=True, help_text='Lo que el agente propuso.')
    enviado = models.TextField(blank=True, help_text='Lo que Deborah realmente envió.')
    editado = models.BooleanField(
        default=False, db_index=True,
        help_text='True si lo enviado difiere del borrador (hubo corrección).',
    )
    # Parte 2: se marcará cuando el clasificador ya procesó este feedback.
    procesado = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Feedback del agente'
        verbose_name_plural = 'Feedback del agente'
        ordering = ['-created_at']

    def __str__(self):
        tag = 'EDITADO' if self.editado else 'SIN EDITAR'
        return f'[{tag}] {self.phone} · {self.created_at:%Y-%m-%d %H:%M}'


class AusenciaEnviada(models.Model):
    """Última vez que se envió el mensaje de ausencia a una conversación (anti-spam).

    Una fila por teléfono; se actualiza cada vez que el inbound dispara la frase de
    ausencia, para no repetirla dentro de la ventana `ausencia_anti_spam_horas`.
    """

    phone = models.CharField(max_length=20, unique=True, db_index=True)
    ultimo_envio = models.DateTimeField()

    class Meta:
        verbose_name = 'Ausencia enviada'
        verbose_name_plural = 'Ausencias enviadas'

    def __str__(self):
        return f'{self.phone} · {self.ultimo_envio:%Y-%m-%d %H:%M}'
