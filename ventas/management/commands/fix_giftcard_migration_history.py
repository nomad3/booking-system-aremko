#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Django Management Command: Fix GiftCard Migration History

PROBLEMA:
Migration 0060 fue aplicada antes que sus dependencias 0058 y 0059,
causando InconsistentMigrationHistory error.

SOLUCIÓN:
Este comando marca migrations 0058 y 0059 como aplicadas (fake)
en la tabla django_migrations sin ejecutar su código SQL.

USO:
    python manage.py fix_giftcard_migration_history

SEGURIDAD:
- Este comando es SEGURO porque solo actualiza django_migrations table
- NO modifica datos existentes en la BD
- Solo marca migraciones como "ya aplicadas"

CUÁNDO USAR:
- Cuando ves error: "Migration 0060 is applied before its dependency 0059"
- Solo una vez después del primer deploy con GiftCards
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Fix migration history for GiftCard feature (mark 0058 and 0059 as applied)'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.WARNING("🔧 FIX GIFTCARD MIGRATION HISTORY"))
        self.stdout.write("=" * 80)
        self.stdout.write("")

        migrations_to_fake = [
            ('ventas', '0058_add_tramo_hito_to_premio'),
            ('ventas', '0059_add_tramos_validos'),
        ]

        with connection.cursor() as cursor:
            # Verificar migraciones actuales
            self.stdout.write("📊 Estado actual de migraciones ventas.005x y 006x:")
            self.stdout.write("")

            cursor.execute("""
                SELECT app, name, applied
                FROM django_migrations
                WHERE app = 'ventas'
                  AND (name LIKE '005%' OR name LIKE '006%')
                ORDER BY name
            """)

            existing_migrations = cursor.fetchall()

            for app, name, applied in existing_migrations:
                self.stdout.write(f"  ✅ {app}.{name} - Applied: {applied}")

            self.stdout.write("")
            self.stdout.write("-" * 80)
            self.stdout.write("")

            # Verificar si 0060 está aplicada
            cursor.execute("""
                SELECT COUNT(*)
                FROM django_migrations
                WHERE app = 'ventas' AND name = '0060_giftcard_ai_personalization'
            """)

            migration_0060_exists = cursor.fetchone()[0] > 0

            if not migration_0060_exists:
                self.stdout.write(self.style.ERROR("❌ Migration 0060 NO está aplicada."))
                self.stdout.write(self.style.ERROR("   Este comando solo es necesario si 0060 ya fue aplicada."))
                self.stdout.write("")
                return

            self.stdout.write(self.style.SUCCESS("✅ Migration 0060 está aplicada (como esperado)"))
            self.stdout.write("")

            # Verificar si 0058 y 0059 YA están aplicadas
            for app, migration_name in migrations_to_fake:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM django_migrations
                    WHERE app = %s AND name = %s
                """, [app, migration_name])

                already_applied = cursor.fetchone()[0] > 0

                if already_applied:
                    self.stdout.write(
                        self.style.WARNING(f"⚠️  {app}.{migration_name} ya está marcada como aplicada - SKIP")
                    )
                else:
                    # Insertar registro de migración (fake apply)
                    self.stdout.write(f"🔧 Marcando {app}.{migration_name} como aplicada...")

                    cursor.execute("""
                        INSERT INTO django_migrations (app, name, applied)
                        VALUES (%s, %s, NOW())
                    """, [app, migration_name])

                    self.stdout.write(
                        self.style.SUCCESS(f"   ✅ {app}.{migration_name} marcada como aplicada (fake)")
                    )

            self.stdout.write("")
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS("✅ FIX COMPLETADO"))
            self.stdout.write("=" * 80)
            self.stdout.write("")
            self.stdout.write("📊 Estado final de migraciones:")
            self.stdout.write("")

            cursor.execute("""
                SELECT app, name, applied
                FROM django_migrations
                WHERE app = 'ventas'
                  AND (name LIKE '005%' OR name LIKE '006%')
                ORDER BY name
            """)

            final_migrations = cursor.fetchall()

            for app, name, applied in final_migrations:
                self.stdout.write(f"  ✅ {app}.{name} - Applied: {applied}")

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("🎉 Ahora puedes hacer redeploy en Render!"))
            self.stdout.write("")
            self.stdout.write("PRÓXIMO PASO:")
            self.stdout.write("  1. Trigger manual deploy en Render Dashboard")
            self.stdout.write("  2. Las migraciones deberían pasar sin errores")
            self.stdout.write("  3. El deploy debería completarse exitosamente")
            self.stdout.write("")
