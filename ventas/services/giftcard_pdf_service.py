# -*- coding: utf-8 -*-
"""
Servicio para generar PDFs de GiftCards y enviar emails
"""

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GiftCardPDFService:
    """
    Servicio para generar PDFs de GiftCards y enviar por email al comprador
    """

    @staticmethod
    def generar_html_giftcard(giftcard_data):
        """
        Genera el HTML de la GiftCard para convertir a PDF o email

        Args:
            giftcard_data (dict): Datos de la GiftCard
                - codigo: Código único de la GiftCard
                - experiencia_nombre: Nombre de la experiencia
                - destinatario_nombre: Nombre del destinatario
                - mensaje_seleccionado: Mensaje personalizado
                - precio: Valor de la GiftCard
                - fecha_emision: Fecha de emisión
                - fecha_vencimiento: Fecha de vencimiento

        Returns:
            str: HTML renderizado
        """

        html_template = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Arial', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .giftcard-container {{
            max-width: 600px;
            margin: 0 auto;
            background: linear-gradient(135deg, #fff8e1 0%, #ffffff 100%);
            border: 3px solid #ffc107;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo {{
            color: #A0522D;
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 10px;
        }}
        .title {{
            color: #D2B48C;
            font-size: 22px;
            font-weight: 600;
        }}
        .divider {{
            border: 0;
            border-top: 2px solid #ffc107;
            margin: 20px 0;
        }}
        .para {{
            text-align: center;
            color: #A0522D;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        .destinatario {{
            text-align: center;
            color: #5C4033;
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 30px;
        }}
        .mensaje {{
            background-color: white;
            border-left: 4px solid #ffc107;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
        }}
        .mensaje-text {{
            color: #5C4033;
            font-style: italic;
            line-height: 1.6;
            font-size: 15px;
        }}
        .details {{
            display: table;
            width: 100%;
            margin: 20px 0;
        }}
        .detail-row {{
            display: table-row;
        }}
        .detail-label {{
            display: table-cell;
            text-align: center;
            color: #A0522D;
            font-size: 12px;
            font-weight: 600;
            padding: 10px;
            width: 50%;
        }}
        .detail-value {{
            display: table-cell;
            text-align: center;
            color: #5C4033;
            font-size: 18px;
            font-weight: 600;
            padding: 10px;
        }}
        .codigo-section {{
            text-align: center;
            margin: 20px 0;
        }}
        .codigo-label {{
            color: #A0522D;
            font-size: 12px;
            margin-bottom: 5px;
        }}
        .codigo {{
            color: #5C4033;
            font-family: 'Courier New', monospace;
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 2px;
        }}
        .validez {{
            text-align: center;
            margin: 20px 0;
        }}
        .validez-label {{
            color: #A0522D;
            font-size: 12px;
        }}
        .validez-fecha {{
            color: #5C4033;
            font-size: 16px;
            font-weight: 600;
        }}
        .instrucciones {{
            text-align: center;
            margin: 30px 0;
            padding: 20px;
            background-color: rgba(255, 193, 7, 0.1);
            border-radius: 8px;
        }}
        .instrucciones-title {{
            color: #A0522D;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 10px;
        }}
        .whatsapp {{
            color: #25D366;
            font-size: 16px;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #D2B48C;
            color: #999;
            font-size: 12px;
        }}
        .precio {{
            color: #16a085;
            font-size: 24px;
            font-weight: 700;
        }}
    </style>
