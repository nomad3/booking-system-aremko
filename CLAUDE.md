# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Aremko Booking System is a Django-based spa management system for Aremko Spa Puerto Varas (Chile) handling:
- Reservation management for services (massages, hot tubs, cabins)
- CRM with customer segmentation and marketing campaigns
- Payment processing via Flow.cl (Chilean gateway) and gift cards
- Dual-channel communications (SMS/Email) with anti-spam controls
- Product orders and inventory management ("comandas" system)
- Provider payment tracking and commission calculations

## Development Commands

### Local Development with Docker (Recommended)
```bash
# Start all services (web, postgres, pgadmin)
docker-compose up --build

# Access points:
# - Django app: http://localhost:8002
# - PostgreSQL: localhost:5435
# - pgAdmin: http://localhost:5052
```

### Manual Development Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Testing
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test ventas
python manage.py test control_gestion

# Run specific test class
python manage.py test ventas.tests.test_models.ClienteTestCase
```

### Database Operations
```bash
# Apply migrations
python manage.py migrate

# Create migrations for apps
python manage.py makemigrations ventas
python manage.py makemigrations control_gestion

# Database backup
python manage.py backup_database

# Normalize duplicate clients
python manage.py normalize_and_merge_clients
```

### Communication Management
```bash
# Create SMS templates
python manage.py create_default_sms_templates

# Send scheduled communications (cron job in production)
python manage.py send_communication_triggers

# Test SMS integration
python manage.py test_redvoiss
```

## Architecture Overview

### Django Apps Structure

**ventas/** - Core business logic (38 subdirectories)
- Models: Cliente, Servicio, Producto, VentaReserva, ReservaServicio, ReservaProducto, Pago, GiftCard, Comanda
- Services: communication_service.py, giftcard_pdf_service.py, pack_descuento_service.py, redvoiss_service.py
- Signals: main_signals.py, giftcard_signals.py
- API: ViewSets and custom endpoints using DRF

**control_gestion/** - Operations management (22 subdirectories)
- Task management with swimlanes (areas)
- Comanda (product order) management
- Performance reports and dashboards

**aremko_project/** - Django configuration
- settings.py: Environment-based configuration
- urls.py: 50+ URL patterns including SEO endpoints

### Key Models and Their Relationships

```python
# Core reservation flow
Cliente -> VentaReserva -> ReservaServicio -> Servicio
                        -> ReservaProducto -> Producto
                        -> Pago -> (multiple payment methods)

# Communication tracking
Cliente -> CommunicationLog <- Campaign -> CampaignInteraction

# Gift card system
Cliente -> GiftCard -> GiftCardHistory
```

### Service Layer Architecture

Services in `ventas/services/`:
- **communication_service.py**: Handles SMS/Email sending with anti-spam logic
- **giftcard_pdf_service.py**: Generates PDF gift cards using WeasyPrint
- **pack_descuento_service.py**: Calculates discounts and pack pricing
- **redvoiss_service.py**: SMS API integration for Chile
- **crm_service.py**: Customer segmentation and campaign management
- **ai_service.py**: OpenAI integration for intelligent features

### Payment Integration Flow

1. **Flow.cl (Chilean processor)**:
   - Create order: POST `/api/flow/create/` with order data
   - Flow redirects to their payment page
   - Webhook callback: `/payment/confirmation/` (verify signature)
   - User returns to: `/payment/return/` with token

2. **Gift Card Payment**:
   - Internal balance-based payment
   - Tracked via GiftCardHistory
   - Can be combined with other payment methods

### Communication System Architecture

**Trigger Points**:
- `send_reservation_confirmation()` - Immediate on booking
- `send_24h_reminder()` - Scheduled via cron
- `send_payment_confirmation()` - On 100% payment
- `send_post_visit_survey()` - D+1 after service
- `send_reactivation_campaign()` - 90 days inactive
- `send_birthday_greeting()` - Annual per client
- `send_newsletter()` - Segmented campaigns

**Anti-Spam Controls**:
```python
# In Cliente model:
sms_daily_limit = IntegerField(default=2)
email_weekly_limit = IntegerField(default=3)
horario_preferido_inicio = TimeField()
horario_preferido_fin = TimeField()
permite_sms = BooleanField()
permite_email = BooleanField()
```

### Comanda (Product Order) System

**Workflow**:
1. Create Comanda linked to VentaReserva
2. Add ComandaItem entries with products
3. Validate inventory (stock > 0)
4. State flow: pendiente -> en_progreso -> completado
5. Track preparation and delivery

**Admin Configuration**:
- ComandaInline in VentaReservaAdmin
- Custom validation in clean() methods
- Inventory auto-decrement on save

### Critical Business Logic

**Availability Calculation**: See slot/calendar logic in `ventas/views.py`. Honors `ServicioBloqueo` (blocked slots), existing `ReservaServicio` load, and service `min_capacity`/`max_capacity`.

**Phone Normalization**: Chilean numbers are stored with `+56` prefix. See `normalize_all_phones.py` and `test_phone_normalization.py`. Run `normalize_and_merge_clients` after bulk imports.

**Client Segmentation** (`ventas/models.py`):
- Frequency: new (0-1 visits), regular (2-4), VIP (5+)
- Spending: low (<100K CLP), medium (100-300K), high (300K+)
- Activity: last visit date tracking

**Provider Payments** (`ventas/models.py`):
- PagoMasajista tracks provider commissions
- DetalleServicioPago breaks down service payments
- Commission rates configurable per provider

## Environment Variables

### Required for Production
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Security
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=aremko.cl,www.aremko.cl

# SMS (Redvoiss - Chile)
REDVOISS_API_URL=https://api.redvoiss.com
REDVOISS_USERNAME=your-username
REDVOISS_PASSWORD=your-password

# Email (SendGrid)
SENDGRID_API_KEY=your-api-key
DEFAULT_FROM_EMAIL=noreply@aremko.cl

# Payment (Flow.cl)
FLOW_API_KEY=your-api-key
FLOW_SECRET_KEY=your-secret-key
FLOW_API_URL=https://www.flow.cl/api
FLOW_RETURN_URL=https://aremko.cl/payment/return/
FLOW_CONFIRMATION_URL=https://aremko.cl/payment/confirmation/

# Storage (Cloudinary preferred)
CLOUDINARY_URL=cloudinary://key:secret@cloud_name

# Anti-spam limits
SMS_DAILY_LIMIT_PER_CLIENT=2
SMS_MONTHLY_LIMIT_PER_CLIENT=8
EMAIL_WEEKLY_LIMIT_PER_CLIENT=1
EMAIL_MONTHLY_LIMIT_PER_CLIENT=4

# Automation endpoints (n8n, campaign targets) — required header X-API-KEY
AUTOMATION_API_KEY=your-key
```

