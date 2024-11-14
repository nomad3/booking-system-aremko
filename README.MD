```markdown
# Booking System

## Tabla de Contenidos
- [Introducción](#introducción)
- [Características](#características)
- [Tecnologías Utilizadas](#tecnologías-utilizadas)
- [Prerequisitos](#prerequisitos)
- [Instalación](#instalación)
- [Configuración de Variables de Entorno](#configuración-de-variables-de-entorno)
- [Despliegue en Render.com](#despliegue-en-rendercom)
- [Gestión de Archivos Estáticos](#gestión-de-archivos-estáticos)
- [Creación de un Superusuario](#creación-de-un-superusuario)
- [Migraciones de la Base de Datos](#migraciones-de-la-base-de-datos)
- [Uso](#uso)
- [Solución de Problemas](#solución-de-problemas)
- [Buenas Prácticas y Consideraciones Adicionales](#buenas-prácticas-y-consideraciones-adicionales)
- [Recursos Adicionales](#recursos-adicionales)

---

## Introducción

**Booking System** es una aplicación web desarrollada con Django que permite gestionar reservas de productos de manera eficiente. La aplicación está diseñada para ser desplegada en Render.com utilizando Docker, asegurando una fácil escalabilidad y mantenimiento.

---

## Características

- **Gestión de Productos:** Añadir, editar y eliminar productos disponibles para reserva.
- **Precios Dinámicos:** Configurar reglas de precios que se ajustan automáticamente según criterios específicos.
- **Panel de Administración:** Interfaz intuitiva para gestionar todas las funcionalidades de la aplicación.
- **Manejo de Archivos Estáticos:** Utiliza WhiteNoise para servir archivos estáticos de manera eficiente.
- **Automatización de Superusuario:** Crea un superusuario automáticamente durante el despliegue utilizando variables de entorno.

---

## Tecnologías Utilizadas

- **Backend:** Django 4.2
- **Base de Datos:** PostgreSQL
- **Servidor de Aplicaciones:** Gunicorn
- **Manejo de Archivos Estáticos:** WhiteNoise
- **Contenerización:** Docker
- **Plataforma de Despliegue:** Render.com

---

## Prerequisitos

Antes de comenzar, asegúrate de tener instalados los siguientes componentes en tu sistema:

- [Python 3.9](https://www.python.org/downloads/)
- [Docker](https://www.docker.com/get-started)
- [Git](https://git-scm.com/downloads)
- [GitHub Account](https://github.com/)

---

## Instalación

Sigue estos pasos para configurar el proyecto localmente:

1. **Clonar el Repositorio:**

   ```bash
   git clone https://github.com/nomad3/booking_system.git
   cd booking_system
   ```

2. **Crear y Activar un Entorno Virtual:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # En Windows usa: venv\Scripts\activate
   ```

3. **Actualizar `pip` e Instalar Dependencias:**

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configurar la Base de Datos Localmente (Opcional):**

   Asegúrate de tener PostgreSQL instalado y crea una base de datos para desarrollo.

   ```bash
   psql
   CREATE DATABASE booking_system_dev;
   \q
   ```

5. **Configurar Variables de Entorno:**

   Crea un archivo `.env` en la raíz del proyecto y añade las siguientes variables:

   ```env
   DEBUG=True
   SECRET_KEY=tu_clave_secreta
   DATABASE_URL=postgres://usuario:contraseña@localhost:5432/booking_system_dev
   DJANGO_SUPERUSER_USERNAME=admin
   DJANGO_SUPERUSER_EMAIL=admin@example.com
   DJANGO_SUPERUSER_PASSWORD=tu_contraseña_segura
   ALLOWED_HOSTS=localhost,127.0.0.1
   ```

   *Reemplaza los valores con tus configuraciones específicas.*

6. **Aplicar Migraciones y Crear Superusuario:**

   ```bash
   python manage.py makemigrations ventas
   python manage.py migrate
   python manage.py createsuperuser
   ```

7. **Recolectar Archivos Estáticos:**

   ```bash
   python manage.py collectstatic
   ```

8. **Iniciar el Servidor de Desarrollo:**

   ```bash
   python manage.py runserver
   ```

   Accede a `http://localhost:8000/admin/` para iniciar sesión en el panel de administración.

---

## Configuración de Variables de Entorno

