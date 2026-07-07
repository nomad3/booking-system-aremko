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

    # Estética alineada al diseño boutique (paleta verde bosque + dorado arena)
    # para que combine con los cuerpos de campaña tipo
    # templates/emails/campana_experiencias_invierno_2026.html.
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#ede7db" style="background-color:#ede7db;">
      <tr>
        <td align="center" style="padding:0 12px 34px 12px;">
          <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;">
            <tr>
              <td style="padding:26px 30px 0 30px;text-align:center;font-family:Arial,Helvetica,sans-serif;color:#6b7a70;font-size:12px;line-height:20px;">
                <div style="font-family:Georgia,'Times New Roman',serif;font-size:15px;letter-spacing:4px;color:#10231d;padding-bottom:10px;">AREMKO</div>
                Ruta R&iacute;o Pescado Km 4 &middot; Puerto Varas, Regi&oacute;n de Los Lagos, Chile<br>
                +56 9 5790 2525 &middot; ventas@aremko.cl
                <p style="margin:14px 0 0 0;font-size:11px;color:#8a978e;">
                    Recibes este correo porque eres cliente de Aremko o te suscribiste a nuestro bolet&iacute;n.
                </p>
                <p style="margin:14px 0 0 0;">
                    <a href="{privacy_url}" style="color:#7d6c42;text-decoration:underline;margin:0 8px;">Pol&iacute;tica de privacidad</a> &middot;
                    <a href="{unsubscribe_url}" style="color:#7d6c42;text-decoration:underline;margin:0 8px;">Darse de baja</a>
                </p>
                <p style="margin:14px 0 0 0;font-size:10px;color:#a5b0a8;">
                    &copy; 2026 Aremko Spa Boutique. Todos los derechos reservados.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
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
