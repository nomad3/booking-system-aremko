"""
Comando de Django para crear la tabla NewsletterSubscriber en la base de datos.
Uso: python manage.py crear_tabla_newsletter
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Crea la tabla ventas_newslettersubscriber en la base de datos'

    def handle(self, *args, **options):
        self.stdout.write('Creando tabla ventas_newslettersubscriber...')
        
        sql = """
        CREATE TABLE IF NOT EXISTS ventas_newslettersubscriber (
            id SERIAL PRIMARY KEY,
            email VARCHAR(254) UNIQUE NOT NULL,
            first_name VARCHAR(100) NOT NULL DEFAULT '',
            last_name VARCHAR(100) NOT NULL DEFAULT '',
            subscribed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            source VARCHAR(50) NOT NULL DEFAULT 'Website Footer',
            notes TEXT NOT NULL DEFAULT '',
            last_email_sent TIMESTAMP WITH TIME ZONE NULL,
            email_open_count INTEGER NOT NULL DEFAULT 0,
            email_click_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS ventas_newslettersubscriber_email_idx 
            ON ventas_newslettersubscriber(email);
        CREATE INDEX IF NOT EXISTS ventas_newslettersubscriber_is_active_idx 
            ON ventas_newslettersubscriber(is_active);
        CREATE INDEX IF NOT EXISTS ventas_newslettersubscriber_subscribed_at_idx 
            ON ventas_newslettersubscriber(subscribed_at);
        """
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
            
            self.stdout.write(self.style.SUCCESS('✅ Tabla creada exitosamente!'))
            self.stdout.write(self.style.SUCCESS('✅ Índices creados para optimizar consultas'))
            
            # Verificar que funciona
            from ventas.models import NewsletterSubscriber
            count = NewsletterSubscriber.objects.count()
            self.stdout.write(self.style.SUCCESS(f'✅ Verificación: {count} suscriptores en la base de datos'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error al crear la tabla: {str(e)}'))
            raise
