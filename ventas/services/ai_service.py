# -*- coding: utf-8 -*-
"""
Servicio de IA para generación de variaciones de contenido de email
Previene filtros de spam mediante variaciones inteligentes del contenido
"""

import os
import json
import requests
import logging
from typing import Dict, List, Optional, Tuple, Union
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AIContentVariationService:
    """Servicio para generar variaciones de contenido usando IA"""
    
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        self.provider = os.getenv('AI_VARIATION_PROVIDER', 'deepseek')
        # TEMPORALMENTE DESHABILITADO por timeouts
        self.enabled = False  # os.getenv('AI_VARIATION_ENABLED', 'true').lower() == 'true'
        self.base_url = "https://api.deepseek.com/v1"
        
        if not self.api_key and self.enabled:
            logger.warning("⚠️ DeepSeek API key no configurada. Variaciones de IA deshabilitadas.")
            self.enabled = False
    
    def generate_subject_variations(self, original_subject: str, count: int = 5) -> List[str]:
        """
        Genera variaciones del asunto del email manteniendo el mensaje principal
        
        Args:
            original_subject: Asunto original
            count: Número de variaciones a generar
            
        Returns:
            Lista de asuntos variados
        """
        if not self.enabled or not original_subject:
            return [original_subject] * count
        
        cache_key = f"ai_subject_variations_{hash(original_subject)}_{count}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        prompt = f"""
Genera {count} variaciones diferentes del siguiente asunto de email manteniendo el mensaje principal y el tono profesional.

Asunto original: "{original_subject}"

Instrucciones:
- Mantén el mensaje y propósito principal
- Varía las palabras y estructura sin cambiar el significado
- Mantén el tono amigable y profesional
- Conserva emojis si los hay
- Cada variación debe sonar natural y diferente
- NO cambies nombres de empresa, montos o fechas específicas

Responde SOLO con un array JSON de strings, ejemplo:
["Variación 1", "Variación 2", "Variación 3"]
"""
        
        try:
            variations = self._call_ai_api(prompt)
            if variations and len(variations) == count:
                cache.set(cache_key, variations, 3600)  # Cache por 1 hora
                return variations
            else:
                logger.warning(f"IA generó {len(variations) if variations else 0} variaciones, esperábamos {count}")
                return [original_subject] * count
                
        except Exception as e:
            logger.error(f"Error generando variaciones de asunto: {e}")
            return [original_subject] * count
    
    def generate_body_variations(self, original_body: str, client_name: str = "") -> str:
        """
        Genera una variación del cuerpo del email manteniendo el contenido principal
        
        Args:
            original_body: Cuerpo original del email
            client_name: Nombre del cliente para personalización
            
        Returns:
            Cuerpo del email variado
        """
        if not self.enabled or not original_body:
            return original_body
        
        # Cache basado en el hash del contenido
        cache_key = f"ai_body_variation_{hash(original_body + client_name)}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        prompt = f"""
Reescribe el siguiente contenido de email manteniendo exactamente el mismo mensaje y propósito, pero variando la estructura y palabras para evitar filtros de spam.

Contenido original:
{original_body}

Instrucciones:
- Mantén EXACTAMENTE el mismo mensaje y propósito
- Varía la estructura de frases y párrafos
- Usa sinónimos y expresiones alternativas
- Mantén el tono profesional y amigable
- Conserva TODOS los datos importantes (montos, fechas, nombres de empresa)
- Mantén la estructura HTML si existe
- Conserva los enlaces y botones
- NO cambies el significado ni el call-to-action
- Si hay placeholder {{nombre_cliente}}, mantenlo

Responde SOLO con el contenido variado, sin explicaciones adicionales.
"""
        
        try:
            variation = self._call_ai_api(prompt, return_string=True)
            if variation:
                cache.set(cache_key, variation, 1800)  # Cache por 30 minutos
                return variation
            else:
                logger.warning("IA no pudo generar variación del cuerpo")
                return original_body
                
        except Exception as e:
            logger.error(f"Error generando variación de cuerpo: {e}")
            return original_body
    
    def apply_anti_spam_techniques(self, content: str) -> str:
        """
        Aplica técnicas anti-spam al contenido
        
        Args:
            content: Contenido a procesar
            
        Returns:
            Contenido con técnicas anti-spam aplicadas
        """
        if not self.enabled or not content:
            return content
        
        prompt = f"""
Aplica técnicas anti-spam sutiles al siguiente contenido de email manteniendo legibilidad y profesionalismo:

Contenido:
{content}

