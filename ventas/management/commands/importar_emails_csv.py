import csv
from django.core.management.base import BaseCommand, CommandError
from ventas.models import MailParaEnviar


class Command(BaseCommand):
    help = "Importa emails desde CSV a la tabla MailParaEnviar"

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Ruta del archivo CSV')
        parser.add_argument('--asunto', required=True, help='Asunto del email')
        parser.add_argument('--contenido', required=True, help='Contenido HTML del email')
        parser.add_argument('--campana', default='', help='Nombre de la campaña')
        parser.add_argument('--prioridad', type=int, default=1, help='Prioridad (1-5)')

    def handle(self, *args, **options):
        archivo = options['file']
        asunto = options['asunto']
        contenido = options['contenido']
        campana = options['campana']
        prioridad = options['prioridad']

        try:
            with open(archivo, newline='', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
        except FileNotFoundError:
            raise CommandError(f'No existe el archivo {archivo}')

        def val(row, *keys):
            for k in keys:
                if k in row and row[k]:
                    return str(row[k]).strip()
            return ''

        def norm_email(v):
            v = (v or '').strip().lower()
            return v if v and '@' in v else ''

        creados = 0
        saltados = 0
        
        for row in rows:
            email = norm_email(val(row, 'email'))
            if not email:
                saltados += 1
                continue
                
            nombre = val(row, 'nombre', 'empresa') or 'Sin nombre'
            ciudad = val(row, 'ciudad')
            rubro = val(row, 'rubro')
            
            # Verificar si ya existe
            if MailParaEnviar.objects.filter(email=email, estado='PENDIENTE').exists():
                self.stdout.write(f'Ya existe PENDIENTE para {email}, saltando...')
                saltados += 1
                continue
            
            # Crear registro
            MailParaEnviar.objects.create(
                nombre=nombre,
                email=email,
                ciudad=ciudad,
                rubro=rubro,
                asunto=asunto,
                contenido_html=contenido,
                estado='PENDIENTE',
                prioridad=prioridad,
                campana=campana
            )
            creados += 1
            
        self.stdout.write(self.style.SUCCESS(f'✅ Importación completada:'))
        self.stdout.write(f'   📧 {creados} emails creados')
        self.stdout.write(f'   ⏭️  {saltados} emails saltados')
        
        total_pendientes = MailParaEnviar.objects.filter(estado='PENDIENTE').count()
        self.stdout.write(f'   📊 Total PENDIENTES: {total_pendientes}')