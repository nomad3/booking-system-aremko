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
from ventas.models import EmailSubjectTemplate, EmailContentTemplate
from datetime import datetime
import locale

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
        self.api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
        # Considerar vacía si es string vacío o None
        if not self.api_key:
            self.api_key = None
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
            return self._generar_propuesta_basica(perfil, estilo)
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando respuesta JSON de IA: {e}")
            return self._generar_propuesta_basica(perfil, estilo)
        except Exception as e:
            logger.error(f"Error en generación con IA: {e}")
            return self._generar_propuesta_basica(perfil, estilo)

    def _generar_propuesta_basica(self, perfil: Dict[str, Any], estilo: str = "formal") -> Dict[str, Any]:
        """
        Genera propuesta básica basada en reglas de negocio (fallback)
        Soporta dos estilos: formal y cálido
        """
        logger.info(f"_generar_propuesta_basica llamada con estilo: {estilo}")

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

        # Intentar usar template editable si existe
        template = EmailContentTemplate.get_active_template(estilo)

        if template:
            logger.info(f"→ Usando template EDITABLE: {template.nombre}")
            # Preparar contexto para el template
            email_body = self._render_email_from_template(template, perfil, categorias, offer, estilo)
        else:
            # Fallback a templates hardcoded
            logger.info(f"→ No hay template editable activo, usando código hardcoded")
            email_body = self._render_email_hardcoded(perfil, categorias, offer, estilo)

        # Generar asunto dinámico según estilo
        email_subject = EmailSubjectTemplate.get_random_subject(
            estilo=estilo,
            nombre_cliente=cliente['nombre']
        )
        logger.info(f"Asunto generado: {email_subject}")

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
            "email_subject": email_subject,
            "email_body": email_body.strip()
        }

    def _render_email_from_template(self, template, perfil, categorias, offer, estilo):
        """
        Renderiza email usando template editable
        """
        cliente = perfil['cliente']
        metricas = perfil['metricas']
        segmentacion = perfil['segmentacion']
        nombre_cliente = cliente['nombre'].split()[0] if estilo == "calido" else cliente['nombre']

        # Construir narrativa de servicios
        servicios_narrativa = self._build_servicios_narrativa(categorias, metricas, estilo)

        # Obtener mes actual
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'es_CL.UTF-8')
            except:
                pass
        mes_actual = datetime.now().strftime('%B')

        # Preparar ofertas según estilo
        if estilo == "calido":
            oferta_porcentaje = "15%"
            oferta_servicios = "tinajas calientes privadas y cabañas"
            oferta_texto_completo = """<strong>15% de descuento</strong> en tu próxima experiencia en tinaja caliente privada o en una estadía en nuestras cabañas (¡tú eliges la forma de relajarte!).<br><br>
                    <strong>10% de descuento</strong> en cualquier masaje de nuestro spa, para que complementes tu descanso como te mereces."""
        else:
            oferta_porcentaje = offer.get('discount', '15% descuento').split()[0]
            oferta_servicios = "todos nuestros servicios"
            oferta_texto_completo = f"<strong>{offer.get('discount', '15% descuento')}</strong>"

        # Preparar contexto para el template
        context = {
            'nombre': nombre_cliente,
            'servicios_narrativa': servicios_narrativa,
            'oferta_porcentaje': oferta_porcentaje,
            'oferta_servicios': oferta_servicios,
            'oferta_texto_completo': oferta_texto_completo,
            'mes_actual': mes_actual,
            'segmento': segmentacion['rfm_segment']
        }

        # Renderizar usando el template
        return template.render_email(context)

    def _build_servicios_narrativa(self, categorias, metricas, estilo):
        """
        Construye la narrativa de servicios desde el historial
        """
        servicios_narrativa = ""

        if estilo == "calido" and categorias:
            for cat in categorias[:2]:
                if 'Cabaña' in cat['service_type'] or 'cabaña' in cat['service_type'].lower():
                    veces = cat['cantidad']
                    servicios_narrativa += f"las {veces} escapadas inolvidables que viviste en nuestras cabañas rodeadas de naturaleza"
                elif 'Tina' in cat['service_type'] or 'tinaja' in cat['service_type'].lower():
                    veces = cat['cantidad']
                    if servicios_narrativa:
                        servicios_narrativa += f", y los momentos de relajo que disfrutaste en nuestras tinajas calientes privadas en {veces} ocasiones"
                    else:
                        servicios_narrativa += f"los {veces} momentos de relajo en nuestras tinajas calientes privadas"
                elif 'Masaje' in cat['service_type']:
                    veces = cat['cantidad']
                    if servicios_narrativa:
                        servicios_narrativa += f", además de {veces} sesiones de masajes relajantes"
                    else:
                        servicios_narrativa += f"las {veces} sesiones de masajes que tanto disfrutaste"

            if not servicios_narrativa:
                servicios_narrativa = f"las {metricas['total_servicios']} veces que nos has visitado"
        else:
            # Formal
            if categorias:
                servicios_narrativa = f"tus {metricas['total_servicios']} visitas anteriores a Aremko"
            else:
                servicios_narrativa = "tu interés en nuestros servicios"

        return servicios_narrativa

    def _render_email_hardcoded(self, perfil, categorias, offer, estilo):
        """
        Renderiza email usando código hardcoded (fallback cuando no hay template editable)
        """
        cliente = perfil['cliente']
        metricas = perfil['metricas']
        nombre_cliente = cliente['nombre'].split()[0] if estilo == "calido" else cliente['nombre']

        # Construir narrativa
        servicios_narrativa = self._build_servicios_narrativa(categorias, metricas, estilo)

        logger.info(f"Generando email con estilo hardcoded: {estilo}")
        if estilo == "calido":
            logger.info("→ Usando template CÁLIDO")
            # Email cálido y emocional con storytelling - estilo muy personal

            # Ofertas diferenciadas por categoría
            ofertas_texto = """<strong>15% de descuento</strong> en tu próxima experiencia en tinaja caliente privada o en una estadía en nuestras cabañas (¡tú eliges la forma de relajarte!).<br><br>
                    <strong>10% de descuento</strong> en cualquier masaje de nuestro spa, para que complementes tu descanso como te mereces."""

            email_body = f"""
            <html>
            <body style="font-family: 'Georgia', serif; line-height: 1.8; color: #333; background-color: #fafafa;">
                <div style="max-width: 600px; margin: 0 auto; padding: 30px 20px; background-color: #ffffff;">
                    <h2 style="color: #2c5530; font-weight: 400; margin-bottom: 20px;">Hola {nombre_cliente},</h2>

                    <p style="font-size: 16px; line-height: 1.8; margin-bottom: 20px;">
                        Espero que te encuentres muy bien. Nos llena de alegría recordar {servicios_narrativa}.
                        Cada visita tuya nos ha permitido conocerte mejor y saber lo que más te hace feliz.
                    </p>

                    <p style="font-size: 16px; line-height: 1.8; margin-bottom: 25px;">
                        Por eso, en agradecimiento a tu lealtad, <strong>este mes de noviembre</strong> queremos tener un detalle especial contigo:
                    </p>

                    <div style="background-color: #f8f5f0; border-left: 4px solid #8B7355; padding: 20px; margin: 25px 0;">
                        <p style="font-size: 16px; line-height: 1.8; margin: 0;">
                            {ofertas_texto}
                        </p>
                    </div>

                    <p style="font-size: 16px; line-height: 1.8; margin-bottom: 20px;">
                        Estos beneficios son válidos durante <strong>todo el mes de noviembre</strong>. Aprovecha esta oportunidad para regalarte el descanso que tanto necesitas antes de que termine el año.
                    </p>

                    <p style="font-size: 16px; line-height: 1.8; margin-bottom: 25px;">
                        Sabes que para nosotros <strong>no eres un cliente más; eres parte de la familia Aremko</strong>. Nos encantaría volver a verte pronto disfrutando y relajándote como en tus visitas anteriores.
                    </p>

                    <p style="font-size: 16px; line-height: 1.8; margin-bottom: 30px;">
                        Si te animas a otra escapada, aquí te estaremos esperando con los brazos abiertos, listos para brindarte una vez más una experiencia inolvidable.
                    </p>

                    <div style="text-align: center; margin: 35px 0;">
                        <a href="https://wa.me/56957902525?text=Hola%2C%20me%20gustar%C3%ADa%20reservar%20aprovechando%20la%20oferta%20especial" style="display: inline-block; background-color: #25d366; color: white; padding: 14px 40px; text-decoration: none; border-radius: 25px; font-size: 16px; font-weight: 500;">
                            📱 Reservar por WhatsApp
                        </a>
                    </div>

                    <p style="font-size: 15px; line-height: 1.7; color: #666; margin-top: 40px; border-top: 1px solid #e0e0e0; padding-top: 20px;">
                        Con cariño,<br>
                        <strong style="color: #2c5530;">El equipo de Aremko</strong><br>
                        <span style="font-size: 14px; color: #999;">Puerto Varas, Chile</span>
                    </p>
                </div>
            </body>
            </html>
            """
        else:
            logger.info("→ Usando template FORMAL")
            # Email formal y profesional
            email_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c5282;">Estimado/a {cliente['nombre']},</h2>

                    <p>En Aremko valoramos tu preferencia y queremos ofrecerte una experiencia única y personalizada basada en {servicios_narrativa}.</p>

                    <h3 style="color: #2c5282;">Tu Historial con Aremko:</h3>
                    <div style="background-color: #f7fafc; padding: 15px; margin: 10px 0; border-left: 4px solid #4299e1;">
                        <p style="margin: 5px 0;"><strong>Total de visitas:</strong> {metricas['total_servicios']}</p>
                        <p style="margin: 5px 0;"><strong>Inversión en bienestar:</strong> ${metricas['gasto_total']:,.0f} CLP</p>
                    </div>

                    <div style="background-color: #edf2f7; padding: 20px; margin: 20px 0; border-radius: 8px;">
                        <h3 style="color: #2c5282; margin-top: 0;">{offer["title"]}</h3>
                        <p>{offer["description"]}</p>
                        {f'<p style="font-size: 18px; color: #e53e3e; font-weight: bold;">{offer["discount"]}</p>' if offer.get("discount") else ''}
                    </div>

                    <p style="text-align: center;">
                        <a href="https://wa.me/56957902525?text=Hola%2C%20me%20interesa%20reservar%20de%20acuerdo%20a%20la%20propuesta%20recibida" style="display: inline-block; background-color: #25d366; color: white; padding: 14px 30px; text-decoration: none; border-radius: 25px; font-weight: bold;">
                            📱 Reservar por WhatsApp
                        </a>
                    </p>

                    <p style="color: #718096; font-size: 14px; margin-top: 30px;">
                        ¡Esperamos verte pronto en Aremko!<br>
                        Equipo Aremko<br>
                        Puerto Varas, Chile
                    </p>
                </div>
            </body>
            </html>
            """

        return email_body

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
