"""Prueba manual de Meta Conversions API.

Requiere META_PIXEL_ID, META_CAPI_ACCESS_TOKEN y (recomendado para tests)
META_CAPI_TEST_EVENT_CODE configurados.

Uso:
    python manage.py test_meta_capi --event purchase --venta-id 12345
    python manage.py test_meta_capi --event lead --pending-id 67890
    python manage.py test_meta_capi --event purchase --venta-id 99 \
        --email test@aremko.cl --phone +56912345678 --amount 75000

El test_event_code (visible en Events Manager → Test Events) permite ver el
evento en vivo sin que cuente como conversion real.
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from ventas.services.meta_capi_service import send_purchase_event, send_lead_event


class Command(BaseCommand):
    help = "Envia un evento de prueba a Meta CAPI (Purchase o Lead)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--event', choices=['purchase', 'lead'], default='purchase',
            help='Tipo de evento a enviar.',
        )
        parser.add_argument('--venta-id', type=int, default=999999)
        parser.add_argument('--pending-id', type=int, default=999999)
        parser.add_argument('--amount', type=float, default=50000.0)
        parser.add_argument('--email', default='test@aremko.cl')
        parser.add_argument('--phone', default='+56912345678')
        parser.add_argument('--nombre', default='Test Aremko')

    def handle(self, *args, **opts):
        if not settings.META_PIXEL_ID:
            raise CommandError("META_PIXEL_ID no configurado.")
        if not settings.META_CAPI_ACCESS_TOKEN:
            raise CommandError("META_CAPI_ACCESS_TOKEN no configurado.")

        test_code = getattr(settings, 'META_CAPI_TEST_EVENT_CODE', '')
        if test_code:
            self.stdout.write(self.style.WARNING(
                f"Usando test_event_code={test_code} (no cuenta como conversion real)."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "SIN test_event_code → evento contara como REAL en Events Manager."
            ))

        event = opts['event']
        if event == 'purchase':
            result = send_purchase_event(
                venta_id=opts['venta_id'],
                amount=opts['amount'],
                email=opts['email'],
                phone=opts['phone'],
                nombre_completo=opts['nombre'],
            )
            label = f"Purchase (venta_id={opts['venta_id']})"
        else:
            result = send_lead_event(
                pending_id=opts['pending_id'],
                amount=opts['amount'],
                email=opts['email'],
                phone=opts['phone'],
                nombre_completo=opts['nombre'],
            )
            label = f"Lead (pending_id={opts['pending_id']})"

        if result.get('ok'):
            self.stdout.write(self.style.SUCCESS(f"OK - {label} enviado a Meta."))
            self.stdout.write(f"Respuesta: {result.get('body')}")
        elif result.get('skipped'):
            self.stdout.write(self.style.ERROR(f"OMITIDO - {result.get('reason')}"))
        else:
            self.stdout.write(self.style.ERROR(f"ERROR - {label}"))
            self.stdout.write(f"Detalle: {result}")

        self.stdout.write(
            "\nVerifica en Meta Business → Events Manager → Test Events "
            f"(si usaste test_event_code) o en Overview del pixel {settings.META_PIXEL_ID}."
        )
