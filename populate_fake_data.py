import os
import django
import random
from datetime import datetime, time, timedelta
from django.utils import timezone

# --- Django Setup ---
# Set the DJANGO_SETTINGS_MODULE environment variable
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings') 
# Initialize Django
django.setup()
# --- End Django Setup ---

# Now import models after Django setup
from ventas.models import CategoriaServicio, Servicio, Cliente 

# Note: This script is now standalone, not a management command.
# We'll define functions directly instead of using BaseCommand.

def create_categories():
    """Creates sample service categories."""
    print('Creating categories...')
    categories = [
        'Masajes',
        'Tratamientos Faciales',
        'Manicure y Pedicure',
        'Depilación',
        'Peluquería',
        'Spa',
    ]
    
    for category_name in categories:
        category, created = CategoriaServicio.objects.get_or_create(
            nombre=category_name
        )
        
        if created:
            print(f'  Created category: {category_name}')
        else:
            print(f'  Category already exists: {category_name}')

def generate_time_slots(start_hour, end_hour, duration):
    """Generate time slots based on service duration"""
    slots = []
    current_hour = start_hour
    
    # Calculate time slot interval (in minutes)
    # For services <= 30 minutes, use 30-minute intervals
    # For services > 30 minutes, use 60-minute intervals
    interval = 30 if duration <= 30 else 60
    
    while current_hour < end_hour:
        for minute in range(0, 60, interval):
            # Ensure the slot END time doesn't exceed the end_hour
            slot_start_dt = datetime.now().replace(hour=current_hour, minute=minute, second=0, microsecond=0)
            slot_end_dt = slot_start_dt + timedelta(minutes=duration)
            if slot_end_dt.hour < end_hour or (slot_end_dt.hour == end_hour and slot_end_dt.minute == 0):
                 slots.append(f"{current_hour:02d}:{minute:02d}")
        current_hour += 1
    
    return slots

