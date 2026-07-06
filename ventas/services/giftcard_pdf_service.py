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

    # Nombres/descripciones para GiftCards ANTIGUAS (vendidas antes del catálogo
    # GiftCardExperiencia en BD, cuando servicio_asociado era una categoría).
    # Las giftcards viven 1 año: este mapa no se puede borrar hasta ~2027.
    EXPERIENCIAS_LEGADO = {
        'tinas': ('Tinas Calientes junto al Río',
                  'Tinas calientes para dos personas, con o sin hidromasaje, junto al Río Pescado.'),
        'masajes': ('Masajes para Dos',
                    'Masajes para dos en domos de bienestar, en medio del antiguo bosque nativo junto al Río Pescado.'),
        'cabanas': ('Alojamiento para Dos',
                    'Alojamiento para dos en cabaña de maderas nativas, en medio del bosque nativo junto al Río Pescado.'),
        'alojamiento_tinas': ('Cabaña + Tinas Calientes',
                              'Alojamiento para dos en cabaña de maderas nativas + tinas calientes, junto al Río Pescado.'),
        'celebracion': ('Celebración Romántica',
                        'Cabaña + tinas calientes con ambientación romántica (velas y espumante) + desayuno.'),
        'monto_libre': ('GiftCard Aremko',
                        'Vale por el monto indicado, para usar en cualquier experiencia de Aremko Spa Boutique.'),
    }

    @staticmethod
    def datos_carta(giftcard):
        """Fuente ÚNICA de los datos que se imprimen en la carta del regalo
        (PDF adjunto, email y descarga). Antes había 4 implementaciones distintas
        (signal, Flow, descarga, vista móvil) y por eso la carta llegaba con
        "Experiencia Aremko Spa" genérico y sin foto.

        Resuelve nombre/descripción/foto desde GiftCardExperiencia por
        id_experiencia SIN filtrar activo (una giftcard vendida vive 1 año y su
        carta debe seguir mostrando la experiencia aunque el catálogo cambie);
        fallback al mapa EXPERIENCIAS_LEGADO para las vendidas antes del catálogo.
        """
        from ..models import GiftCardExperiencia

        sid = giftcard.servicio_asociado or ''
        nombre, descripcion, foto = None, None, ''

        if sid:
            exp = GiftCardExperiencia.objects.filter(id_experiencia=sid).first()
            if exp:
                nombre = exp.nombre
                descripcion = exp.descripcion_giftcard or exp.descripcion
                if exp.imagen:
                    try:
                        foto = exp.imagen.url or ''
                    except Exception:
                        foto = ''
            elif sid in GiftCardPDFService.EXPERIENCIAS_LEGADO:
                nombre, descripcion = GiftCardPDFService.EXPERIENCIAS_LEGADO[sid]

        if not nombre:
            nombre = 'Experiencia Aremko Spa'

        # Foto liviana para la carta: recorte 4:3 + calidad auto, SIN f_auto
        # (WeasyPrint descarga sin header Accept → forzamos que siga siendo JPG).
        if foto.startswith('http') and '/upload/' in foto:
            foto = foto.replace('/upload/', '/upload/c_fill,ar_4:3,g_auto,w_800,q_auto/', 1)
        elif not foto.startswith('http'):
            foto = ''

        return {
            'codigo': giftcard.codigo,
            'experiencia_nombre': nombre,
            'experiencia_descripcion': descripcion,
            'experiencia_imagen_url': foto,
            'destinatario_nombre': giftcard.destinatario_nombre or 'Invitado Especial',
            'mensaje_seleccionado': giftcard.mensaje_personalizado or 'Un regalo especial para ti',
            'precio': giftcard.monto_inicial,
            'fecha_emision': giftcard.fecha_emision,
            'fecha_vencimiento': giftcard.fecha_vencimiento,
        }

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
    def generar_html_giftcard_mobile(giftcard_data):
        """
        Carta del regalo en diseño BOUTIQUE (5.5 x 9.8 pulgadas) — el mismo que
        promete la vitrina /ventas/giftcards/ (mockup mk-card): verde bosque,
        nombre de la experiencia como título, dedicatoria en cursiva y el
        beneficio "válida cualquier día" visible. Rediseño 2026-07-06; el diseño
        amarillo anterior no coincidía con la marca boutique.

        OJO WeasyPrint: sin emojis (el server no tiene fuente de emojis → tofu),
        sin f_auto en fotos (descarga sin Accept → JPG seguro).
        """

        # Obtener URL de la imagen si existe
        imagen_url = giftcard_data.get('experiencia_imagen_url', '')
        # Validar que la URL sea válida y comience con http (imagen real de Cloudinary)
        tiene_imagen = bool(imagen_url) and (imagen_url.startswith('http://') or imagen_url.startswith('https://'))

        # Generar HTML de la imagen si existe - optimizado para móvil
        imagen_html = ''
        if tiene_imagen:
            imagen_html = f'''
        <div class="foto-experiencia">
            <img src="{imagen_url}" alt="" class="foto-img">
        </div>
        '''

        descripcion = (giftcard_data.get('experiencia_descripcion') or '').strip()
        descripcion_html = f'<div class="exp-desc">{descripcion}</div>' if descripcion else ''

        html_template = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* Carta boutique — reset base para móvil/PDF */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        @page {{
            size: 5.5in 9.8in;
            margin: 0.15in;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            background: #ffffff;
            width: 5.2in;
            height: 9.5in;
            font-size: 12pt;
            line-height: 1.35;
            page-break-inside: avoid;
            page-break-after: avoid;
        }}

        /* La carta: verde bosque, mismos tonos del mockup de la vitrina (mk-card) */
        .carta {{
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            background: linear-gradient(160deg, #10231d 0%, #1e4438 100%);
            border-radius: 18px;
            padding: 0.3in 0.28in 0.22in;
            color: #f3efe6;
            text-align: center;
            overflow: hidden;
        }}

        .marca {{
            font-size: 11pt;
            letter-spacing: 4px;
            text-transform: uppercase;
            color: #cdbf9d;
            font-weight: 600;
        }}

        .tipo {{
            font-size: 8.5pt;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: #9db8ab;
            margin-top: 3px;
        }}

        .exp-nombre {{
            font-size: 21pt;
            font-weight: 700;
            color: #ffffff;
            line-height: 1.15;
            margin-top: 0.16in;
        }}

        .exp-para {{
            font-size: 12pt;
            color: #bcd3c8;
            margin-top: 4px;
        }}

        .foto-experiencia {{
            width: 100%;
            height: 1.85in;
            border-radius: 12px;
            overflow: hidden;
            margin-top: 0.14in;
        }}

        .foto-img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }}

        .dedicatoria {{
            font-style: italic;
            font-size: 12pt;
            line-height: 1.55;
            color: #e8e2d2;
            border-top: 1px solid rgba(255, 255, 255, 0.16);
            border-bottom: 1px solid rgba(255, 255, 255, 0.16);
            padding: 0.13in 0.05in;
            margin-top: 0.15in;
        }}

        .code-label {{
            font-size: 8.5pt;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: #9db8ab;
            margin-top: 0.16in;
        }}

        .code-value {{
            font-family: 'SF Mono', Menlo, Monaco, 'Courier New', monospace;
            font-size: 18pt;
            font-weight: 700;
            letter-spacing: 3px;
            color: #ffffff;
            background: rgba(255, 255, 255, 0.07);
            border: 1px solid rgba(205, 191, 157, 0.45);
            border-radius: 12px;
            padding: 0.11in 0.08in;
            margin-top: 6px;
            word-break: break-all;
        }}

        .beneficio {{
            font-size: 10pt;
            font-weight: 600;
            color: #cdbf9d;
            margin-top: 0.13in;
        }}

        .validez {{
            font-size: 9pt;
            color: #9db8ab;
            margin-top: 2px;
        }}

        .exp-desc {{
            font-size: 9.5pt;
            line-height: 1.5;
            color: #bcd3c8;
            margin-top: 0.12in;
            padding: 0 0.06in;
        }}

        .whatsapp {{
            background: rgba(37, 211, 102, 0.12);
            border: 1px solid rgba(37, 211, 102, 0.45);
            border-radius: 12px;
            padding: 0.12in;
            margin-top: 0.15in;
        }}

        .ws-label {{
            font-size: 8.5pt;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: #7fe0a8;
            font-weight: 600;
        }}

        .ws-numero {{
            font-size: 15pt;
            font-weight: 800;
            color: #ffffff;
            margin-top: 2px;
        }}

        .ws-nota {{
            font-size: 8.5pt;
            color: #bcd3c8;
            margin-top: 2px;
        }}

        .footer {{
            margin-top: auto;
            padding-top: 0.12in;
        }}

        .footer-lema {{
            font-size: 9.5pt;
            font-style: italic;
            color: #cdbf9d;
        }}

        .footer-datos {{
            font-size: 8pt;
            color: #8fa89b;
            margin-top: 3px;
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <div class="carta">
        <div class="marca">Aremko Spa Boutique</div>
        <div class="tipo">Certificado de Regalo</div>

        <div class="exp-nombre">{giftcard_data['experiencia_nombre']}</div>
        <div class="exp-para">para {giftcard_data['destinatario_nombre']}</div>

        {imagen_html}

        <div class="dedicatoria">"{giftcard_data['mensaje_seleccionado']}"</div>

        <div class="code-label">Tu código</div>
        <div class="code-value">{giftcard_data['codigo']}</div>

        <div class="beneficio">Válida cualquier día de la semana — incluso viernes y sábado</div>
        <div class="validez">Hasta el {giftcard_data['fecha_vencimiento'].strftime('%d/%m/%Y')}</div>

        {descripcion_html}

        <div class="whatsapp">
            <div class="ws-label">Reserva por WhatsApp</div>
            <div class="ws-numero">+56 9 5790 2525</div>
            <div class="ws-nota">Menciona tu código al reservar</div>
        </div>

        <div class="footer">
            <div class="footer-lema">Aguas calientes junto al río</div>
            <div class="footer-datos">www.aremko.cl · Puerto Varas · Emitido: {giftcard_data['fecha_emision'].strftime('%d/%m/%Y')}</div>
        </div>
    </div>
</body>
</html>
"""
        return html_template

    @staticmethod
    def generar_pdf_giftcard(giftcard_data, formato='mobile'):
        """
        Genera un PDF a partir de los datos de la GiftCard

        Args:
            giftcard_data (dict): Datos de la GiftCard
            formato (str): 'mobile' para 5.5x9.8 pulgadas, 'a4' para formato tradicional

        Returns:
            bytes: Contenido del PDF en bytes
        """
        if not WEASYPRINT_AVAILABLE:
            logger.warning("WeasyPrint not available - PDF generation disabled")
            return None

        try:
            # Seleccionar template según formato
            if formato == 'mobile':
                html_content = GiftCardPDFService.generar_html_giftcard_mobile(giftcard_data)
                # No necesita CSS adicional, todo está inline
                css_pdf = None
            else:
                # Formato A4 tradicional
                html_content = GiftCardPDFService.generar_html_giftcard(giftcard_data)
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
            if css_pdf:
                pdf_bytes = html_doc.write_pdf(
                    stylesheets=[css_pdf],
                    font_config=font_config
                )
            else:
                pdf_bytes = html_doc.write_pdf(font_config=font_config)

            logger.info(f"✅ PDF generado exitosamente para GiftCard {giftcard_data['codigo']} (formato: {formato})")
            return pdf_bytes

        except Exception as e:
            logger.error(f"❌ Error generando PDF para GiftCard {giftcard_data.get('codigo', 'N/A')}: {str(e)}", exc_info=True)
            raise e

    @staticmethod
    def generar_multiples_pdfs(giftcards_data, formato='mobile'):
        """
        Genera múltiples PDFs de GiftCards y los combina en un solo archivo

        Args:
            giftcards_data (list): Lista de datos de GiftCards
            formato (str): 'mobile' para 5.5x9.8 pulgadas, 'a4' para formato tradicional

        Returns:
            bytes: Contenido del PDF combinado en bytes
        """
        if not WEASYPRINT_AVAILABLE:
            logger.warning("WeasyPrint not available - PDF generation disabled")
            return None

        try:
            # Si es solo una GiftCard, usar función simple
            if len(giftcards_data) == 1:
                return GiftCardPDFService.generar_pdf_giftcard(giftcards_data[0], formato=formato)

            # Para múltiples GiftCards, combinar HTML
            html_content = ""
            for i, giftcard_data in enumerate(giftcards_data):
                if formato == 'mobile':
                    html_content += GiftCardPDFService.generar_html_giftcard_mobile(giftcard_data)
                else:
                    html_content += GiftCardPDFService.generar_html_giftcard(giftcard_data)
                # Agregar salto de página entre gift cards (excepto la última)
                if i < len(giftcards_data) - 1:
                    html_content += '<div style="page-break-after: always;"></div>'

            # CSS para múltiples páginas según formato
            if formato == 'mobile':
                # No necesita CSS adicional para móvil, todo está inline
                css_pdf = None
            else:
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
            if css_pdf:
                pdf_bytes = html_doc.write_pdf(
                    stylesheets=[css_pdf],
                    font_config=font_config
                )
            else:
                pdf_bytes = html_doc.write_pdf(font_config=font_config)

            logger.info(f"✅ PDF combinado generado exitosamente para {len(giftcards_data)} GiftCards (formato: {formato})")
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

            # Crear HTML para el email con botón de vista móvil
            from django.conf import settings
            base_url = getattr(settings, 'BASE_URL', 'https://www.aremko.cl')

            # Generar HTML del email
            email_html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(160deg, #10231d 0%, #1e4438 100%); color: #f3efe6; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
        .logo {{ font-size: 22px; font-weight: 700; letter-spacing: 4px; text-transform: uppercase; color: #cdbf9d; margin-bottom: 6px; }}
        .lema {{ font-size: 13px; font-style: italic; color: #9db8ab; margin-bottom: 12px; }}
        .content {{ background: white; padding: 30px; border: 1px solid #e0e0e0; border-radius: 0 0 10px 10px; }}
        .greeting {{ font-size: 18px; color: #5C4033; margin-bottom: 20px; }}
        .gift-list {{ background: #f8f4e6; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .gift-item {{ background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #cdbf9d; }}
        .code {{ font-family: monospace; font-size: 16px; font-weight: bold; color: #1e4438; letter-spacing: 1px; }}
        .btn-container {{ text-align: center; margin: 30px 0; }}
        .btn {{ display: inline-block; padding: 15px 30px; margin: 10px; text-decoration: none; border-radius: 25px; font-weight: 600; }}
        .btn-primary {{ background: linear-gradient(135deg, #25D366 0%, #128C7E 100%); color: white; }}
        .btn-secondary {{ background: #A0522D; color: white; }}
        .instructions {{ background: rgba(37, 211, 102, 0.1); padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .footer {{ text-align: center; color: #666; font-size: 14px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; }}
        .attachment-note {{ background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border: 1px solid #ffc107; }}
        @media (max-width: 600px) {{
            .container {{ padding: 10px; }}
            .content {{ padding: 20px; }}
            .btn {{ display: block; margin: 10px 0; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">Aremko Spa Boutique</div>
            <div class="lema">Aguas calientes junto al río</div>
            <div>🎁 {'Tus GiftCards están listas' if es_multiple else 'Tu GiftCard está lista'}</div>
        </div>

        <div class="content">
            <div class="greeting">Hola {comprador_nombre},</div>

            <p>{mensaje_principal}</p>

            <div class="gift-list">
                <h3 style="margin-top: 0;">{'📋 GiftCards incluidas:' if es_multiple else '📋 GiftCard incluida:'}</h3>
"""

            # Agregar cada GiftCard
            for gc in giftcards_data:
                email_html += f"""
                <div class="gift-item">
                    <strong>{gc['destinatario_nombre']}</strong><br>
                    Código: <span class="code">{gc['codigo']}</span><br>
                    Experiencia: {gc['experiencia_nombre']}
                </div>
"""

            email_html += f"""
            </div>

            <div class="btn-container">
                <a href="https://wa.me/56957902525" class="btn btn-primary">
                    💬 Contactar por WhatsApp
                </a>
            </div>

            <div class="attachment-note">
                <strong>📎 Archivos adjuntos:</strong><br>
                {explicacion_adjuntos.replace(chr(10), '<br>')}
            </div>

            <div class="instructions">
                <h3 style="margin-top: 0;">📝 Instrucciones de canje:</h3>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li>Abrir el PDF adjunto (puedes imprimirlo o enviarlo digitalmente)</li>
                    <li>Contactar por WhatsApp al <strong>+56 9 5790 2525</strong></li>
                    <li>Mencionar el código al momento de reservar</li>
                    <li><strong>Válida cualquier día de la semana — incluso viernes y sábado</strong></li>
                    <li>Vigencia hasta la fecha indicada en cada certificado</li>
                </ul>
            </div>

            <p style="text-align: center; font-size: 18px; color: #5C4033; margin: 30px 0;">
                <strong>¡Gracias por regalar momentos inolvidables!</strong>
            </p>
        </div>

        <div class="footer">
            <strong>Aremko Spa Boutique</strong> · Aguas calientes junto al río<br>
            Puerto Varas, Chile<br>
            📱 WhatsApp: +56 9 5790 2525<br>
            🌐 <a href="https://www.aremko.cl" style="color: #1e4438;">www.aremko.cl</a><br><br>
            <small>Este email fue enviado porque realizaste una compra de GiftCard en nuestro spa.</small>
        </div>
    </div>
</body>
</html>
"""

            # Mensaje de texto plano como fallback
            message = f"""Hola {comprador_nombre},

{mensaje_principal}

{'Códigos incluidos' if es_multiple else 'Código incluido'}:
{lista_codigos}

{explicacion_adjuntos}

INSTRUCCIONES DE CANJE:
✅ Abrir el PDF adjunto (puedes imprimirlo o enviarlo digitalmente)
✅ Contactar por WhatsApp al +56 9 5790 2525
✅ Mencionar el código al momento de reservar
✅ Válido hasta la fecha indicada en cada certificado

Recuerda: la GiftCard es válida cualquier día de la semana — incluso viernes y sábado.

¡Gracias por regalar momentos inolvidables junto al río!

Aremko Spa Boutique — Aguas calientes junto al río
Puerto Varas, Chile
WhatsApp: +56 9 5790 2525
www.aremko.cl

---
{'Este email contiene archivos PDF separados para facilitar la entrega individual.' if es_multiple else 'Este email contiene tu certificado de regalo en formato PDF.'}
"""

            # Crear el email con contenido HTML
            from django.core.mail import EmailMultiAlternatives
            from ventas.utils.email_footer import get_email_footer_html

            # Agregar footer con link de unsubscribe
            email_html_con_footer = email_html + get_email_footer_html(comprador_email)

            email = EmailMultiAlternatives(
                subject=subject,
                body=message,  # Texto plano como fallback
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[comprador_email],
                bcc=['ventas@aremko.cl'],  # Copia oculta a ventas
            )

            # Agregar contenido HTML
            email.attach_alternative(email_html_con_footer, "text/html")

            # Generar y adjuntar PDFs - usando formato móvil por defecto
            if es_multiple:
                # 1. PDF Resumen con todas las GiftCards (formato móvil)
                pdf_resumen = GiftCardPDFService.generar_multiples_pdfs(giftcards_data, formato='mobile')
                filename_resumen = f"Resumen_GiftCards_Aremko_{datetime.now().strftime('%Y%m%d')}.pdf"
                email.attach(filename_resumen, pdf_resumen, 'application/pdf')

                # 2. PDFs individuales para cada GiftCard (formato móvil)
                for giftcard_data in giftcards_data:
                    pdf_individual = GiftCardPDFService.generar_pdf_giftcard(giftcard_data, formato='mobile')
                    # Limpiar nombre del destinatario para nombre de archivo
                    nombre_limpio = giftcard_data['destinatario_nombre'].replace(' ', '_').replace('.', '').replace(',', '')
                    filename_individual = f"GiftCard_{nombre_limpio}_{datetime.now().strftime('%Y%m%d')}.pdf"
                    email.attach(filename_individual, pdf_individual, 'application/pdf')

                logger.info(f"✅ Generados {len(giftcards_data)} PDFs individuales + 1 PDF resumen (formato móvil)")
            else:
                # Una sola GiftCard - PDF individual únicamente (formato móvil)
                pdf_individual = GiftCardPDFService.generar_pdf_giftcard(giftcards_data[0], formato='mobile')
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
