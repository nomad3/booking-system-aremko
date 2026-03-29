#!/usr/bin/env python
"""
Script completo de diagnóstico para SendGrid
Requiere: pip install requests
Ejecutar en shell de Render: python scripts/diagnostics/test_sendgrid_full.py
"""

import os
import sys
import json
from datetime import datetime

def print_section(title):
    """Imprime un separador de sección"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def check_environment_variables():
    """Verifica las variables de entorno necesarias para SendGrid"""

    print_section("VERIFICACIÓN DE VARIABLES DE ENTORNO")

    # Variables comunes de SendGrid
    possible_vars = [
        'SENDGRID_API_KEY',
        'SENDGRID_API_KEY_ID',
        'SENDGRID_SECRET',
        'EMAIL_HOST',
        'EMAIL_HOST_USER',
        'EMAIL_HOST_PASSWORD',
        'DEFAULT_FROM_EMAIL',
        'SERVER_EMAIL',
    ]

    found_vars = {}
    sendgrid_key = None

    for var in possible_vars:
        value = os.getenv(var)
        if value:
            if 'key' in var.lower() or 'password' in var.lower() or 'secret' in var.lower():
                # Ocultar valores sensibles
                print(f"✅ {var}: [CONFIGURADO - {len(value)} caracteres]")
                if 'sendgrid' in var.lower() and 'key' in var.lower():
                    sendgrid_key = value
            else:
                print(f"✅ {var}: {value}")
            found_vars[var] = value
        else:
            print(f"❌ {var}: NO CONFIGURADO")

    # Verificar si está configurado como SMTP
    if os.getenv('EMAIL_HOST') == 'smtp.sendgrid.net':
        print("\n📧 Configuración detectada: SendGrid via SMTP")
        print("   Host: smtp.sendgrid.net")
        print("   Puerto: 587 (TLS) o 465 (SSL)")
        print("   Usuario: apikey (literal)")
        print("   Contraseña: Tu API Key de SendGrid")

    return sendgrid_key or os.getenv('EMAIL_HOST_PASSWORD'), found_vars

def test_sendgrid_api(api_key):
    """Prueba la API de SendGrid directamente"""

    try:
        import requests
    except ImportError:
        print("\n⚠️  Módulo 'requests' no disponible")
        print("   La prueba de API requiere: pip install requests")
        return False

    print_section("TEST DE API DE SENDGRID")

    if not api_key:
        print("❌ No se encontró API Key de SendGrid")
        return False

    # Verificar que la API key tenga el formato correcto
    if not api_key.startswith('SG.'):
        print("⚠️  La API Key no parece tener el formato correcto de SendGrid (debe empezar con 'SG.')")

    print(f"API Key detectada: {api_key[:10]}... ({len(api_key)} caracteres)")

    # Test 1: Verificar la autenticación
    print("\n1. Verificando autenticación con SendGrid...")

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    try:
        # Endpoint para verificar el API key
        response = requests.get(
            'https://api.sendgrid.com/v3/scopes',
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            print("✅ Autenticación exitosa!")
            scopes = response.json().get('scopes', [])
            print(f"   Permisos disponibles: {len(scopes)} scopes")
            if 'mail.send' in scopes:
                print("   ✅ Permiso para enviar correos: SÍ")
            else:
                print("   ❌ Permiso para enviar correos: NO")
                print("      La API key necesita el permiso 'mail.send'")
        elif response.status_code == 401:
            print("❌ API Key inválida o sin permisos")
            print(f"   Respuesta: {response.text}")
            return False
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("❌ Timeout al conectar con SendGrid")
        return False
    except Exception as e:
        print(f"❌ Error al conectar con API: {e}")
        return False

    # Test 2: Obtener información de la cuenta
    print("\n2. Obteniendo información de la cuenta...")

    try:
        response = requests.get(
            'https://api.sendgrid.com/v3/user/profile',
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            profile = response.json()
            print("✅ Información de cuenta obtenida:")
            print(f"   Email: {profile.get('email', 'N/A')}")
            print(f"   Nombre: {profile.get('first_name', '')} {profile.get('last_name', '')}")
        else:
            print(f"⚠️  No se pudo obtener perfil: {response.status_code}")

    except Exception as e:
        print(f"⚠️  Error al obtener perfil: {e}")

    # Test 3: Verificar estadísticas recientes
    print("\n3. Verificando actividad reciente...")

    try:
        # Obtener estadísticas de los últimos 7 días
        response = requests.get(
            'https://api.sendgrid.com/v3/stats',
            headers=headers,
            params={'aggregated_by': 'day', 'limit': 7},
            timeout=10
        )

        if response.status_code == 200:
            stats = response.json()
            if stats:
                print("✅ Estadísticas recientes:")
                total_sent = sum(day['stats'][0]['metrics'].get('requests', 0) for day in stats if day.get('stats'))
                total_delivered = sum(day['stats'][0]['metrics'].get('delivered', 0) for day in stats if day.get('stats'))
                total_bounces = sum(day['stats'][0]['metrics'].get('bounces', 0) for day in stats if day.get('stats'))

                print(f"   Correos enviados (últimos 7 días): {total_sent}")
                print(f"   Correos entregados: {total_delivered}")
                print(f"   Rebotes: {total_bounces}")
            else:
                print("   No hay actividad reciente")

    except Exception as e:
        print(f"⚠️  Error al obtener estadísticas: {e}")

    return True

def test_smtp_sendgrid(api_key):
    """Prueba la conexión SMTP de SendGrid"""

    print_section("TEST DE CONEXIÓN SMTP CON SENDGRID")

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = 'smtp.sendgrid.net'
    smtp_port = 587
    smtp_user = 'apikey'  # Siempre es 'apikey' para SendGrid
    smtp_password = api_key

    print(f"Host: {smtp_host}")
    print(f"Puerto: {smtp_port}")
    print(f"Usuario: {smtp_user}")
    print(f"Password: {smtp_password[:10]}... ({len(smtp_password)} caracteres)")

    if not smtp_password:
        print("❌ No hay API Key configurada")
        return False

    try:
        print("\nConectando con SendGrid SMTP...")
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.set_debuglevel(1)  # Debug activado

        print("Iniciando TLS...")
        server.starttls()

        print("Autenticando...")
        server.login(smtp_user, smtp_password)

        print("✅ Conexión SMTP exitosa!")
        server.quit()
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Error de autenticación: {e}")
        print("\nPosibles causas:")
        print("1. API Key incorrecta o expirada")
        print("2. API Key sin permisos de envío")
        print("3. Cuenta de SendGrid suspendida")

    except Exception as e:
        print(f"❌ Error: {e}")

    return False

def send_test_email_api(api_key):
    """Envía un correo de prueba usando la API de SendGrid"""

    try:
        import requests
    except ImportError:
        print("\n⚠️  No se puede enviar correo via API sin 'requests'")
        return send_test_email_smtp(api_key)

    print_section("ENVÍO DE CORREO DE PRUEBA (API)")

    if not api_key:
        print("❌ No se puede enviar sin API Key")
        return False

    # Solicitar información
    from_email = input("Correo remitente (Enter para usar ventas@aremko.cl): ").strip()
    if not from_email:
        from_email = "ventas@aremko.cl"

    to_email = input("Correo destino para la prueba: ").strip()
    if not to_email:
        print("❌ Correo destino requerido")
        return False

    # Preparar el mensaje
    message = {
        "personalizations": [
            {
                "to": [{"email": to_email}],
                "subject": f"Prueba SendGrid - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        ],
        "from": {"email": from_email, "name": "Sistema Aremko"},
        "content": [
            {
                "type": "text/plain",
                "value": f"""
