# 🚀 Guía de Instalación y Configuración - Aremko Booking System

## 📑 Tabla de Contenidos

- [Requisitos Previos](#requisitos-previos)
- [Instalación Local](#instalación-local)
- [Instalación con Docker](#instalación-con-docker)
- [Configuración](#configuración)
- [Configuración de Servicios Externos](#configuración-de-servicios-externos)
- [Inicialización del Sistema](#inicialización-del-sistema)
- [Verificación](#verificación)
- [Troubleshooting](#troubleshooting)

## 📋 Requisitos Previos

### Sistema Operativo
- Ubuntu 20.04+ / macOS 10.15+ / Windows 10+ con WSL2
- 4GB RAM mínimo (8GB recomendado)
- 10GB espacio en disco

### Software Requerido
- **Python 3.11+**
- **PostgreSQL 13+**
- **Git**
- **pip y virtualenv**
- **Node.js 16+** (para compilar assets)

### Software Opcional
- **Docker y Docker Compose** (para instalación containerizada)
- **Redis** (para caché - futuro)
- **nginx** (para producción local)

## 💻 Instalación Local

### 1. Clonar el Repositorio

```bash
# Clonar el repositorio
git clone https://github.com/nomad3/booking-system-aremko.git

# Entrar al directorio
cd booking-system-aremko
```

### 2. Configurar Entorno Virtual

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Linux/macOS:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3. Instalar Dependencias

```bash
# Actualizar pip
pip install --upgrade pip

# Instalar dependencias de desarrollo
pip install -r requirements.txt

# Para producción usar:
# pip install -r requirements-prod.txt
```

### 4. Configurar PostgreSQL

```bash
# Instalar PostgreSQL (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# macOS con Homebrew
brew install postgresql
brew services start postgresql

# Crear usuario y base de datos
sudo -u postgres psql

# En la consola PostgreSQL:
CREATE USER aremko_user WITH PASSWORD 'tu_password_seguro';
CREATE DATABASE aremko_db OWNER aremko_user;
GRANT ALL PRIVILEGES ON DATABASE aremko_db TO aremko_user;
\q
```

### 5. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar con tu editor favorito
nano .env  # o vim, code, etc.
```

Configurar las siguientes variables esenciales:

```env
# Django
SECRET_KEY=django-insecure-genera-una-clave-segura-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Base de datos
DATABASE_URL=postgres://aremko_user:tu_password_seguro@localhost:5432/aremko_db

# Email (SendGrid)
SENDGRID_API_KEY=tu-api-key-de-sendgrid
VENTAS_FROM_EMAIL=aremkospa@gmail.com
VENTAS_BCC_EMAIL=admin@aremko.cl

# Cloudinary
CLOUDINARY_CLOUD_NAME=tu-cloud-name
CLOUDINARY_API_KEY=tu-api-key
CLOUDINARY_API_SECRET=tu-api-secret

# URLs
SITE_URL=http://localhost:8000
```

### 6. Ejecutar Migraciones

```bash
# Crear migraciones si hay cambios
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Ver migraciones aplicadas
python manage.py showmigrations
```

### 7. Cargar Datos Iniciales

```bash
# Crear superusuario
python manage.py createsuperuser
# Seguir las instrucciones: usuario, email, password

# Cargar fixtures (si existen)
python manage.py loaddata fixtures/categorias.json
python manage.py loaddata fixtures/servicios_iniciales.json

# Crear templates de SMS por defecto
python manage.py create_default_sms_templates
```

### 8. Recopilar Archivos Estáticos

```bash
# Recopilar archivos estáticos
python manage.py collectstatic --noinput
```

### 9. Ejecutar Servidor de Desarrollo

```bash
# Iniciar servidor
python manage.py runserver

# O en un puerto específico
python manage.py runserver 0.0.0.0:8080
```

Acceder a:
- **Aplicación**: http://localhost:8000
- **Admin**: http://localhost:8000/admin

## 🐳 Instalación con Docker

### 1. Prerequisitos Docker

```bash
# Verificar instalación
docker --version
docker-compose --version
```

### 2. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp .env.docker.example .env

# Editar configuración
nano .env
```

### 3. Construir y Ejecutar

```bash
# Construir imágenes
docker-compose build

# Iniciar servicios
docker-compose up -d

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down

# Detener y eliminar volúmenes (CUIDADO: elimina datos)
docker-compose down -v
```

### 4. Comandos Útiles con Docker

```bash
# Ejecutar migraciones
docker-compose exec web python manage.py migrate

# Crear superusuario
docker-compose exec web python manage.py createsuperuser

# Acceder a shell Django
docker-compose exec web python manage.py shell

# Acceder a PostgreSQL
docker-compose exec db psql -U aremko_user -d aremko_db

# Ejecutar tests
docker-compose exec web python manage.py test
```

## ⚙️ Configuración

### Variables de Entorno Completas

```env
# ===== DJANGO CORE =====
SECRET_KEY=tu-secret-key-super-segura
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,www.aremko.cl
CSRF_TRUSTED_ORIGINS=https://www.aremko.cl,https://aremko.cl
DJANGO_SETTINGS_MODULE=aremko_project.settings

# ===== DATABASE =====
DATABASE_URL=postgres://user:password@host:port/dbname
DB_CONN_MAX_AGE=60

# ===== EMAIL (SendGrid) =====
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxx
VENTAS_FROM_EMAIL=aremkospa@gmail.com
VENTAS_BCC_EMAIL=admin@aremko.cl,backup@aremko.cl
EMAIL_BACKEND=anymail.backends.sendgrid.EmailBackend

# ===== CLOUDINARY =====
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=abcdefghijklmnopqrstuvwx
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name

# ===== PAYMENT GATEWAYS =====
# Flow.cl
FLOW_API_KEY=your-flow-api-key
FLOW_SECRET_KEY=your-flow-secret-key
FLOW_ENVIRONMENT=production  # o sandbox para testing

# Mercado Pago
MERCADOPAGO_ACCESS_TOKEN=APP_USR-xxxxxxxxxxxx
MERCADOPAGO_PUBLIC_KEY=APP_USR-xxxxxxxxxxxx

# ===== URLS =====
SITE_URL=https://www.aremko.cl
MEDIA_URL=/media/
STATIC_URL=/static/

# ===== SECURITY =====
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_BROWSER_XSS_FILTER=True
SECURE_CONTENT_TYPE_NOSNIFF=True

# ===== SUPERUSER (para creación automática) =====
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@aremko.cl
DJANGO_SUPERUSER_PASSWORD=password-super-seguro

# ===== COMUNICACIONES =====
COMMUNICATION_SMS_ENABLED=true
SMS_DAILY_LIMIT_PER_CLIENT=2
SMS_MONTHLY_LIMIT_PER_CLIENT=8
EMAIL_WEEKLY_LIMIT_PER_CLIENT=1
EMAIL_MONTHLY_LIMIT_PER_CLIENT=4

# ===== MONITORING =====
SENTRY_DSN=https://xxxx@sentry.io/yyyy
LOG_LEVEL=INFO
```

### Configuración de Settings.py

El archivo `settings.py` ya está configurado para leer estas variables de entorno. Principales secciones:

```python
# Base de datos
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600
    )
}

# Email
EMAIL_BACKEND = 'anymail.backends.sendgrid.EmailBackend'
ANYMAIL = {
    'SENDGRID_API_KEY': os.getenv('SENDGRID_API_KEY'),
}

# Cloudinary
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
}
```

## 🔧 Configuración de Servicios Externos

### SendGrid (Email)

1. **Crear cuenta en SendGrid**
   - Ir a https://sendgrid.com/
   - Registrarse (plan gratuito disponible)

2. **Generar API Key**
   - Settings → API Keys → Create API Key
   - Permisos: Full Access
   - Guardar la key generada

3. **Verificar dominio**
   - Settings → Sender Authentication
   - Domain Authentication → Authenticate Domain
   - Seguir instrucciones DNS

4. **Configurar templates** (opcional)
   - Email API → Dynamic Templates
   - Crear templates para emails transaccionales

### Cloudinary (Imágenes)

1. **Crear cuenta**
   - Ir a https://cloudinary.com/
   - Registrarse (plan gratuito disponible)

2. **Obtener credenciales**
   - Dashboard muestra:
     - Cloud Name
     - API Key
     - API Secret

3. **Configurar transformaciones**
   - Settings → Upload
   - Crear presets para optimización

### Flow.cl (Pagos Chile)

1. **Registro comercio**
   - https://www.flow.cl/
   - Completar proceso KYC

2. **Obtener credenciales**
   - Mi Cuenta → Seguridad → API
   - API Key y Secret Key

3. **Configurar URLs**
   - Configuración → URLs
   - URL confirmación: https://tu-dominio.cl/payment/confirmation/
   - URL retorno: https://tu-dominio.cl/payment/return/

### Mercado Pago

1. **Crear aplicación**
   - https://www.mercadopago.cl/developers/
   - Crear aplicación

2. **Obtener credenciales**
   - Credenciales de producción
   - Access Token y Public Key

3. **Configurar webhooks**
   - Configurar notificaciones IPN

## 🎯 Inicialización del Sistema

### 1. Crear Categorías y Servicios Básicos

```python
# Django shell
python manage.py shell

from ventas.models import Categoria, Servicio, Proveedor

# Crear categorías
cat_masajes = Categoria.objects.create(
    nombre="Masajes",
    descripcion="Masajes relajantes y terapéuticos",
    slug="masajes",
    orden=1
)

cat_tinas = Categoria.objects.create(
    nombre="Tinas Calientes",
    descripcion="Tinas con hidromasaje y vista al lago",
    slug="tinas-calientes",
    orden=2
)

# Crear proveedor
proveedor = Proveedor.objects.create(
    nombre="Spa Aremko",
    email="spa@aremko.cl"
)

# Crear servicio ejemplo
servicio = Servicio.objects.create(
    nombre="Masaje Relajación 60min",
    categoria=cat_masajes,
    descripcion="Masaje de relajación profunda",
    duracion=60,
    precio=45000,
    proveedor=proveedor,
    capacidad_max=1,
    activo=True
)
```

### 2. Configurar Horarios

```python
# Configurar slots disponibles
servicio.slots_disponibles = {
    "lunes": ["10:00", "11:30", "15:00", "16:30"],
    "martes": ["10:00", "11:30", "15:00", "16:30"],
    "miércoles": ["10:00", "11:30", "15:00", "16:30"],
    "jueves": ["10:00", "11:30", "15:00", "16:30"],
    "viernes": ["10:00", "11:30", "15:00", "16:30", "18:00"],
    "sábado": ["10:00", "11:30", "14:00", "15:30", "17:00"],
    "domingo": ["10:00", "11:30", "14:00", "15:30"]
}
servicio.save()
```

### 3. Crear Usuario Staff

```python
from django.contrib.auth.models import User, Group

# Crear grupo recepcionista
grupo_recepcion, created = Group.objects.get_or_create(
    name='Recepcionistas'
)

# Crear usuario
user = User.objects.create_user(
    username='recepcion',
    email='recepcion@aremko.cl',
    password='password_seguro',
    first_name='Usuario',
    last_name='Recepción'
)

# Asignar permisos
user.groups.add(grupo_recepcion)
user.is_staff = True
user.save()
```

## ✅ Verificación

### 1. Verificar Instalación

```bash
# Verificar Django
python manage.py check

# Verificar base de datos
python manage.py dbshell
\dt  # Listar tablas
\q   # Salir

# Verificar estáticos
ls staticfiles/
```

### 2. Tests Básicos

```bash
# Ejecutar tests
python manage.py test

# Test específico
python manage.py test ventas.tests.test_models

# Con coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

### 3. Verificar Servicios

```python
# Shell Django
python manage.py shell

# Verificar modelos
from ventas.models import Servicio, Cliente
print(f"Servicios: {Servicio.objects.count()}")
print(f"Clientes: {Cliente.objects.count()}")

# Test email
from django.core.mail import send_mail
send_mail(
    'Test Email',
    'Este es un test.',
    'from@example.com',
    ['to@example.com'],
    fail_silently=False,
)
```

## 🔨 Troubleshooting

### Errores Comunes

#### 1. Error de Conexión a PostgreSQL

```
django.db.utils.OperationalError: FATAL: password authentication failed
```

**Solución**:
- Verificar credenciales en DATABASE_URL
- Verificar que PostgreSQL está corriendo
- Verificar pg_hba.conf permite conexiones

#### 2. Error de Migración

```
django.db.migrations.exceptions.InconsistentMigrationHistory
```

**Solución**:
```bash
# Resetear migraciones (CUIDADO en producción)
python manage.py migrate --fake-initial

# O resetear app específica
python manage.py migrate ventas zero --fake
python manage.py migrate ventas
```

#### 3. Error de Archivos Estáticos

```
404 para archivos CSS/JS
```

**Solución**:
```bash
# Verificar STATIC_ROOT
python manage.py collectstatic --noinput

# En desarrollo, agregar a urls.py:
from django.conf import settings
from django.conf.urls.static import static

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```

#### 4. Error de Permisos

```
PermissionError: [Errno 13] Permission denied
```

**Solución**:
```bash
# Linux/macOS
sudo chown -R $USER:$USER .

# Permisos de ejecución
chmod +x entrypoint.sh
chmod +x manage.py
```

### Logs y Debugging

```python
# En settings.py para debugging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'ventas': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

### Comandos de Diagnóstico

```bash
# Verificar configuración
python manage.py diffsettings

# Listar URLs
python manage.py show_urls

# Shell Plus (si tienes django-extensions)
python manage.py shell_plus

# Verificar emails
python manage.py check_booking_email

# Diagnóstico gift cards
python manage.py diagnostico_giftcards
```

## 📚 Siguiente Paso

Una vez completada la instalación:

1. Revisar [Guía de Desarrollo](DESARROLLO.md)
2. Configurar [Servicios Externos](SERVICIOS_EXTERNOS.md)
3. Leer [Manual de Usuario](MANUAL_USUARIO.md)

---

<p align="center">
  ¿Necesitas ayuda? Contacta a soporte@aremko.cl
</p>