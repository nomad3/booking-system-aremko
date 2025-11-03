#!/usr/bin/env python
"""
Script para corregir la dependencia de la migración 0059
"""
import os

# Leer el archivo actual
migration_path = 'ventas/migrations/0059_add_tramos_validos.py'

try:
    with open(migration_path, 'r') as f:
        content = f.read()

    # Reemplazar la dependencia incorrecta
    content = content.replace(
        "('ventas', '0058_servicehistory_clientepremio_premio_region_and_more')",
        "('ventas', '0057_emailcontenttemplate_whatsapp_button')"
    )

    # Escribir el archivo corregido
    with open(migration_path, 'w') as f:
        f.write(content)

    print("✅ Migración corregida exitosamente")
    print("\nAhora ejecuta:")
    print("  python manage.py migrate ventas")
    print("  python manage.py configurar_tramos_premios")

except Exception as e:
    print(f"❌ Error: {e}")