Este es un correo de prueba enviado desde el script de diagnóstico de SendGrid.

Configuración utilizada:
- API: SendGrid
- Remitente: {from_email}
- Fecha: {datetime.now()}

Si recibes este mensaje, SendGrid está funcionando correctamente.
                """
            },
            {
                "type": "text/html",
                "value": f"""
<html>
<body>
    <h2>Prueba de SendGrid</h2>
    <p>Este es un correo de prueba enviado desde el script de diagnóstico de SendGrid.</p>

    <h3>Configuración utilizada:</h3>
    <ul>
        <li><b>API:</b> SendGrid</li>
        <li><b>Remitente:</b> {from_email}</li>
        <li><b>Fecha:</b> {datetime.now()}</li>
    </ul>

    <p style="color: green;">
        ✅ Si recibes este mensaje, SendGrid está funcionando correctamente.
    </p>
</body>
</html>
                """
            }
        ]
    }

    # Enviar
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    print(f"\nEnviando correo de {from_email} a {to_email}...")

    try:
        response = requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            headers=headers,
            json=message,
            timeout=10
        )

        if response.status_code == 202:
            print("✅ Correo enviado exitosamente!")
            print(f"   Message ID: {response.headers.get('X-Message-Id', 'N/A')}")
            print("   Revisa la bandeja de entrada (y SPAM)")
            return True
        else:
            print(f"❌ Error al enviar: {response.status_code}")
            print(f"   Respuesta: {response.text}")

            # Decodificar errores si es JSON
            try:
                errors = response.json()
                if 'errors' in errors:
                    for error in errors['errors']:
                        print(f"   - {error.get('message', error)}")
            except:
                pass

    except Exception as e:
        print(f"❌ Error al enviar: {e}")

    return False

def send_test_email_smtp(api_key):
    """Envía correo de prueba via SMTP como alternativa"""

    print_section("ENVÍO DE CORREO DE PRUEBA (SMTP)")

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    from_email = input("Correo remitente (Enter para ventas@aremko.cl): ").strip() or "ventas@aremko.cl"
    to_email = input("Correo destino: ").strip()

    if not to_email:
        print("❌ Correo destino requerido")
        return False

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = f"Prueba SendGrid SMTP - {datetime.now().strftime('%H:%M')}"

    body = f"""
