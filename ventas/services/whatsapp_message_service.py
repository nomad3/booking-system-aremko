"""
WhatsAppMessageService - Generación de mensajes personalizados de WhatsApp con IA
Segmenta clientes y genera mensajes contextualizados usando DeepSeek API
"""
from django.conf import settings
from ventas.services.crm_service import CRMService
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)

# Importar OpenAI client (compatible con DeepSeek)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI SDK no está instalado. Instalar con: pip install openai")


class WhatsAppMessageService:
    """Servicio para generación de mensajes personalizados de WhatsApp con IA"""

    # Perfiles de clientes
    CLIENTE_NUEVO = "CLIENTE_NUEVO"
    PRIMERA_RESERVA = "PRIMERA_RESERVA"
    RECURRENTE_ACTIVO = "RECURRENTE_ACTIVO"
    REACTIVADO = "REACTIVADO"
    VIP = "VIP"
    EN_RIESGO = "EN_RIESGO"

    @classmethod
    def determinar_perfil_cliente(cls, datos_360: dict) -> str:
        """
        Determina el perfil del cliente basado en sus métricas del sistema 360°

        Args:
            datos_360: Dict con datos del perfil 360° del cliente

        Returns:
            String con el perfil identificado
        """
        metricas = datos_360['metricas']
        segmentacion = datos_360['segmentacion']

        total_servicios = metricas['total_servicios']
        servicios_historicos = metricas['servicios_historicos']
        servicios_actuales = metricas['servicios_actuales']
        gasto_total = metricas['gasto_total']
        dias_como_cliente = metricas['dias_como_cliente']
        segmento_rfm = segmentacion['rfm_segment']

        # Calcular días desde última visita
        ultimo_servicio = metricas.get('ultimo_servicio')
        if ultimo_servicio:
            dias_desde_ultima = (datetime.now().date() - ultimo_servicio).days
        else:
            dias_desde_ultima = 9999

        # 1. Cliente Completamente Nuevo (no existe en BD)
        if total_servicios == 0:
            return cls.CLIENTE_NUEVO

        # 2. Cliente Nuevo con Primera Reserva
        if servicios_actuales <= 3 and servicios_historicos == 0 and dias_como_cliente < 30:
            return cls.PRIMERA_RESERVA

        # 3. Cliente VIP / Champions
        if segmento_rfm in ['Champions', 'VIP', 'Loyal Customers'] or gasto_total > 500000:
            return cls.VIP

        # 4. Cliente En Riesgo (fue activo pero hace tiempo no viene)
        if segmento_rfm in ['At Risk', 'About to Sleep', 'Hibernating'] and dias_desde_ultima > 180:
            return cls.EN_RIESGO

        # 5. Cliente Antiguo Reactivado (tiene históricos, regresó después de mucho tiempo)
        if servicios_historicos > 0 and servicios_actuales <= 3:
            # Verificar si hubo un gap largo entre históricos y actuales
            primer_servicio = metricas.get('primer_servicio')
            if primer_servicio:
                años_desde_primer_servicio = (datetime.now().date() - primer_servicio).days / 365
                if años_desde_primer_servicio > 2:  # Más de 2 años desde primer servicio
                    return cls.REACTIVADO

        # 6. Cliente Recurrente Activo (default)
        return cls.RECURRENTE_ACTIVO

    @classmethod
    def _generar_prompt_ia(cls, perfil_cliente: str, datos_360: dict) -> str:
        """
        Genera el prompt para OpenAI GPT-4o según el perfil del cliente

        Args:
            perfil_cliente: Perfil identificado del cliente
            datos_360: Dict con datos del perfil 360°

        Returns:
            String con el prompt completo para la IA
        """
        cliente = datos_360['cliente']
        metricas = datos_360['metricas']
        segmentacion = datos_360['segmentacion']
        categorias = datos_360.get('categorias_favoritas', [])

        # Formatear categorías favoritas
        categorias_str = ', '.join([c['service_type'] for c in categorias[:3]]) if categorias else 'N/A'

        # Formatear último servicio
        ultimo_servicio = metricas.get('ultimo_servicio')
        ultimo_servicio_str = ultimo_servicio.strftime('%d/%m/%Y') if ultimo_servicio else 'N/A'

        # Calcular días desde última visita
        if ultimo_servicio:
            dias_desde_ultima = (datetime.now().date() - ultimo_servicio).days
            meses_desde_ultima = dias_desde_ultima // 30
        else:
            dias_desde_ultima = 0
            meses_desde_ultima = 0

        base_context = f"""Eres un asistente de comunicación para Aremko Spa, un spa de lujo en Chile especializado en tinas de hidromasaje, cabañas y masajes terapéuticos.

Tu tarea es generar un mensaje de WhatsApp personalizado, cálido, profesional y natural para iniciar una conversación con el cliente.

IMPORTANTE:
- Usa un tono chileno amigable y cercano
- Sé breve y directo (máximo 6 líneas)
- Usa emojis moderadamente (2-3 máximo)
- Termina con una pregunta abierta que invite a la conversación
- NO uses lenguaje corporativo o formal en exceso
- Sé genuino y humano

INFORMACIÓN DEL CLIENTE:
- Nombre: {cliente['nombre']}
- Total servicios: {metricas['total_servicios']}
- Servicios históricos: {metricas['servicios_historicos']}
- Servicios actuales: {metricas['servicios_actuales']}
- Gasto total: ${metricas['gasto_total']:,.0f} CLP
- Días como cliente: {metricas['dias_como_cliente']}
- Días desde última visita: {dias_desde_ultima}
- Meses desde última visita: {meses_desde_ultima}
- Última visita: {ultimo_servicio_str}
- Segmento RFM: {segmentacion['rfm_segment']}
- Categorías favoritas: {categorias_str}

PERFIL IDENTIFICADO: {perfil_cliente}
"""

        # Instrucciones específicas por perfil
        instrucciones_por_perfil = {
            cls.CLIENTE_NUEVO: """
OBJETIVO: Dar bienvenida cálida a un cliente que NUNCA ha visitado el spa.
TONO: Acogedor, informativo, amigable.
LONGITUD: 3-4 líneas máximo.
ESTRUCTURA SUGERIDA:
1. Saludo inicial con emoji
2. Presentación breve de Aremko (tinas, cabañas, masajes)
3. Pregunta abierta: "¿En qué podemos ayudarte?"

EJEMPLO DE REFERENCIA (NO COPIAR EXACTAMENTE):
"¡Hola! 👋 Bienvenido/a a Aremko Spa. Somos especialistas en tinas de hidromasaje, cabañas y masajes. ¿En qué podemos ayudarte hoy?"
""",

            cls.PRIMERA_RESERVA: """
OBJETIVO: Reforzar emoción de primera visita.
TONO: Entusiasta, servicial, anticipación positiva.
LONGITUD: 4-5 líneas.
ESTRUCTURA SUGERIDA:
1. Saludo personalizado con nombre
2. Mencionar que es su primera visita (si aplica)
3. Expresar emoción por recibirlo
4. Tip útil o pregunta sobre necesidades

EJEMPLO DE REFERENCIA (NO COPIAR EXACTAMENTE):
"¡Hola María! 😊 Veo que tienes tu primera visita agendada. ¡Estamos emocionados de recibirte! Llega 10 minutos antes para aprovechar al máximo. ¿Tienes alguna pregunta?"
""",

            cls.RECURRENTE_ACTIVO: """
OBJETIVO: Reconocer lealtad y personalizar según preferencias.
TONO: Cercano, apreciativo, como hablar con un conocido.
LONGITUD: 4-5 líneas.
ESTRUCTURA SUGERIDA:
1. Saludo personalizado
2. Mencionar cantidad de visitas o categoría favorita
3. Sugerencia personalizada o pregunta relevante

EJEMPLO DE REFERENCIA (NO COPIAR EXACTAMENTE):
"¡Hola Carlos! 😊 Qué gusto saber de ti. Veo que has venido {X} veces y te encantan las {categoría}. ¿Vienes por tu favorito o quieres probar algo nuevo?"
""",

            cls.REACTIVADO: """
OBJETIVO: Bienvenida de regreso emotiva, reconocer historia con el spa.
TONO: Nostálgico, cálido, apreciativo, "te extrañamos".
LONGITUD: 5-6 líneas.
ESTRUCTURA SUGERIDA:
1. Saludo emocionado "¡Qué alegría verte de vuelta!"
2. Mencionar años como cliente o última visita
3. Breve mención de novedades
4. Pregunta sobre preferencias

EJEMPLO DE REFERENCIA (NO COPIAR EXACTAMENTE):
"¡Ana! 🤗 Qué alegría verte de vuelta después de {X} años. Tu última visita disfrutaste de {servicio}. Hemos renovado las cabañas y agregado nuevas tinas. ¿Te gustaría conocer las novedades?"
""",

            cls.VIP: """
OBJETIVO: Tratamiento exclusivo, reconocimiento de estatus especial.
TONO: Elegante, premium, personalizado, pero no excesivamente formal.
LONGITUD: 5-6 líneas.
ESTRUCTURA SUGERIDA:
1. Saludo personalizado con reconocimiento especial
2. Mencionar métricas impresionantes (visitas, años como cliente)
3. Ofrecer atención prioritaria o experiencia personalizada
4. Pregunta VIP

EJEMPLO DE REFERENCIA (NO COPIAR EXACTAMENTE):
"¡Roberto! ✨ Es un placer saber de ti. Como uno de nuestros clientes más especiales ({X} visitas, cliente desde {año}), queremos asegurarnos de brindarte la mejor experiencia. ¿Necesitas una reserva prioritaria o algo especial?"
""",

            cls.EN_RIESGO: """
OBJETIVO: Reactivación emotiva, incentivo para regresar SIN ser insistente.
TONO: "Te extrañamos", cálido, genuino, con incentivo sutil.
LONGITUD: 5-6 líneas.
ESTRUCTURA SUGERIDA:
1. Saludo + "Te extrañamos"
2. Mencionar tiempo sin visitarnos
3. Recordar último servicio que disfrutó
4. Mención de novedad atractiva
5. Invitación suave a regresar

EJEMPLO DE REFERENCIA (NO COPIAR EXACTAMENTE):
"¡Hola Laura! 😊 Te extrañamos en Aremko. Veo que tu última visita fue hace {X} meses, cuando disfrutaste de {servicio}. Hemos agregado nuevas experiencias que creo te encantarían. ¿Te gustaría volver a visitarnos?"
"""
        }

        return base_context + "\n" + instrucciones_por_perfil.get(perfil_cliente, "")

    @classmethod
    def generar_mensaje_whatsapp(cls, cliente_id: int) -> dict:
        """
        Genera un mensaje personalizado de WhatsApp usando IA

        Args:
            cliente_id: ID del cliente

        Returns:
            Dict con:
            {
                'success': bool,
                'mensaje': str,
                'perfil': str,
                'telefono': str,
                'whatsapp_url': str,
                'error': str (si hay error)
            }
        """
        try:
            # Obtener datos 360° del cliente
            datos_360 = CRMService.get_customer_360(cliente_id)

            # Determinar perfil del cliente
            perfil = cls.determinar_perfil_cliente(datos_360)

            # Generar prompt para IA
            prompt = cls._generar_prompt_ia(perfil, datos_360)

            # Llamar a DeepSeek API
            if not OPENAI_AVAILABLE:
                return {
                    'success': False,
                    'error': 'OpenAI SDK no está instalado. Ejecuta: pip install openai'
                }

            # Usar DeepSeek API key (ya configurada en variables de entorno)
            deepseek_api_key = os.getenv('DEEPSEEK_API_KEY') or getattr(settings, 'DEEPSEEK_API_KEY', None)
            if not deepseek_api_key:
                return {
                    'success': False,
                    'error': 'DEEPSEEK_API_KEY no está configurada en las variables de entorno'
                }

            # Inicializar cliente DeepSeek (usando OpenAI SDK compatible)
            client = OpenAI(
                api_key=deepseek_api_key,
                base_url="https://api.deepseek.com"  # Endpoint de DeepSeek
            )

            # Llamar a DeepSeek Chat (modelo deepseek-chat)
            response = client.chat.completions.create(
                model="deepseek-chat",  # Modelo de DeepSeek
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un experto en comunicación personalizada para spas de lujo. Generas mensajes cálidos, profesionales y naturales en español de Chile."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,  # Balance entre creatividad y coherencia
                max_tokens=300,
                top_p=1,
                frequency_penalty=0.3,
                presence_penalty=0.3,
                stream=False
            )

            mensaje_generado = response.choices[0].message.content.strip()

            # Limpiar mensaje (remover comillas si las tiene)
            mensaje_generado = mensaje_generado.strip('"').strip("'")

            # Obtener teléfono del cliente
            telefono = datos_360['cliente']['telefono']
            # Limpiar teléfono (remover espacios, guiones, paréntesis)
            telefono_limpio = ''.join(filter(str.isdigit, telefono)) if telefono else ''

            # Generar URL de WhatsApp
            import urllib.parse
            whatsapp_url = f"https://wa.me/56{telefono_limpio}?text={urllib.parse.quote(mensaje_generado)}"

            logger.info(f"Mensaje WhatsApp generado para cliente {cliente_id} - Perfil: {perfil}")

            return {
                'success': True,
                'mensaje': mensaje_generado,
                'perfil': perfil,
                'perfil_nombre': cls._obtener_nombre_perfil(perfil),
                'telefono': telefono,
                'telefono_limpio': telefono_limpio,
                'whatsapp_url': whatsapp_url,
                'nombre_cliente': datos_360['cliente']['nombre']
            }

        except Exception as e:
            logger.error(f"Error generando mensaje WhatsApp para cliente {cliente_id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    @classmethod
    def _obtener_nombre_perfil(cls, perfil: str) -> str:
        """Obtiene el nombre legible del perfil"""
        nombres = {
            cls.CLIENTE_NUEVO: "Cliente Completamente Nuevo 🆕",
            cls.PRIMERA_RESERVA: "Cliente con Primera Reserva 🌱",
            cls.RECURRENTE_ACTIVO: "Cliente Recurrente Activo ⭐",
            cls.REACTIVADO: "Cliente Antiguo Reactivado 🔄",
            cls.VIP: "Cliente VIP / Champions 👑",
            cls.EN_RIESGO: "Cliente En Riesgo ⚠️"
        }
        return nombres.get(perfil, perfil)

    @classmethod
    def generar_mensaje_cliente_nuevo_sin_bd(cls, telefono: str, nombre: str = None) -> dict:
        """
        Genera mensaje para cliente que NO existe en base de datos

        Args:
            telefono: Número de teléfono del cliente
            nombre: Nombre del cliente (opcional)

        Returns:
            Dict con mensaje generado
        """
        try:
            if not OPENAI_AVAILABLE:
                # Mensaje fallback si no hay SDK
                mensaje = f"¡Hola{' ' + nombre if nombre else ''}! 👋\n\n¡Bienvenido/a a Aremko Spa! 🌿\n\nSomos especialistas en tinas de hidromasaje, cabañas y masajes terapéuticos.\n\n¿En qué podemos ayudarte hoy?"
            else:
                # Usar DeepSeek API para generar mensaje más natural
                deepseek_api_key = os.getenv('DEEPSEEK_API_KEY') or getattr(settings, 'DEEPSEEK_API_KEY', None)
                if not deepseek_api_key:
                    mensaje = f"¡Hola{' ' + nombre if nombre else ''}! 👋 Bienvenido/a a Aremko Spa. ¿En qué podemos ayudarte?"
                else:
                    client = OpenAI(
                        api_key=deepseek_api_key,
                        base_url="https://api.deepseek.com"
                    )
                    prompt = f"""Genera un mensaje de bienvenida cálido y breve (3-4 líneas) para WhatsApp de un cliente completamente nuevo que nunca ha visitado Aremko Spa (spa de lujo con tinas, cabañas y masajes en Chile).

Nombre del cliente: {nombre if nombre else 'Cliente'}

El mensaje debe:
- Ser cálido y acogedor
- Presentar brevemente Aremko
- Terminar con pregunta abierta
- Usar 1-2 emojis
- Tono chileno amigable"""

                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[
                            {"role": "system", "content": "Eres un experto en comunicación para spas de lujo en Chile."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=200,
                        stream=False
                    )
                    mensaje = response.choices[0].message.content.strip().strip('"').strip("'")

            # Limpiar teléfono
            telefono_limpio = ''.join(filter(str.isdigit, telefono))

            # Generar URL WhatsApp
            import urllib.parse
            whatsapp_url = f"https://wa.me/56{telefono_limpio}?text={urllib.parse.quote(mensaje)}"

            return {
                'success': True,
                'mensaje': mensaje,
                'perfil': cls.CLIENTE_NUEVO,
                'perfil_nombre': cls._obtener_nombre_perfil(cls.CLIENTE_NUEVO),
                'telefono': telefono,
                'telefono_limpio': telefono_limpio,
                'whatsapp_url': whatsapp_url,
                'nombre_cliente': nombre or 'Cliente'
            }

        except Exception as e:
            logger.error(f"Error generando mensaje para cliente nuevo sin BD: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
