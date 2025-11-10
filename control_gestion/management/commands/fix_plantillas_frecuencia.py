"""
Comando para arreglar plantillas sin frecuencia

Establece frecuencia='DIARIA' en todas las plantillas que tengan frecuencia=NULL
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Establece frecuencia=DIARIA en plantillas sin frecuencia'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sin hacer cambios reales',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        print("\n" + "="*80)
        print("FIX: PLANTILLAS SIN FRECUENCIA")
        print("="*80 + "\n")

        if dry_run:
            print("🔍 MODO SIMULACIÓN (--dry-run)")
            print("   No se harán cambios reales\n")

        # 1. Verificar si la columna existe
        print("1. Verificando si columna 'frecuencia' existe...")
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'control_gestion_tasktemplate'
                AND column_name = 'frecuencia';
            """)
            exists = cursor.fetchone()

        if not exists:
            print("❌ ERROR: La columna 'frecuencia' no existe")
            print("   Primero debes ejecutar las migraciones:")
            print("   python manage.py migrate control_gestion")
            return

        print("✅ Columna 'frecuencia' existe\n")

        # 2. Contar plantillas sin frecuencia
        print("2. Contando plantillas sin frecuencia...")
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM control_gestion_tasktemplate
                WHERE frecuencia IS NULL OR frecuencia = '';
            """)
            count = cursor.fetchone()[0]

        if count == 0:
            print("✅ No hay plantillas sin frecuencia")
            print("   Todas las plantillas ya tienen frecuencia definida\n")
            return

        print(f"⚠️  Encontradas {count} plantillas sin frecuencia\n")

        # 3. Mostrar plantillas afectadas
        print("3. Plantillas que serán actualizadas:")
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, title_template, activa
                FROM control_gestion_tasktemplate
                WHERE frecuencia IS NULL OR frecuencia = ''
                ORDER BY id;
            """)
            plantillas = cursor.fetchall()

        for p in plantillas:
            pid, title, activa = p
            estado = "✅ Activa" if activa else "⏸️  Inactiva"
            print(f"   - ID {pid}: {title} ({estado})")

        # 4. Actualizar plantillas
        if not dry_run:
            print(f"\n4. Actualizando {count} plantillas a frecuencia='DIARIA'...")
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE control_gestion_tasktemplate
                    SET frecuencia = 'DIARIA'
                    WHERE frecuencia IS NULL OR frecuencia = '';
                """)
                updated = cursor.rowcount

            print(f"✅ {updated} plantillas actualizadas correctamente")
        else:
            print(f"\n4. SIMULACIÓN: Se actualizarían {count} plantillas")
            print("   Ejecuta sin --dry-run para aplicar los cambios")

        # 5. Verificación final
        if not dry_run:
            print("\n5. Verificación final...")
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM control_gestion_tasktemplate
                    WHERE frecuencia IS NULL OR frecuencia = '';
                """)
                remaining = cursor.fetchone()[0]

            if remaining == 0:
                print("✅ Todas las plantillas tienen frecuencia definida")
            else:
                print(f"⚠️  Aún quedan {remaining} plantillas sin frecuencia")

        print("\n" + "="*80)
        print("RESUMEN")
        print("="*80)

        if dry_run:
            print(f"🔍 SIMULACIÓN: {count} plantillas serían actualizadas")
            print("   Ejecuta: python manage.py fix_plantillas_frecuencia")
        else:
            print(f"✅ FIX COMPLETADO: {count} plantillas actualizadas")
            print("   Ahora puedes acceder al dashboard de plantillas")

        print("\n")
