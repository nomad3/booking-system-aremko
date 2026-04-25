from django.db import models

from .enums import (
    BlockType,
    ChannelType,
    ConversationStatus,
    InterestType,
    MessageSenderType,
    PartnershipLevel,
    PlaceType,
    ProfileType,
    DurationType,
)


class DurationCase(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    duration_type = models.CharField(max_length=30, choices=DurationType.choices)
    days = models.PositiveSmallIntegerField()
    nights = models.PositiveSmallIntegerField()
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["sort_order", "days"]
        verbose_name = "Caso de duración"
        verbose_name_plural = "Casos de duración"

    def __str__(self):
        return f"{self.code} — {self.name}"


class Circuit(models.Model):
    number = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    short_description = models.CharField(max_length=255)
    long_description = models.TextField(blank=True)
    duration_case = models.ForeignKey(
        DurationCase,
        on_delete=models.PROTECT,
        related_name="circuits",
    )
    primary_interest = models.CharField(
        max_length=30,
        choices=InterestType.choices,
        db_index=True,
    )
    recommended_profile = models.CharField(
        max_length=20,
        choices=ProfileType.choices,
        blank=True,
    )
    is_romantic = models.BooleanField(default=False)
    is_family_friendly = models.BooleanField(default=False)
    is_adventure = models.BooleanField(default=False)
    is_rain_friendly = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False)
    published = models.BooleanField(default=False, db_index=True)
    featured = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)
    # ─── Narrativa IA (DPV CMS-IA · Capa 3) ───
    places_signature = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=(
            "Hash de las paradas en orden, calculado al generar la narrativa. "
            "Si difiere del hash actual, la narrativa quedó stale y conviene regenerarla."
        ),
    )
    last_narrative_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última vez que se aplicó una narrativa IA al long_description.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "number"]
        verbose_name = "Circuito"
        verbose_name_plural = "Circuitos"

    def __str__(self):
        return f"#{self.number} — {self.name}"

    def compute_places_signature(self) -> str:
        """SHA256 corto de las paradas en orden (day_number, visit_order, place_id).

        Permite detectar cambios sin guardar snapshot completo.
        """
        import hashlib

        tuples = []
        for day in self.days.order_by("day_number", "sort_order"):
            for stop in day.place_stops.order_by("visit_order"):
                tuples.append((day.day_number, stop.visit_order, stop.place_id))
        raw = "|".join(f"{d}-{v}-{p}" for d, v, p in tuples)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def is_narrative_stale(self) -> bool:
        """True si las paradas cambiaron desde que se generó la narrativa."""
        if not self.places_signature:
            return True
        return self.compute_places_signature() != self.places_signature


class CircuitDay(models.Model):
    circuit = models.ForeignKey(
        Circuit,
        on_delete=models.CASCADE,
        related_name="days",
    )
    day_number = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)
    block_type = models.CharField(max_length=30, choices=BlockType.choices)
    summary = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["circuit", "day_number", "sort_order"]
        verbose_name = "Día de circuito"
        verbose_name_plural = "Días de circuito"
        constraints = [
            models.UniqueConstraint(
                fields=["circuit", "day_number"],
                name="uq_circuitday_circuit_day",
            ),
        ]

    def __str__(self):
        return f"{self.circuit} · Día {self.day_number}: {self.title}"


