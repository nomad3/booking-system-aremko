from django.core.management.base import BaseCommand
from django.db import connection
from ventas.models import Servicio
from datetime import datetime

class Command(BaseCommand):
    help = 'Crear bloqueo de servicio de forma segura (bypass error 500)'

    def add_arguments(self, parser):
        parser.add_argument('servicio_id', type=int, help='ID del servicio a bloquear')
        parser.add_argument('fecha_inicio', help='Fecha inicio (YYYY-MM-DD)')
        parser.add_argument('fecha_fin', help='Fecha fin (YYYY-MM-DD)')
        parser.add_argument('motivo', help='Motivo del bloqueo')
        parser.add_argument(
            '--notas',
            default='',
            help='Notas adicionales (opcional)'
        )

    def handle(self, *args, **options):
        try:
            # Verificar que el servicio existe
            servicio = Servicio.objects.get(id=options['servicio_id'])
            self.stdout.write(f"Bloqueando servicio: {servicio.nombre}")

            # Inserción directa para evitar validaciones problemáticas
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO ventas_serviciobloqueo
                    (servicio_id, fecha_inicio, fecha_fin, motivo, activo,
                     creado_en, creado_por_id, notas, fecha, hora_slot)
                    VALUES (%s, %s, %s, %s, true, NOW(), 1, %s, %s, 'N/A')
                    RETURNING id
                """, [
                    servicio.id,
                    options['fecha_inicio'],
                    options['fecha_fin'],
                    options['motivo'],
                    options['notas'],
                    options['fecha_inicio']  # fecha = fecha_inicio
                ])

                bloqueo_id = cursor.fetchone()[0]

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✅ Bloqueo creado exitosamente!\n'
                        f'   ID: {bloqueo_id}\n'
                        f'   Servicio: {servicio.nombre}\n'
                        f'   Periodo: {options["fecha_inicio"]} al {options["fecha_fin"]}\n'
                        f'   Motivo: {options["motivo"]}'
                    )
                )

        except Servicio.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Error: No existe servicio con ID {options["servicio_id"]}')
            )
            self.stdout.write('\nServicios disponibles:')
            for s in Servicio.objects.filter(activo=True):
                self.stdout.write(f'  ID {s.id}: {s.nombre}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al crear bloqueo: {str(e)}'))