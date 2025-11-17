# -*- coding: utf-8 -*-
"""
Management command para hacer que los campos del wizard de GiftCard acepten NULL

PROBLEMA:
Los campos del wizard en la tabla ventas_giftcard están configurados como NOT NULL,
pero el nuevo flujo no captura datos del comprador en el wizard (se capturan en checkout).
Esto causa errores si los campos quedan vacíos.

SOLUCIÓN:
Cambiar todos los campos del wizard a nullable para permitir que queden vacíos
durante la creación inicial de la GiftCard.

Uso:
    python manage.py fix_giftcard_null_constraints
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = 'Hace que los campos del wizard de GiftCard acepten NULL'

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write(self.style.WARNING('MODIFICANDO CONSTRAINTS DE CAMPOS GIFTCARD'))
        self.stdout.write('=' * 80)

        campos_a_modificar = [
            # Datos del comprador
            'comprador_nombre',
            'comprador_email',
            'comprador_telefono',

            # Datos del destinatario
            'destinatario_nombre',
            'destinatario_email',
            'destinatario_telefono',
            'destinatario_relacion',
            'detalle_especial',

            # Configuración de mensaje IA
            'tipo_mensaje',
            'mensaje_personalizado',
            'mensaje_alternativas',

            # Servicio asociado
            'servicio_asociado',
        ]

        with connection.cursor() as cursor:
            # Verificar estado actual
            cursor.execute("""
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'ventas_giftcard'
                AND table_schema = 'public'
                AND column_name = ANY(%s)
                ORDER BY column_name;
            """, [campos_a_modificar])

            campos_actuales = {row[0]: row[1] for row in cursor.fetchall()}

            self.stdout.write('\n📊 ESTADO ACTUAL:')
            not_null_count = sum(1 for nullable in campos_actuales.values() if nullable == 'NO')
            self.stdout.write(f'   • {len(campos_actuales)} campos encontrados')
            self.stdout.write(f'   • {not_null_count} campos con NOT NULL (deben cambiarse)')
            self.stdout.write('')

            # Modificar campos
            with transaction.atomic():
                for campo in campos_a_modificar:
                    if campo not in campos_actuales:
                        self.stdout.write(self.style.WARNING(f'⚠️  Campo "{campo}" no existe, omitiendo...'))
                        continue

                    if campos_actuales[campo] == 'YES':
                        self.stdout.write(self.style.SUCCESS(f'✅ Campo "{campo}" ya acepta NULL, omitiendo...'))
                        continue

                    # Cambiar a nullable
                    sql = f'ALTER TABLE ventas_giftcard ALTER COLUMN {campo} DROP NOT NULL;'

                    try:
                        cursor.execute(sql)
                        self.stdout.write(self.style.SUCCESS(f'✅ Campo "{campo}" ahora acepta NULL'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'❌ Error al modificar "{campo}": {str(e)}'))
                        raise

        # Verificar cambios
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('VERIFICACIÓN FINAL'))
        self.stdout.write('=' * 80)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'ventas_giftcard'
                AND table_schema = 'public'
                AND column_name = ANY(%s)
                ORDER BY column_name;
            """, [campos_a_modificar])

            resultados = cursor.fetchall()

            if resultados:
                not_null_count = sum(1 for row in resultados if row[2] == 'NO')
                null_count = sum(1 for row in resultados if row[2] == 'YES')

                self.stdout.write(self.style.SUCCESS(f'\n✅ {len(resultados)} campos del wizard encontrados:'))
                self.stdout.write(f'   • {null_count} campos aceptan NULL ✅')
                self.stdout.write(f'   • {not_null_count} campos con NOT NULL ⚠️\n')

                for columna, tipo, nullable in resultados:
                    nullable_str = "NULL ✅" if nullable == 'YES' else "NOT NULL ⚠️"
                    style_func = self.style.SUCCESS if nullable == 'YES' else self.style.ERROR
                    self.stdout.write(style_func(f'   • {columna:<25} {tipo:<20} {nullable_str}'))

                if not_null_count == 0:
                    self.stdout.write('\n' + '=' * 80)
                    self.stdout.write(self.style.SUCCESS('🎉 TODOS LOS CAMPOS AHORA ACEPTAN NULL'))
                    self.stdout.write('=' * 80)
                    self.stdout.write(self.style.SUCCESS('''
✅ CONFIGURACIÓN CORRECTA

Ahora el flujo funciona así:
1. Wizard → Agrega GiftCard al carrito SIN datos del comprador
2. Checkout → Usuario ingresa datos del comprador
3. GiftCard se crea con datos completos del comprador + destinatario

Los campos pueden quedar NULL temporalmente hasta que se completen en checkout.
                    '''))
                else:
                    self.stdout.write('\n' + '=' * 80)
                    self.stdout.write(self.style.ERROR(f'⚠️ AÚN HAY {not_null_count} CAMPOS CON NOT NULL'))
                    self.stdout.write('=' * 80)
                    self.stdout.write(self.style.ERROR('Ejecutar nuevamente el comando para intentar corregir.'))

            else:
                self.stdout.write(self.style.ERROR('❌ No se encontraron los campos del wizard'))
