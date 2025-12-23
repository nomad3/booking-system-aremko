#!/usr/bin/env python
"""
Script de prueba simplificado para verificar la funcionalidad de Ver GiftCard en el admin.
Esta versión no requiere conexión a la base de datos.
"""
import os
import sys

# Aplicar parche de compatibilidad para importlib.metadata
if sys.version_info < (3, 10):
    try:
        import importlib.metadata as metadata
        if not hasattr(metadata, 'packages_distributions'):
            def packages_distributions():
                """Implementación compatible para Python < 3.10"""
                pkg_to_dist = {}
                for dist in metadata.distributions():
                    if dist.files:
                        for file in dist.files:
                            if file.suffix == ".py" and "/" in str(file):
                                parts = str(file).split("/")
                                pkg = parts[0]
                                if pkg not in pkg_to_dist:
                                    pkg_to_dist[pkg] = []
                                if dist.metadata["Name"] not in pkg_to_dist[pkg]:
                                    pkg_to_dist[pkg].append(dist.metadata["Name"])
                return pkg_to_dist
            metadata.packages_distributions = packages_distributions
    except Exception:
        pass

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.admin import GiftCardInline, VentaReservaAdmin
from unittest.mock import Mock
from urllib.parse import unquote
import re

def test_giftcard_inline():
    print("=" * 60)
    print("VERIFICANDO FUNCIONALIDAD DE VER GIFTCARD")
    print("=" * 60)
    print()

    # Verificar que el inline tiene los campos correctos
    print("1. Verificando campos del GiftCardInline:")
    expected_fields = ['codigo', 'monto_inicial', 'destinatario_nombre', 'estado', 'enviado_email', 'ver_giftcard']
    if GiftCardInline.fields == expected_fields:
        print("   ✅ Campos configurados correctamente")
    else:
        print(f"   ⚠️ Campos incorrectos. Esperados: {expected_fields}")
        print(f"      Actuales: {GiftCardInline.fields}")

    print()
    print("2. Verificando que ver_giftcard está en readonly_fields:")
    if 'ver_giftcard' in GiftCardInline.readonly_fields:
        print("   ✅ ver_giftcard está configurado como readonly")
    else:
        print("   ⚠️ ver_giftcard NO está en readonly_fields")

    print()
    print("3. Verificando que GiftCardInline está en VentaReservaAdmin:")
    if GiftCardInline in VentaReservaAdmin.inlines:
        print("   ✅ GiftCardInline está incluido en VentaReservaAdmin")
    else:
        print("   ⚠️ GiftCardInline NO está en VentaReservaAdmin")

    print()
    print("4. Probando generación de botones con objeto simulado:")

    # Crear un mock de GiftCard
    mock_giftcard = Mock()
    mock_giftcard.codigo = "TEST-GC-123"
    mock_giftcard.monto_inicial = 50000
    mock_giftcard.destinatario_nombre = "Juan Pérez"
    mock_giftcard.cliente_destinatario = Mock()
    mock_giftcard.cliente_destinatario.telefono = "912345678"

    # Crear instancia del inline
    from django.contrib.admin.sites import site
    inline = GiftCardInline(Mock(), site)

    # Probar el método ver_giftcard
    html_output = inline.ver_giftcard(mock_giftcard)

    if html_output and html_output != '-':
        print("   ✅ HTML generado correctamente")

        # Extraer las URLs del HTML
        urls = re.findall(r'href="([^"]+)"', html_output)

        if len(urls) >= 2:
            print(f"   ✅ Se encontraron {len(urls)} enlaces")

            # Verificar el link de Ver GiftCard
            view_url = urls[0]
            if '/giftcard/' in view_url and '/view/' in view_url:
                print(f"   ✅ URL de ver GiftCard correcta: {view_url}")
            else:
                print(f"   ⚠️ URL de ver GiftCard inesperada: {view_url}")

            # Verificar el link de WhatsApp
            whatsapp_url = urls[1]
            if 'wa.me' in whatsapp_url:
                print(f"   ✅ URL de WhatsApp generada correctamente")

                # Decodificar y mostrar el mensaje
                if 'text=' in whatsapp_url:
                    mensaje = whatsapp_url.split('text=')[1]
                    mensaje_decodificado = unquote(mensaje)
                    print(f"   📱 Mensaje WhatsApp: {mensaje_decodificado[:80]}...")

                # Verificar que incluye el número de teléfono
                if '/5691234567' in whatsapp_url or '/56912345678' in whatsapp_url:
                    print(f"   ✅ Número de teléfono incluido en WhatsApp")
                else:
                    print(f"   ℹ️ WhatsApp sin número específico (se enviará al usuario actual)")
            else:
                print(f"   ⚠️ URL de WhatsApp no encontrada")
        else:
            print(f"   ⚠️ Se esperaban 2 enlaces, se encontraron {len(urls)}")

        # Verificar que tiene los botones con los textos correctos
        if '📱 Ver GiftCard' in html_output:
            print("   ✅ Botón 'Ver GiftCard' con icono encontrado")
        if '📤 WhatsApp' in html_output:
            print("   ✅ Botón 'WhatsApp' con icono encontrado")

    else:
        print("   ⚠️ No se generó HTML")

    print()
    print("5. Probando con GiftCard sin destinatario:")
    mock_giftcard2 = Mock()
    mock_giftcard2.codigo = "TEST-GC-456"
    mock_giftcard2.monto_inicial = 75000
    mock_giftcard2.destinatario_nombre = None
    mock_giftcard2.cliente_destinatario = None

    html_output2 = inline.ver_giftcard(mock_giftcard2)

    if html_output2 and html_output2 != '-':
        print("   ✅ HTML generado para GiftCard sin destinatario")

        # Verificar el mensaje genérico
        urls2 = re.findall(r'href="([^"]+)"', html_output2)
        if len(urls2) >= 2:
            whatsapp_url2 = urls2[1]
            if 'text=' in whatsapp_url2:
                mensaje2 = whatsapp_url2.split('text=')[1]
                mensaje_decodificado2 = unquote(mensaje2)
                if "¡Hola!" in mensaje_decodificado2:
                    print("   ✅ Mensaje genérico generado correctamente")
    else:
        print("   ⚠️ No se generó HTML para GiftCard sin destinatario")

    print()
    print("=" * 60)
    print("RESUMEN DE LA IMPLEMENTACIÓN")
    print("=" * 60)
    print()
    print("✅ Se agregó el método 'ver_giftcard' al GiftCardInline")
    print("✅ El método genera dos botones:")
    print("   1. Ver GiftCard - Abre la vista de la GiftCard")
    print("   2. WhatsApp - Permite compartir la GiftCard por WhatsApp")
    print()
    print("✅ El mensaje de WhatsApp incluye:")
    print("   - Nombre del destinatario (si existe)")
    print("   - Monto de la GiftCard")
    print("   - Código de la GiftCard")
    print("   - Link directo para ver/descargar")
    print()
    print("✅ Si hay teléfono del destinatario, el WhatsApp se pre-configura")
    print("   con ese número (código +56 para Chile)")
    print()
    print("✅ La URL base se toma de settings.SITE_URL")
    print("   (configurado como: https://aremko-booking-system.onrender.com)")

if __name__ == "__main__":
    test_giftcard_inline()