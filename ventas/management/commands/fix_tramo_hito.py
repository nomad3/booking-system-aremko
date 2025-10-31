"""
Management command para aplicar migración de campo tramo_hito
Ejecutar en Render Shell: python manage.py fix_tramo_hito
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Aplica migración manual para agregar campo tramo_hito a Premio'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("🔧 FIX: Migración manual de campo tramo_hito"))
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Paso 1: Verificar si la columna ya existe
        self.stdout.write("📋 PASO 1: Verificando si la columna tramo_hito ya existe...")
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='ventas_premio' AND column_name='tramo_hito';
            """)
            exists = cursor.fetchone()

        if exists:
            self.stdout.write(self.style.SUCCESS("   ✅ La columna 'tramo_hito' YA EXISTE"))
            self.stdout.write("   ℹ️  No es necesario agregar la columna\n")
        else:
            self.stdout.write(self.style.WARNING("   ⚠️  La columna 'tramo_hito' NO EXISTE"))
            self.stdout.write("   ➕ Agregando columna...\n")

            # Paso 2: Agregar la columna
            self.stdout.write("📋 PASO 2: Agregando columna tramo_hito a ventas_premio...")
            with connection.cursor() as cursor:
                cursor.execute("""
                    ALTER TABLE ventas_premio
                    ADD COLUMN tramo_hito INTEGER NULL;
                """)
            self.stdout.write(self.style.SUCCESS("   ✅ Columna agregada exitosamente\n"))

        # Paso 3: Registrar la migración en django_migrations
        self.stdout.write("📋 PASO 3: Registrando migración en django_migrations...")
        with connection.cursor() as cursor:
            # Verificar si ya está registrada
            cursor.execute("""
                SELECT id FROM django_migrations
                WHERE app='ventas' AND name='0058_add_tramo_hito_to_premio';
            """)
            registered = cursor.fetchone()

            if registered:
                self.stdout.write(self.style.SUCCESS("   ✅ La migración YA ESTÁ REGISTRADA"))
            else:
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES ('ventas', '0058_add_tramo_hito_to_premio', NOW());
                """)
                self.stdout.write(self.style.SUCCESS("   ✅ Migración registrada exitosamente"))

        self.stdout.write("")

        # Paso 4: Poblar datos iniciales
        self.stdout.write("📋 PASO 4: Poblando datos iniciales...")
        from ventas.models import Premio

        updates = [
            (2, 5, "Vale $60K"),
            (3, 10, "Noche VIP"),
            (4, 15, "Vale Premium"),
            (5, 20, "Noche Elite"),
        ]

        for premio_id, tramo, nombre in updates:
            updated = Premio.objects.filter(id=premio_id).update(tramo_hito=tramo)
            if updated:
                self.stdout.write(self.style.SUCCESS(
                    f"   ✅ Premio ID {premio_id} ({nombre}) → Tramo {tramo}"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"   ⚠️  Premio ID {premio_id} no encontrado"
                ))

        self.stdout.write("")

        # Paso 5: Verificar resultado
        self.stdout.write("📋 PASO 5: Verificación final...")
        premios = Premio.objects.all()
        self.stdout.write("")
        for p in premios:
            tramo_desc = p.descripcion_tramo() if hasattr(p, 'descripcion_tramo') else f"Tramo {p.tramo_hito}"
            self.stdout.write(f"   ID {p.id}: {p.nombre[:40]:<40} → {tramo_desc}")

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        self.stdout.write("📌 El módulo de premios debería funcionar ahora.")
        self.stdout.write("📌 Recarga la página en el navegador para verificar.")
        self.stdout.write("")
