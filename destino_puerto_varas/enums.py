from django.db import models


class DurationType(models.TextChoices):
    HALF_DAY = "HALF_DAY", "Medio día"
    FULL_DAY = "FULL_DAY", "Día completo"
    TWO_DAYS_ONE_NIGHT = "TWO_DAYS_ONE_NIGHT", "2 días / 1 noche"
    THREE_DAYS_TWO_NIGHTS = "THREE_DAYS_TWO_NIGHTS", "3 días / 2 noches"
    FOUR_DAYS_THREE_NIGHTS = "FOUR_DAYS_THREE_NIGHTS", "4 días / 3 noches"
    FIVE_DAYS_FOUR_NIGHTS = "FIVE_DAYS_FOUR_NIGHTS", "5 días / 4 noches"
    SIX_DAYS_FIVE_NIGHTS = "SIX_DAYS_FIVE_NIGHTS", "6 días / 5 noches"
    SEVEN_DAYS_SIX_NIGHTS = "SEVEN_DAYS_SIX_NIGHTS", "7 días / 6 noches"


class InterestType(models.TextChoices):
    NATURE = "NATURE", "Naturaleza"
    GASTRONOMY = "GASTRONOMY", "Gastronomía"
    ADVENTURE = "ADVENTURE", "Aventura"
    RELAX_ROMANTIC = "RELAX_ROMANTIC", "Relax / Romántico"
    MIXED = "MIXED", "Mixto"


class ProfileType(models.TextChoices):
    COUPLE = "COUPLE", "Pareja"
    FAMILY = "FAMILY", "Familia"
    FRIENDS = "FRIENDS", "Amigos"
    SOLO = "SOLO", "Solo/a"


class BlockType(models.TextChoices):
    ARRIVAL = "ARRIVAL", "Llegada"
    HALF_DAY = "HALF_DAY", "Medio día"
    FULL_DAY = "FULL_DAY", "Día completo"
    DEPARTURE = "DEPARTURE", "Salida"
    AREMKO_MOMENT = "AREMKO_MOMENT", "Momento Aremko"


class PlaceType(models.TextChoices):
    # Naturales / atracciones
    ATTRACTION = "ATTRACTION", "Atracción"
    VIEWPOINT = "VIEWPOINT", "Mirador"
    PARK = "PARK", "Parque"
    # Comerciales
    RESTAURANT = "RESTAURANT", "Restaurante"
    CAFE = "CAFE", "Café"
    SHOP = "SHOP", "Tienda"
    LODGING = "LODGING", "Alojamiento"
    SPA = "SPA", "Spa / Bienestar"
    TOUR_OPERATOR = "TOUR_OPERATOR", "Operador turístico"
    BUSINESS = "BUSINESS", "Empresa / Servicio"
    ACTIVITY = "ACTIVITY", "Actividad"
    # Culturales / institucionales
    MUSEUM = "MUSEUM", "Museo"
    THEATER = "THEATER", "Teatro / Sala"
    CHURCH = "CHURCH", "Iglesia"
    CULTURAL_CENTER = "CULTURAL_CENTER", "Centro cultural"
    OTHER = "OTHER", "Otro"


class PartnershipLevel(models.TextChoices):
    OWNED = "OWNED", "Propio (Aremko)"
    PARTNER = "PARTNER", "Partner / Aliado"
    LISTED = "LISTED", "Listado (sin acuerdo comercial)"
    DIRECTORY = "DIRECTORY", "Directorio (referencial)"


class ConversationStatus(models.TextChoices):
    OPEN = "OPEN", "Abierta"
    CLOSED = "CLOSED", "Cerrada"
    WAITING_USER = "WAITING_USER", "Esperando usuario"
    QUALIFIED = "QUALIFIED", "Calificada"
    REFERRED_TO_AREMKO = "REFERRED_TO_AREMKO", "Derivada a Aremko"


class ChannelType(models.TextChoices):
    WHATSAPP = "WHATSAPP", "WhatsApp"
    INSTAGRAM = "INSTAGRAM", "Instagram"
    WEB = "WEB", "Web"
    TELEGRAM = "TELEGRAM", "Telegram"


class MessageSenderType(models.TextChoices):
    USER = "USER", "Usuario"
    ASSISTANT = "ASSISTANT", "Asistente"
    AGENT = "AGENT", "Agente humano"
    SYSTEM = "SYSTEM", "Sistema"
