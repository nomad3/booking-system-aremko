"""
Management command para importar servicios históricos desde CSV
"""
from django.core.management.base import BaseCommand
from django.db import connection
from ventas.models import Cliente, ServiceHistory
import csv
import os
from datetime import datetime
from decimal import Decimal
import re


class Command(BaseCommand):
    help = 'Importa servicios históricos desde CSV a la tabla crm_service_history'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-path',
            type=str,
            default='data/servicios_historicos.csv',
            help='Path al archivo CSV con los servicios históricos'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Tamaño del batch para inserciones'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar sin hacer cambios en la BD (solo análisis)'
        )

    def normalize_phone(self, phone_str):
        """
        Normaliza número de teléfono chileno
        """
        if not phone_str or phone_str.strip() == '':
            return None

        # Limpiar caracteres no numéricos
        phone = re.sub(r'[^0-9]', '', str(phone_str))

        # Validar longitud (Chile: 8-9 dígitos o con código país)
        if len(phone) < 8:
            return None

        # Si tiene código de país 56, dejarlo
        if phone.startswith('56') and len(phone) in [11, 12]:
            return phone

        # Si tiene 9 dígitos y empieza con 9, agregar código país
        if len(phone) == 9 and phone.startswith('9'):
            return f'56{phone}'

        # Si tiene 8 dígitos (fijo), agregar código país y código área 2 (Santiago)
        if len(phone) == 8:
            return f'562{phone}'

        # Retornar tal cual si no cumple con los patrones conocidos
        return phone if len(phone) >= 8 else None

    def get_or_create_cliente(self, nombre, email, telefono):
        """
        Busca o crea un cliente basándose en email/teléfono
        Retorna tuple (cliente, created)
        """
        nombre = str(nombre).strip() if nombre else "Cliente Histórico"
        email = str(email).strip().lower() if email and str(email).strip() != '' else None
        telefono = self.normalize_phone(telefono)

        # Buscar por email primero
        if email:
            try:
                cliente = Cliente.objects.get(email=email)
                return cliente, False
            except Cliente.DoesNotExist:
                pass
            except Cliente.MultipleObjectsReturned:
                # Si hay múltiples, tomar el primero
                cliente = Cliente.objects.filter(email=email).first()
                return cliente, False

        # Buscar por teléfono
        if telefono:
            try:
                cliente = Cliente.objects.get(telefono=telefono)
                return cliente, False
            except Cliente.DoesNotExist:
                pass
            except Cliente.MultipleObjectsReturned:
                cliente = Cliente.objects.filter(telefono=telefono).first()
                return cliente, False

        # No existe, crear nuevo
        cliente = Cliente.objects.create(
            nombre=nombre,
            email=email if email else '',
            telefono=telefono if telefono else ''
        )
        return cliente, True

    def parse_date(self, date_str):
        """
        Parsea fecha en formato YYYY-MM-DD
        """
        if not date_str or str(date_str).strip() == '':
            return None

        try:
            return datetime.strptime(str(date_str).strip(), '%Y-%m-%d').date()
        except:
            return None

    def parse_price(self, price_str):
        """
        Parsea precio eliminando separadores de miles
        """
        if not price_str or str(price_str).strip() == '':
            return Decimal('0')

        try:
            # Remover separadores de miles y convertir
            clean_price = str(price_str).replace(',', '').replace('.', '').strip()
            return Decimal(clean_price) if clean_price else Decimal('0')
        except:
            return Decimal('0')

    def categorize_service(self, categoria, servicio):
        """
        Categoriza el servicio en Tinas, Masajes o Cabañas
        """
        categoria_str = str(categoria).lower() if categoria else ''
        servicio_str = str(servicio).lower() if servicio else ''

        if 'cabaña' in categoria_str or 'cabaña' in servicio_str or 'torre' in servicio_str:
            return 'Cabañas'
        elif 'masaje' in categoria_str or 'masaje' in servicio_str:
            return 'Masajes'
        elif 'tina' in categoria_str or 'tinaja' in categoria_str or 'tina' in servicio_str:
            return 'Tinas'
        else:
            return 'Otros'

    def get_season(self, fecha):
        """
        Determina la temporada basándose en la fecha
        """
        if not fecha:
            return 'Desconocida'

        month = fecha.month

        if month in [12, 1, 2]:
            return 'Verano'
        elif month in [3, 4, 5]:
            return 'Otoño'
        elif month in [6, 7, 8]:
            return 'Invierno'
        else:
            return 'Primavera'

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        batch_size = options['batch_size']
        dry_run = options['dry_run']

        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('IMPORTACIÓN DE SERVICIOS HISTÓRICOS'))
        self.stdout.write('=' * 70)

        # Verificar que el CSV existe
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f'\n❌ El archivo CSV no existe: {csv_path}'))
            return

        self.stdout.write(f'\n📁 Archivo CSV: {csv_path}')

        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  MODO DRY-RUN: No se guardarán cambios\n'))

        # Estadísticas
        stats = {
            'total_rows': 0,
            'imported': 0,
            'skipped': 0,
            'errors': 0,
            'new_clients': 0,
            'existing_clients': 0
        }

        # Leer CSV
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            batch = []

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                stats['total_rows'] += 1

                try:
                    # Extraer datos
                    nombre_cliente = row.get('cliente', '').strip()
                    email = row.get('mail', '').strip()
                    telefono = row.get('telefono', '').strip()
                    servicio_nombre = row.get('servicio', '').strip()
                    categoria = row.get('categoria', '').strip()
                    cantidad_str = row.get('cantidad', '1').strip()
                    valor_str = row.get('valor', '0').strip()
                    reserva_id = row.get('reserva', '').strip()
                    fecha_str = row.get('checkin', '').strip()
                    año_str = row.get('Año', '').strip()

                    # Validaciones básicas
                    if not nombre_cliente or nombre_cliente == '':
                        stats['skipped'] += 1
                        continue

                    # Parsear datos
                    fecha = self.parse_date(fecha_str)
                    if not fecha:
                        stats['skipped'] += 1
                        continue

                    precio = self.parse_price(valor_str)
                    cantidad = int(cantidad_str) if cantidad_str and cantidad_str.isdigit() else 1
                    año = int(año_str.replace(',', '')) if año_str and año_str.replace(',', '').isdigit() else fecha.year

                    # Categorizar servicio
                    service_type = self.categorize_service(categoria, servicio_nombre)
                    season = self.get_season(fecha)

                    # Obtener o crear cliente
                    if not dry_run:
                        cliente, created = self.get_or_create_cliente(nombre_cliente, email, telefono)
                        if created:
                            stats['new_clients'] += 1
                        else:
                            stats['existing_clients'] += 1

                        # Crear ServiceHistory
                        service_history = ServiceHistory(
                            cliente=cliente,
                            reserva_id=reserva_id,
                            service_type=service_type,
                            service_name=servicio_nombre,
                            service_date=fecha,
                            quantity=cantidad,
                            price_paid=precio,
                            season=season,
                            year=año
                        )
                        batch.append(service_history)
                    else:
                        # En dry-run solo incrementar contador
                        stats['imported'] += 1

                    # Insertar en batch
                    if not dry_run and len(batch) >= batch_size:
                        ServiceHistory.objects.bulk_create(batch, ignore_conflicts=True)
                        stats['imported'] += len(batch)
                        batch = []

                        # Mostrar progreso
                        if stats['imported'] % 1000 == 0:
                            self.stdout.write(f'  ⏳ Importados {stats["imported"]:,}/{stats["total_rows"]:,}...')

                except Exception as e:
                    stats['errors'] += 1
                    if stats['errors'] <= 10:  # Mostrar solo los primeros 10 errores
                        self.stdout.write(self.style.ERROR(f'  ❌ Error en fila {row_num}: {str(e)}'))

            # Insertar el último batch
            if not dry_run and batch:
                ServiceHistory.objects.bulk_create(batch, ignore_conflicts=True)
                stats['imported'] += len(batch)

        # Mostrar resumen
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('RESUMEN DE IMPORTACIÓN'))
        self.stdout.write('=' * 70)

        self.stdout.write(f'\n📊 Total filas procesadas:      {stats["total_rows"]:,}')
        self.stdout.write(self.style.SUCCESS(f'✅ Servicios importados:        {stats["imported"]:,}'))
        self.stdout.write(self.style.WARNING(f'⚠️  Registros omitidos:          {stats["skipped"]:,}'))
        self.stdout.write(self.style.ERROR(f'❌ Errores:                     {stats["errors"]:,}'))

        if not dry_run:
            self.stdout.write(f'\n👥 Clientes nuevos creados:     {stats["new_clients"]:,}')
            self.stdout.write(f'👤 Clientes existentes usados:  {stats["existing_clients"]:,}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  MODO DRY-RUN: No se guardaron cambios'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ IMPORTACIÓN COMPLETADA EXITOSAMENTE'))

        self.stdout.write('\n')
