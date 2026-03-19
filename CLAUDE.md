# CLAUDE.md

Este archivo proporciona orientación a Claude Code (claude.ai/code) cuando trabaja con código en este repositorio.

## Resumen del Proyecto

Sistema de Reservas Aremko es un sistema de gestión de spa basado en Django que maneja:
- Gestión de reservas para servicios (masajes, tinas calientes, cabañas)
- Gestión de Relaciones con Clientes (CRM) con segmentación y campañas
- Procesamiento de pagos vía Flow.cl (Chile) y Stripe (internacional)
- Comunicaciones SMS/Email con controles anti-spam
- Sistema de gift cards y premios
- Órdenes de productos y gestión de inventario ("comandas")

## Comandos Comunes de Desarrollo

### Configuración de Desarrollo Local
```bash
# Usando Docker Compose (recomendado)
docker-compose up --build

# Configuración manual (si no usas Docker)
python -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Operaciones de Base de Datos
```bash
# Ejecutar migraciones
python manage.py migrate

# Crear nuevas migraciones
python manage.py makemigrations ventas
python manage.py makemigrations control_gestion

# Crear superusuario
python manage.py createsuperuser

# Respaldar base de datos
python manage.py backup_database
```

### Pruebas
```bash
# Ejecutar todas las pruebas
python manage.py test

# Ejecutar pruebas de app específica
python manage.py test ventas
python manage.py test control_gestion

# Ejecutar archivo de prueba específico
python manage.py test ventas.tests.test_models
```

### Archivos Estáticos
```bash
# Recolectar archivos estáticos (para producción)
python manage.py collectstatic --noinput
```

### Comandos de Gestión Comunes
```bash
# Crear plantillas SMS predeterminadas
python manage.py create_default_sms_templates

# Enviar comunicaciones programadas (ejecutar vía cron en producción)
python manage.py send_communication_triggers

# Normalizar y fusionar clientes duplicados
python manage.py normalize_and_merge_clients

# Probar integración SMS
python manage.py test_redvoiss
```

## Vista General de la Arquitectura

### Apps Django
- **ventas**: Lógica principal del negocio para reservas, servicios, productos, pagos, CRM y comunicaciones
- **control_gestion**: Funciones administrativas, reportes y gestión de órdenes de productos ("comandas")
- **aremko_project**: Configuración principal del proyecto Django

### Modelos Clave (ventas/models.py)
- **Cliente**: Registros de clientes con preferencias de comunicación y segmentación
- **Servicio/CategoriaServicio**: Servicios ofrecidos (masajes, tinas calientes, etc.)
- **Producto**: Productos físicos para venta
- **VentaReserva**: Registro principal de reserva/venta
- **ReservaServicio**: Reservas de servicios vinculadas a VentaReserva
- **ReservaProducto**: Órdenes de productos vinculadas a VentaReserva
- **Pago**: Registros de pago con soporte para múltiples métodos de pago
- **GiftCard**: Gestión de gift cards con seguimiento de saldo
- **Comanda**: Sistema de gestión de órdenes de productos para cocina/bar
- **Campaign/CampaignInteraction**: Gestión de campañas CRM
- **SMSTemplate/EmailTemplate**: Plantillas de comunicación

### Sistema de Comunicaciones
- Canal dual (SMS + Email) con diferentes disparadores:
  - Confirmación de reserva
  - Recordatorios 24h antes
  - Confirmación de pago
  - Encuestas post-visita (D+1)
  - Reactivación a 90 días
  - Saludos de cumpleaños
  - Newsletters segmentados
- Controles anti-spam vía preferencias de Cliente y CommunicationLog
- Integración con Redvoiss (SMS) y SendGrid (Email)

### Integración de Pagos
- **Flow.cl**: Procesador de pagos chileno
  - Crear orden: `/api/flow/create/`
  - Confirmación webhook: `/payment/confirmation/`
  - URL de retorno: `/payment/return/`
- **Gift Cards**: Método de pago interno con gestión de saldo

### Estructura de URLs
- **Admin**: `/admin/`
- **Reservas públicas**: `/`, `/servicios/`, `/calendario/`
- **Reportes**: `/servicios-vendidos/`, `/productos-vendidos/`, `/caja-diaria/`
- **CRM**: `/crm/dashboard/`, `/crm/clientes/`
- **API**: `/api/` (router DRF para endpoints REST)

### Integraciones Externas
- **Google Calendar API**: Sincronizar reservas con calendario
- **Google Cloud Storage**: Almacenamiento de archivos multimedia (imágenes)
- **Cloudinary**: Almacenamiento multimedia alternativo
- **ManyChat**: Integración WhatsApp (opcional)
- **n8n**: Plataforma de automatización de flujos de trabajo

### Variables de Entorno
Variables clave a configurar:
- Base de datos: `DATABASE_URL`
- Seguridad: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- SMS: `REDVOISS_API_URL`, `REDVOISS_USERNAME`, `REDVOISS_PASSWORD`
- Email: `SENDGRID_API_KEY`, `DEFAULT_FROM_EMAIL`
- Pagos: `FLOW_API_KEY`, `FLOW_SECRET_KEY`
- Almacenamiento: `GOOGLE_APPLICATION_CREDENTIALS`, `GS_BUCKET_NAME`
- Límites de comunicación: `SMS_DAILY_LIMIT_PER_CLIENT`, `EMAIL_WEEKLY_LIMIT_PER_CLIENT`

### Despliegue
- Producción: Render.com usando Docker
- Archivos estáticos: WhiteNoise
- Servidor web: Gunicorn
- Base de datos: PostgreSQL
- Punto de entrada: `entrypoint.sh` maneja migraciones, recolección de estáticos e inicio del servidor

### Puertos de Desarrollo
- Django: http://localhost:8002
- PostgreSQL: localhost:5435
- pgAdmin: http://localhost:5052

## Lógica de Negocio Crítica

### Flujo de Reservas
1. Cliente selecciona servicios/productos en sitio público
2. Agrega al carrito (basado en sesión)
3. Procede al checkout con información del cliente
4. Pago vía Flow.cl o gift card
5. Confirmación dispara SMS/Email
6. Crea evento en calendario y actualiza disponibilidad

### Sistema de "Comandas" (Órdenes de Productos)
- Sistema recientemente implementado para órdenes de cocina/bar
- Rastrea preparación y entrega de productos
- Valida inventario antes de permitir órdenes
- Flujo de estados: pendiente → en_progreso → completado

### Gestión de Gift Cards
- Pueden comprarse como productos o darse como premios/compensaciones
- Seguimiento de saldo con historial de uso
- Pueden usarse como método de pago
- Soporte para fecha de vencimiento

### Segmentación de Clientes
- Segmentación automática basada en:
  - Frecuencia de visitas (nuevo, regular, VIP)
  - Niveles de gasto (bajo, medio, alto)
  - Fecha de última visita
- Usada para campañas de marketing dirigidas

## Archivos Importantes para Órdenes de Productos ("Comandas")
- `ventas/admin.py`: Configuración de interfaz admin con ComandaInline
- `ventas/models.py`: Modelo Comanda con validación de inventario
- `control_gestion/views_comandas.py`: Vistas para gestionar órdenes de productos