class Place(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    place_type = models.CharField(
        max_length=30,
        choices=PlaceType.choices,
        db_index=True,
    )
    short_description = models.CharField(max_length=255)
    long_description = models.TextField(blank=True)
    location_label = models.CharField(max_length=200)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    is_rain_friendly = models.BooleanField(default=False)
    is_romantic = models.BooleanField(default=False)
    is_family_friendly = models.BooleanField(default=False)
    is_adventure_related = models.BooleanField(default=False)
    practical_tips = models.TextField(blank=True)
    safety_notes = models.TextField(blank=True)
    did_you_know = models.TextField(blank=True)
    nobody_tells_you = models.TextField(blank=True)
    # ─── Datos estructurados enriquecibles por IA (DPV CMS-IA) ───
    elevation_m = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Altitud en metros sobre el nivel del mar (ej: 2652 para Volcán Osorno).",
    )
    year_established = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Año de creación / declaración (ej: 1926 para Parque Vicente Pérez Rosales).",
    )
    has_parking = models.BooleanField(default=False)
    has_restrooms = models.BooleanField(default=False)
    has_conaf_office = models.BooleanField(default=False)
    has_food_service = models.BooleanField(default=False)
    entry_fee_clp = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Entrada en CLP (0 = gratis, null = no aplica/desconocido).",
    )
    best_season = models.CharField(
        max_length=120,
        blank=True,
        help_text="Mejor temporada para visitar. Ej: 'Diciembre a marzo' o 'Todo el año'.",
    )
    accessibility_notes = models.TextField(
        blank=True,
        help_text="Accesibilidad para personas con movilidad reducida, niños pequeños, etc.",
    )
    distance_from_pv_km = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Distancia en km desde Puerto Varas centro.",
    )
    drive_time_from_pv_min = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Tiempo en auto desde Puerto Varas centro (minutos).",
    )
    extra_data = models.JSONField(
        blank=True,
        default=dict,
        help_text=(
            "Campos no anticipados que la IA puede extraer (glaciar, fauna, "
            "infraestructura adicional, etc.). Estructura libre."
        ),
    )
    last_enriched_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última vez que un draft IA fue aprobado y aplicado a este lugar.",
    )
    # ─── Datos comerciales (negocios, restaurantes, teatros, museos, etc.) ───
    partnership_level = models.CharField(
        max_length=20,
        choices=PartnershipLevel.choices,
        default=PartnershipLevel.LISTED,
        db_index=True,
        help_text=(
            "Nivel de relación comercial. PROPIO=Aremko; PARTNER=acuerdo activo; "
            "LISTED=mencionable sin acuerdo; DIRECTORY=solo referencia (atracción natural, "
            "iglesia, etc. sin relación comercial)."
        ),
    )
    phone = models.CharField(
        max_length=40,
        blank=True,
        help_text="Teléfono de contacto (formato libre).",
    )
    website = models.URLField(
        max_length=300,
        blank=True,
        help_text="Sitio web oficial.",
    )
    instagram = models.CharField(
        max_length=120,
        blank=True,
        help_text="Handle de Instagram (sin @) o URL.",
    )
    reservations_url = models.URLField(
        max_length=400,
        blank=True,
        help_text="URL directa para reservar (si aplica).",
    )
    price_range = models.CharField(
        max_length=20,
        blank=True,
        help_text="$, $$, $$$, $$$$ — escala de precios relativa.",
    )
    opening_hours = models.JSONField(
        blank=True,
        default=dict,
        help_text=(
            "Horarios estructurados. Estructura sugerida: "
            "{'mon': '09:00-18:00', 'tue': '09:00-18:00', ..., 'sun': 'cerrado', "
            "'notes': 'cerrado feriados'}. Vacío si no aplica."
        ),
    )
    published = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Lugar"
        verbose_name_plural = "Lugares"

    def __str__(self):
        return self.name


class CircuitPlace(models.Model):
    circuit_day = models.ForeignKey(
        CircuitDay,
        on_delete=models.CASCADE,
        related_name="place_stops",
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.PROTECT,
        related_name="circuit_stops",
    )
    visit_order = models.PositiveSmallIntegerField(default=0)
    is_main_stop = models.BooleanField(default=False)

    class Meta:
        ordering = ["circuit_day", "visit_order"]
        verbose_name = "Parada de circuito"
        verbose_name_plural = "Paradas de circuito"

    def __str__(self):
        return f"{self.circuit_day} · {self.place}"


class AremkoRecommendation(models.Model):
    name = models.CharField(max_length=150)
    context_key = models.CharField(max_length=80, unique=True)
    title = models.CharField(max_length=200)
    message_text = models.TextField()
    recommended_service_type = models.CharField(max_length=50, blank=True)
    priority = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["priority", "name"]
        verbose_name = "Recomendación Aremko"
        verbose_name_plural = "Recomendaciones Aremko"

    def __str__(self):
        return f"{self.context_key} — {self.name}"


class TravelTip(models.Model):
    title = models.CharField(max_length=200)
    tip_text = models.TextField()
    interest = models.CharField(
        max_length=30,
        choices=InterestType.choices,
        blank=True,
    )
    profile = models.CharField(
        max_length=20,
        choices=ProfileType.choices,
        blank=True,
    )
    duration_case = models.ForeignKey(
        DurationCase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="travel_tips",
    )
    applies_when_raining = models.BooleanField(default=False)
    applies_when_sunny = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "title"]
        verbose_name = "Tip de viaje"
        verbose_name_plural = "Tips de viaje"

    def __str__(self):
        return self.title


