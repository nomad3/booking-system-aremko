# -*- coding: utf-8 -*-
"""Retención del media de conversaciones: borra de Cloudinary los adjuntos de
WhatsApp / Instagram / Messenger con más de N días (default 90 = 3 meses).

CONSERVA el registro del mensaje (texto/caption). Solo elimina el ARCHIVO y deja
el campo media_file vacío. Si el mensaje no tenía texto, deja un marcador para que
el hilo no quede en blanco.

Idempotente: un mensaje ya purgado (media_file vacío) se ignora.

Uso:
    python manage.py purgar_media_chat --dry-run          # ver qué borraría, sin tocar nada
    python manage.py purgar_media_chat                    # borra > 90 días (default)
    python manage.py purgar_media_chat --dias 180         # otra ventana
    python manage.py purgar_media_chat --canal whatsapp   # solo un canal
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

MARCADOR = '[archivo eliminado por antigüedad]'


class Command(BaseCommand):
    help = "Borra de Cloudinary los adjuntos de chat con más de N días (conserva el texto)."

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=90,
                            help='Borrar adjuntos con más de N días (default 90 = 3 meses).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo informar qué se borraría, sin tocar nada.')
        parser.add_argument('--canal', choices=['all', 'whatsapp', 'instagram', 'messenger'],
                            default='all', help='Limitar a un canal (default all).')

    def _con_media_viejo(self, qs, cutoff):
        return (qs.exclude(media_file='').exclude(media_file__isnull=True)
                  .filter(timestamp__lt=cutoff))

    def _purgar_qs(self, etiqueta, qs, dry_run):
        total = qs.count()
        if not total:
            self.stdout.write(f'{etiqueta}: 0 adjuntos a purgar.')
            return 0, 0
        if dry_run:
            self.stdout.write(self.style.WARNING(f'{etiqueta}: {total} adjuntos se borrarían (dry-run).'))
            return total, 0
        borrados, errores = 0, 0
        for obj in qs.iterator(chunk_size=200):
            try:
                obj.media_file.delete(save=False)  # elimina el archivo de Cloudinary
                obj.media_file = None
                campos = ['media_file']
                if not (obj.body or '').strip():
                    obj.body = MARCADOR
                    campos.append('body')
                obj.save(update_fields=campos)
                borrados += 1
                if borrados % 200 == 0:
                    self.stdout.write(f'  ...{borrados}/{total}')
            except Exception as exc:  # noqa: BLE001 — un archivo con error no debe frenar el batch
                errores += 1
                self.stderr.write(f'  error purgando id={getattr(obj, "id", "?")}: {exc}')
        self.stdout.write(self.style.SUCCESS(f'{etiqueta}: {borrados} borrados, {errores} errores.'))
        return total, borrados

    def handle(self, *args, **options):
        dias = options['dias']
        dry_run = options['dry_run']
        canal = options['canal']
        cutoff = timezone.now() - timedelta(days=dias)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Retención de media de chat: borrar > {dias} días (corte {cutoff:%Y-%m-%d}). '
            f'{"DRY-RUN (no se toca nada)" if dry_run else "EJECUCIÓN REAL"}'))

        tot, bor = 0, 0

        if canal in ('all', 'whatsapp'):
            from ventas.models import WhatsAppMessage
            qs = self._con_media_viejo(WhatsAppMessage.objects.all(), cutoff)
            t, b = self._purgar_qs('WhatsApp', qs, dry_run)
            tot += t; bor += b

        if canal in ('all', 'instagram', 'messenger'):
            try:
                from inbox_omnicanal.models import ChannelMessage
                qs = ChannelMessage.objects.all()
                if canal in ('instagram', 'messenger'):
                    qs = qs.filter(canal=canal)
                qs = self._con_media_viejo(qs, cutoff)
                etiqueta = 'Instagram/Messenger' if canal == 'all' else canal.capitalize()
                t, b = self._purgar_qs(etiqueta, qs, dry_run)
                tot += t; bor += b
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f'(no se pudo procesar ChannelMessage: {exc})')

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'\n=== DRY-RUN: {tot} adjuntos se borrarían. Corre sin --dry-run para ejecutar. ==='))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n=== LISTO: {bor} adjuntos borrados de Cloudinary (de {tot}). '
                f'El texto de las conversaciones se conservó. ==='))
