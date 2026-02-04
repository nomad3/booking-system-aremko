# 🏗️ Arquitectura del Sistema - Aremko Booking System

## 📑 Tabla de Contenidos

- [Visión General](#visión-general)
- [Arquitectura de Alto Nivel](#arquitectura-de-alto-nivel)
- [Stack Tecnológico](#stack-tecnológico)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Arquitectura de la Aplicación](#arquitectura-de-la-aplicación)
- [Base de Datos](#base-de-datos)
- [APIs e Integraciones](#apis-e-integraciones)
- [Seguridad](#seguridad)
- [Despliegue](#despliegue)
- [Rendimiento y Escalabilidad](#rendimiento-y-escalabilidad)

## 🎯 Visión General

Aremko Booking System está diseñado siguiendo una arquitectura monolítica modular basada en Django, con clara separación de responsabilidades y preparado para escalar según las necesidades del negocio.

### Principios de Diseño

1. **Modularidad**: Separación clara entre módulos funcionales
2. **Escalabilidad**: Diseñado para crecer con el negocio
3. **Mantenibilidad**: Código limpio y bien documentado
4. **Seguridad**: Implementación de mejores prácticas de seguridad
5. **Usabilidad**: Interfaz intuitiva para usuarios y administradores

## 🏛️ Arquitectura de Alto Nivel

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Usuarios)                      │
│  HTML5 + CSS3 + JavaScript + Bootstrap + Responsive Design      │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────┴────────────────────────────────────┐
│                    Servidor Web (Gunicorn)                       │
│                    + WhiteNoise (Static Files)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                     Django Application                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Ventas    │  │Control      │  │    Admin    │            │
│  │   Module    │  │Gestión      │  │   Module    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   CRM       │  │  Analytics  │  │   Email     │            │
│  │   Module    │  │   Module    │  │   Module    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                    PostgreSQL Database                           │
└─────────────────────────────────────────────────────────────────┘
                             │
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ SendGrid │ │Cloudinary│ │  Flow    │ │ Mercado  │          │
│  │  (Email) │ │ (Images) │ │(Payments)│ │   Pago   │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## 💻 Stack Tecnológico

### Backend
- **Framework**: Django 4.2+
- **Lenguaje**: Python 3.11+
- **ORM**: Django ORM
- **API**: Django REST Framework
- **Servidor**: Gunicorn
- **Tareas Asíncronas**: Django Management Commands + Cron

### Frontend
- **HTML5**: Estructura semántica
- **CSS3**: Estilos responsive con Bootstrap 5
- **JavaScript**: Vanilla JS para interactividad
- **AJAX**: Para operaciones asíncronas
- **jQuery**: Para compatibilidad y plugins

### Base de Datos
- **Principal**: PostgreSQL 13+
- **Índices**: Optimizados para queries frecuentes
- **Respaldos**: Automatizados diariamente

### Infraestructura
- **Hosting**: Render.com
- **CDN**: Cloudinary (imágenes)
- **Email**: SendGrid
- **Monitoreo**: Render Dashboard
- **DNS**: Cloudflare

### Herramientas de Desarrollo
- **Control de Versiones**: Git + GitHub
- **CI/CD**: GitHub Actions + Render Auto-Deploy
- **Testing**: Django Test Suite
- **Linting**: Flake8 + Black
- **Documentación**: Markdown + Docstrings

## 📁 Estructura del Proyecto

```
booking-system-aremko/
│
├── aremko_project/              # Configuración principal de Django
│   ├── __init__.py
│   ├── settings.py              # Configuraciones del proyecto
│   ├── urls.py                  # URLs principales
│   ├── wsgi.py                  # Entrada WSGI para producción
│   └── asgi.py                  # Entrada ASGI (futuro)
│
├── ventas/                      # App principal de ventas y reservas
│   ├── models.py                # Modelos de datos (~2000 líneas)
│   ├── admin.py                 # Configuración del admin (~1900 líneas)
│   ├── views/                   # Vistas organizadas por función
│   │   ├── __init__.py
│   │   ├── public_views.py      # Vistas públicas
│   │   ├── checkout_views.py    # Proceso de compra
│   │   ├── api_views.py         # Endpoints API
│   │   ├── analytics_views.py   # Dashboards y reportes
│   │   ├── giftcard_views.py    # Gift cards
│   │   └── ...                  # Otras vistas especializadas
│   │
│   ├── forms/                   # Formularios Django
│   │   ├── __init__.py
│   │   └── original_forms.py
│   │
│   ├── services/                # Lógica de negocio
│   │   ├── email_service.py     # Servicio de emails
│   │   ├── giftcard_pdf_service.py # Generación PDFs
│   │   ├── pack_descuento_service.py # Cálculo descuentos
│   │   └── ...
│   │
│   ├── signals/                 # Señales Django
│   │   ├── main_signals.py      # Señales principales
│   │   └── giftcard_signals.py  # Señales gift cards
│   │
│   ├── management/commands/     # Comandos personalizados
│   │   ├── enviar_campana_email.py
│   │   ├── diagnostico_giftcards.py
│   │   └── ...
│   │
│   ├── templates/ventas/        # Templates HTML
│   │   ├── base_public.html     # Template base
│   │   ├── homepage.html        # Página principal
│   │   ├── category_detail.html # Detalle categorías
│   │   └── ...
│   │
│   ├── static/                  # Archivos estáticos
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   │
│   └── migrations/              # Migraciones de BD
│
├── control_gestion/             # Módulo de control de gestión
│   ├── models.py                # Modelos de control
│   ├── services.py              # Servicios de análisis
│   ├── views.py                 # Vistas de reportes
│   └── tasks.py                 # Tareas programadas
│
├── templates/                   # Templates globales
│   ├── admin/                   # Personalización admin
│   └── emails/                  # Templates de email
│
├── static/                      # Archivos estáticos globales
├── media/                       # Archivos subidos (local)
├── scripts/                     # Scripts de utilidad
├── docs/                        # Documentación
│
├── requirements.txt             # Dependencias Python
├── requirements-prod.txt        # Dependencias producción
├── Dockerfile                   # Configuración Docker
├── docker-compose.yml           # Orquestación local
├── entrypoint.sh               # Script de inicio
└── manage.py                   # Comando Django
```

## 🏛️ Arquitectura de la Aplicación

### Patrón MVT (Model-View-Template)

Django sigue el patrón MVT:

1. **Models**: Definen la estructura de datos y lógica de negocio
2. **Views**: Manejan las peticiones y devuelven respuestas
3. **Templates**: Renderizan la interfaz de usuario

### Capas de la Aplicación

#### 1. Capa de Presentación
- Templates HTML con herencia
- CSS responsive con Bootstrap
- JavaScript para interactividad
- AJAX para operaciones asíncronas

#### 2. Capa de Aplicación
- Views que procesan requests
- Forms para validación de datos
- Serializers para API REST
- Middleware para funciones transversales

#### 3. Capa de Negocio
- Models con lógica de dominio
- Services para operaciones complejas
- Signals para eventos del sistema
- Validators personalizados

#### 4. Capa de Datos
- Django ORM para abstracción de BD
- Managers personalizados
- Queries optimizadas
- Migraciones versionadas

### Módulos Principales

#### Módulo Ventas
- Gestión de servicios y productos
- Sistema de reservas
- Carrito de compras
- Proceso de checkout
- Integración con pagos

#### Módulo CRM
- Gestión de clientes
- Segmentación
- Campañas de email
- Historial de comunicaciones
- Sistema de premios

#### Módulo Analytics
- Dashboards en tiempo real
- Reportes de ventas
- Análisis de ocupación
- Métricas de rendimiento
- Exportación de datos

#### Módulo Gift Cards
- Venta de gift cards
- Generación de PDFs
- Sistema de códigos únicos
- Validación y redención
- Seguimiento de saldos

## 🗄️ Base de Datos

### Modelo Relacional

El sistema utiliza PostgreSQL con las siguientes entidades principales:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Cliente   │────<│VentaReserva │>────│  Servicio   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           │
                    ┌──────┴──────┐
                    │    Pago     │
                    └─────────────┘
```

### Entidades Principales

1. **Cliente**: Información de clientes
2. **Servicio**: Servicios ofrecidos (masajes, tinas, alojamiento)
3. **VentaReserva**: Reservas realizadas
4. **ReservaServicio**: Detalle de servicios en cada reserva
5. **Pago**: Pagos realizados
6. **GiftCard**: Gift cards vendidas
7. **Proveedor**: Proveedores de servicios (masajistas)
8. **EmailCampaign**: Campañas de marketing

### Optimizaciones

- Índices en campos de búsqueda frecuente
- Queries optimizadas con `select_related()` y `prefetch_related()`
- Caché de queries complejas
- Particionamiento de tablas grandes (futuro)

## 🔌 APIs e Integraciones

### API REST Interna

Endpoints principales:
- `/api/servicios/` - CRUD de servicios
- `/api/disponibilidad/` - Consulta disponibilidad
- `/api/reservas/` - Gestión de reservas
- `/api/clientes/` - Gestión de clientes
- `/api/pagos/` - Procesamiento de pagos

### Integraciones Externas

#### SendGrid (Email)
- Envío transaccional de emails
- Templates personalizados
- Tracking de apertura y clicks
- Gestión de bounces

#### Cloudinary (Imágenes)
- Almacenamiento de imágenes
- Transformaciones on-the-fly
- CDN global
- Optimización automática

#### Flow.cl (Pagos)
- Procesamiento de pagos en Chile
- Soporte múltiples medios de pago
- Webhooks de confirmación
- Gestión de reembolsos

#### Mercado Pago
- Alternativa de pagos
- Integración con wallet
- Pagos en cuotas
- Reportes de conciliación

## 🔐 Seguridad

### Medidas Implementadas

1. **Autenticación y Autorización**
   - Django Authentication System
   - Permisos granulares por usuario/grupo
   - Sesiones seguras
   - Password policies

2. **Protección contra Ataques**
   - CSRF Protection en todos los forms
   - XSS Prevention con escape automático
   - SQL Injection prevención con ORM
   - Clickjacking Protection

3. **HTTPS y Encriptación**
   - SSL/TLS obligatorio en producción
   - Cookies seguras (Secure, HttpOnly)
   - Encriptación de datos sensibles
   - Hashing de passwords con PBKDF2

4. **Validación y Sanitización**
   - Validación en frontend y backend
   - Sanitización de inputs
   - Rate limiting en APIs
   - Validación de archivos subidos

5. **Auditoría y Logs**
   - Registro de acciones importantes
   - Logs de errores centralizados
   - Monitoreo de actividad sospechosa
   - Respaldos encriptados

## 🚀 Despliegue

### Ambiente de Producción

```
┌─────────────────┐
│   Cloudflare    │ (DNS + CDN + Firewall)
└────────┬────────┘
         │
┌────────┴────────┐
│   Render.com    │
│  ┌───────────┐  │
│  │ Web Service│  │
│  │ (Gunicorn)│  │
│  └───────────┘  │
│  ┌───────────┐  │
│  │PostgreSQL │  │
│  │ Database  │  │
│  └───────────┘  │
└─────────────────┘
```

### Proceso de Despliegue

1. **Desarrollo Local**
   - Desarrollo en rama feature
   - Testing local
   - Code review

2. **Staging** (opcional)
   - Merge a rama staging
   - Deploy automático
   - Testing QA

3. **Producción**
   - Merge a main
   - Deploy automático vía Render
   - Migraciones automáticas
   - Health checks

### Configuración de Render

- **Build Command**: `pip install -r requirements-prod.txt`
- **Start Command**: `./entrypoint.sh`
- **Environment**: Python 3.11
- **Auto-Deploy**: Habilitado desde main

## 📈 Rendimiento y Escalabilidad

### Optimizaciones Actuales

1. **Frontend**
   - Compresión de assets con WhiteNoise
   - Lazy loading de imágenes
   - Minificación de CSS/JS
   - Caché del navegador

2. **Backend**
   - Queries optimizadas
   - Paginación de resultados
   - Bulk operations cuando es posible
   - Connection pooling

3. **Base de Datos**
   - Índices estratégicos
   - VACUUM automático
   - Query optimization
   - Connection limits

### Plan de Escalabilidad

1. **Corto Plazo**
   - Implementar Redis para caché
   - CDN para assets estáticos
   - Optimizar queries N+1

2. **Mediano Plazo**
   - Separar servicios (microservicios)
   - Implementar queue system (Celery)
   - Read replicas para BD

3. **Largo Plazo**
   - Kubernetes para orquestación
   - API Gateway
   - Event-driven architecture
   - Multi-region deployment

## 🔄 Flujos Principales

### Flujo de Reserva

```
Usuario → Selecciona Servicio → Verifica Disponibilidad →
→ Agrega al Carrito → Completa Datos → Selecciona Pago →
→ Procesa Pago → Confirmación → Email de Confirmación
```

### Flujo de Gift Card

```
Usuario → Selecciona Gift Card → Personaliza → Checkout →
→ Pago → Generación PDF → Envío Email → Código QR
```

### Flujo de CRM

```
Acción Cliente → Trigger → Evaluación Reglas →
→ Segmentación → Campaña → Envío → Tracking
```

## 📚 Documentación Técnica Adicional

- [Guía de Instalación](INSTALACION.md)
- [API Reference](API_REFERENCE.md)
- [Guía de Contribución](CONTRIBUTING.md)
- [Troubleshooting](TROUBLESHOOTING.md)

---

<p align="center">
  Última actualización: Febrero 2026
</p>