def create_services():
    """Creates sample services."""
    print('Creating services...')
    # Get all categories
    categories = CategoriaServicio.objects.all()
    
    if not categories:
        print('ERROR: No categories found. Please create categories first.')
        return
    
    services_data = [
        # Masajes
        {
            'category_name': 'Masajes',
            'services': [
                {'nombre': 'Masaje Relajante', 'precio_base': 35000, 'duracion': 60},
                {'nombre': 'Masaje Descontracturante', 'precio_base': 40000, 'duracion': 60},
                {'nombre': 'Masaje con Piedras Calientes', 'precio_base': 45000, 'duracion': 75},
                {'nombre': 'Masaje Deportivo', 'precio_base': 42000, 'duracion': 60},
            ]
        },
        # Tratamientos Faciales
        {
            'category_name': 'Tratamientos Faciales',
            'services': [
                {'nombre': 'Limpieza Facial Profunda', 'precio_base': 30000, 'duracion': 60},
                {'nombre': 'Tratamiento Antiarrugas', 'precio_base': 45000, 'duracion': 75},
                {'nombre': 'Hidratación Facial', 'precio_base': 28000, 'duracion': 45},
                {'nombre': 'Peeling Facial', 'precio_base': 35000, 'duracion': 45},
            ]
        },
        # Manicure y Pedicure
        {
            'category_name': 'Manicure y Pedicure',
            'services': [
                {'nombre': 'Manicure Tradicional', 'precio_base': 15000, 'duracion': 30},
                {'nombre': 'Pedicure Tradicional', 'precio_base': 18000, 'duracion': 45},
                {'nombre': 'Manicure Semipermanente', 'precio_base': 22000, 'duracion': 45},
                {'nombre': 'Pedicure Semipermanente', 'precio_base': 25000, 'duracion': 60},
            ]
        },
        # Depilación
        {
            'category_name': 'Depilación',
            'services': [
                {'nombre': 'Depilación Piernas Completas', 'precio_base': 25000, 'duracion': 45},
                {'nombre': 'Depilación Axilas', 'precio_base': 12000, 'duracion': 15},
                {'nombre': 'Depilación Bikini', 'precio_base': 18000, 'duracion': 30},
                {'nombre': 'Depilación Facial', 'precio_base': 10000, 'duracion': 15},
            ]
        },
        # Peluquería
        {
            'category_name': 'Peluquería',
            'services': [
                {'nombre': 'Corte de Cabello', 'precio_base': 15000, 'duracion': 30},
                {'nombre': 'Tinte', 'precio_base': 35000, 'duracion': 90},
                {'nombre': 'Peinado', 'precio_base': 20000, 'duracion': 45},
                {'nombre': 'Tratamiento Capilar', 'precio_base': 28000, 'duracion': 60},
            ]
        },
        # Spa
        {
            'category_name': 'Spa',
            'services': [
                {'nombre': 'Circuito de Aguas', 'precio_base': 30000, 'duracion': 90},
                {'nombre': 'Exfoliación Corporal', 'precio_base': 35000, 'duracion': 60},
                {'nombre': 'Envoltura de Chocolate', 'precio_base': 40000, 'duracion': 75},
                {'nombre': 'Día de Spa Completo', 'precio_base': 80000, 'duracion': 240},
            ]
        },
    ]
    
    # Create services for each category
    for service_group in services_data:
        try:
            category = CategoriaServicio.objects.get(nombre=service_group['category_name'])
            
            for service_data in service_group['services']:
                service, created = Servicio.objects.get_or_create(
                    nombre=service_data['nombre'],
                    defaults={
                        'categoria': category,
                        'precio_base': service_data['precio_base'],
                        'duracion': service_data['duracion'],
                        'horario_apertura': time(9, 0),  # 9:00 AM
                        'horario_cierre': time(19, 0),   # 7:00 PM
                        'activo': True,
                        'slots_disponibles': generate_time_slots(9, 19, service_data['duracion'])
                    }
                )
                
                if created:
                    print(f'  Created service: {service_data["nombre"]}')
                else:
                    print(f'  Service already exists: {service_data["nombre"]}')
        
        except CategoriaServicio.DoesNotExist:
            print(f'WARNING: Category not found: {service_group["category_name"]}')

def create_clients():
    """Creates sample clients."""
    print('Creating clients...')
    # Sample client data
    clients_data = [
        {'nombre': 'Juan Pérez', 'email': 'juan.perez@example.com', 'telefono': '912345678'},
        {'nombre': 'María González', 'email': 'maria.gonzalez@example.com', 'telefono': '923456789'},
        {'nombre': 'Carlos Rodríguez', 'email': 'carlos.rodriguez@example.com', 'telefono': '934567890'},
        {'nombre': 'Ana Martínez', 'email': 'ana.martinez@example.com', 'telefono': '945678901'},
        {'nombre': 'Pedro Sánchez', 'email': 'pedro.sanchez@example.com', 'telefono': '956789012'},
        {'nombre': 'Laura López', 'email': 'laura.lopez@example.com', 'telefono': '967890123'},
        {'nombre': 'Miguel Fernández', 'email': 'miguel.fernandez@example.com', 'telefono': '978901234'},
        {'nombre': 'Sofía Díaz', 'email': 'sofia.diaz@example.com', 'telefono': '989012345'},
        {'nombre': 'Javier Moreno', 'email': 'javier.moreno@example.com', 'telefono': '990123456'},
        {'nombre': 'Carmen Álvarez', 'email': 'carmen.alvarez@example.com', 'telefono': '901234567'},
    ]
    
    for client_data in clients_data:
        client, created = Cliente.objects.get_or_create(
            email=client_data['email'],
            defaults={
                'nombre': client_data['nombre'],
                'telefono': client_data['telefono'],
                'ciudad': 'Santiago',
                'pais': 'Chile'
            }
        )
        
        if created:
            print(f'  Created client: {client_data["nombre"]}')
        else:
            print(f'  Client already exists: {client_data["nombre"]}')

