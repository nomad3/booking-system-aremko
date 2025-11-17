# -*- coding: utf-8 -*-
"""
Management command para hacer nullable TODOS los campos personalizados de GiftCard

Este comando busca TODOS los campos en la tabla ventas_giftcard que no sean
campos base (id, codigo, monto_inicial, etc.) y los hace nullable.

Útil cuando hay campos agregados manualmente a la BD que no están sincronizados
con el modelo Python.

Uso:
    python manage.py fix_all_giftcard_constraints
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = 'Hace nullable TODOS los campos personalizados de GiftCard'

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write(self.style.WARNING('HACIENDO NULLABLE TODOS LOS CAMPOS PERSONALIZADOS DE GIFTCARD'))
        self.stdout.write('=' * 80)

        # Campos base que NO deben modificarse (campos originales del modelo)
        campos_base = {
            'id',
            'codigo',
            'monto_inicial',
            'monto_disponible',
            'fecha_emision',
            'fecha_vencimiento',
            'estado',
            'cliente_comprador_id',
            'cliente_destinatario_id',
        }

        with connection.cursor() as cursor:
            # Obtener TODOS los campos de la tabla
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'ventas_giftcard'
                AND table_schema = 'public'
                ORDER BY column_name;
            """)

            todos_campos = cursor.fetchall()

            # Filtrar campos personalizados (no base)
            campos_personalizados = [
                (nombre, tipo, nullable)
                for nombre, tipo, nullable in todos_campos
                if nombre not in campos_base
            ]

            self.stdout.write(f'\n📊 ANÁLISIS DE TABLA ventas_giftcard:')
            self.stdout.write(f'   • Total de campos: {len(todos_campos)}')
            self.stdout.write(f'   • Campos base (no modificar): {len(campos_base)}')
            self.stdout.write(f'   • Campos personalizados: {len(campos_personalizados)}')

            not_null_personalizados = [
                nombre for nombre, _, nullable in campos_personalizados
                if nullable == 'NO'
            ]

            if not_null_personalizados:
                self.stdout.write(f'   • Campos personalizados con NOT NULL: {len(not_null_personalizados)}')
                self.stdout.write('')
                self.stdout.write(self.style.WARNING('⚠️  Campos que se modificarán:'))
                for campo in not_null_personalizados:
                    self.stdout.write(f'      - {campo}')
            else:
                self.stdout.write(self.style.SUCCESS('\n✅ Todos los campos personalizados ya aceptan NULL'))
                return

            # Modificar campos
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write('MODIFICANDO CAMPOS...')
            self.stdout.write('=' * 80)

            with transaction.atomic():
                for nombre, tipo, nullable in campos_personalizados:
                    if nullable == 'YES':
                        self.stdout.write(self.style.SUCCESS(f'✅ {nombre:<30} ya acepta NULL'))
                        continue

                    # Cambiar a nullable
                    sql = f'ALTER TABLE ventas_giftcard ALTER COLUMN {nombre} DROP NOT NULL;'

                    try:
                        cursor.execute(sql)
                        self.stdout.write(self.style.SUCCESS(f'✅ {nombre:<30} modificado a NULL'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'❌ Error en {nombre}: {str(e)}'))
                        raise

        # Verificación final
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('VERIFICACIÓN FINAL'))
        self.stdout.write('=' * 80)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'ventas_giftcard'
                AND table_schema = 'public'
                AND column_name NOT IN ('id', 'codigo', 'monto_inicial', 'monto_disponible',
                                       'fecha_emision', 'fecha_vencimiento', 'estado',
                                       'cliente_comprador_id', 'cliente_destinatario_id')
                ORDER BY column_name;
            """)

            campos_personalizados_final = cursor.fetchall()

            not_null_count = sum(1 for _, _, nullable in campos_personalizados_final if nullable == 'NO')
            null_count = sum(1 for _, _, nullable in campos_personalizados_final if nullable == 'YES')

            self.stdout.write(f'\n📊 RESUMEN FINAL:')
            self.stdout.write(f'   • Total campos personalizados: {len(campos_personalizados_final)}')
            self.stdout.write(self.style.SUCCESS(f'   • Campos con NULL: {null_count} ✅'))
            if not_null_count > 0:
                self.stdout.write(self.style.ERROR(f'   • Campos con NOT NULL: {not_null_count} ⚠️'))

            self.stdout.write('\n📋 DETALLE DE CAMPOS PERSONALIZADOS:\n')
            for nombre, tipo, nullable in campos_personalizados_final:
                nullable_str = "NULL ✅" if nullable == 'YES' else "NOT NULL ⚠️"
                style_func = self.style.SUCCESS if nullable == 'YES' else self.style.ERROR
                self.stdout.write(style_func(f'   • {nombre:<30} {tipo:<20} {nullable_str}'))

            if not_null_count == 0:
                self.stdout.write('\n' + '=' * 80)
                self.stdout.write(self.style.SUCCESS('🎉 ÉXITO - TODOS LOS CAMPOS PERSONALIZADOS AHORA ACEPTAN NULL'))
                self.stdout.write('=' * 80)
                self.stdout.write(self.style.SUCCESS('''
✅ La tabla ventas_giftcard está correctamente configurada.

FLUJO ACTUALIZADO:
1. Wizard → Captura datos del destinatario y mensaje IA
2. Carrito → GiftCard con campos de comprador en NULL (temporal)
3. Checkout → Captura datos del comprador
4. GiftCard → Se crea con TODOS los datos completos

Todos los campos pueden quedar NULL temporalmente hasta completarse en checkout.
                '''))
            else:
                self.stdout.write('\n' + '=' * 80)
                self.stdout.write(self.style.ERROR(f'⚠️ AÚN HAY {not_null_count} CAMPOS CON NOT NULL'))
                self.stdout.write('=' * 80)
                self.stdout.write('Ejecutar nuevamente el comando para intentar corregir.')
