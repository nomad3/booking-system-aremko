"""
Management command para limpiar el historial de una conversación.

Útil para testing: permite borrar mensajes antiguos que puedan inducir errores en Luna.

Uso:
    python manage.py limpiar_conversacion --phone +56958655810
    python manage.py limpiar_conversacion  # usa valor por defecto
"""

from django.core.management.base import BaseCommand, CommandError
from ventas.models import WhatsAppMessage
from carrito_reservas.models import CarritoReserva
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Limpia el historial de una conversación por teléfono'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            type=str,
            default='+56958655810',
            help='Teléfono a limpiar (default: +56958655810)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='No pedir confirmación',
        )

    def handle(self, *args, **options):
        phone = options['phone']
        force = options['force']

        self.stdout.write(f'🧹 Limpiando conversación: {phone}')

        # Contar mensajes a borrar
        msg_count = WhatsAppMessage.objects.filter(phone=phone).count()
        carrito_count = CarritoReserva.objects.filter(
            canal='whatsapp',
            external_id=phone
        ).count()

        if msg_count == 0 and carrito_count == 0:
            self.stdout.write(self.style.WARNING(f'No hay conversación para {phone}'))
            return

        # Confirmación
        if not force:
            self.stdout.write(
                f'\n⚠️  Se borrarán:\n'
                f'   • {msg_count} mensajes WhatsApp\n'
                f'   • {carrito_count} carrito(s)\n'
            )
            confirm = input('¿Confirmar? (s/n): ').strip().lower()
            if confirm != 's':
                self.stdout.write(self.style.WARNING('Cancelado'))
                return

        # Borrar mensajes
        if msg_count > 0:
            WhatsAppMessage.objects.filter(phone=phone).delete()
            self.stdout.write(self.style.SUCCESS(f'✅ Borrados {msg_count} mensajes'))
            logger.info(f'[Limpiar] Borrados {msg_count} msgs de {phone}')

        # Borrar carrito
        if carrito_count > 0:
            CarritoReserva.objects.filter(canal='whatsapp', external_id=phone).delete()
            self.stdout.write(self.style.SUCCESS(f'✅ Borrados {carrito_count} carrito(s)'))
            logger.info(f'[Limpiar] Borrados {carrito_count} carritos de {phone}')

        self.stdout.write(self.style.SUCCESS('\n✨ Conversación limpia. Luna comenzará con registro vacío.'))
