# -*- coding: utf-8 -*-
"""
Management command para agregar campos del wizard a la tabla GiftCard en producción

Este comando agrega los campos necesarios para el wizard de GiftCards personalizado con IA:
- Datos del comprador (nombre, email, teléfono)
- Datos del destinatario (nombre, email, teléfono, relación, detalle especial)
- Configuración de mensaje IA (tipo, mensaje personalizado, alternativas)
- Servicio asociado (experiencia seleccionada)

Uso:
    python manage.py add_giftcard_wizard_fields
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = 'Agrega campos del wizard a la tabla ventas_giftcard'

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write(self.style.WARNING('AGREGANDO CAMPOS DEL WIZARD A TABLA GIFTCARD'))
        self.stdout.write('=' * 80)

        with connection.cursor() as cursor:
            # Verificar si los campos ya existen
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'ventas_giftcard'
                AND table_schema = 'public';
            """)
            existing_columns = {row[0] for row in cursor.fetchall()}

            campos_a_agregar = [
                # Datos del comprador
                ("comprador_nombre", "VARCHAR(255)"),
                ("comprador_email", "VARCHAR(254)"),
                ("comprador_telefono", "VARCHAR(20)"),

                # Datos del destinatario
                ("destinatario_nombre", "VARCHAR(255)"),
                ("destinatario_email", "VARCHAR(254)"),
                ("destinatario_telefono", "VARCHAR(20)"),
                ("destinatario_relacion", "VARCHAR(100)"),
                ("detalle_especial", "TEXT"),

                # Configuración de mensaje IA
                ("tipo_mensaje", "VARCHAR(50)"),
                ("mensaje_personalizado", "TEXT"),
                ("mensaje_alternativas", "JSONB"),

                # Servicio asociado
                ("servicio_asociado", "VARCHAR(100)"),
            ]

            with transaction.atomic():
                for campo, tipo_sql in campos_a_agregar:
                    if campo in existing_columns:
                        self.stdout.write(self.style.WARNING(f'⏭️  Campo "{campo}" ya existe, omitiendo...'))
                    else:
                        # Todos los campos son NULL permitidos (compatibilidad con registros existentes)
                        sql = f'ALTER TABLE ventas_giftcard ADD COLUMN {campo} {tipo_sql} NULL;'

                        # Para JSONB, agregar default de lista vacía
                        if tipo_sql == "JSONB":
                            sql = f'ALTER TABLE ventas_giftcard ADD COLUMN {campo} {tipo_sql} DEFAULT \'[]\' NULL;'

                        try:
                            cursor.execute(sql)
                            self.stdout.write(self.style.SUCCESS(f'✅ Campo "{campo}" ({tipo_sql}) agregado correctamente'))
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'❌ Error al agregar campo "{campo}": {str(e)}'))
                            raise

        # Verificar campos finales
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('VERIFICACIÓN FINAL'))
        self.stdout.write('=' * 80)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'ventas_giftcard'
                AND table_schema = 'public'
                AND column_name IN (
                    'comprador_nombre', 'comprador_email', 'comprador_telefono',
                    'destinatario_nombre', 'destinatario_email', 'destinatario_telefono',
                    'destinatario_relacion', 'detalle_especial',
                    'tipo_mensaje', 'mensaje_personalizado', 'mensaje_alternativas',
                    'servicio_asociado'
                )
                ORDER BY column_name;
            """)

            resultados = cursor.fetchall()

            if resultados:
                self.stdout.write(self.style.SUCCESS(f'\n✅ {len(resultados)} campos del wizard encontrados:\n'))
                for columna, tipo, nullable in resultados:
                    nullable_str = "NULL" if nullable == 'YES' else "NOT NULL"
                    self.stdout.write(f'   • {columna:<25} {tipo:<20} {nullable_str}')
            else:
                self.stdout.write(self.style.ERROR('❌ No se encontraron los campos del wizard'))

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('PROCESO COMPLETADO'))
        self.stdout.write('=' * 80)
        self.stdout.write(self.style.SUCCESS('''
PRÓXIMOS PASOS:
1. Verificar que todos los campos estén presentes (12 campos esperados)
2. Hacer deploy del código actualizado (models.py y checkout_views.py)
3. Probar el flujo completo de GiftCard: Wizard → Carrito → Checkout → Pago

FLUJO ACTUALIZADO:
- Wizard captura: destinatario, mensaje IA, experiencia
- Checkout captura: comprador (nombre, email, teléfono, región, comuna)
- GiftCard se crea con TODOS los datos combinados
        '''))
