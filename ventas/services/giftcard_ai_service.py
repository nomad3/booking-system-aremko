# -*- coding: utf-8 -*-
"""
Servicio de IA para generación de mensajes personalizados en GiftCards

Usa DeepSeek (via OpenAI API) para generar mensajes emocionales, elegantes y memorables
basados en el tipo de mensaje, destinatario y contexto proporcionado.
"""

from openai import OpenAI
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class GiftCardAIService:
    """
    Servicio para generar mensajes personalizados usando IA
    """

    # Mapeo de tipos de mensaje a tonos descriptivos para la IA
    TONOS_MENSAJE = {
        'romantico': 'romántico, íntimo y apasionado',
        'cumpleanos': 'celebrativo, alegre y festivo',
        'aniversario': 'nostálgico, especial y conmemorativo',
        'celebracion': 'festivo, emocionante y positivo',
        'relajacion': 'tranquilo, sereno y revitalizante',
        'parejas': 'romántico, cómplice y especial para dos',
        'agradecimiento': 'agradecido, cálido y sincero',
        'amistad': 'fraternal, cariñoso y genuino',
    }

    @staticmethod
    def generar_mensajes(tipo_mensaje, nombre, relacion, detalle='', cantidad=3):
        """
        Genera mensajes personalizados usando DeepSeek AI

        Args:
            tipo_mensaje (str): Tipo de mensaje ('romantico', 'cumpleanos', etc.)
            nombre (str): Nombre o apodo del destinatario
            relacion (str): Relación con el comprador ('pareja', 'amigo', 'madre', etc.)
            detalle (str, optional): Detalle especial para enriquecer el mensaje
            cantidad (int, optional): Cantidad de mensajes a generar. Default: 3

        Returns:
            list: Lista de mensajes generados por IA

        Raises:
            ValueError: Si tipo_mensaje no es válido
            Exception: Si hay error en la llamada a la API
        """

        # Validar tipo de mensaje
        if tipo_mensaje not in GiftCardAIService.TONOS_MENSAJE:
            raise ValueError(f"Tipo de mensaje '{tipo_mensaje}' no válido. Opciones: {list(GiftCardAIService.TONOS_MENSAJE.keys())}")

        # Obtener tono descriptivo
        tono = GiftCardAIService.TONOS_MENSAJE[tipo_mensaje]

        # Construir prompt para DeepSeek
        prompt = f"""Genera {cantidad} frases breves (entre 25 y 50 palabras), emocionales, elegantes y memorables para una giftcard del Spa "Aremko Aguas Calientes & Spa", localizado en Puerto Varas junto al río Pescado, rodeado de bosque nativo, con tinas calientes y experiencias románticas.

Tono seleccionado: {tono}.

Datos del destinatario:
- Nombre/apodo: {nombre}
- Relación con el comprador: {relacion}
- Detalle especial: {detalle if detalle else 'No especificado'}

Objetivo:
Crear mensajes únicos, cálidos, inspiradores y personales, dignos de un regalo especial. Deben sonar humanos, íntimos y auténticos. Evita clichés. Cada mensaje debe mencionar el nombre del destinatario de forma natural.

Contexto del spa:
- Ubicado en Puerto Varas, junto al río Pescado
- Rodeado de bosque nativo y naturaleza
- Experiencias de tinas calientes, masajes y relax
- Ambiente romántico y tranquilo

IMPORTANTE: Retorna SOLO las {cantidad} frases, una por línea, sin numeración, viñetas ni comentarios adicionales. Cada frase debe ser completa y autosuficiente."""

        try:
            # Verificar que existe la API key
            api_key = getattr(settings, 'DEEPSEEK_API_KEY', None)
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY no configurada en settings.py")

            # Inicializar cliente de OpenAI apuntando a DeepSeek
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )

            # Llamar a la API de DeepSeek
            logger.info(f"Generando {cantidad} mensajes de tipo '{tipo_mensaje}' para {nombre} usando DeepSeek")

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Eres un experto en redacción creativa y emocional para regalos especiales. Generas mensajes únicos y memorables."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1024,
                temperature=0.8,  # Un poco de creatividad
                stream=False
            )

            # Parsear respuesta
            respuesta_texto = response.choices[0].message.content.strip()
            mensajes = [m.strip() for m in respuesta_texto.split('\n') if m.strip()]

            # Limpiar mensajes (remover numeración si existe)
            mensajes_limpios = []
            for mensaje in mensajes:
                # Remover numeración al inicio (ej: "1. ", "1) ", "- ")
                mensaje_limpio = mensaje
                for prefijo in ['1. ', '2. ', '3. ', '1) ', '2) ', '3) ', '- ', '• ']:
                    if mensaje_limpio.startswith(prefijo):
                        mensaje_limpio = mensaje_limpio[len(prefijo):].strip()

                if mensaje_limpio:
                    mensajes_limpios.append(mensaje_limpio)

            # Limitar a la cantidad solicitada
            mensajes_finales = mensajes_limpios[:cantidad]

            # Validar que se generaron suficientes mensajes
            if len(mensajes_finales) < cantidad:
                logger.warning(f"Solo se generaron {len(mensajes_finales)} mensajes de {cantidad} solicitados")

            logger.info(f"Mensajes generados exitosamente: {len(mensajes_finales)}")
            return mensajes_finales

        except Exception as e:
            logger.error(f"Error generando mensajes con IA: {str(e)}", exc_info=True)
            raise Exception(f"Error al generar mensajes con IA: {str(e)}")

    @staticmethod
    def regenerar_mensaje_unico(tipo_mensaje, nombre, relacion, detalle='', mensajes_previos=None):
        """
        Genera UN nuevo mensaje diferente a los mensajes previos

        Args:
            tipo_mensaje (str): Tipo de mensaje
            nombre (str): Nombre del destinatario
            relacion (str): Relación con el comprador
            detalle (str, optional): Detalle especial
            mensajes_previos (list, optional): Lista de mensajes ya generados para evitar repetición

        Returns:
            str: Un nuevo mensaje diferente
        """

        # Si hay mensajes previos, agregamos contexto al prompt
        contexto_previos = ""
        if mensajes_previos and len(mensajes_previos) > 0:
            contexto_previos = f"\n\nMensajes ya generados (no repetir ideas similares):\n" + "\n".join([f"- {m}" for m in mensajes_previos])

        # Obtener tono
        tono = GiftCardAIService.TONOS_MENSAJE.get(tipo_mensaje, 'cálido y personal')

        prompt = f"""Genera UNA frase breve (entre 25 y 50 palabras), emocional, elegante y memorable para una giftcard del Spa "Aremko Aguas Calientes & Spa", localizado en Puerto Varas junto al río Pescado, rodeado de bosque nativo.

Tono: {tono}.

Destinatario:
- Nombre/apodo: {nombre}
- Relación: {relacion}
- Detalle especial: {detalle if detalle else 'No especificado'}

{contexto_previos}

IMPORTANTE:
- Retorna SOLO la frase, sin numeración ni comentarios
- Debe ser única y diferente a los mensajes previos
- Menciona el nombre del destinatario naturalmente
- Evita clichés y frases genéricas"""

        try:
            api_key = getattr(settings, 'DEEPSEEK_API_KEY', None)
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY no configurada")

            client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Eres un experto en redacción creativa y emocional para regalos especiales."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=512,
                temperature=0.9,  # Más creatividad para regenerar
                stream=False
            )

            nuevo_mensaje = response.choices[0].message.content.strip()

            # Limpiar prefijos de numeración
            for prefijo in ['1. ', '1) ', '- ', '• ']:
                if nuevo_mensaje.startswith(prefijo):
                    nuevo_mensaje = nuevo_mensaje[len(prefijo):].strip()

            logger.info("Mensaje regenerado exitosamente")
            return nuevo_mensaje

        except Exception as e:
            logger.error(f"Error regenerando mensaje: {str(e)}", exc_info=True)
            raise Exception(f"Error al regenerar mensaje: {str(e)}")