class RecommendationRule(models.Model):
    name = models.CharField(max_length=200)
    duration_case = models.ForeignKey(
        DurationCase,
        on_delete=models.CASCADE,
        related_name="recommendation_rules",
    )
    interest = models.CharField(
        max_length=30,
        choices=InterestType.choices,
        blank=True,
    )
    profile = models.CharField(
        max_length=20,
        choices=ProfileType.choices,
        blank=True,
    )
    is_rainy = models.BooleanField(null=True, blank=True)
    recommended_circuit = models.ForeignKey(
        Circuit,
        on_delete=models.CASCADE,
        related_name="recommendation_rules",
    )
    priority = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["priority", "name"]
        verbose_name = "Regla de recomendación"
        verbose_name_plural = "Reglas de recomendación"

    def __str__(self):
        return f"{self.name} → {self.recommended_circuit}"


class LeadConversation(models.Model):
    channel = models.CharField(
        max_length=20,
        choices=ChannelType.choices,
        db_index=True,
    )
    external_id = models.CharField(max_length=120, blank=True, db_index=True)
    contact_name = models.CharField(max_length=200, blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    contact_email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=30,
        choices=ConversationStatus.choices,
        default=ConversationStatus.OPEN,
        db_index=True,
    )
    detected_interest = models.CharField(
        max_length=30,
        choices=InterestType.choices,
        blank=True,
    )
    detected_profile = models.CharField(
        max_length=20,
        choices=ProfileType.choices,
        blank=True,
    )
    detected_duration_case = models.ForeignKey(
        DurationCase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    recommended_circuit = models.ForeignKey(
        Circuit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    referred_to_aremko = models.BooleanField(default=False)
    showed_interest_in_aremko = models.BooleanField(
        default=False,
        help_text="True si el usuario mencionó spa/masaje/tina/alojamiento durante la conversación.",
    )
    last_user_message_at = models.DateTimeField(null=True, blank=True)
    last_assistant_message_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Conversación de lead"
        verbose_name_plural = "Conversaciones de leads"

    def __str__(self):
        label = self.contact_name or self.contact_phone or self.external_id or "sin contacto"
        return f"[{self.get_channel_display()}] {label}"


class ConversationMessage(models.Model):
    conversation = models.ForeignKey(
        LeadConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender_type = models.CharField(
        max_length=20,
        choices=MessageSenderType.choices,
    )
    text = models.TextField()
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # ─── LLM metadata (DPV-004) ───
    llm_model = models.CharField(max_length=80, blank=True, default="")
    llm_input_tokens = models.PositiveIntegerField(default=0)
    llm_output_tokens = models.PositiveIntegerField(default=0)
    llm_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    llm_latency_ms = models.PositiveIntegerField(default=0)
    llm_error = models.CharField(max_length=200, blank=True, default="")
    # ─── External message dedup (DPV-006) ───
    external_message_id = models.CharField(
        max_length=120, blank=True, default="", db_index=True
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Mensaje de conversación"
        verbose_name_plural = "Mensajes de conversación"

    def __str__(self):
        return f"{self.conversation} · {self.get_sender_type_display()} · {self.created_at:%Y-%m-%d %H:%M}"


class AgentPromptTemplate(models.Model):
    """Prompt del agente conversacional LLM — editable desde Django admin.

    El servicio agent_service busca el template activo por `slug` y lo usa
    como system prompt. Cambiar el prompt no requiere deploy.
    """

    slug = models.SlugField(
        max_length=80,
        unique=True,
        help_text="Identificador interno estable. Ej: 'dpv-main-guide'. No cambiar en caliente.",
    )
    name = models.CharField(
        max_length=150,
        help_text="Nombre descriptivo para el admin. Ej: 'Destino Puerto Varas · Guía principal'.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Solo el template activo con el slug buscado será utilizado.",
    )
    system_prompt = models.TextField(
        help_text=(
            "Prompt de sistema del agente. Puede incluir instrucciones, tono, reglas, "
            "políticas de derivación a Aremko, etc. Los lugares/circuitos los inyecta el "
            "agent_service vía tools — NO los hardcodees aquí."
        ),
    )
    model_name = models.CharField(
        max_length=120,
        default="anthropic/claude-haiku-4.5",
        help_text="Identificador del modelo en OpenRouter. Ej: 'anthropic/claude-3.5-sonnet', 'openai/gpt-4o-mini'.",
    )
    temperature = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.7,
        help_text="0.0 (muy predecible) a 1.0+ (más creativo). 0.5-0.8 recomendado para conversaciones.",
    )
    max_output_tokens = models.PositiveIntegerField(
        default=600,
        help_text="Tope de tokens de salida por respuesta. WhatsApp/Telegram = respuestas cortas.",
    )
    history_window = models.PositiveSmallIntegerField(
        default=10,
        help_text="Cuántos mensajes previos de la conversación enviar al LLM como contexto.",
    )
    notes = models.TextField(
        blank=True,
        help_text="Notas internas sobre este template (ej: changelog, A/B test en curso).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]
        verbose_name = "Template de prompt del agente"
        verbose_name_plural = "Templates de prompt del agente"

    def __str__(self):
        estado = "activo" if self.is_active else "inactivo"
        return f"{self.name} [{self.slug}] ({estado})"


class PlacePhoto(models.Model):
    """Foto asociada a un Place. Inicialmente desde la web (source_url),
    luego reemplazables por fotos propias.
    """

    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(
        upload_to="dpv/places/",
        blank=True,
        null=True,
        help_text="Foto subida a storage (Cloudinary). Opcional si solo tenemos source_url.",
    )
    source_url = models.URLField(
        blank=True,
        max_length=500,
        help_text="URL de origen si la foto vino de la web (Wikipedia, Unsplash, etc.). "
                  "Para fotos propias, dejar vacío.",
    )
    caption = models.CharField(max_length=255, blank=True)
    credit = models.CharField(
        max_length=200,
        blank=True,
        help_text="Atribución (ej: 'Foto: Wikimedia Commons, CC-BY-SA').",
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Foto principal del lugar (la que sale primero).",
    )
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["place", "order", "id"]
        verbose_name = "Foto de lugar"
        verbose_name_plural = "Fotos de lugares"

    def __str__(self):
        marker = " ★" if self.is_primary else ""
        return f"{self.place.name} · foto #{self.order}{marker}"


class PlaceEnrichmentDraft(models.Model):
    """Borrador generado por IA para enriquecer un Place.
    Requiere revisión humana antes de aplicarse al Place real.
    """

    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_APPLIED = "applied"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Borrador (pendiente revisión)"),
        (STATUS_APPROVED, "Aprobado (listo para aplicar)"),
        (STATUS_REJECTED, "Rechazado"),
        (STATUS_APPLIED, "Aplicado al Place"),
    ]

    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="enrichment_drafts",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    proposed_data = models.JSONField(
        default=dict,
        help_text=(
            "Estructura: {'fields': {'elevation_m': 2652, ...}, "
            "'extra_data': {...}, 'photos': [{url, caption, credit}, ...], "
            "'long_description': '...'}"
        ),
    )
    raw_search_response = models.JSONField(
        blank=True,
        null=True,
        help_text="Respuesta cruda del proveedor de búsqueda (Perplexity) para auditoría.",
    )
    search_provider = models.CharField(
        max_length=40,
        default="perplexity",
        help_text="Proveedor usado: perplexity, tavily, brave, etc.",
    )
    llm_model = models.CharField(max_length=80, blank=True, default="")
    llm_input_tokens = models.PositiveIntegerField(default=0)
    llm_output_tokens = models.PositiveIntegerField(default=0)
    llm_latency_ms = models.PositiveIntegerField(default=0)
    review_notes = models.TextField(
        blank=True,
        help_text="Comentarios del revisor humano (qué se cambió, por qué se rechazó, etc.).",
    )
    reviewed_by = models.CharField(
        max_length=80,
        blank=True,
        help_text="Username de quien revisó (admin Django).",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Borrador de enriquecimiento"
        verbose_name_plural = "Borradores de enriquecimiento"

    def __str__(self):
        return f"{self.place.name} · {self.get_status_display()} · {self.created_at:%Y-%m-%d}"


class CircuitNarrativeDraft(models.Model):
    """Borrador de narrativa editorial para un Circuit, generado por IA.

    Análogo a PlaceEnrichmentDraft pero para Circuits. Toma los Places ordenados
    del circuito y le pide al LLM que arme un texto continuo y coherente.
    Requiere revisión humana antes de aplicarse.
    """

    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_APPLIED = "applied"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Borrador (pendiente revisión)"),
        (STATUS_APPROVED, "Aprobado (listo para aplicar)"),
        (STATUS_REJECTED, "Rechazado"),
        (STATUS_APPLIED, "Aplicado al Circuit"),
    ]

    circuit = models.ForeignKey(
        Circuit,
        on_delete=models.CASCADE,
        related_name="narrative_drafts",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    places_signature = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Hash de paradas en el momento de generar (para auditar staleness).",
    )
    proposed_data = models.JSONField(
        default=dict,
        help_text=(
            "Estructura: {'circuit_long_description': '...', "
            "'day_summaries': {'1': '...', '2': '...'}}"
        ),
    )
    llm_model = models.CharField(max_length=80, blank=True, default="")
    llm_input_tokens = models.PositiveIntegerField(default=0)
    llm_output_tokens = models.PositiveIntegerField(default=0)
    llm_latency_ms = models.PositiveIntegerField(default=0)
    review_notes = models.TextField(blank=True)
    reviewed_by = models.CharField(max_length=80, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Borrador de narrativa"
        verbose_name_plural = "Borradores de narrativa"

    def __str__(self):
        return f"{self.circuit} · {self.get_status_display()} · {self.created_at:%Y-%m-%d}"


class CircuitCompositionDraft(models.Model):
    """Borrador de circuito completo armado por IA a partir de una idea libre.

    A diferencia de CircuitNarrativeDraft (que solo redacta narrativa para un
    Circuit ya armado), este draft compone el circuito desde cero:
    selecciona paradas del catálogo de Places publicados, las distribuye en
    días, propone metadata (nombre, slug, flags) y opcionalmente la narrativa.

    Flujo:
        1. Usuario describe la idea en el quick-create form.
        2. Servicio circuit_composer_service llama al LLM con catálogo + idea.
        3. Se crea este draft con proposed_data (sin tocar Circuit todavía).
        4. Usuario revisa el draft. Si aprueba: apply_composition crea Circuit +
           CircuitDay + CircuitPlace y marca el draft como APPLIED.

    Estructura de proposed_data:
        {
          "name": "Romántico de un día con tinas",
          "slug": "romantico-un-dia-tinas",
          "short_description": "...",
          "long_description": "...",
          "primary_interest": "RELAX_ROMANTIC",
          "recommended_profile": "COUPLE",
          "duration_case_code": "FULL_DAY",
          "is_romantic": true,
          "is_family_friendly": false,
          "is_adventure": false,
          "is_rain_friendly": true,
          "is_premium": false,
          "days": [
             {
                "day_number": 1,
                "title": "Mañana",
                "block_type": "HALF_DAY",
                "summary": "...",
                "stops": [
                    {"place_id": 12, "visit_order": 1, "is_main_stop": false},
                    {"place_id": 7,  "visit_order": 2, "is_main_stop": true},
                ],
             },
             ...
          ],
          "gaps_detected": ["Faltaría un café entre Frutillar y Pto Varas"],
          "rationale": "Por qué la IA eligió estas paradas..."
        }
    """

    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_APPLIED = "applied"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Borrador (pendiente revisión)"),
        (STATUS_APPROVED, "Aprobado (listo para aplicar)"),
        (STATUS_REJECTED, "Rechazado"),
        (STATUS_APPLIED, "Aplicado (Circuit creado)"),
    ]

    # ─── Input del usuario ───
    user_idea = models.TextField(
        help_text="Descripción libre del circuito que el usuario pidió.",
    )
    duration_case = models.ForeignKey(
        DurationCase,
        on_delete=models.PROTECT,
        related_name="composition_drafts",
        null=True,
        blank=True,
        help_text="Duración pedida en el form. La IA debe respetarla.",
    )
    primary_interest = models.CharField(
        max_length=30,
        choices=InterestType.choices,
        blank=True,
        help_text="Interés primario pedido en el form.",
    )
    recommended_profile = models.CharField(
        max_length=20,
        choices=ProfileType.choices,
        blank=True,
    )
    anchor_place_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="IDs de Places que el usuario pidió incluir obligatoriamente.",
    )

    # ─── Estado del draft ───
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    proposed_data = models.JSONField(
        default=dict,
        help_text="Estructura propuesta por la IA. Ver docstring del modelo.",
    )

    # ─── Resultado al aplicar ───
    created_circuit = models.ForeignKey(
        Circuit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="composition_drafts",
        help_text="Circuit que este draft creó al aplicarse.",
    )

    # ─── Métricas LLM ───
    llm_model = models.CharField(max_length=80, blank=True, default="")
    llm_input_tokens = models.PositiveIntegerField(default=0)
    llm_output_tokens = models.PositiveIntegerField(default=0)
    llm_latency_ms = models.PositiveIntegerField(default=0)

    # ─── Auditoría ───
    review_notes = models.TextField(blank=True)
    reviewed_by = models.CharField(max_length=80, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Borrador de circuito (composición IA)"
        verbose_name_plural = "Borradores de circuito (composición IA)"

    def __str__(self):
        proposed_name = (self.proposed_data or {}).get("name") or "(sin nombre)"
        return f"{proposed_name} · {self.get_status_display()} · {self.created_at:%Y-%m-%d}"
