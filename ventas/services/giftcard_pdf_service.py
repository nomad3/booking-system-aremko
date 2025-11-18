# -*- coding: utf-8 -*-
"""
Servicio para generar PDFs de GiftCards y enviar emails
"""

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from datetime import datetime
import logging
import io
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 8px;
            background-color: #f5f5f5;
            line-height: 1.5;
        }}
        .giftcard-container {{
            max-width: 100%;
            width: 100%;
            margin: 0 auto;
            background: linear-gradient(135deg, #fff8e1 0%, #ffffff 100%);
            border: 3px solid #ffc107;
            border-radius: 16px;
            padding: 20px;
            box-sizing: border-box;
            min-height: auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo {{
            color: #A0522D;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 8px;
            word-break: break-word;
        }}
        .title {{
            color: #D2B48C;
            font-size: 1.4rem;
            font-weight: 600;
            line-height: 1.3;
        }}
        .divider {{
            border: 0;
            border-top: 2px solid #ffc107;
            margin: 16px 0;
        }}
        .para {{
            text-align: center;
            color: #A0522D;
            font-size: 1rem;
            margin-bottom: 8px;
            font-weight: 500;
        }}
        .destinatario {{
            text-align: center;
            color: #5C4033;
            font-size: 1.6rem;
            font-weight: 600;
            margin-bottom: 20px;
            word-break: break-word;
            line-height: 1.2;
        }}
        .mensaje {{
            background-color: white;
            border-left: 4px solid #ffc107;
            padding: 16px;
            margin: 16px 0;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}
        .mensaje-text {{
            color: #5C4033;
            font-style: italic;
            line-height: 1.6;
            font-size: 1.1rem;
            text-align: left;
            margin: 0;
        }}
        .details {{
            display: block;
            width: 100%;
            margin: 20px 0;
        }}
        .detail-row {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 16px;
        }}
        .detail-section {{
            background-color: rgba(255, 193, 7, 0.08);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
            text-align: center;
        }}
        .detail-label {{
            color: #A0522D;
            font-size: 0.9rem;
            font-weight: 600;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .detail-value {{
            color: #5C4033;
            font-size: 1.2rem;
            font-weight: 600;
            line-height: 1.3;
            word-break: break-word;
        }}
        .codigo-section {{
            background-color: rgba(255, 193, 7, 0.1);
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
            text-align: center;
        }}
        .codigo-label {{
            color: #A0522D;
            font-size: 0.9rem;
            margin-bottom: 8px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .codigo {{
            color: #5C4033;
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 1.4rem;
            font-weight: 700;
            letter-spacing: 1px;
            word-break: break-all;
            line-height: 1.2;
        }}
        .validez {{
            text-align: center;
            margin: 20px 0;
            background-color: rgba(255, 193, 7, 0.08);
            border-radius: 12px;
            padding: 16px;
        }}
        .validez-label {{
            color: #A0522D;
            font-size: 0.9rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        .validez-fecha {{
            color: #5C4033;
            font-size: 1.1rem;
            font-weight: 600;
        }}
        .instrucciones {{
            text-align: center;
            margin: 24px 0;
            padding: 20px;
            background-color: rgba(37, 211, 102, 0.1);
            border-radius: 12px;
            border: 1px solid rgba(37, 211, 102, 0.2);
        }}
        .instrucciones-title {{
            color: #A0522D;
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .whatsapp {{
            color: #25D366;
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        .footer {{
            text-align: center;
            margin-top: 24px;
            padding-top: 16px;
            border-top: 1px solid #D2B48C;
            color: #666;
            font-size: 0.85rem;
            line-height: 1.4;
        }}
        .precio {{
            color: #16a085;
            font-size: 1.8rem;
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
            <div class="detail-section">
                <div class="detail-label">EXPERIENCIA</div>
                <div class="detail-value">{giftcard_data['experiencia_nombre']}</div>
            </div>

            <div class="detail-section">
                <div class="detail-label">VALOR</div>
                <div class="precio">${int(giftcard_data['precio']):,}</div>
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
    def generar_pdf_giftcard(giftcard_data):
        """
        Genera un PDF a partir de los datos de la GiftCard

        Args:
            giftcard_data (dict): Datos de la GiftCard

        Returns:
            bytes: Contenido del PDF en bytes
        """
        try:
            # Generar HTML
            html_content = GiftCardPDFService.generar_html_giftcard(giftcard_data)

            # CSS adicional optimizado para PDF mobile-friendly
            css_pdf = CSS(string="""
                @page {
                    size: A4;
                    margin: 10mm;
                    @bottom-center {
                        content: "AREMKO Spa - www.aremko.cl";
                        font-size: 9px;
                        color: #999;
                    }
                }
                body {
                    font-size: 16px;
                    line-height: 1.5;
                }
                .giftcard-container {
                    max-width: 100%;
                    box-shadow: none;
                    border: 3px solid #ffc107;
                    padding: 16px;
                }
                .logo {
                    font-size: 28px;
                }
                .codigo {
                    font-size: 18px;
                    letter-spacing: 0.5px;
                    word-break: break-all;
                }
                .precio {
                    font-size: 24px;
                }
                /* Optimizaciones para PDF */
                .detail-section {
                    background-color: rgba(255, 193, 7, 0.15) !important;
                    -webkit-print-color-adjust: exact;
                    color-adjust: exact;
                }
                .instrucciones {
                    background-color: rgba(37, 211, 102, 0.15) !important;
                    -webkit-print-color-adjust: exact;
                    color-adjust: exact;
                }
            """)

            # Configuración de fuentes
            font_config = FontConfiguration()

            # Crear PDF desde HTML
            html_doc = HTML(string=html_content)
            pdf_bytes = html_doc.write_pdf(
                stylesheets=[css_pdf],
                font_config=font_config
            )

            logger.info(f"✅ PDF generado exitosamente para GiftCard {giftcard_data['codigo']}")
            return pdf_bytes

        except Exception as e:
            logger.error(f"❌ Error generando PDF para GiftCard {giftcard_data.get('codigo', 'N/A')}: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def generar_multiples_pdfs(giftcards_data):
        """
        Genera múltiples PDFs de GiftCards y los combina en un solo archivo

        Args:
            giftcards_data (list): Lista de datos de GiftCards

        Returns:
            bytes: Contenido del PDF combinado en bytes
        """
        try:
            # Si es solo una GiftCard, usar función simple
            if len(giftcards_data) == 1:
                return GiftCardPDFService.generar_pdf_giftcard(giftcards_data[0])

            # Para múltiples GiftCards, combinar HTML
            html_content = ""
            for i, giftcard_data in enumerate(giftcards_data):
                html_content += GiftCardPDFService.generar_html_giftcard(giftcard_data)
                # Agregar salto de página entre gift cards (excepto la última)
                if i < len(giftcards_data) - 1:
                    html_content += '<div style="page-break-after: always;"></div>'

            # CSS para múltiples páginas mobile-friendly
            css_pdf = CSS(string="""
                @page {
                    size: A4;
                    margin: 10mm;
                    @bottom-center {
                        content: "AREMKO Spa - www.aremko.cl - Página " counter(page);
                        font-size: 9px;
                        color: #999;
                    }
                }
                body {
                    font-size: 16px;
                    line-height: 1.5;
                }
                .giftcard-container {
                    max-width: 100%;
                    box-shadow: none;
                    border: 3px solid #ffc107;
                    margin-bottom: 16px;
                    padding: 16px;
                }
                .logo {
                    font-size: 28px;
                }
                .codigo {
                    font-size: 18px;
                    letter-spacing: 0.5px;
                    word-break: break-all;
                }
                .precio {
                    font-size: 24px;
                }
                /* Optimizaciones para PDF múltiple */
                .detail-section {
                    background-color: rgba(255, 193, 7, 0.15) !important;
                    -webkit-print-color-adjust: exact;
                    color-adjust: exact;
                }
                .instrucciones {
                    background-color: rgba(37, 211, 102, 0.15) !important;
                    -webkit-print-color-adjust: exact;
                    color-adjust: exact;
                }
            """)

            # Crear PDF combinado
            font_config = FontConfiguration()
            html_doc = HTML(string=html_content)
            pdf_bytes = html_doc.write_pdf(
                stylesheets=[css_pdf],
                font_config=font_config
            )

            logger.info(f"✅ PDF combinado generado exitosamente para {len(giftcards_data)} GiftCards")
            return pdf_bytes

        except Exception as e:
            logger.error(f"❌ Error generando PDF combinado: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def enviar_giftcard_por_email(comprador_email, comprador_nombre, giftcards_data):
        """
        Envía un email al comprador con las GiftCards como archivo PDF adjunto

        Args:
            comprador_email (str): Email del comprador
            comprador_nombre (str): Nombre del comprador
            giftcards_data (list): Lista de diccionarios con datos de GiftCards

        Returns:
            bool: True si se envió correctamente, False si hubo error
        """
        try:
            # Generar PDF con todas las GiftCards
            pdf_bytes = GiftCardPDFService.generar_multiples_pdfs(giftcards_data)

            # Preparar el email
            subject = f"🎁 Tu{'s' if len(giftcards_data) > 1 else ''} GiftCard{'s' if len(giftcards_data) > 1 else ''} Aremko {'están' if len(giftcards_data) > 1 else 'está'} {'listas' if len(giftcards_data) > 1 else 'lista'}"

            # Mensaje del email (texto plano)
            message = f"""Hola {comprador_nombre},

¡Gracias por tu compra en Aremko Spa!

Tu{'s' if len(giftcards_data) > 1 else ''} GiftCard{'s' if len(giftcards_data) > 1 else ''} personalizada{'s' if len(giftcards_data) > 1 else ''} {'están' if len(giftcards_data) > 1 else 'está'} {'listas' if len(giftcards_data) > 1 else 'lista'} y {'adjuntas' if len(giftcards_data) > 1 else 'adjunta'} en este email como archivo PDF.

{'Códigos' if len(giftcards_data) > 1 else 'Código'} incluido{'s' if len(giftcards_data) > 1 else ''}:
{chr(10).join([f"• {gc['codigo']} para {gc['destinatario_nombre']} - {gc['experiencia_nombre']}" for gc in giftcards_data])}

INSTRUCCIONES:
✅ Descargar e imprimir el certificado PDF adjunto
✅ Entregar al destinatario en persona o digitalmente
✅ Para canjear: contactar por WhatsApp al +56 9 5790 2525 con el código

El destinatario debe mencionar su código al momento de reservar para usar la experiencia.

¡Gracias por regalar momentos inolvidables en nuestro spa!

AREMKO Spa
Puerto Varas, Chile
WhatsApp: +56 9 5790 2525
www.aremko.cl

---
Este email contiene {'los certificados' if len(giftcards_data) > 1 else 'tu certificado'} de regalo en formato PDF.
"""

            # Crear el email
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[comprador_email],
            )

            # Nombre del archivo PDF
            filename = f"GiftCard{'s' if len(giftcards_data) > 1 else ''}_Aremko_{datetime.now().strftime('%Y%m%d')}.pdf"

            # Adjuntar el PDF
            email.attach(filename, pdf_bytes, 'application/pdf')

            # Enviar
            email.send()

            logger.info(f"✅ Email con PDF de GiftCard enviado a {comprador_email} - Archivo: {filename}")
            return True

        except Exception as e:
            logger.error(f"❌ Error al enviar email con PDF de GiftCard: {str(e)}", exc_info=True)
            return False
