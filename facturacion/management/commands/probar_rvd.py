"""Sonda: cómo se le pide a SimpleAPI el Registro de Ventas Diarias (ex-RCOF).

No hay endpoint propio de consumo de folios en el catálogo de la API, así que
la hipótesis es que se pide con el mismo endpoint del sobre cambiando el tipo
de envío. Esto prueba varias formas de nombrar ese parámetro y muestra QUÉ
devuelve cada una. No envía nada al SII.
"""
import datetime

from django.core.management.base import BaseCommand, CommandError

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion
from facturacion.services import simpleapi_client


class Command(BaseCommand):
    help = 'Prueba formas de pedir el RVD y muestra la respuesta cruda.'

    def handle(self, *args, **opts):
        if not simpleapi_client.credenciales_listas():
            raise CommandError('Faltan credenciales.')
        config = ConfiguracionFacturacion.get()
        cert_bytes, cert_password = simpleapi_client.obtener_certificado()
        hoy = datetime.date.today()
        dia = hoy.strftime('%Y-%m-%d')

        boletas = [b for b in BoletaElectronica.objects
                   .filter(caso_set__startswith='CASO', ambiente='certificacion')
                   .exclude(estado='error').order_by('-folio')[:5]][::-1]
        xmls = [b.xml_dte for b in boletas]
        self.stdout.write(f'Folios: {[b.folio for b in boletas]}')

        base = {
            "RutEmisor": config.rut_emisor,
            "RutReceptor": simpleapi_client.RUT_SII,
            "FechaResolucion": config.fecha_resolucion.strftime('%Y-%m-%d')
                               if config.fecha_resolucion else '',
            "NumeroResolucion": config.numero_resolucion,
            "FechaEnvio": dia, "FechaInicio": dia, "FechaFinal": dia,
            "SecEnvio": "1",
        }
        cert = {"Rut": config.rut_firmante, "Password": cert_password}

        variantes = [
            ('A · "Tipo": 4 en la raíz', {"Certificado": cert, "Caratula": base, "Tipo": 4}),
            ('B · "tipo": 4 minúscula', {"Certificado": cert, "Caratula": base, "tipo": 4}),
            ('C · "TipoEnvio": 4', {"Certificado": cert, "Caratula": base, "TipoEnvio": 4}),
            ('D · Tipo 4 + Ambiente 0', {"Certificado": cert, "Caratula": base,
                                         "Tipo": 4, "Ambiente": 0}),
        ]
        for etiqueta, input_json in variantes:
            archivos = [('files', 'certificado.pfx', cert_bytes, 'application/x-pkcs12')]
            for i, xml in enumerate(xmls, start=2):
                archivos.append((f'files{i}', f'dte_{i - 1}.xml',
                                 xml.encode('ISO-8859-1', errors='replace'), 'text/xml'))
            try:
                resp = simpleapi_client._post_multipart(
                    simpleapi_client.BASE_URL + simpleapi_client.PATH_GENERAR_SOBRE,
                    input_json, archivos)
                plano = ' '.join(str(resp).split())
                raiz = plano.split('<')[1].split('>')[0].split()[0] if '<' in plano else '?'
                self.stdout.write(f'{etiqueta} :: raíz=<{raiz}> :: {plano[:220]}')
            except Exception as exc:
                self.stdout.write(f'{etiqueta} :: ERROR {str(exc)[:220]}')