Correo de prueba enviado via SMTP.

Si recibes este mensaje, SendGrid está funcionando.

Fecha: {datetime.now()}
Remitente: {from_email}
    """
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.sendgrid.net', 587)
        server.starttls()
        server.login('apikey', api_key)
        server.send_message(msg)
        server.quit()
        print("✅ Correo enviado!")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_django_settings():
    """Muestra configuración recomendada para Django con SendGrid"""

    print_section("CONFIGURACIÓN PARA DJANGO")

    print("\n1. OPCIÓN A: SendGrid via SMTP (en settings.py):")
    print("""
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.sendgrid.net'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = 'apikey'  # Siempre 'apikey' para SendGrid
    EMAIL_HOST_PASSWORD = os.environ.get('SENDGRID_API_KEY')
    DEFAULT_FROM_EMAIL = 'ventas@aremko.cl'
    SERVER_EMAIL = 'ventas@aremko.cl'
    """)

    print("\n2. OPCIÓN B: SendGrid via API (usando django-sendgrid-v5):")
    print("""
    # Instalar: pip install django-sendgrid-v5

    EMAIL_BACKEND = 'sendgrid_backend.SendgridBackend'
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    SENDGRID_SANDBOX_MODE_IN_DEBUG = False
    DEFAULT_FROM_EMAIL = 'ventas@aremko.cl'
    """)

    print("\n3. VARIABLES DE ENTORNO EN RENDER:")
    print("""
    SENDGRID_API_KEY = SG.xxxxx...  (tu API key completa)
    DEFAULT_FROM_EMAIL = ventas@aremko.cl
    """)

    print("\n4. VERIFICAR EN SENDGRID:")
    print("   - Dominio verificado (aremko.cl)")
    print("   - Sender Authentication configurado")
    print("   - API Key con permisos de 'Mail Send'")
    print("   - Límites de envío no excedidos")

def main():
    """Función principal"""

    print("\n" + "="*60)
    print(" DIAGNÓSTICO DE SENDGRID PARA ventas@aremko.cl")
    print("="*60)

    # Verificar variables y obtener API key
    api_key, vars_found = check_environment_variables()

    if not api_key:
        print("\n❌ No se encontró API Key de SendGrid")
        print("   Busqué en: SENDGRID_API_KEY, EMAIL_HOST_PASSWORD")
        print("   Configúrala en las variables de entorno de Render")

        # Mostrar configuración recomendada
        check_django_settings()
        return

    # Probar la API (si requests está disponible)
    api_ok = test_sendgrid_api(api_key)

    # Siempre probar SMTP
    smtp_ok = test_smtp_sendgrid(api_key)

    if api_ok or smtp_ok:
        # Ofrecer enviar correo de prueba
        print("\n¿Deseas enviar un correo de prueba? (s/n): ", end="")
        if input().strip().lower() == 's':
            if api_ok:
                send_test_email_api(api_key)
            else:
                send_test_email_smtp(api_key)

    # Mostrar configuración de Django
    check_django_settings()

    # Resumen final
    print_section("RESUMEN Y PRÓXIMOS PASOS")

    if api_ok or smtp_ok:
        print("✅ La conexión con SendGrid funciona")
        print("\nSi los correos no se envían desde la aplicación:")
        print("1. Verifica que Django use las mismas variables de entorno")
        print("2. Revisa los logs de la aplicación en Render")
        print("3. Verifica el dominio remitente en SendGrid")
        print("4. Revisa los Activity Feed en SendGrid Dashboard")
    else:
        print("❌ Problemas detectados con SendGrid")
        print("\n1. Verifica o regenera tu API Key en SendGrid")
        print("2. Asegúrate de que tenga permisos de 'Mail Send'")
        print("3. Verifica el dominio en Sender Authentication")
        print("4. Revisa si la cuenta no está suspendida")

    print("\n📊 Panel de SendGrid: https://app.sendgrid.com/")
    print("📧 Activity Feed: https://app.sendgrid.com/email_activity")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScript interrumpido")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()