Técnicas a aplicar:
- Insertar espacios ocasionales en palabras clave (ej: "g r a t i s" en lugar de "gratis")
- Usar caracteres Unicode similares ocasionalmente (ej: "ó" en lugar de "o")
- Variar la estructura de enlaces
- Agregar texto invisible usando spans con color de fondo
- Usar entidades HTML ocasionalmente

Instrucciones:
- Aplica técnicas MUY sutilmente, sin afectar la legibilidad
- Mantén el contenido profesional y confiable
- NO exageres las técnicas
- Conserva toda la información importante
- Mantén la estructura HTML

Responde SOLO con el contenido procesado.
"""
        
        try:
            processed_content = self._call_ai_api(prompt, return_string=True)
            return processed_content if processed_content else content
        except Exception as e:
            logger.error(f"Error aplicando técnicas anti-spam: {e}")
            return content
    
    def _call_ai_api(self, prompt: str, return_string: bool = False) -> Optional[Union[List[str], str]]:
        """
        Llama a la API de DeepSeek
        
        Args:
            prompt: Prompt para la IA
            return_string: Si True, retorna string; si False, retorna lista
            
        Returns:
            Respuesta de la IA procesada
        """
        if not self.api_key:
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un experto en marketing por email y redacción creativa. Generas variaciones de contenido que mantienen el mensaje original pero evitan filtros de spam."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=15  # Reducir timeout a 15 segundos
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                
                if return_string:
                    return content
                else:
                    # Intentar parsear como JSON
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        # Si no es JSON válido, extraer strings entre comillas
                        import re
                        matches = re.findall(r'"([^"]*)"', content)
                        return matches if matches else [content]
            else:
                logger.error(f"Error en API DeepSeek: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión con DeepSeek API: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado en _call_ai_api: {e}")
            return None
    
    def get_status(self) -> Dict:
        """Retorna el estado del servicio de IA"""
        return {
            'enabled': self.enabled,
            'provider': self.provider,
            'model': self.model,
            'api_key_configured': bool(self.api_key),
            'cache_stats': {
                'subject_variations_cached': len([k for k in cache._cache.keys() if 'ai_subject_variations' in str(k)]),
                'body_variations_cached': len([k for k in cache._cache.keys() if 'ai_body_variation' in str(k)])
            } if hasattr(cache, '_cache') else {}
        }


# Instancia global del servicio
ai_service = AIContentVariationService()


def generate_personalized_content(subject_template: str, body_template: str, client_name: str, 
                                client_data: Dict = None) -> Tuple[str, str]:
    """
    Genera contenido personalizado y variado para un cliente específico
    
    Args:
        subject_template: Template del asunto
        body_template: Template del cuerpo
        client_name: Nombre del cliente
        client_data: Datos adicionales del cliente
        
    Returns:
        Tupla (asunto_personalizado, cuerpo_personalizado)
    """
    client_data = client_data or {}
    
    # Reemplazar placeholders básicos
    personalized_subject = subject_template.replace('{nombre_cliente}', client_name)
    personalized_body = body_template.replace('{nombre_cliente}', client_name)
    
    # Aplicar variaciones de IA si está habilitado
    if ai_service.enabled:
        try:
            # Generar una variación del asunto con timeout
            subject_variations = ai_service.generate_subject_variations(personalized_subject, 1)
            if subject_variations:
                personalized_subject = subject_variations[0]
            
            # Generar variación del cuerpo con timeout
            ai_body = ai_service.generate_body_variations(personalized_body, client_name)
            if ai_body:  # Solo usar si la IA devolvió algo
                personalized_body = ai_body
            
            # Aplicar técnicas anti-spam si está configurado
            if os.getenv('AI_ANTI_SPAM_ENABLED', 'true').lower() == 'true':
                anti_spam_body = ai_service.apply_anti_spam_techniques(personalized_body)
                if anti_spam_body:  # Solo usar si la IA devolvió algo
                    personalized_body = anti_spam_body
                    
        except Exception as e:
            # Si falla la IA, continuar sin personalización avanzada
            logger.warning(f"IA no disponible, usando contenido básico: {e}")
            pass
    
    return personalized_subject, personalized_body


def test_ai_service() -> Dict:
    """Función de prueba para verificar que el servicio de IA funciona"""
    test_subject = "🎁 ¡Tu giftcard de $15,000 te espera!"
    test_body = "Hola {nombre_cliente}, tenemos una sorpresa especial para ti..."
    
    try:
        variations = ai_service.generate_subject_variations(test_subject, 3)
        varied_body = ai_service.generate_body_variations(test_body, "Juan")
        status = ai_service.get_status()
        
        return {
            'success': True,
            'subject_variations': variations,
            'body_variation': varied_body,
            'service_status': status
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'service_status': ai_service.get_status()
        }