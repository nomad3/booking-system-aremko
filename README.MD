# Aremko Booking & CRM System

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Django Version](https://img.shields.io/badge/django-4.2-green.svg)](https://www.djangoproject.com/)
[![Docker](https://img.shields.io/badge/docker-✓-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Sistema integral para la gestión de reservas de servicios y productos, complementado con funcionalidades de CRM para la gestión de clientes y campañas de marketing.

## Tabla de Contenidos
- [Introducción](#introducción)
- [Características Principales](#características-principales)
  - [Sistema de Reservas](#sistema-de-reservas)
  - [Funcionalidades CRM](#funcionalidades-crm)
- [Tecnologías Utilizadas](#tecnologías-utilizadas)
- [Prerequisitos](#prerequisitos)
- [Instalación Local](#instalación-local)
- [Configuración de Variables de Entorno](#configuración-de-variables-de-entorno)
- [Despliegue (Ej: Render.com)](#despliegue-ej-rendercom)
- [Gestión de Archivos Estáticos](#gestión-de-archivos-estáticos)
- [Creación de Superusuario](#creación-de-superusuario)
- [Migraciones de Base de Datos](#migraciones-de-base-de-datos)
- [Uso](#uso)
- [Buenas Prácticas](#buenas-prácticas)
- [Recursos Adicionales](#recursos-adicionales)

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
- **API Endpoints:** (Si existen, listar las rutas base, ej: `https://<tu_dominio>/api/`)

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
