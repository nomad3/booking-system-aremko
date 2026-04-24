"""Constantes conversacionales de DPV. Estados inferidos, no persistidos."""

# Estados conversacionales — inferidos desde LeadConversation, no viven en BD
STATE_START = "START"
STATE_ASK_DURATION = "ASK_DURATION"
STATE_ASK_INTEREST = "ASK_INTEREST"
STATE_ASK_PROFILE = "ASK_PROFILE"
STATE_RECOMMEND_CIRCUIT = "RECOMMEND_CIRCUIT"
STATE_FOLLOW_UP = "FOLLOW_UP"
STATE_AREMKO_SUGGESTED = "AREMKO_SUGGESTED"
STATE_REFERRED_TO_AREMKO = "REFERRED_TO_AREMKO"

# Niveles de confianza para la recomendación
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

# Umbrales
MAX_PARSE_RETRIES = 2  # tras 2 intentos fallidos de parseo, derivar a WhatsApp Aremko

# Tipos de reply en la estructura de respuesta JSON
REPLY_TYPE_QUESTION = "question"
REPLY_TYPE_RECOMMENDATION = "recommendation"
REPLY_TYPE_INFO = "info"
REPLY_TYPE_REFERRAL = "referral"
