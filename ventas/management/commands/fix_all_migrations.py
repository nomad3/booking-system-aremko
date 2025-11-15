#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Django Management Command: Fix ALL Migration History Issues

PROBLEMA:
- Múltiples migraciones duplicadas (0051, 0057, 0058, 0059)
- Migraciones que crean modelo Premio en diferentes puntos
- KeyError: ('ventas', 'premio') durante migrate

SOLUCIÓN:
Este comando limpia TODAS las migraciones duplicadas y deja solo
las migraciones correctas que deben estar aplicadas.

USO:
    python manage.py fix_all_migrations

SEGURIDAD:
- Solo actualiza tabla django_migrations
- NO modifica datos de usuario
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Fix ALL migration history issues (remove duplicates, keep only correct ones)'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.WARNING("🔧 FIX ALL MIGRATIONS - LIMPIEZA COMPLETA"))
        self.stdout.write("=" * 80)
        self.stdout.write("")

        with connection.cursor() as cursor:
            # Mostrar estado actual
            self.stdout.write("📊 Migraciones actuales de ventas:")
            self.stdout.write("")

            cursor.execute("""
                SELECT name, applied
                FROM django_migrations
                WHERE app = 'ventas'
                ORDER BY name
            """)

            current_migrations = cursor.fetchall()
            for name, applied in current_migrations:
                self.stdout.write(f"  - {name} ({applied})")

            self.stdout.write("")
            self.stdout.write(f"Total: {len(current_migrations)} migraciones")
            self.stdout.write("")
            self.stdout.write("-" * 80)
            self.stdout.write("")

            # Migraciones que DEBEN mantenerse (las correctas)
            migrations_to_keep = [
                '0050_homepagesettings',
                '0051_advanced_email_campaigns',
                '0052_servicehistory',
                '0053_emailsubjecttemplate',
                '0054_emailcontenttemplate',
                '0055_create_default_email_templates',
                '0056_cliente_created_at',
                '0057_emailcontenttemplate_whatsapp_button',
                '0058_add_tramo_hito_to_premio',
                '0059_add_tramos_validos',
                '0060_giftcard_ai_personalization',
            ]

            self.stdout.write("🎯 Migraciones que DEBEN mantenerse:")
            for migration in migrations_to_keep:
                self.stdout.write(f"  ✅ {migration}")
            self.stdout.write("")

            # Eliminar todas las migraciones que NO están en la lista correcta
            self.stdout.write("🗑️  Eliminando migraciones duplicadas/incorrectas...")
            self.stdout.write("")

            cursor.execute("""
                SELECT name
                FROM django_migrations
                WHERE app = 'ventas'
            """)

            all_migrations = [row[0] for row in cursor.fetchall()]
            migrations_to_delete = [m for m in all_migrations if m not in migrations_to_keep]

            if not migrations_to_delete:
                self.stdout.write(self.style.SUCCESS("  ✅ No hay migraciones duplicadas para eliminar"))
            else:
                for migration_name in migrations_to_delete:
                    cursor.execute("""
                        DELETE FROM django_migrations
                        WHERE app = 'ventas' AND name = %s
                    """, [migration_name])
                    self.stdout.write(f"  🗑️  Eliminada: {migration_name}")

            self.stdout.write("")
            self.stdout.write("-" * 80)
            self.stdout.write("")

            # Verificar que todas las migraciones correctas estén aplicadas
            self.stdout.write("🔍 Verificando migraciones correctas...")
            self.stdout.write("")

            cursor.execute("""
                SELECT name
                FROM django_migrations
                WHERE app = 'ventas'
            """)

            applied_migrations = [row[0] for row in cursor.fetchall()]

            for migration in migrations_to_keep:
                if migration in applied_migrations:
                    self.stdout.write(f"  ✅ {migration} - Aplicada")
                else:
                    # Agregar migración faltante
                    cursor.execute("""
                        INSERT INTO django_migrations (app, name, applied)
                        VALUES ('ventas', %s, NOW())
                    """, [migration])
                    self.stdout.write(f"  ➕ {migration} - Agregada (fake)")

            self.stdout.write("")
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS("✅ FIX COMPLETADO"))
            self.stdout.write("=" * 80)
            self.stdout.write("")

            # Mostrar estado final
            self.stdout.write("📊 Estado final de migraciones ventas:")
            self.stdout.write("")

            cursor.execute("""
                SELECT name, applied
                FROM django_migrations
                WHERE app = 'ventas'
                ORDER BY name
            """)

            final_migrations = cursor.fetchall()
            for name, applied in final_migrations:
                self.stdout.write(f"  ✅ {name} ({applied})")

            self.stdout.write("")
            self.stdout.write(f"Total: {len(final_migrations)} migraciones")
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("🎉 Historial de migraciones limpiado!"))
            self.stdout.write("")
            self.stdout.write("PRÓXIMO PASO:")
            self.stdout.write("  1. Salir de este shell")
            self.stdout.write("  2. Trigger manual deploy en Render Dashboard")
            self.stdout.write("  3. Deploy debería completar exitosamente")
            self.stdout.write("")