</head>
<body>
    <div class="giftcard-container">
        <!-- Header -->
        <div class="header">
            <div class="logo">AREMKO SPA</div>
            <div class="title">🎁 Certificado de Regalo 🎁</div>
        </div>

        <hr class="divider">

        <!-- Destinatario -->
        <div class="para">Para:</div>
        <div class="destinatario">{giftcard_data['destinatario_nombre']}</div>

        <!-- Mensaje -->
        <div class="mensaje">
            <div class="mensaje-text">{giftcard_data['mensaje_seleccionado']}</div>
        </div>

        <hr class="divider">

        <!-- Experiencia y Valor -->
        <div class="details">
            <div class="detail-row">
                <div class="detail-label">
                    <div style="margin-bottom: 5px;">EXPERIENCIA</div>
                    <div class="detail-value" style="font-size: 16px;">{giftcard_data['experiencia_nombre']}</div>
                </div>
                <div class="detail-label">
                    <div style="margin-bottom: 5px;">VALOR</div>
                    <div class="precio">${int(giftcard_data['precio']):,}</div>
                </div>
            </div>
        </div>

        <!-- Código -->
        <div class="codigo-section">
            <div class="codigo-label">CÓDIGO</div>
            <div class="codigo">{giftcard_data['codigo']}</div>
        </div>

        <!-- Validez -->
        <div class="validez">
            <div class="validez-label">VÁLIDO HASTA</div>
            <div class="validez-fecha">{giftcard_data['fecha_vencimiento'].strftime('%d de %B de %Y')}</div>
        </div>

        <hr class="divider">

        <!-- Instrucciones -->
        <div class="instrucciones">
            <div class="instrucciones-title">CÓMO USAR</div>
            <div class="whatsapp">📱 WhatsApp: +56 9 5790 2525</div>
            <div style="color: #666; font-size: 13px; margin-top: 10px;">
                Menciona tu código para reservar tu experiencia
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            www.aremko.cl | Puerto Varas<br>
            Emitido el {giftcard_data['fecha_emision'].strftime('%d/%m/%Y')}
        </div>
    </div>
</body>
</html>
"""
        return html_template

    @staticmethod
    def enviar_giftcard_por_email(comprador_email, comprador_nombre, giftcards_data):
        """
        Envía un email al comprador con las GiftCards en HTML

        Args:
            comprador_email (str): Email del comprador
            comprador_nombre (str): Nombre del comprador
            giftcards_data (list): Lista de diccionarios con datos de GiftCards

        Returns:
            bool: True si se envió correctamente, False si hubo error
        """
        try:
            # Generar HTML para cada GiftCard
            giftcards_html = ""
            for giftcard_data in giftcards_data:
                giftcards_html += GiftCardPDFService.generar_html_giftcard(giftcard_data)
                giftcards_html += "<div style='page-break-after: always;'></div>"

            # Preparar el email
            subject = f"✅ Tu{'s' if len(giftcards_data) > 1 else ''} GiftCard{'s' if len(giftcards_data) > 1 else ''} Aremko {'están' if len(giftcards_data) > 1 else 'está'} {'listas' if len(giftcards_data) > 1 else 'lista'}"

            # Mensaje del email
            message = f"""
Hola {comprador_nombre},

¡Gracias por tu compra!

Tu{'s' if len(giftcards_data) > 1 else ''} GiftCard{'s' if len(giftcards_data) > 1 else ''} personalizada{'s' if len(giftcards_data) > 1 else ''} {'están' if len(giftcards_data) > 1 else 'está'} {'listas' if len(giftcards_data) > 1 else 'lista'}.

Puedes:
- Imprimir el certificado y entregarlo personalmente
- Reenviar este email al destinatario
- Compartir el código por WhatsApp

{'Códigos' if len(giftcards_data) > 1 else 'Código'} de {'regalo' if len(giftcards_data) == 1 else 'regalos'}:
{chr(10).join([f"- {gc['codigo']} para {gc['destinatario_nombre']}" for gc in giftcards_data])}

CÓMO CANJEAR:
El destinatario debe contactar por WhatsApp al +56 9 5790 2525
y mostrar el código para reservar su experiencia.

¡Gracias por regalar momentos inolvidables!

AREMKO Spa Puerto Varas
www.aremko.cl
"""

            # Crear el email
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[comprador_email],
            )

            # Agregar el HTML como contenido alternativo
            email.content_subtype = "html"
            email.body = giftcards_html

            # Enviar
            email.send()

            logger.info(f"✅ Email de GiftCard enviado a {comprador_email}")
            return True

        except Exception as e:
            logger.error(f"❌ Error al enviar email de GiftCard: {str(e)}", exc_info=True)
            return False