Es crucial manejar de manera segura las variables de entorno, especialmente las que contienen información sensible. Asegúrate de configurar las siguientes variables en Render.com:

- `DEBUG`: `False` en producción.
- `SECRET_KEY`: Una clave secreta segura.
- `DATABASE_URL`: URL de conexión a tu base de datos PostgreSQL en Render.com.
- `DJANGO_SUPERUSER_USERNAME`: Nombre de usuario para el superusuario.
- `DJANGO_SUPERUSER_EMAIL`: Correo electrónico para el superusuario.
- `DJANGO_SUPERUSER_PASSWORD`: Contraseña para el superusuario.
- `ALLOWED_HOSTS`: Dominios permitidos (e.g., `booking-system-ykvv.onrender.com`).

---

## Despliegue en Render.com

Sigue estos pasos para desplegar la aplicación en Render.com:

1. **Crear un Nuevo Servicio Web en Render.com:**

   - Ve a tu [Dashboard de Render.com](https://render.com/) e inicia sesión.
   - Haz clic en **New** > **Web Service**.
   - Selecciona tu repositorio de GitHub (`nomad3/booking_system`).

2. **Configurar el Servicio Web:**

   - **Name:** `booking-system`
   - **Environment:** Docker
   - **Build Command:** (Dejar vacío si usas Docker)
   - **Start Command:** (Definido en `entrypoint.sh`)
   - **Region:** Selecciona la región más cercana a tus usuarios.
   - **Instance Type:** Selecciona según tus necesidades (el plan gratuito es suficiente para comenzar).

3. **Configurar Variables de Entorno:**

   Añade todas las variables de entorno necesarias como se describió anteriormente.

4. **Configurar el `Dockerfile`:**

   Asegúrate de que tu `Dockerfile` está correctamente configurado para copiar y ejecutar `entrypoint.sh`.

5. **Desplegar la Aplicación:**

   Render.com detectará automáticamente el `Dockerfile` y comenzará el proceso de construcción y despliegue. Monitorea los logs para asegurarte de que todo se construye y despliega correctamente.

---

## Gestión de Archivos Estáticos

La aplicación utiliza **WhiteNoise** para servir archivos estáticos de manera eficiente. Asegúrate de que **WhiteNoise** está correctamente configurado:

1. **Instalación de WhiteNoise:**

   Asegúrate de que `whitenoise` está listado en `requirements.txt`:

   ```bash
   whitenoise==6.4.0
   ```

2. **Configuración en `settings.py`:**

   ```python
   MIDDLEWARE = [
       'django.middleware.security.SecurityMiddleware',
       'whitenoise.middleware.WhiteNoiseMiddleware',
       # ... otros middleware ...
   ]

   STATIC_URL = '/static/'
   STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

   STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
   ```

3. **Recolectar Archivos Estáticos:**

   El script `entrypoint.sh` ya incluye el comando para recolectar archivos estáticos:

   ```bash
   python manage.py collectstatic --noinput
   ```

---

## Creación de un Superusuario

Dado que el plan gratuito de Render.com no permite acceso a la consola de shell, la creación del superusuario se automatiza mediante el script `entrypoint.sh`.

### **a. Configurar Variables de Entorno para el Superusuario**

En Render.com, añade las siguientes variables de entorno:

- `DJANGO_SUPERUSER_USERNAME`: Nombre de usuario del superusuario.
- `DJANGO_SUPERUSER_EMAIL`: Correo electrónico del superusuario.
- `DJANGO_SUPERUSER_PASSWORD`: Contraseña del superusuario.

### **b. Modificar `entrypoint.sh` para Crear el Superusuario**

Asegúrate de que tu `entrypoint.sh` incluye el siguiente bloque para crear el superusuario automáticamente:

```bash
# Crear superusuario si no existe
echo "Creando superusuario si no existe..."
python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
import os

username = os.getenv('DJANGO_SUPERUSER_USERNAME')
email = os.getenv('DJANGO_SUPERUSER_EMAIL')
password = os.getenv('DJANGO_SUPERUSER_PASSWORD')

if username and email and password:
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
        print("Superusuario creado.")
    else:
        print("Superusuario ya existe.")
else:
    print("Variables de entorno para superusuario no están completamente configuradas.")
EOF
```

*Recuerda manejar las credenciales de manera segura y eliminar este bloque una vez creado el superusuario para evitar riesgos de seguridad.*

### **c. Despliegue y Verificación**

1. **Commit y Push de los Cambios:**

   ```bash
   git add entrypoint.sh
   git commit -m "Automatizar creación de superusuario"
   git push origin main
   ```

2. **Monitorear el Despliegue:**

   Render.com ejecutará el script `entrypoint.sh` durante el despliegue. Verifica los logs para confirmar que el superusuario se ha creado correctamente.

3. **Acceder al Panel de Administración:**

   Ve a `https://booking-system-ykvv.onrender.com/admin/` e inicia sesión con las credenciales del superusuario.

4. **Eliminar o Comentar el Bloque de Creación Automática (Recomendado):**

   Para mejorar la seguridad, una vez creado el superusuario, comenta o elimina el bloque que lo crea automáticamente en `entrypoint.sh` y realiza un nuevo despliegue.

---

## Migraciones de la Base de Datos

Es esencial mantener las migraciones sincronizadas con los modelos de Django para evitar errores como columnas faltantes.

### **a. Crear Migraciones Localmente**

1. **Crear Migraciones:**

   ```bash
   python manage.py makemigrations ventas
   ```

2. **Aplicar Migraciones Localmente:**

   ```bash
   python manage.py migrate
   ```

### **b. Commit y Push de Migraciones a GitHub**

1. **Añadir Migraciones:**

   ```bash
   git add ventas/migrations/
   ```

2. **Cometer Migraciones:**

   ```bash
   git commit -m "Agregar migraciones para el campo 'nombre_regla' en PrecioDinamico"
   ```

3. **Push a la Rama Principal:**

   ```bash
   git push origin main
   ```

Render.com aplicará automáticamente las migraciones durante el despliegue.

---

## Uso

Una vez desplegada la aplicación, puedes acceder a las siguientes URLs:

- **Panel de Administración:**
  ```
  https://booking-system-ykvv.onrender.com/admin/
  ```

- **Página de Inicio:**
  ```
  https://booking-system-ykvv.onrender.com/
  ```

*Reemplaza `booking-system-ykvv.onrender.com` con tu dominio personalizado si lo tienes.*

---

## Buenas Prácticas y Consideraciones Adicionales

### **Seguridad**
- **Mantén `DEBUG = False` en Producción:**
  - Evita exponer información sensible.
  
- **Configura Correctamente `ALLOWED_HOSTS`:**
  - Especifica solo los dominios necesarios.

- **Gestión Segura de `SECRET_KEY`:**
  - Usa variables de entorno para manejarla de manera segura.

### **Manejo de Archivos Estáticos y Media**
- **Usar WhiteNoise para Archivos Estáticos:**
  - Simplifica el manejo y mejora el rendimiento.

- **Servir Archivos Media Externamente:**
  - Considera servicios como AWS S3 para manejar subidas de usuarios.

### **Monitorización y Logs**
- **Integrar Herramientas de Monitorización:**
  - Servicios como **Sentry** pueden ayudar a monitorear errores en tiempo real.

- **Revisar Regularmente los Logs:**
  - Detecta y soluciona problemas rápidamente.

### **Backup de la Base de Datos**
- **Automatizar Backups:**
  - Asegura que tu base de datos en Render.com tenga backups automáticos para evitar pérdida de datos.

### **CI/CD y Automatización**
- **GitHub Actions:**
  - Configura pipelines más complejos para automatizar pruebas y builds si es necesario.

---

## Recursos Adicionales

- **Documentación de Render.com:**
  - [Deploying a Django Application](https://render.com/docs/deploy-django)
  - [Troubleshooting Deploys](https://render.com/docs/troubleshooting-deploys)

- **Documentación de Django:**
  - [URL Dispatcher](https://docs.djangoproject.com/en/4.2/topics/http/urls/)
  - [Settings](https://docs.djangoproject.com/en/4.2/ref/settings/)

- **Gunicorn:**
  - [Gunicorn Documentation](https://docs.gunicorn.org/en/stable/)

- **WhiteNoise:**
  - [WhiteNoise Documentation](http://whitenoise.evans.io/en/stable/)

- **Sentry (Opcional para Monitorización):**
  - [Sentry Documentation](https://docs.sentry.io/platforms/python/django/)

---