# --- Main execution block ---
if __name__ == '__main__':
    print('Starting fake data population...')
    
    # Create service categories
    create_categories()
    
    # Create services
    create_services()
    
    # Create clients
    create_clients()
    
    print('Successfully created fake data!')

    def handle(self, *args, **kwargs):
        self.stdout.write('Creating fake data...')
        
        # Create service categories
        self.create_categories()
        
        # Create services
        self.create_services()
        
        # Create clients
        self.create_clients()
        
        self.stdout.write(self.style.SUCCESS('Successfully created fake data!'))
    
    def create_categories(self):
        categories = [
            'Masajes',
            'Tratamientos Faciales',
            'Manicure y Pedicure',
            'Depilación',
            'Peluquería',
            'Spa',
        ]
        
        for category_name in categories:
            category, created = CategoriaServicio.objects.get_or_create(
                nombre=category_name
            )
            
            if created:
                self.stdout.write(f'Created category: {category_name}')
            else:
                self.stdout.write(f'Category already exists: {category_name}')
    
    def create_services(self):
        # Get all categories
        categories = CategoriaServicio.objects.all()
        
        if not categories:
            self.stdout.write(self.style.ERROR('No categories found. Please create categories first.'))
            return
        
        services_data = [
            # Masajes
            {
                'category_name': 'Masajes',
                'services': [
                    {'nombre': 'Masaje Relajante', 'precio_base': 35000, 'duracion': 60},
                    {'nombre': 'Masaje Descontracturante', 'precio_base': 40000, 'duracion': 60},
                    {'nombre': 'Masaje con Piedras Calientes', 'precio_base': 45000, 'duracion': 75},
                    {'nombre': 'Masaje Deportivo', 'precio_base': 42000, 'duracion': 60},
                ]
            },
            # Tratamientos Faciales
            {
                'category_name': 'Tratamientos Faciales',
                'services': [
                    {'nombre': 'Limpieza Facial Profunda', 'precio_base': 30000, 'duracion': 60},
                    {'nombre': 'Tratamiento Antiarrugas', 'precio_base': 45000, 'duracion': 75},
                    {'nombre': 'Hidratación Facial', 'precio_base': 28000, 'duracion': 45},
                    {'nombre': 'Peeling Facial', 'precio_base': 35000, 'duracion': 45},
                ]
            },
            # Manicure y Pedicure
            {
                'category_name': 'Manicure y Pedicure',
                'services': [
                    {'nombre': 'Manicure Tradicional', 'precio_base': 15000, 'duracion': 30},
                    {'nombre': 'Pedicure Tradicional', 'precio_base': 18000, 'duracion': 45},
                    {'nombre': 'Manicure Semipermanente', 'precio_base': 22000, 'duracion': 45},
                    {'nombre': 'Pedicure Semipermanente', 'precio_base': 25000, 'duracion': 60},
                ]
            },
            # Depilación
            {
                'category_name': 'Depilación',
                'services': [
                    {'nombre': 'Depilación Piernas Completas', 'precio_base': 25000, 'duracion': 45},
                    {'nombre': 'Depilación Axilas', 'precio_base': 12000, 'duracion': 15},
                    {'nombre': 'Depilación Bikini', 'precio_base': 18000, 'duracion': 30},
                    {'nombre': 'Depilación Facial', 'precio_base': 10000, 'duracion': 15},
                ]
            },
            # Peluquería
            {
                'category_name': 'Peluquería',
                'services': [
                    {'nombre': 'Corte de Cabello', 'precio_base': 15000, 'duracion': 30},
                    {'nombre': 'Tinte', 'precio_base': 35000, 'duracion': 90},
                    {'nombre': 'Peinado', 'precio_base': 20000, 'duracion': 45},
                    {'nombre': 'Tratamiento Capilar', 'precio_base': 28000, 'duracion': 60},
                ]
            },
            # Spa
            {
                'category_name': 'Spa',
                'services': [
                    {'nombre': 'Circuito de Aguas', 'precio_base': 30000, 'duracion': 90},
                    {'nombre': 'Exfoliación Corporal', 'precio_base': 35000, 'duracion': 60},
                    {'nombre': 'Envoltura de Chocolate', 'precio_base': 40000, 'duracion': 75},
                    {'nombre': 'Día de Spa Completo', 'precio_base': 80000, 'duracion': 240},
                ]
            },
        ]
        
        # Create services for each category
        for service_group in services_data:
            try:
                category = CategoriaServicio.objects.get(nombre=service_group['category_name'])
                
                for service_data in service_group['services']:
                    service, created = Servicio.objects.get_or_create(
                        nombre=service_data['nombre'],
                        defaults={
                            'categoria': category,
                            'precio_base': service_data['precio_base'],
                            'duracion': service_data['duracion'],
                            'horario_apertura': time(9, 0),  # 9:00 AM
                            'horario_cierre': time(19, 0),   # 7:00 PM
                            'activo': True,
                            'slots_disponibles': self.generate_time_slots(9, 19, service_data['duracion'])
                        }
                    )
                    
                    if created:
                        self.stdout.write(f'Created service: {service_data["nombre"]}')
                    else:
                        self.stdout.write(f'Service already exists: {service_data["nombre"]}')
            
            except CategoriaServicio.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Category not found: {service_group["category_name"]}'))
    
    def generate_time_slots(self, start_hour, end_hour, duration):
        """Generate time slots based on service duration"""
        slots = []
        current_hour = start_hour
        
        # Calculate time slot interval (in minutes)
        # For services <= 30 minutes, use 30-minute intervals
        # For services > 30 minutes, use 60-minute intervals
        interval = 30 if duration <= 30 else 60
        
        while current_hour < end_hour:
            for minute in range(0, 60, interval):
                if current_hour + (minute + duration) / 60 <= end_hour:
                    slots.append(f"{current_hour:02d}:{minute:02d}")
            current_hour += 1
        
        return slots
    
    def create_clients(self):
        # Sample client data
        clients_data = [
            {'nombre': 'Juan Pérez', 'email': 'juan.perez@example.com', 'telefono': '912345678'},
            {'nombre': 'María González', 'email': 'maria.gonzalez@example.com', 'telefono': '923456789'},
            {'nombre': 'Carlos Rodríguez', 'email': 'carlos.rodriguez@example.com', 'telefono': '934567890'},
            {'nombre': 'Ana Martínez', 'email': 'ana.martinez@example.com', 'telefono': '945678901'},
            {'nombre': 'Pedro Sánchez', 'email': 'pedro.sanchez@example.com', 'telefono': '956789012'},
            {'nombre': 'Laura López', 'email': 'laura.lopez@example.com', 'telefono': '967890123'},
            {'nombre': 'Miguel Fernández', 'email': 'miguel.fernandez@example.com', 'telefono': '978901234'},
            {'nombre': 'Sofía Díaz', 'email': 'sofia.diaz@example.com', 'telefono': '989012345'},
            {'nombre': 'Javier Moreno', 'email': 'javier.moreno@example.com', 'telefono': '990123456'},
            {'nombre': 'Carmen Álvarez', 'email': 'carmen.alvarez@example.com', 'telefono': '901234567'},
        ]
        
        for client_data in clients_data:
            client, created = Cliente.objects.get_or_create(
                email=client_data['email'],
                defaults={
                    'nombre': client_data['nombre'],
                    'telefono': client_data['telefono'],
                    'ciudad': 'Santiago',
                    'pais': 'Chile'
                }
            )
            
            if created:
                self.stdout.write(f'Created client: {client_data["nombre"]}')
            else:
                self.stdout.write(f'Client already exists: {client_data["nombre"]}')
