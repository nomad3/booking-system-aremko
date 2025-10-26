import csv
from django.core.management.base import BaseCommand, CommandError
from ventas.models import CommunicationLog, Contact, Company


class Command(BaseCommand):
    help = "Crea entries PENDING en CommunicationLog a partir de un CSV con columnas: nombre,email,celular,rubro,ciudad,empresa"

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Ruta del archivo CSV')
        parser.add_argument('--subject', default='🌿 Reuniones con Resultados: Productividad + Bienestar en un solo lugar', help='Asunto por defecto')

    def handle(self, *args, **options):
        path = options['file']
        subject = options['subject']

        try:
            with open(path, newline='', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
        except FileNotFoundError:
            raise CommandError(f'No existe el archivo {path}')

        def val(row, *keys):
            for k in keys:
                if k in row and row[k]:
                    return str(row[k]).strip()
            return ''

        def norm_email(v):
            v = (v or '').strip().lower()
            return v if v and '@' in v else ''

        def norm_phone(v):
            d = ''.join(filter(str.isdigit, str(v or '')))
            if d.startswith('56') and len(d) >= 11:
                d = d[-9:]
            if len(d) == 8:
                d = '9' + d
            return f'+56{d}' if len(d) == 9 and d.startswith('9') else ''

        msg_types = dict(CommunicationLog.MESSAGE_TYPES)
        promo_key = 'PROMOTIONAL' if 'PROMOTIONAL' in msg_types else 'PROMOCIONAL'

        created = 0
        for r in rows:
            email = norm_email(val(r, 'email'))
            if not email:
                continue

            nombre = val(r, 'nombre', 'first_name') or '-'
            apellido = val(r, 'apellido', 'last_name')
            phone = norm_phone(val(r, 'celular', 'phone')) or None
            empresa = val(r, 'empresa', 'company_name')
            rubro = val(r, 'rubro', 'industry')
            ciudad = val(r, 'ciudad', 'city')

            company = None
            if empresa:
                company, _ = Company.objects.get_or_create(name=empresa)
                if rubro and hasattr(company, 'industry') and (company.industry or '') != rubro:
                    company.industry = rubro
                    company.save(update_fields=['industry'])

            contact, _ = Contact.objects.get_or_create(email=email, defaults={
                'first_name': nombre,
                'last_name': apellido,
                'phone': phone,
                'company': company,
                'notes': '; '.join([p for p in [f"Ciudad: {ciudad}" if ciudad else '', f"Rubro: {rubro}" if rubro else ''] if p])
            })

            exists = CommunicationLog.objects.filter(
                destination=email,
                communication_type='EMAIL',
                message_type=promo_key,
                status='PENDING'
            ).exists()
            if not exists:
                CommunicationLog.objects.create(
                    cliente=None,
                    campaign=None,
                    communication_type='EMAIL',
                    message_type=promo_key,
                    subject=subject,
                    content='(se rellenará al enviar)',
                    destination=email,
                    status='PENDING'
                )
                created += 1

        total = CommunicationLog.objects.filter(communication_type='EMAIL', message_type=promo_key, status='PENDING').count()
        self.stdout.write(self.style.SUCCESS(f'PENDING nuevos creados: {created}'))
        self.stdout.write(self.style.SUCCESS(f'Total PENDING: {total}'))

