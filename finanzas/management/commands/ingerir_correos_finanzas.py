# -*- coding: utf-8 -*-
"""P-22 F3: lee los correos de plata de ecolonco por IMAP y los convierte en
movimientos financieros. v1: transferencias SALIENTES de Mercado Pago («Tu
transferencia fue enviada») — pagos a trabajadores, insumos y barridos a
Scotiabank, que la API de MP no expone.

Modo LECTURA por defecto (muestra qué haría); con --aplicar escribe.
Idempotente por Message-ID. La sesión IMAP es de SOLO LECTURA (readonly=True):
no marca como leído ni toca nada en la bandeja de Jorge.

Credenciales por variables de entorno (nunca en el código):
  GMAIL_FINANZAS_USER          (default ecolonco@gmail.com)
  GMAIL_FINANZAS_APP_PASSWORD  (App Password de Gmail, se crea en 1 minuto)
"""
import email
import email.header
import email.utils
import imaplib
import os
import re
from datetime import date, timedelta

from django.core.management.base import BaseCommand

# Los nombres de mes de IMAP son fijos en inglés — no depender del locale.
MESES_IMAP = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
              7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}

REMITENTE_MP = 'info@mercadopago.com'
ASUNTO_MP = 'Tu transferencia fue enviada'


def _carpeta_todos(conexion):
    """Nombre de la carpeta All Mail (localizada: '[Gmail]/Todos' en español)."""
    try:
        typ, carpetas = conexion.list()
        for cruda in carpetas or []:
            linea = cruda.decode(errors='replace')
            if '\\All' in linea:
                m = re.search(r'"([^"]+)"\s*$', linea)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def _asunto(msg):
    partes = email.header.decode_header(msg.get('Subject', ''))
    out = ''
    for texto, cod in partes:
        out += texto.decode(cod or 'utf-8', errors='replace') if isinstance(texto, bytes) else texto
    return out.strip()


def _cuerpo_html(msg):
    """La parte HTML del correo (o el texto plano como respaldo)."""
    respaldo = ''
    for parte in msg.walk():
        tipo = parte.get_content_type()
        if tipo not in ('text/html', 'text/plain'):
            continue
        crudo = parte.get_payload(decode=True)
        if crudo is None:
            continue
        texto = crudo.decode(parte.get_content_charset() or 'utf-8', errors='replace')
        if tipo == 'text/html':
            return texto
        respaldo = respaldo or texto
    return respaldo


class Command(BaseCommand):
    help = 'Lee correos de transferencias MP (IMAP solo-lectura) y crea movimientos.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=7,
                            help='Ventana hacia atrás en días (default 7).')
        parser.add_argument('--aplicar', action='store_true',
                            help='Escribe. Sin esto, solo informa.')

    def handle(self, *args, **opts):
        from finanzas.services import (parsear_transferencia_mp,
                                       referencia_correo,
                                       registrar_transferencia_mp)

        usuario = os.environ.get('GMAIL_FINANZAS_USER', 'ecolonco@gmail.com')
        clave = os.environ.get('GMAIL_FINANZAS_APP_PASSWORD')
        if not clave:
            # Salida limpia a propósito: auditoria_horaria sigue con lo demás.
            self.stdout.write(self.style.WARNING(
                'GMAIL_FINANZAS_APP_PASSWORD no configurada — ingesta de '
                'correos saltada.'))
            return

        desde = date.today() - timedelta(days=opts['dias'])
        criterio = (f'(SINCE {desde.day:02d}-{MESES_IMAP[desde.month]}-{desde.year} '
                    f'FROM "{REMITENTE_MP}" SUBJECT "transferencia fue enviada")')

        con = imaplib.IMAP4_SSL('imap.gmail.com')
        try:
            con.login(usuario, clave)
            carpeta = _carpeta_todos(con) or 'INBOX'
            con.select(f'"{carpeta}"', readonly=True)
            typ, datos = con.search(None, criterio)
            ids = (datos[0] or b'').split()
            self.stdout.write(f'{len(ids)} correos de transferencias MP en '
                              f'{opts["dias"]} días (carpeta {carpeta}).')

            resumen = {'creado': 0, 'ya_existe': 0, 'en_historico': 0,
                       'sin_parsear': 0, 'movs': 0}
            for num in ids:
                typ, crudo = con.fetch(num, '(RFC822)')
                if typ != 'OK' or not crudo or crudo[0] is None:
                    continue
                msg = email.message_from_bytes(crudo[0][1])
                if not _asunto(msg).startswith(ASUNTO_MP):
                    continue

                datos_tr = parsear_transferencia_mp(_cuerpo_html(msg))
                try:
                    fecha = email.utils.parsedate_to_datetime(msg.get('Date')).date()
                except Exception:
                    fecha = None
                if not datos_tr or not fecha:
                    resumen['sin_parsear'] += 1
                    self.stdout.write(self.style.WARNING(
                        f'  SIN PARSEAR (revisar a mano): {_asunto(msg)!r} '
                        f'del {msg.get("Date")}'))
                    continue

                ref = referencia_correo(msg.get('Message-ID'),
                                        respaldo=f"{fecha}|{datos_tr['monto']}|{datos_tr['beneficiario']}")
                etiqueta = (f"  {fecha} ${datos_tr['monto']:,} → "
                            f"{datos_tr['beneficiario']}").replace(',', '.')
                if opts['aplicar']:
                    estado, n = registrar_transferencia_mp(datos_tr, fecha, ref)
                    resumen[estado] += 1
                    resumen['movs'] += n
                    self.stdout.write(f'{etiqueta}  [{estado}]')
                else:
                    ya = 'creado' if not _ya_registrada(ref) else 'ya_existe'
                    self.stdout.write(f'{etiqueta}  [{ya} si se aplica]')
        finally:
            try:
                con.logout()
            except Exception:
                pass

        if opts['aplicar']:
            self.stdout.write(self.style.SUCCESS(
                f"Correos: {resumen['creado']} nuevos ({resumen['movs']} movimientos) · "
                f"{resumen['ya_existe']} ya estaban · {resumen['en_historico']} en histórico · "
                f"{resumen['sin_parsear']} sin parsear"))
        else:
            self.stdout.write(self.style.WARNING(
                'MODO LECTURA. Con --aplicar se escriben.'))


def _ya_registrada(referencia):
    from finanzas.models import MovimientoFinanciero
    return MovimientoFinanciero.objects.filter(
        referencia__in=(referencia, f'{referencia}:sale')).exists()
