# -*- coding: utf-8 -*-
"""Dimensiona el media de conversaciones (WhatsApp + Instagram/Messenger) que se
guarda en Cloudinary, para evaluar el ahorro de una política de retención.

Cuenta los adjuntos por canal y tipo, y cuántos son más viejos que N días
(= lo que recuperaría la retención). NO calcula GB exactos (eso se ve en el
dashboard de Cloudinary → Usage); el conteo por tipo ya dimensiona el peso
(video/audio pesan mucho más que imágenes).

Uso:
    python manage.py medir_media_chat
    python manage.py medir_media_chat --dias 90
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Cuenta los adjuntos de WhatsApp/Instagram en Cloudinary (total y > N días)."

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=90,
                            help='Umbral de antigüedad para estimar lo reciclable (default 90).')

    def _con_media(self, qs):
        return qs.exclude(media_file='').exclude(media_file__isnull=True)

    def _resumen(self, titulo, qs, campo_fecha, cutoff):
        con_media = self._con_media(qs)
        total = con_media.count()
        viejos = con_media.filter(**{f'{campo_fecha}__lt': cutoff}).count()
        self.stdout.write(self.style.MIGRATE_HEADING(f'\n{titulo}'))
        self.stdout.write(f'  Adjuntos en Cloudinary: {total}')
        self.stdout.write(f'  De ellos > umbral (reciclables): {viejos}  '
                          f'({(100*viejos//total) if total else 0}%)')
        # Desglose por tipo (imagen vs audio/voz vs video vs documento)
        self.stdout.write('  Por tipo:')
        por_tipo = {}
        for mt in con_media.values_list('msg_type', flat=True):
            por_tipo[mt or '—'] = por_tipo.get(mt or '—', 0) + 1
        for tipo, n in sorted(por_tipo.items(), key=lambda x: -x[1]):
            self.stdout.write(f'    {tipo:<12} {n}')
        return total, viejos

    def handle(self, *args, **options):
        dias = options['dias']
        cutoff = timezone.now() - timedelta(days=dias)
        self.stdout.write(self.style.WARNING(
            f'Umbral de retención: {dias} días (corte {cutoff:%Y-%m-%d}).'))

        from ventas.models import WhatsAppMessage
        tot_wa, viejos_wa = self._resumen(
            'WhatsApp (ventas.WhatsAppMessage)', WhatsAppMessage.objects.all(), 'timestamp', cutoff)

        tot_ch, viejos_ch = 0, 0
        try:
            from inbox_omnicanal.models import ChannelMessage
            qs = ChannelMessage.objects.all()
            tot_ch, viejos_ch = self._resumen(
                'Instagram/Messenger (inbox_omnicanal.ChannelMessage)', qs, 'timestamp', cutoff)
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f'  (no se pudo leer ChannelMessage: {exc})'))

        self.stdout.write(self.style.SUCCESS(
            f'\n=== TOTAL adjuntos en Cloudinary: {tot_wa + tot_ch} '
            f'| reciclables (> {dias} días): {viejos_wa + viejos_ch} ==='))
        self.stdout.write(
            'Para ver los GB exactos: dashboard de Cloudinary → Usage (desglose por carpeta '
            'whatsapp/ e instagram/). Video y audio pesan mucho más que las imágenes.')
