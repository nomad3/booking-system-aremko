"""
Función helper para generar el footer legal de emails de marketing.
Cumple con requisitos de SendGrid y regulaciones de email marketing.
"""


def get_email_footer_html(recipient_email=''):
    """
    Retorna el HTML del footer legal para emails de marketing.
    
    Args:
        recipient_email: Email del destinatario para el link de unsubscribe
    
    Returns:
        str: HTML del footer con links de unsubscribe y privacy policy
    """
    unsubscribe_url = f"https://www.aremko.cl/unsubscribe/{recipient_email}/" if recipient_email else "#"
    privacy_url = "https://www.aremko.cl/privacy-policy/"
    
    return f"""
    <div style="margin-top: 40px; padding-top: 30px; border-top: 2px solid #e0e0e0; text-align: center; color: #666; font-size: 13px; line-height: 1.6;">
        <p style="margin: 10px 0;">
            <strong>Aremko Spa</strong><br>
            Rio Pescado Km 4<br>
            Puerto Varas, Región de Los Lagos<br>
            Chile
        </p>
        <p style="margin: 15px 0;">
            📞 +56 9 5790 2525 | 📧 ventas@aremko.cl
        </p>
        <p style="margin: 15px 0; font-size: 12px;">
            Estás recibiendo este correo porque te suscribiste a nuestro boletín o eres cliente de Aremko.
        </p>
        <p style="margin: 15px 0;">
            <a href="{privacy_url}" style="color: #667eea; text-decoration: none; margin: 0 10px;">Política de Privacidad</a> | 
            <a href="{unsubscribe_url}" style="color: #667eea; text-decoration: none; margin: 0 10px;">Darse de baja</a>
        </p>
        <p style="margin: 15px 0; font-size: 11px; color: #999;">
            © 2025 Aremko Spa. Todos los derechos reservados.
        </p>
    </div>
    """


def get_email_footer_text(recipient_email=''):
    """
    Retorna la versión texto plano del footer legal.
    
    Args:
        recipient_email: Email del destinatario para el link de unsubscribe
    
    Returns:
        str: Texto plano del footer
    """
    unsubscribe_url = f"https://www.aremko.cl/unsubscribe/{recipient_email}/" if recipient_email else "https://www.aremko.cl"
    privacy_url = "https://www.aremko.cl/privacy-policy/"
    
    return f"""
---
Aremko Spa
Rio Pescado Km 4
Puerto Varas, Región de Los Lagos, Chile

Teléfono: +56 9 5790 2525
Email: ventas@aremko.cl

Política de Privacidad: {privacy_url}
Darse de baja: {unsubscribe_url}

Estás recibiendo este correo porque te suscribiste a nuestro boletín o eres cliente de Aremko.
"""
