"""
Deja la ConfiguracionFacturacion con los datos OFICIALES de Aremko Hotel Spa.

Existe porque los jobs de Render mastican los `shell -c` con comillas anidadas
(salen 0 sin ejecutar) y el formulario del admin puede perder un submit si un
deploy reinicia el worker en medio. Este comando NO recibe argumentos → corre
seguro como job. Los datos provienen de la boleta real del SII (2026-07-12) y
de la postulación aceptada ese mismo día. Siguen editables por admin.

Uso: python manage.py configurar_emisor
"""
import datetime

from django.core.management.base import BaseCommand

from facturacion.models import ConfiguracionFacturacion

DATOS = {
    'rut_emisor': '76485192-7',
    'razon_social': 'AREMKO HOTEL SPA',
    # Giro EXACTO de la boleta del sistema gratuito del SII (foto 2026-07-12)
    'giro_boleta': 'Arriendo de Alojamiento, tinas, masajes y sauna. Cafeteria, artesanas',
    'direccion': 'RIO PESCADO KM 4 PARCELA 3',
    'comuna': 'Puerto Varas',
    'indicador_servicio': 3,
    'rut_firmante': '7604892-4',
    # Certificación: resolución 0 con fecha de la postulación aceptada
    'fecha_resolucion': datetime.date(2026, 7, 12),
    'numero_resolucion': 0,
}


class Command(BaseCommand):
    help = 'Setea los datos oficiales del emisor (Aremko) en ConfiguracionFacturacion.'

    def handle(self, *args, **options):
        config = ConfiguracionFacturacion.get()
        for campo, valor in DATOS.items():
            setattr(config, campo, valor)
        config.save()
        self.stdout.write(self.style.SUCCESS(
            f"Emisor configurado: {config.rut_emisor} | giro({len(config.giro_boleta)}) | "
            f"{config.direccion} | resol {config.numero_resolucion} del {config.fecha_resolucion}"))
