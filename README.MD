# 🏔️ Aremko Booking System

[![Version](https://img.shields.io/badge/version-1.0-blue.svg)](https://github.com/nomad3/booking-system-aremko)
[![Python](https://img.shields.io/badge/python-3.11+-brightgreen.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-4.2+-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

Sistema integral de reservas y gestión para **Aremko Spa Puerto Varas**, un spa boutique que combina servicios de masajes, tinas calientes (tinajas) y alojamiento en cabañas con vistas espectaculares al lago y volcanes de la región de Los Lagos, Chile.

## Tabla de Contenidos
- [Introducción](#introducción)
- [Características Principales](#características-principales)
  - [Sistema de Reservas](#sistema-de-reservas)
  - [Funcionalidades CRM](#funcionalidades-crm)
  - [Comunicaciones Inteligentes (SMS + Email)](#comunicaciones-inteligentes-sms--email)
  - [Reportes y Exportaciones](#reportes-y-exportaciones)
- [Tecnologías Utilizadas](#tecnologías-utilizadas)
- [Prerequisitos](#prerequisitos)
- [Instalación Local](#instalación-local)
- [Configuración de Variables de Entorno](#configuración-de-variables-de-entorno)
- [Despliegue (Ej: Render.com)](#despliegue-ej-rendercom)
- [Gestión de Archivos Estáticos](#gestión-de-archivos-estáticos)
- [Creación de Superusuario](#creación-de-superusuario)
- [Migraciones de Base de Datos](#migraciones-de-base-de-datos)
- [Uso](#uso)
- [Integraciones](#integraciones)
- [API y Automatización](#api-y-automatización)
- [Comandos de Gestión](#comandos-de-gestión)
- [Buenas Prácticas](#buenas-prácticas)
- [Recursos Adicionales](#recursos-adicionales)
 - [Módulo IA](#módulo-ia)
- [Variables de Entorno Clave](#variables-de-entorno-clave)

---

## Introducción

**Aremko Booking & CRM System** es una aplicación web robusta desarrollada con Django, diseñada para gestionar eficientemente reservas de servicios y productos, y potenciar la relación con los clientes a través de un módulo CRM integrado. La aplicación está preparada para despliegue en plataformas como Render.com utilizando Docker, asegurando escalabilidad y fácil mantenimiento.

---

## Características Principales

### Sistema de Reservas
- **Gestión de Servicios y Productos:** Creación, edición y eliminación de servicios y productos ofrecidos.
- **Categorización:** Organización de servicios y productos en categorías.
- **Gestión de Proveedores:** Administración de proveedores asociados a servicios.
- **Gestión de Horarios:** Configuración de horarios disponibles para servicios.
- **Capacidad y Duración:** Definición de capacidad mínima/máxima y duración de los servicios.
- **Reservas Online:** Interfaz pública para que los clientes realicen reservas.
- **Carrito de Compras:** Funcionalidad de carrito para múltiples reservas.
- **Checkout y Pagos:** Integración con pasarelas de pago (ej: Flow).
- **Gestión de Ventas:** Seguimiento de ventas y reservas.
- **Gestión de Caja:** Reportes de caja diaria.
- **Gift Cards:** Emisión y gestión de tarjetas de regalo.
- **Precios Dinámicos:** (Si aplica, describir brevemente)

### Funcionalidades CRM
- **Gestión de Clientes:** Base de datos centralizada de clientes con información detallada (contacto, historial, etc.).
- **Segmentación de Clientes:** Creación de segmentos de clientes basados en diversos criterios (gasto, visitas, etc.).
- **Gestión de Campañas:**
    - Creación y administración de campañas de marketing y remarketing.
    - Definición de objetivos (ej: gasto mínimo, visitas mínimas).
    - Plantillas de comunicación (Email, SMS - si aplica).
    - Notas de automatización y seguimiento.
- **Gestión de Interacciones:** Registro de interacciones con clientes asociadas a campañas.
- **Modelo de Ventas (Leads, Deals):**
    - Gestión de Leads (Prospectos).
    - Gestión de Deals (Oportunidades de Venta).
    - Gestión de Companies (Empresas).
    - Gestión de Contacts (Contactos asociados a Empresas/Deals).
- **Gestión de Actividades:** Seguimiento de actividades relacionadas con contactos, leads o deals (llamadas, reuniones, tareas).
- **Integraciones:** (Mencionar si existen, ej: ManyChat, Google Calendar, N8N para automatizaciones).
- **Reportes CRM:** (Mencionar si existen reportes específicos de CRM).

### Comunicaciones Inteligentes (SMS + Email)
- **Confirmaciones de reserva (dual):** Envío automático de SMS y Email al crear la reserva, con plantilla y datos del servicio/fecha/hora.
- **Recordatorios de cita (24h antes):** Envío automático (Email + SMS opcional) evitando duplicados.
- **Pago 100% confirmado:** Notificación dual cuando la reserva queda pagada al 100%.
- **Encuesta de satisfacción (D+1):** Email y SMS opcional con link a encuesta y referencia TripAdvisor.
- **Reactivación 90 días:** Email y SMS con Gift Card de CLP $10.000 y control de frecuencia trimestral.
- **Cumpleaños:** SMS de saludo 1 vez/año por cliente.
- **Newsletter segmentado:** Envío de emails personalizados por segmento (ej. VIP mensual).
- **Anti‑Spam y preferencias:** Límites por cliente (diario/mensual/semana), horarios preferidos y opt‑out granular por tipo de mensaje.
- **Logs y auditoría:** `CommunicationLog` con estados, costos y trazabilidad por reserva/campaña.
- **Plantillas SMS:** `SMSTemplate` con variables dinámicas y activación por tipo.

### Reportes y Exportaciones
- **Servicios vendidos:** Filtros por fecha/categoría/venta y exportación a Excel.
- **Productos vendidos:** Totales por proveedor/producto y exportación a Excel.
- **Caja diaria:** Totales por método de pago y usuario; vista especial para recepcionistas.
- **Auditoría de movimientos:** Historial filtrable de `MovimientoCliente` con paginación.
- **Segmentación de clientes:** Tablero por segmentos (nuevo, regular, VIP; bajo/medio/alto gasto) y lista por segmento.

---

## Tecnologías Utilizadas

- **Backend:** Django 4.2
- **Base de Datos:** PostgreSQL
- **Servidor de Aplicaciones:** Gunicorn
- **Manejo de Archivos Estáticos:** WhiteNoise
- **Contenerización:** Docker
- **Frontend:** HTML, CSS, JavaScript (posiblemente con algún framework como Bootstrap si se usa)
- **APIs/Integraciones:** (Listar las relevantes: Flow, Google Calendar API, ManyChat API, etc.)

---

## Prerequisitos

- [Python 3.9+](https://www.python.org/downloads/)
- [Docker](https://www.docker.com/get-started) & [Docker Compose](https://docs.docker.com/compose/install/)
- [Git](https://git-scm.com/downloads)
- [Cuenta de GitHub](https://github.com/) (para despliegue desde repositorio)
- [Cliente PostgreSQL](https://www.postgresql.org/download/) (para gestión local)

---

## Instalación Local

1.  **Clonar Repositorio:**
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd booking-system-aremko # o el nombre del directorio
    ```
2.  **Configurar Variables de Entorno (Local):**
    Crea un archivo `.env` en la raíz del proyecto. Puedes basarte en `README.local.md` o definir las necesarias:
    ```env
    DEBUG=True
    SECRET_KEY='django-insecure-...' # Cambiar por una clave segura
    DATABASE_URL=postgres://user:password@localhost:5432/aremko_db # Ajustar a tu config local
    DJANGO_SUPERUSER_USERNAME=admin
    DJANGO_SUPERUSER_EMAIL=admin@example.com
    DJANGO_SUPERUSER_PASSWORD=password # Cambiar por una contraseña segura
    ALLOWED_HOSTS=localhost,127.0.0.1
    # Añadir otras variables necesarias (APIs, etc.)
    ```
3.  **(Opción A) Usando Docker Compose (Recomendado):**
    Asegúrate de tener `docker-compose.yml` configurado.
    ```bash
    docker-compose up --build
    ```
    Esto levantará la aplicación, la base de datos y otros servicios definidos. Las migraciones y la creación del superusuario suelen manejarse en el `entrypoint.sh`.

4.  **(Opción B) Instalación Manual:**
    a.  **Crear y Activar Entorno Virtual:**
        ```bash
        python -m venv venv
        source venv/bin/activate  # Linux/macOS
        # venv\Scripts\activate    # Windows
        ```
    b.  **Instalar Dependencias:**
        ```bash
        pip install -r requirements.txt
        ```
    c.  **Configurar Base de Datos Local:**
        Asegúrate de tener PostgreSQL corriendo y crea la base de datos especificada en `DATABASE_URL`.
    d.  **Aplicar Migraciones:**
        ```bash
        python manage.py migrate
        ```
    e.  **Crear Superusuario (si no se usa entrypoint):**
        ```bash
        python manage.py createsuperuser
        ```
    f.  **Recolectar Estáticos:**
        ```bash
        python manage.py collectstatic --noinput
        ```
    g.  **Iniciar Servidor:**
        ```bash
        python manage.py runserver
        ```
        Accede a `http://localhost:8000/` o `http://localhost:8000/admin/`.

---

## Configuración de Variables de Entorno

Es crucial configurar correctamente las variables de entorno tanto para desarrollo local como para producción. Las variables clave incluyen:

- `DEBUG`: `True` para desarrollo, `False` para producción.
- `SECRET_KEY`: Clave secreta única y segura para Django.
- `DATABASE_URL`: URL de conexión a la base de datos PostgreSQL.
- `ALLOWED_HOSTS`: Lista de dominios permitidos para servir la aplicación.
- `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD`: Credenciales para la creación automática del superusuario (usado en `entrypoint.sh`).
- **Claves de APIs:** Para servicios externos como Flow, Google Calendar, ManyChat, etc.
- **Otras configuraciones:** Cualquier otra variable específica de la aplicación.

*Gestiona estas variables de forma segura, especialmente en producción (ej: usando secretos de la plataforma de despliegue).*

---

## Despliegue (Ej: Render.com)

1.  **Preparar Repositorio:** Asegúrate de que `Dockerfile`, `docker-compose.yml` (si aplica), `entrypoint.sh`, y `requirements.txt` estén actualizados y en el repositorio.
2.  **Crear Servicio en Render:**
    - Conecta tu repositorio GitHub/GitLab.
    - Elige "Web Service".
    - Configura el entorno como "Docker".
    - Render detectará el `Dockerfile`.
3.  **Configurar Variables de Entorno:** Añade todas las variables necesarias en la sección "Environment" de Render, asegurándote de que `DEBUG=False` y usando la `DATABASE_URL` proporcionada por Render (o tu base de datos externa).
4.  **Configurar Comando de Build/Start:** Render usará los comandos del `Dockerfile` (`CMD` o `ENTRYPOINT`). Asegúrate que `entrypoint.sh` ejecute las migraciones, recolección de estáticos y Gunicorn.
5.  **Desplegar:** Inicia el despliegue. Render construirá la imagen Docker y lanzará el servicio. Monitorea los logs.

---

## Gestión de Archivos Estáticos

Se utiliza **WhiteNoise** para servir archivos estáticos eficientemente en producción.

- **Configuración (`settings.py`):**
  ```python
  MIDDLEWARE = [
      'django.middleware.security.SecurityMiddleware',
      'whitenoise.middleware.WhiteNoiseMiddleware', # Debe ir después de SecurityMiddleware
      # ... otros middleware ...
  ]
  STATIC_URL = '/static/'
  STATIC_ROOT = BASE_DIR / 'staticfiles' # Usando pathlib
  STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
  ```
- **Recolección:** El comando `python manage.py collectstatic --noinput` (generalmente en `entrypoint.sh`) recolecta todos los archivos estáticos en el directorio `STATIC_ROOT`.

---

## Creación de Superusuario

La creación del superusuario se automatiza en `entrypoint.sh` usando las variables de entorno `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, y `DJANGO_SUPERUSER_PASSWORD`. Esto es útil para entornos donde no hay acceso directo a la shell (como planes gratuitos de PaaS).

```bash
# Parte relevante en entrypoint.sh
echo "Creando superusuario si no existe..."
python manage.py shell <<EOF
# ... (código para crear superusuario basado en variables de entorno) ...
EOF
```
*Asegúrate de que este script maneje el caso donde el usuario ya existe.*

---

## Migraciones de Base de Datos

Las migraciones de Django son esenciales para mantener la estructura de la base de datos sincronizada con los modelos.

1.  **Crear Migraciones:** Cuando cambies los modelos (`models.py`):
    ```bash
    python manage.py makemigrations <nombre_app> # ej: ventas
    ```
2.  **Aplicar Migraciones (Local):**
    ```bash
    python manage.py migrate
    ```
3.  **Commit y Push:** Añade los archivos de migración generados al control de versiones (`git add`, `git commit`, `git push`).
4.  **Aplicar en Producción:** El script `entrypoint.sh` debe incluir `python manage.py migrate` para aplicar las migraciones automáticamente durante el despliegue.

---

## Uso

- **Panel de Administración:** `https://<tu_dominio>/admin/` (Gestiona productos, servicios, clientes, campañas, etc.)
- **Interfaz Pública:** `https://<tu_dominio>/` (Portal para clientes, reservas)
- **Reportes:**
  - `https://<tu_dominio>/servicios-vendidos/`
  - `https://<tu_dominio>/productos-vendidos/`
  - `https://<tu_dominio>/caja-diaria/` y `.../caja-diaria-recepcionistas/`
  - `https://<tu_dominio>/auditoria-movimientos/`
  - `https://<tu_dominio>/reportes/segmentacion-clientes/` y `.../<segment_name>/`
- **API Endpoints (DRF base):** `https://<tu_dominio>/` + router (ver sección API y Automatización)

---

## Integraciones

- **Flow.cl (Pagos):** Creación de órdenes, webhook de confirmación y página de retorno. Al confirmar pago (status=2) se crea `Pago` y se actualiza `VentaReserva`.
- **Redvoiss (SMS):** Envío individual y masivo, mensajes con respuesta, consulta de estado de lote y respuestas. Limpieza/validación de teléfonos chilenos.
- **Google Calendar:** Creación de eventos en calendario a partir de reservas.
- **ManyChat:** Punto de integración preparado para notificaciones de reserva.
- **n8n/Automatización:** Endpoints para obtener targets de campaña y registrar actividades/interacciones externas.

---

## API y Automatización

- **Router DRF:**
  - `api/proveedores`, `api/categorias`, `api/productos`, `api/ventasreservas`, `api/pagos`, `api/clientes`, `api/servicios`, `api/categorias-servicio`, `api/reservaproductos`, `api/reservaservicios`.
- **Búsqueda/Utilidades:**
  - `api/get-client-details/?telefono=<numero>`
- **Pagos Flow:**
  - `api/flow/create/` (POST) — inicia pago.
  - `payment/confirmation/` (POST webhook) — confirma pago.
  - `payment/return/` (GET) — retorno usuario.
- **Remarketing/Automación (proteger con `X-API-KEY`):**
  - `api/campaigns/<id>/details/` (GET)
  - `api/campaigns/<id>/targets/` (GET)
  - `api/activities/log/` (POST)
  - `api/interactions/log/` (POST)

---

## Comandos de Gestión

- `python manage.py create_default_sms_templates` — Crea plantillas base de SMS.
- `python manage.py send_communication_triggers` — Ejecuta tareas programadas (recordatorios, encuestas, cumpleaños, reactivación, newsletter VIP).
- `python manage.py normalize_and_merge_clients` — Normaliza/mergea clientes desde fuentes externas.
- `python manage.py test_redvoiss` — Pruebas de conectividad/flujo con Redvoiss.

---

## Buenas Prácticas

- **Seguridad:** `DEBUG=False` en producción, `ALLOWED_HOSTS` restrictivo, gestión segura de `SECRET_KEY` y claves API.
- **Archivos Media:** Para archivos subidos por usuarios (ej: imágenes de servicios), considera usar almacenamiento externo como AWS S3, Google Cloud Storage, etc., configurando `DEFAULT_FILE_STORAGE`.
- **Monitorización:** Integra herramientas como Sentry para seguimiento de errores.
- **Logs:** Revisa los logs de la aplicación y del servidor regularmente.
- **Backups:** Asegura backups regulares de la base de datos.
- **Pruebas:** Implementa pruebas unitarias e de integración.

---

## Recursos Adicionales

- [Documentación de Django](https://docs.djangoproject.com/en/4.2/)
- [Documentación de Docker](https://docs.docker.com/)
- [Documentación de Render.com](https://render.com/docs)
- [WhiteNoise Documentation](http://whitenoise.evans.io/en/stable/)
- [Gunicorn Documentation](https://docs.gunicorn.org/en/stable/)

now you can create the helm chart with the provided instructions.

---

## Módulo IA

Consulta el diseño funcional y técnico del Módulo IA (Fase 1: Chat IA de negocio, Recomendaciones por cliente y Copiloto de campañas) en el documento dedicado:

- `docs/modulo_ia.md`

Este módulo está planificado para añadir capacidades de análisis, personalización y apoyo a marketing, con foco en seguridad (solo lectura para consultas) y control de costos.

---

## Variables de Entorno Clave

- **SMS/Email (Anti‑Spam y Preferencias):**
  - `COMMUNICATION_SMS_ENABLED=true`
  - `SMS_DAILY_LIMIT_PER_CLIENT=2`, `SMS_MONTHLY_LIMIT_PER_CLIENT=8`
  - `EMAIL_WEEKLY_LIMIT_PER_CLIENT=1`, `EMAIL_MONTHLY_LIMIT_PER_CLIENT=4`
  - `SURVEY_PUBLIC_BASE_URL`, `TRIPADVISOR_URL`
- **Redvoiss:**
  - `REDVOISS_API_URL`, `REDVOISS_USERNAME`, `REDVOISS_PASSWORD`
- **Flow:**
  - `FLOW_API_KEY`, `FLOW_SECRET_KEY`, `FLOW_CREATE_API_URL`, `FLOW_STATUS_API_URL`, `FLOW_CONFIRMATION_URL`, `FLOW_RETURN_URL`
- **Automatización:**
  - `AUTOMATION_API_KEY` (protege endpoints n8n)
- **IA (si aplica):** ver sección `Módulo IA` para `DEEPSEEK_API_KEY` y límites de costo.