### Scheduled Tasks (cron)
`python manage.py send_communication_triggers` is the central cron entry point. It dispatches: 24h reminders, post-visit surveys (D+1), 90-day reactivation campaigns, birthday greetings, and segmented newsletters. Run from host cron or Render cron job.

## Deployment Configuration

### Docker Deployment (Render.com)
- Uses Dockerfile with python:3.9-slim base
- entrypoint.sh handles migrations and static collection
- Gunicorn with 1 worker, 120s timeout
- WhiteNoise serves static files

### Database Considerations
- PostgreSQL 13+ required
- Connection pooling: CONN_MAX_AGE=600
- Timeout: 10 seconds
- Use DATABASE_URL for configuration

### Static Files Strategy
1. Development: Django serves from /static/
2. Production: WhiteNoise with compressed manifest storage
3. Media files: Cloudinary (primary) or GCS (fallback)

## Important Files for Specific Features

### Comanda (Product Orders)
- `ventas/admin.py`: ComandaInline configuration (~lines 800-900)
- `ventas/models.py`: Comanda and ComandaItem models
- `control_gestion/views_comandas.py`: Management views
- `ventas/templates/ventas/comanda_*.html`: UI templates

### Gift Cards
- `ventas/models.py`: GiftCard model with balance tracking
- `ventas/services/giftcard_pdf_service.py`: PDF generation
- `ventas/views.py`: Purchase and redemption logic
- `ventas/signals/giftcard_signals.py`: Auto-creation triggers

### CRM and Campaigns
- `ventas/models.py`: Campaign, CampaignInteraction models
- `ventas/crm/`: CRM-specific views and utilities
- `ventas/services/crm_service.py`: Segmentation logic
- `ventas/templates/ventas/crm/`: CRM UI templates

### SMS/Email Communications
- `ventas/services/communication_service.py`: Core sending logic
- `ventas/models.py`: SMSTemplate, EmailTemplate models
- `ventas/management/commands/send_communication_triggers.py`: Cron job
- `ventas/templates/ventas/emails/`: Email HTML templates

## API Endpoints

### Public API
- `/api/servicios/` - Service listing and availability
- `/api/calendario/` - Calendar availability
- `/api/flow/create/` - Payment initiation
- `/api/cart/` - Shopping cart operations

### Admin API (requires authentication)
- `/api/ventas/` - Sales management
- `/api/clientes/` - Customer management
- `/api/comandas/` - Product order management
- `/api/campaigns/` - Marketing campaigns

### Webhook Endpoints
- `/payment/confirmation/` - Flow.cl payment webhook
- `/manychat/webhook/` - ManyChat integration
- `/n8n/webhook/` - n8n automation platform

## Database Schema Notes

### Performance Indexes
- Cliente: telefono, email (unique constraints)
- VentaReserva: fecha_reserva, estado_pago
- ReservaServicio: fecha, hora_inicio, servicio_id
- CommunicationLog: cliente_id, created_at

### Audit Trail
- `MovimientoCliente` logs client-facing changes (see `/auditoria-movimientos/` report).
- `CommunicationLog` is the source of truth for send attempts, costs and errors.