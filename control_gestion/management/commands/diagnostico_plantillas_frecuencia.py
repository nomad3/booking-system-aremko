"""
Comando de diagnóstico para verificar el estado de las plantillas con frecuencia

Verifica:
1. Si la columna frecuencia existe en la tabla
2. Si hay plantillas sin frecuencia definida
3. Si las migraciones se aplicaron correctamente
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Diagnostica el estado de las plantillas con el campo frecuencia'

    def handle(self, *args, **options):
        print("\n" + "="*80)
        print("DIAGNÓSTICO: PLANTILLAS CON FRECUENCIA")
        print("="*80 + "\n")

        # 1. Verificar si la columna frecuencia existe
        print("1. VERIFICANDO ESTRUCTURA DE LA TABLA")
        print("-" * 80)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'control_gestion_tasktemplate'
                AND column_name IN ('frecuencia', 'dia_del_mes', 'mes_inicio', 'ultima_generacion')
                ORDER BY column_name;
            """)

            columns = cursor.fetchall()

            if not columns:
                print("❌ ERROR: No se encontraron las columnas nuevas")
                print("   Las migraciones NO se ejecutaron correctamente")
                print("\n   SOLUCIÓN:")
                print("   1. Conectarse a Render Shell")
                print("   2. Ejecutar: python manage.py migrate control_gestion")
                return

            print("✅ Columnas encontradas:")
            for col in columns:
                col_name, data_type, nullable, default = col
                print(f"   - {col_name}: {data_type} (nullable={nullable}, default={default})")

        # 2. Verificar plantillas existentes
        print("\n2. VERIFICANDO PLANTILLAS EXISTENTES")
        print("-" * 80)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN frecuencia IS NULL THEN 1 END) as sin_frecuencia,
                    COUNT(CASE WHEN frecuencia = 'DIARIA' THEN 1 END) as diarias,
                    COUNT(CASE WHEN frecuencia = 'MENSUAL' THEN 1 END) as mensuales,
                    COUNT(CASE WHEN frecuencia = 'TRIMESTRAL' THEN 1 END) as trimestrales,
                    COUNT(CASE WHEN frecuencia = 'SEMESTRAL' THEN 1 END) as semestrales,
                    COUNT(CASE WHEN frecuencia = 'ANUAL' THEN 1 END) as anuales
                FROM control_gestion_tasktemplate;
            """)

            stats = cursor.fetchone()
            total, sin_frec, diarias, mensuales, trimestrales, semestrales, anuales = stats

            print(f"   Total plantillas: {total}")
            print(f"   Sin frecuencia (NULL): {sin_frec}")
            print(f"   Diarias: {diarias}")
            print(f"   Mensuales: {mensuales}")
            print(f"   Trimestrales: {trimestrales}")
            print(f"   Semestrales: {semestrales}")
            print(f"   Anuales: {anuales}")

            if sin_frec > 0:
                print(f"\n   ⚠️  ADVERTENCIA: Hay {sin_frec} plantillas sin frecuencia")
                print("   Esto causará errores al acceder a get_dias_str()")

        # 3. Mostrar plantillas con problemas
        print("\n3. PLANTILLAS CON PROBLEMAS POTENCIALES")
        print("-" * 80)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, title_template, frecuencia, dia_del_mes, mes_inicio
                FROM control_gestion_tasktemplate
                WHERE frecuencia IS NULL OR frecuencia = ''
                LIMIT 10;
            """)

            problematicas = cursor.fetchall()

            if not problematicas:
                print("   ✅ No hay plantillas con problemas")
            else:
                print("   Plantillas sin frecuencia:")
                for p in problematicas:
                    pid, title, freq, dia, mes = p
                    print(f"   - ID {pid}: {title} (frecuencia={freq})")

        # 4. Verificar migración aplicada
        print("\n4. VERIFICANDO MIGRACIÓN EN DJANGO_MIGRATIONS")
        print("-" * 80)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT name, applied
                FROM django_migrations
                WHERE app = 'control_gestion'
                AND name LIKE '%periodic%' OR name LIKE '%0059%'
                ORDER BY applied DESC;
            """)

            migrations = cursor.fetchall()

            if not migrations:
                print("   ⚠️  No se encontró la migración 0059_add_periodic_task_frequencies")
                print("   La migración puede no haberse ejecutado")
            else:
                print("   Migraciones encontradas:")
                for m in migrations:
                    name, applied = m
                    print(f"   - {name} (aplicada: {applied})")

        # 5. Resumen y recomendaciones
        print("\n" + "="*80)
        print("RESUMEN")
        print("="*80)

        if not columns:
            print("❌ PROBLEMA: Columnas no existen")
            print("   Ejecutar: python manage.py migrate control_gestion")
        elif sin_frec > 0:
            print("⚠️  PROBLEMA: Plantillas sin frecuencia")
            print("   Ejecutar: python manage.py shell")
            print("   >>> from control_gestion.models_templates import TaskTemplate")
            print("   >>> TaskTemplate.objects.filter(frecuencia__isnull=True).update(frecuencia='DIARIA')")
        else:
            print("✅ TODO OK: Sistema funcionando correctamente")

        print("\n")
