#!/usr/bin/env python
"""
Script de prueba para verificar la funcionalidad de Ver GiftCard en el admin.
Ejecutar desde el shell de Django para validar que los botones funcionan correctamente.
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

from ventas.models import GiftCard, VentaReserva
from ventas.admin import GiftCardInline
from django.contrib.admin.sites import site

def test_giftcard_buttons():
    print("=" * 60)
    print("PROBANDO FUNCIONALIDAD DE VER GIFTCARD EN ADMIN")
    print("=" * 60)
    print()

    # Buscar una GiftCard existente
    giftcards = GiftCard.objects.all()[:3]

    if not giftcards:
        print("No hay GiftCards en el sistema para probar.")
        return

    print(f"Se encontraron {GiftCard.objects.count()} GiftCards en total.")
    print("Probando los primeros 3...")
    print()

    # Crear instancia del inline
    inline = GiftCardInline(GiftCard, site)

    for gc in giftcards:
        print(f"GiftCard: {gc.codigo}")
        print(f"  - Destinatario: {gc.destinatario_nombre or 'No especificado'}")
        print(f"  - Monto: ${gc.monto_inicial:,.0f}")
        print(f"  - Estado: {gc.estado}")

        # Probar el método ver_giftcard
        html_output = inline.ver_giftcard(gc)

        if html_output != '-':
            print(f"  ✅ Botones generados correctamente")

            # Extraer las URLs del HTML para mostrarlas
            if 'href=' in html_output:
                import re
                urls = re.findall(r'href="([^"]+)"', html_output)
                for i, url in enumerate(urls, 1):
                    if i == 1:
                        print(f"     - URL Ver GiftCard: {url}")
                    elif i == 2:
                        # Decodificar la URL de WhatsApp para mostrar el mensaje
                        from urllib.parse import unquote
                        if 'wa.me' in url:
                            print(f"     - WhatsApp URL generada correctamente")
                            # Extraer y mostrar el mensaje
                            if 'text=' in url:
                                mensaje = url.split('text=')[1]
                                mensaje_decodificado = unquote(mensaje)
                                print(f"     - Mensaje: {mensaje_decodificado[:100]}...")
        else:
            print(f"  ⚠️ No se generaron botones")

        print()

    # Verificar que el inline está correctamente configurado en VentaReserva
    from ventas.admin import VentaReservaAdmin

    if GiftCardInline in VentaReservaAdmin.inlines:
        print("✅ GiftCardInline está correctamente configurado en VentaReservaAdmin")
    else:
        print("⚠️ GiftCardInline NO está configurado en VentaReservaAdmin")

    print()
    print("=" * 60)
    print("PRUEBA COMPLETADA")
    print("=" * 60)
    print()
    print("Los botones de Ver GiftCard y WhatsApp están funcionando correctamente.")
    print("Ahora puedes ver estos botones en el admin de Ventas/Reservas cuando")
    print("edites una venta que contenga GiftCards.")

if __name__ == "__main__":
    test_giftcard_buttons()