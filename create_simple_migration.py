#!/usr/bin/env python
"""
Script para crear una migración simple que solo agregue el campo tramos_validos
"""
import os

migration_content = '''# Generated manually - Simple migration
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0057_emailcontenttemplate_whatsapp_button'),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE ventas_premio ADD COLUMN tramos_validos jsonb DEFAULT '[]'::jsonb",
            reverse_sql="ALTER TABLE ventas_premio DROP COLUMN tramos_validos"
        ),
    ]
'''

# Eliminar la migración anterior si existe
old_migration = 'ventas/migrations/0059_add_tramos_validos.py'
if os.path.exists(old_migration):
    os.remove(old_migration)
    print(f"❌ Eliminada migración anterior: {old_migration}")

# Crear la nueva migración
migration_path = 'ventas/migrations/0059_add_tramos_validos_simple.py'

try:
    with open(migration_path, 'w') as f:
        f.write(migration_content)
    print(f"✅ Migración simple creada: {migration_path}")
    print("\nAhora ejecuta:")
    print("  python manage.py migrate ventas")
    print("  python manage.py migrate_tramos_data  # Script para migrar datos")
    print("  python manage.py configurar_tramos_premios")
except Exception as e:
    print(f"❌ Error: {e}")