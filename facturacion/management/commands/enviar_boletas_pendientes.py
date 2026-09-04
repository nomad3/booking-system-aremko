"""
Le manda su boleta a los clientes que quedaron fuera de la ventana de 24h.

Fase 3 del diseño de Jorge (04-09-2026). Las boletas de clientes que
escribieron hace poco ya salieron solas con el PDF adjunto (fase 2, gratis).
Las que quedan son de clientes que no escribieron: para esos WhatsApp exige
una plantilla, y **la plantilla se paga**. Por eso acá se agrupa: un cliente
con tres boletas de la misma visita recibe UN mensaje, no tres.

El mensaje lleva el enlace a su PASE, donde están todas — por eso da igual si
son una o cinco, el texto es el mismo. Sin esa idea, la plantilla habría
necesitado un parámetro distinto según cuántas boletas hubiera.

Uso:
  python manage.py enviar_boletas_pendientes            # manda de verdad
  python manage.py enviar_boletas_pendientes --simular  # solo muestra a quién
  python manage.py enviar_boletas_pendientes --dias 3   # ventana hacia atrás
"""
import datetime
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone

PLANTILLA = 'boleta_electronica'
IDIOMA = 'es'


class Command(BaseCommand):
    help = ('Envía por plantilla las boletas de clientes fuera de la ventana '
            'de 24h, agrupadas: un mensaje por cliente.')

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=7,
                            help='Cuántos días hacia atrás mirar. Default 7 — el '
                                 'SII da 3 días de plazo y un cliente puede '
                                 'quedar sin enviar si el cron falló un día.')
        parser.add_argument('--simular', action='store_true',
                            help='Muestra a quién se le mandaría, sin enviar.')
        parser.add_argument('--limite', type=int, default=100,
                            help='Tope de clientes por corrida (freno de seguridad).')

    def handle(self, *args, **opts):
        from facturacion.models import BoletaElectronica
        from facturacion.services.envio_whatsapp import ventana_abierta

        desde = timezone.now() - datetime.timedelta(days=opts['dias'])
        pendientes = (BoletaElectronica.objects
                      .filter(ambiente='produccion', enviada_cliente_at__isnull=True,
                              emitida_at__gte=desde)
                      .exclude(folio__isnull=True)
                      .exclude(estado__in=('error', 'pendiente', 'simulada'))
                      .select_related('venta_reserva__cliente')
                      .order_by('folio'))

        # Se agrupa por RESERVA y no por cliente: el enlace que se manda es el
        # del Pase, que es de una visita. Un cliente que vino dos veces recibe
        # un mensaje por visita, cada uno con sus boletas — juntarlos mandaría
        # un Pase que no contiene las boletas de la otra.
        por_reserva = defaultdict(list)
        sin_reserva = 0
        for b in pendientes:
            if not b.venta_reserva_id:
                sin_reserva += 1
                continue
            por_reserva[b.venta_reserva_id].append(b)

        if sin_reserva:
            self.stdout.write(self.style.WARNING(
                f'{sin_reserva} boleta(s) sin reserva asociada: no se pueden enviar.'))
        if not por_reserva:
            self.stdout.write('Sin boletas pendientes de enviar.')
            return

        enviados = saltados = fallidos = 0
        for venta_id, boletas in list(por_reserva.items())[:opts['limite']]:
            venta = boletas[0].venta_reserva
            cliente = getattr(venta, 'cliente', None)
            telefono = (getattr(cliente, 'telefono', '') or '').strip()
            folios = ', '.join(str(b.folio) for b in boletas)

            if not telefono:
                self.stdout.write(f'  reserva {venta_id}: sin teléfono — folios {folios}')
                saltados += 1
                continue
            # Si la ventana se abrió entremedio (el cliente escribió después de
            # emitida la boleta), no se gasta una plantilla: la fase 2 la manda
            # gratis con el PDF en el próximo cobro, y si no, mañana ya estará
            # cerrada y entra por acá.
            if ventana_abierta(telefono):
                self.stdout.write(f'  reserva {venta_id}: ventana abierta, '
                                  f'se deja para el envío directo — folios {folios}')
                saltados += 1
                continue

            if opts['simular']:
                self.stdout.write(f'  [simulado] reserva {venta_id} → {telefono} '
                                  f'· {len(boletas)} boleta(s): {folios}')
                enviados += 1
                continue

            ok, motivo = self._enviar(venta, cliente, telefono, boletas)
            if ok:
                self.stdout.write(self.style.SUCCESS(
                    f'  reserva {venta_id} → {telefono}: {len(boletas)} boleta(s) '
                    f'avisada(s) ({folios})'))
                enviados += 1
            else:
                self.stdout.write(self.style.WARNING(
                    f'  reserva {venta_id}: no se pudo enviar — {motivo}'))
                fallidos += 1

        self.stdout.write('')
        self.stdout.write(f'Enviados: {enviados} · saltados: {saltados} · '
                          f'fallidos: {fallidos}')

    def _enlace(self, venta, boletas):
        """A dónde manda el mensaje: al PDF si hay UNA boleta, al Pase si hay
        varias.

        Jorge (04-09-2026): «se da muchas vueltas, ¿por qué no poner directo
        el link de la boleta en pdf?». Con una sola boleta tenía razón — el
        camino era mensaje → Pase → boleta → descargar, tres toques para algo
        que el cliente solo quiere guardar. Con varias no se puede: un enlace
        no lleva a tres PDF, y ahí el Pase sí gana porque las muestra todas.
        """
        import os

        from django.urls import reverse

        from ventas.views.ficha_reserva_view import url_ficha_reserva

        base = os.getenv('COMANDA_PUBLIC_BASE_URL', 'https://www.aremko.cl').rstrip('/')
        if len(boletas) == 1:
            return base + reverse('facturacion:boleta_impresa_por_token',
                                  kwargs={'token': boletas[0].token_consulta})
        return url_ficha_reserva(venta.pk)

    def _enviar(self, venta, cliente, telefono, boletas):
        """Manda UNA plantilla con el enlace al Pase y marca las boletas."""
        import os

        import requests

        from facturacion.services.envio_whatsapp import _base_url
        from ventas.views.ficha_reserva_view import url_ficha_reserva

        nombre = ((getattr(cliente, 'nombre', '') or '').strip().split(' ') or [''])[0]
        try:
            url_pase = self._enlace(venta, boletas)
        except Exception as exc:  # noqa: BLE001
            return False, f'no se pudo armar el enlace: {exc}'

        try:
            resp = requests.post(
                f'{_base_url()}/api/v1/whatsapp/send-template',
                json={'to': telefono, 'template_name': PLANTILLA, 'lang': IDIOMA,
                      # En orden: {{1}} nombre, {{2}} enlace al Pase.
                      'texts': [nombre or 'hola', url_pase],
                      'display_text': f'Boleta electrónica: {url_pase}'},
                timeout=60)
        except Exception as exc:  # noqa: BLE001
            return False, f'error de red: {exc}'
        if resp.status_code != 200:
            return False, f'el backend respondió {resp.status_code}: {resp.text[:200]}'

        # Marcar TODAS las de esa visita: el mensaje las cubre a todas, y sin
        # esto la próxima corrida volvería a pagar otra plantilla por lo mismo.
        ahora = timezone.now()
        for b in boletas:
            b.enviada_cliente_at = ahora
            b.save(update_fields=['enviada_cliente_at', 'actualizada_at'])
        return True, ''
