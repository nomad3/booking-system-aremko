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
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    HTML = None
    CSS = None
    FontConfiguration = None

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
                - experiencia_imagen_url: URL de la imagen de la experiencia (opcional)
                - destinatario_nombre: Nombre del destinatario
                - mensaje_seleccionado: Mensaje personalizado
                - precio: Valor de la GiftCard
                - fecha_emision: Fecha de emisión
                - fecha_vencimiento: Fecha de vencimiento

        Returns:
            str: HTML renderizado
        """

        # Obtener URL de la imagen si existe
        imagen_url = giftcard_data.get('experiencia_imagen_url', '')
        tiene_imagen = bool(imagen_url)

        # Generar HTML de la imagen si existe
        imagen_html = ''
        if tiene_imagen:
            imagen_html = f'''
        <!-- Imagen de la Experiencia -->
        <div class="imagen-experiencia">
            <img src="{imagen_url}" alt="{giftcard_data['experiencia_nombre']}" class="experiencia-img">
        </div>
        '''

        html_template = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 4px;
            background-color: #f5f5f5;
            line-height: 1.4;
        }}
        .giftcard-container {{
            max-width: 100%;
            width: 100%;
            margin: 0 auto;
            background: linear-gradient(135deg, #fff8e1 0%, #ffffff 100%);
            border: 3px solid #ffc107;
            border-radius: 12px;
            padding: 16px;
            box-sizing: border-box;
            min-height: auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .logo {{
            color: #A0522D;
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 6px;
            word-break: break-word;
            line-height: 1.1;
        }}
        .title {{
            color: #D2B48C;
            font-size: 1.2rem;
            font-weight: 600;
            line-height: 1.2;
        }}
        .imagen-experiencia {{
            width: 100%;
            margin: 16px 0;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .experiencia-img {{
            width: 100%;
            height: auto;
            display: block;
            object-fit: cover;
            max-height: 300px;
        }}
        .divider {{
            border: 0;
            border-top: 2px solid #ffc107;
            margin: 12px 0;
        }}
        .para {{
            text-align: center;
            color: #A0522D;
            font-size: 1rem;
            margin-bottom: 6px;
            font-weight: 500;
        }}
        .destinatario {{
            text-align: center;
            color: #5C4033;
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 16px;
            word-break: break-word;
            line-height: 1.2;
        }}
        .mensaje {{
            background-color: white;
            border-left: 4px solid #ffc107;
            padding: 14px;
            margin: 12px 0;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}
        .mensaje-text {{
            color: #5C4033;
            font-style: italic;
            line-height: 1.5;
            font-size: 1.3rem;
            text-align: left;
            margin: 0;
            font-weight: 500;
        }}
        .details {{
            display: block;
            width: 100%;
            margin: 16px 0;
        }}
        .detail-row {{
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 12px;
        }}
        .detail-section {{
            background-color: rgba(255, 193, 7, 0.08);
            border-radius: 12px;
            padding: 14px;
            margin-bottom: 10px;
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
            font-size: 1.4rem;
            font-weight: 600;
            line-height: 1.4;
            word-break: break-word;
        }}
        .codigo-section {{
            background-color: rgba(255, 193, 7, 0.1);
            border-radius: 12px;
            padding: 16px;
            margin: 16px 0;
            text-align: center;
        }}
        .codigo-label {{
            color: #A0522D;
            font-size: 0.9rem;
            margin-bottom: 6px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .codigo {{
            color: #5C4033;
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 1.3rem;
            font-weight: 700;
            letter-spacing: 1px;
            word-break: break-all;
            line-height: 1.2;
        }}
        .validez {{
            text-align: center;
            margin: 16px 0;
            background-color: rgba(255, 193, 7, 0.08);
            border-radius: 12px;
            padding: 14px;
        }}
        .validez-label {{
            color: #A0522D;
            font-size: 0.9rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }}
        .validez-fecha {{
            color: #5C4033;
            font-size: 1.1rem;
            font-weight: 600;
        }}
        .instrucciones {{
            text-align: center;
            margin: 16px 0;
            padding: 16px;
            background-color: rgba(37, 211, 102, 0.1);
            border-radius: 12px;
            border: 1px solid rgba(37, 211, 102, 0.2);
        }}
        .instrucciones-title {{
            color: #A0522D;
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .whatsapp {{
            color: #25D366;
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 6px;
        }}
        .footer {{
            text-align: center;
            margin-top: 16px;
            padding-top: 12px;
            border-top: 1px solid #D2B48C;
            color: #666;
            font-size: 0.8rem;
            line-height: 1.3;
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
            <div class="logo">AREMKO AGUAS CALIENTES & SPA</div>
            <div class="title">🎁 Certificado de Regalo 🎁</div>
        </div>

        <hr class="divider">

        <!-- Destinatario -->
        <div class="para">Para:</div>
        <div class="destinatario">{giftcard_data['destinatario_nombre']}</div>

        {imagen_html}

        <!-- Mensaje -->
        <div class="mensaje">
            <div class="mensaje-text">{giftcard_data['mensaje_seleccionado']}</div>
        </div>

        <hr class="divider">

        <!-- Experiencia -->
        <div class="details">
            <div class="detail-section">
                <div class="detail-label">EXPERIENCIA</div>
                <div class="detail-value">{giftcard_data['experiencia_nombre']}</div>
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
        if not WEASYPRINT_AVAILABLE:
            logger.warning("WeasyPrint not available - PDF generation disabled")
            return None

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
        if not WEASYPRINT_AVAILABLE:
            logger.warning("WeasyPrint not available - PDF generation disabled")
            return None

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
        Envía un email al comprador con PDFs individuales + PDF resumen para múltiples destinatarios

        Args:
            comprador_email (str): Email del comprador
            comprador_nombre (str): Nombre del comprador
            giftcards_data (list): Lista de diccionarios con datos de GiftCards

        Returns:
            bool: True si se envió correctamente, False si hubo error
        """
        try:
            # Determinar si son múltiples GiftCards
            es_multiple = len(giftcards_data) > 1

            # Preparar el email
            if es_multiple:
                subject = f"🎁 Tus {len(giftcards_data)} GiftCards Aremko están listas"
                mensaje_principal = f"¡Gracias por tu compra de {len(giftcards_data)} GiftCards en Aremko Spa!"
                explicacion_adjuntos = f"""
📎 ARCHIVOS ADJUNTOS:
• Resumen_GiftCards_Aremko.pdf (todas las GiftCards juntas para tu respaldo)
{chr(10).join([f"• GiftCard_{gc['destinatario_nombre'].replace(' ', '_')}.pdf (individual para entregar)" for gc in giftcards_data])}

💡 CÓMO USAR:
✅ Puedes entregar cada archivo individual a su destinatario
✅ O usar el archivo de resumen para imprimir todo junto
✅ Cada PDF contiene las instrucciones de canje
"""
            else:
                subject = f"🎁 Tu GiftCard Aremko está lista"
                mensaje_principal = "¡Gracias por tu compra en Aremko Spa!"
                explicacion_adjuntos = """
📎 ARCHIVO ADJUNTO:
• Tu GiftCard en formato PDF, lista para imprimir o compartir digitalmente
"""

            # Lista de códigos
            lista_codigos = chr(10).join([
                f"• {gc['codigo']} para {gc['destinatario_nombre']} - {gc['experiencia_nombre'][:50]}{'...' if len(gc['experiencia_nombre']) > 50 else ''}"
                for gc in giftcards_data
            ])

            # Mensaje completo del email
            message = f"""Hola {comprador_nombre},

{mensaje_principal}

{'Códigos incluidos' if es_multiple else 'Código incluido'}:
{lista_codigos}
{explicacion_adjuntos}

INSTRUCCIONES DE CANJE:
✅ El destinatario debe contactar por WhatsApp al +56 9 5790 2525
✅ Mencionar su código al momento de reservar
✅ Válido hasta la fecha indicada en cada certificado

¡Gracias por regalar momentos inolvidables en nuestro spa!

AREMKO Aguas Calientes & Spa
Puerto Varas, Chile
WhatsApp: +56 9 5790 2525
www.aremko.cl

---
{'Este email contiene archivos PDF separados para facilitar la entrega individual.' if es_multiple else 'Este email contiene tu certificado de regalo en formato PDF.'}
"""

            # Crear el email
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[comprador_email],
                bcc=['ventas@aremko.cl'],  # Copia oculta a ventas
            )

            # Generar y adjuntar PDFs
            if es_multiple:
                # 1. PDF Resumen con todas las GiftCards
                pdf_resumen = GiftCardPDFService.generar_multiples_pdfs(giftcards_data)
                filename_resumen = f"Resumen_GiftCards_Aremko_{datetime.now().strftime('%Y%m%d')}.pdf"
                email.attach(filename_resumen, pdf_resumen, 'application/pdf')

                # 2. PDFs individuales para cada GiftCard
                for giftcard_data in giftcards_data:
                    pdf_individual = GiftCardPDFService.generar_pdf_giftcard(giftcard_data)
                    # Limpiar nombre del destinatario para nombre de archivo
                    nombre_limpio = giftcard_data['destinatario_nombre'].replace(' ', '_').replace('.', '').replace(',', '')
                    filename_individual = f"GiftCard_{nombre_limpio}_{datetime.now().strftime('%Y%m%d')}.pdf"
                    email.attach(filename_individual, pdf_individual, 'application/pdf')

                logger.info(f"✅ Generados {len(giftcards_data)} PDFs individuales + 1 PDF resumen")
            else:
                # Una sola GiftCard - PDF individual únicamente
                pdf_individual = GiftCardPDFService.generar_pdf_giftcard(giftcards_data[0])
                nombre_limpio = giftcards_data[0]['destinatario_nombre'].replace(' ', '_').replace('.', '').replace(',', '')
                filename_individual = f"GiftCard_{nombre_limpio}_{datetime.now().strftime('%Y%m%d')}.pdf"
                email.attach(filename_individual, pdf_individual, 'application/pdf')

            # Enviar email
            email.send()

            if es_multiple:
                logger.info(f"✅ Email enviado a {comprador_email} (con copia a ventas@aremko.cl) con {len(giftcards_data)} PDFs individuales + 1 resumen")
            else:
                logger.info(f"✅ Email enviado a {comprador_email} (con copia a ventas@aremko.cl) con 1 PDF individual")

            return True

        except Exception as e:
            logger.error(f"❌ Error al enviar email con PDFs de GiftCard: {str(e)}", exc_info=True)
            return False
