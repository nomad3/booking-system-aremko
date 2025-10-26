"""
Servicio de Generación de Propuestas Personalizadas con IA
Usa DeepSeek API para análisis inteligente de clientes
"""
import os
import json
import logging
from typing import Dict, Any
import httpx
from django.conf import settings
from ventas.services.crm_service import CRMService

logger = logging.getLogger(__name__)


class AIProposalService:
    """
    Servicio para generar propuestas personalizadas usando DeepSeek
    """

    # Configuración de DeepSeek
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL = "deepseek-chat"

    def __init__(self):
        # Obtener API key de variables de entorno
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY no configurada. Propuestas usarán fallback.")

    def generar_propuesta(self, customer_id: int, estilo: str = "formal") -> Dict[str, Any]:
        """
        Genera propuesta personalizada para un cliente usando IA

        Args:
            customer_id: ID del cliente
            estilo: "formal" (corporativo) o "calido" (emocional/personal)

        Returns:
            Dict con propuesta estructurada
        """
        try:
            # Obtener perfil 360 del cliente
            perfil = CRMService.get_customer_360(customer_id)

            # Si no hay API key, usar propuesta básica
            if not self.api_key:
                return self._generar_propuesta_basica(perfil, estilo)

            # Generar propuesta con IA
            return self._generar_propuesta_con_ia(perfil, estilo)

        except Exception as e:
            logger.error(f"Error generando propuesta para cliente {customer_id}: {e}")
            # Fallback a propuesta básica en caso de error
            try:
                perfil = CRMService.get_customer_360(customer_id)
                return self._generar_propuesta_basica(perfil, estilo)
            except:
                raise Exception(f"Error generando propuesta: {str(e)}")

    def _generar_propuesta_con_ia(self, perfil: Dict[str, Any], estilo: str = "formal") -> Dict[str, Any]:
        """
        Genera propuesta usando DeepSeek API con estilo específico
        """
        try:
            # Preparar contexto para la IA
            contexto = self._preparar_contexto(perfil)

            # Determinar instrucciones según estilo
            if estilo == "calido":
                instrucciones_estilo = """
ESTILO CÁLIDO Y EMOCIONAL:
- Usa lenguaje cercano, como si hablaras con un amigo
- Evoca recuerdos de visitas pasadas (menciona servicios que ha disfrutado)
- Crea una narrativa emocional sobre su experiencia en Aremko
- Usa frases como "recordamos que disfrutaste...", "te vimos relajarte en..."
- Ofertas diferenciadas: 15% en alojamiento/tinas, 10% en masajes
- Email con storytelling emocional, no solo lista de servicios
- Saludo muy personal usando solo el nombre de pila
"""
            else:  # formal
                instrucciones_estilo = """
ESTILO FORMAL Y PROFESIONAL:
- Tono corporativo y estructurado
- Datos y métricas claras
- Lenguaje profesional pero amable
- Oferta única y clara (15% general o según segmento)
- Email con estructura clara: saludo, recomendaciones, oferta, CTA
- Saludo profesional con nombre completo
"""

            # Prompt para DeepSeek
            prompt = f"""Eres un experto en marketing y turismo de bienestar. Analiza el siguiente perfil de cliente de Aremko (centro de bienestar y spa) y genera una propuesta personalizada.

PERFIL DEL CLIENTE:
{json.dumps(contexto, indent=2, ensure_ascii=False)}

{instrucciones_estilo}

TAREA:
Genera una propuesta personalizada en JSON con la siguiente estructura:

{{
    "insights": {{
        "segmento": "descripción del tipo de cliente",
        "comportamiento": "análisis de comportamiento de compra",
        "preferencias": "servicios preferidos y patrones"
    }},
    "recommendations": [
        {{
            "service_name": "nombre del servicio",
            "reason": "por qué se recomienda este servicio (máx 100 caracteres)",
            "confidence": 0.85,
            "estimated_price": 50000
        }}
    ],
    "offer": {{
        "title": "Título de la oferta especial",
        "description": "Descripción de la oferta (2-3 líneas)",
        "discount": "10% descuento" o null
    }},
    "email_body": "Email HTML profesional y personalizado con saludo al cliente, recomendaciones, oferta y call-to-action"
}}

INSTRUCCIONES:
1. Recommendations: Recomienda 2-3 servicios basados en el historial
2. Confidence: Valor entre 0.0 y 1.0
3. Offer: Crea oferta especial atractiva basada en el segmento RFM
4. Email: HTML simple, profesional, cálido y personalizado
5. Usa precios realistas en pesos chilenos (CLP)

Responde SOLO con el JSON, sin explicaciones adicionales."""

            # Llamar a DeepSeek
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.DEEPSEEK_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "Eres un experto en marketing y CRM para centros de bienestar y spa. Generas propuestas personalizadas basadas en análisis de datos de clientes."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }

            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.DEEPSEEK_API_URL,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                result = response.json()
                content = result['choices'][0]['message']['content']

                # Extraer JSON de la respuesta
                # A veces la IA responde con texto antes/después del JSON
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx]
                    propuesta = json.loads(json_str)
                else:
                    # Si no se puede extraer JSON, usar respuesta básica
                    logger.warning("No se pudo extraer JSON de respuesta de IA")
                    return self._generar_propuesta_basica(perfil)

                # Agregar customer_profile
                propuesta['customer_profile'] = {
                    'nombre': perfil['cliente']['nombre'],
                    'email': perfil['cliente']['email'],
                    'segmento': perfil['segmentacion']['rfm_segment'],
                    'total_servicios': perfil['metricas']['total_servicios'],
                    'gasto_total': perfil['metricas']['gasto_total']
                }

                return propuesta

        except httpx.HTTPError as e:
            logger.error(f"Error llamando a DeepSeek API: {e}")
            return self._generar_propuesta_basica(perfil)
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta JSON de IA: {e}")
            return self._generar_propuesta_basica(perfil)
        except Exception as e:
            logger.error(f"Error en generación con IA: {e}")
            return self._generar_propuesta_basica(perfil)

    def _generar_propuesta_basica(self, perfil: Dict[str, Any], estilo: str = "formal") -> Dict[str, Any]:
        """
        Genera propuesta básica basada en reglas de negocio (fallback)
        Soporta dos estilos: formal y cálido
        """
        cliente = perfil['cliente']
        metricas = perfil['metricas']
        segmentacion = perfil['segmentacion']
        categorias = perfil.get('categorias_favoritas', [])

        # Nombre según estilo
        nombre_cliente = cliente['nombre'].split()[0] if estilo == "calido" else cliente['nombre']

        # Insights básicos
        insights = {
            "segmento": f"Cliente {segmentacion['rfm_segment']}",
            "comportamiento": f"Ha utilizado {metricas['total_servicios']} servicios con un gasto total de ${metricas['gasto_total']:,.0f}",
            "preferencias": f"Categorías favoritas: {', '.join([c['service_type'] for c in categorias[:3]])}" if categorias else "Cliente nuevo sin historial"
        }

        # Recomendaciones basadas en categorías favoritas
        recommendations = []

        if categorias:
            # Recomendar servicios de categorías favoritas
            for cat in categorias[:2]:
                recommendations.append({
                    "service_name": f"Paquete Premium {cat['service_type']}",
                    "reason": f"Has disfrutado {cat['cantidad']} veces de {cat['service_type']}",
                    "confidence": 0.85,
                    "estimated_price": int(cat['gasto'] / cat['cantidad'] * 1.2)
                })
        else:
            # Cliente nuevo - recomendar servicios populares
            recommendations.append({
                "service_name": "Paquete de Bienvenida - Masaje Relajante",
                "reason": "Perfecto para comenzar tu experiencia Aremko",
                "confidence": 0.75,
                "estimated_price": 45000
            })

        # Oferta especial según segmento
        if segmentacion['is_vip']:
            offer = {
                "title": "Oferta Exclusiva VIP",
                "description": "Como cliente VIP, disfruta de un 15% de descuento en tu próxima reserva y acceso prioritario a nuevos servicios.",
                "discount": "15% descuento"
            }
        elif segmentacion['en_riesgo']:
            offer = {
                "title": "¡Te Extrañamos!",
                "description": "Vuelve a disfrutar de la experiencia Aremko con un 20% de descuento especial en cualquier servicio.",
                "discount": "20% descuento"
            }
        else:
            offer = {
                "title": "Promoción Especial",
                "description": "Reserva ahora y obtén un 10% de descuento en tu próximo servicio.",
                "discount": "10% descuento"
            }

        # Email HTML según estilo
        if estilo == "calido":
            # Email cálido y emocional con storytelling
            servicios_texto = "".join([f"· {cat['service_type']}" for cat in categorias[:2]])
            email_body = f"""
            <html>
            <body style="font-family: 'Georgia', serif; line-height: 1.8; color: #444;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; background: linear-gradient(to bottom, #f9f7f4 0%, #ffffff 100%);">
                    <h2 style="color: #8B4513; font-weight: 300; margin-bottom: 5px;">Hola {nombre_cliente},</h2>
                    <p style="color: #999; font-size: 14px; font-style: italic; margin-top: 0;">Un saludo cálido desde Puerto Varas 🌿</p>

                    <p>Recordamos cada visita que nos has hecho... Esas {metricas['total_servicios']} ocasiones en las que decidiste regalarte tiempo para ti. Nos emociona ver que has encontrado en Aremko tu refugio de bienestar.</p>

                    <p>Sabemos lo mucho que disfrutas {servicios_texto}. Cada vez que te vemos relajarte en nuestras instalaciones, confirmamos que estamos cumpliendo nuestra misión: crear momentos inolvidables.</p>

                    <div style="background: #fff8f0; padding: 20px; margin: 25px 0; border-left: 4px solid #d2691e; border-radius: 0 8px 8px 0;">
                        <h3 style="color: #8B4513; font-weight: 300; margin-top: 0;">Pensamos en ti y creamos esto:</h3>
                        {"".join([f'''
                        <div style="margin: 20px 0;">
                            <p style="font-size: 18px; color: #8B4513; margin-bottom: 8px;"><strong>{rec["service_name"]}</strong></p>
                            <p style="color: #666; font-style: italic; margin: 5px 0;">{rec["reason"]}</p>
                            <p style="color: #999; font-size: 14px;">Valor estimado: ${rec["estimated_price"]:,}</p>
                        </div>
                        ''' for rec in recommendations])}
                    </div>

                    <div style="background: linear-gradient(135deg, #8B4513 0%, #d2691e 100%); color: white; padding: 25px; margin: 25px 0; border-radius: 8px; text-align: center;">
                        <h3 style="margin-top: 0; font-weight: 300;">✨ Este mes, algo especial para ti</h3>
                        <p style="font-size: 16px; line-height: 1.6;">{offer["description"]}</p>
                        <p style="font-size: 24px; margin: 15px 0; font-weight: bold;">{offer["discount"]}</p>
                        <p style="font-size: 14px; opacity: 0.9;">Válido durante noviembre 2024</p>
                    </div>

                    <p style="text-align: center; margin: 30px 0;">
                        <a href="https://www.aremko.cl/reservas" style="display: inline-block; background: #8B4513; color: white; padding: 15px 35px; text-decoration: none; border-radius: 30px; font-size: 16px; box-shadow: 0 4px 10px rgba(139, 69, 19, 0.3);">Reservar Mi Momento Especial</a>
                    </p>

                    <p style="color: #666; font-size: 15px; line-height: 1.7; margin-top: 40px;">
                        Te esperamos con los brazos abiertos en tu segundo hogar de descanso. Queremos seguir siendo parte de esos momentos que te hacen bien.<br><br>
                        Con cariño,<br>
                        <strong style="color: #8B4513;">Todo el equipo de Aremko</strong> 💚
                    </p>
                </div>
            </body>
            </html>
            """
        else:
            # Email formal y profesional
            email_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c5282;">Hola {cliente['nombre']},</h2>

                    <p>En Aremko valoramos tu preferencia y queremos ofrecerte una experiencia única y personalizada.</p>

                    <h3 style="color: #2c5282;">Recomendaciones Especiales para Ti:</h3>

                    {"".join([f'''
                    <div style="background-color: #f7fafc; padding: 15px; margin: 10px 0; border-left: 4px solid #4299e1;">
                        <strong>{rec["service_name"]}</strong><br>
                        <span style="color: #718096;">{rec["reason"]}</span><br>
                        <span style="color: #2d3748; font-weight: bold;">Precio estimado: ${rec["estimated_price"]:,}</span>
                    </div>
                    ''' for rec in recommendations])}

                    <div style="background-color: #edf2f7; padding: 20px; margin: 20px 0; border-radius: 8px;">
                        <h3 style="color: #2c5282; margin-top: 0;">{offer["title"]}</h3>
                        <p>{offer["description"]}</p>
                        {f'<p style="font-size: 18px; color: #e53e3e; font-weight: bold;">{offer["discount"]}</p>' if offer.get("discount") else ''}
                    </div>

                    <p><a href="https://www.aremko.cl" style="display: inline-block; background-color: #4299e1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">Reservar Ahora</a></p>

                    <p style="color: #718096; font-size: 14px;">
                        ¡Esperamos verte pronto en Aremko!<br>
                        Equipo Aremko
                    </p>
                </div>
            </body>
            </html>
            """

        return {
            "customer_profile": {
                "nombre": cliente['nombre'],
                "email": cliente['email'],
                "segmento": segmentacion['rfm_segment'],
                "total_servicios": metricas['total_servicios'],
                "gasto_total": metricas['gasto_total']
            },
            "insights": insights,
            "recommendations": recommendations,
            "offer": offer,
            "email_body": email_body.strip()
        }

    def _preparar_contexto(self, perfil: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepara contexto simplificado para la IA
        """
        return {
            "cliente": {
                "nombre": perfil['cliente']['nombre'],
                "ciudad": perfil['cliente'].get('ciudad', 'No registrado'),
                "pais": perfil['cliente'].get('pais', 'No registrado')
            },
            "metricas": {
                "total_servicios": perfil['metricas']['total_servicios'],
                "servicios_historicos": perfil['metricas']['servicios_historicos'],
                "servicios_actuales": perfil['metricas']['servicios_actuales'],
                "gasto_total": perfil['metricas']['gasto_total'],
                "ticket_promedio": perfil['metricas']['ticket_promedio'],
                "dias_como_cliente": perfil['metricas']['dias_como_cliente']
            },
            "segmentacion": perfil['segmentacion'],
            "categorias_favoritas": perfil.get('categorias_favoritas', [])[:3],
            "historial_reciente": perfil.get('historial_reciente', [])[:5]
        }


# Instancia global del servicio
_ai_service = None

def get_ai_service() -> AIProposalService:
    """
    Obtiene instancia singleton del servicio de IA
    """
    global _ai_service
    if _ai_service is None:
        _ai_service = AIProposalService()
    return _ai_service
