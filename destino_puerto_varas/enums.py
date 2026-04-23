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
    ATTRACTION = "ATTRACTION", "Atracción"
    RESTAURANT = "RESTAURANT", "Restaurante"
    ACTIVITY = "ACTIVITY", "Actividad"
    VIEWPOINT = "VIEWPOINT", "Mirador"
    CAFE = "CAFE", "Café"
    SHOP = "SHOP", "Tienda"
    PARK = "PARK", "Parque"
    MUSEUM = "MUSEUM", "Museo"
    OTHER = "OTHER", "Otro"


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


class MessageSenderType(models.TextChoices):
    USER = "USER", "Usuario"
    ASSISTANT = "ASSISTANT", "Asistente"
    AGENT = "AGENT", "Agente humano"
    SYSTEM = "SYSTEM", "Sistema"
