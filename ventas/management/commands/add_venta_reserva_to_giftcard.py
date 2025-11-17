# -*- coding: utf-8 -*-
"""
Management command para agregar campo venta_reserva_id a la tabla GiftCard

Este comando agrega el campo venta_reserva_id que vincula cada GiftCard con la
VentaReserva donde se compró.

Uso:
    python manage.py add_venta_reserva_to_giftcard
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = 'Agrega campo venta_reserva_id a la tabla ventas_giftcard'

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write(self.style.WARNING('AGREGANDO CAMPO VENTA_RESERVA_ID A TABLA GIFTCARD'))
        self.stdout.write('=' * 80)

        with connection.cursor() as cursor:
            # Verificar si el campo ya existe
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'ventas_giftcard'
                AND table_schema = 'public'
                AND column_name = 'venta_reserva_id';
            """)

            if cursor.fetchone():
                self.stdout.write(self.style.WARNING('\n⏭️  Campo "venta_reserva_id" ya existe, omitiendo...'))
            else:
                # Agregar campo
                with transaction.atomic():
                    try:
                        sql = '''
                            ALTER TABLE ventas_giftcard
                            ADD COLUMN venta_reserva_id INTEGER NULL
                            REFERENCES ventas_ventareserva(id)
                            ON DELETE SET NULL;
                        '''

                        cursor.execute(sql)
                        self.stdout.write(self.style.SUCCESS('\n✅ Campo "venta_reserva_id" agregado correctamente'))

                        # Crear índice para mejorar performance
                        cursor.execute('''
                            CREATE INDEX idx_giftcard_venta_reserva
                            ON ventas_giftcard(venta_reserva_id);
                        ''')
                        self.stdout.write(self.style.SUCCESS('✅ Índice creado en venta_reserva_id'))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'\n❌ Error al agregar campo: {str(e)}'))
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
                AND column_name = 'venta_reserva_id';
            """)

            resultado = cursor.fetchone()

            if resultado:
                columna, tipo, nullable = resultado
                nullable_str = "NULL ✅" if nullable == 'YES' else "NOT NULL"
                self.stdout.write(self.style.SUCCESS(f'\n✅ Campo encontrado:'))
                self.stdout.write(f'   • {columna:<25} {tipo:<20} {nullable_str}')

                # Verificar foreign key
                cursor.execute("""
                    SELECT
                        tc.constraint_name,
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_name = 'ventas_giftcard'
                      AND kcu.column_name = 'venta_reserva_id';
                """)

                fk_info = cursor.fetchone()
                if fk_info:
                    self.stdout.write(self.style.SUCCESS(f'✅ Foreign Key configurado correctamente'))
                    self.stdout.write(f'   → Referencia a tabla: {fk_info[2]}({fk_info[3]})')

                self.stdout.write('\n' + '=' * 80)
                self.stdout.write(self.style.SUCCESS('🎉 CONFIGURACIÓN COMPLETADA'))
                self.stdout.write('=' * 80)
                self.stdout.write(self.style.SUCCESS('''
✅ Campo venta_reserva_id agregado exitosamente

PRÓXIMOS PASOS:
1. Hacer deploy del código actualizado (models.py, checkout_views.py, admin.py, signals)
2. Las nuevas compras de GiftCards se vincularán automáticamente a su VentaReserva
3. Cuando vendedora registre un pago, se enviarán los emails automáticamente

FLUJO COMPLETO:
1. Cliente compra GiftCard → VentaReserva creada con GiftCards vinculadas
2. Vendedora registra pago → Signal detecta GiftCards
3. GiftCards cambian a estado 'cobrado'
4. Email automático enviado al comprador con PDFs
5. Comprador reenvía al destinatario

VERIFICAR EN ADMIN:
- VentaReserva ahora muestra columna "🎁 GiftCards"
- Al editar VentaReserva, verás inline con las GiftCards
- GiftCards aparecen con código, destinatario, estado
                '''))
            else:
                self.stdout.write(self.style.ERROR('\n❌ Campo no encontrado después de la creación'))
