#!/bin/sh

# Salir inmediatamente si un comando falla
set -e

# Función para extraer DB_HOST y DB_PORT de DATABASE_URL usando Python
extract_db_host_port() {
    # Usar Python para parsear DATABASE_URL y extraer host y port
    eval "$(python -c 'import os
from urllib.parse import urlparse

database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("Error: DATABASE_URL no está definido.")
    exit(1)

parsed_url = urlparse(database_url)

db_host = parsed_url.hostname
db_port = parsed_url.port if parsed_url.port else 5432  # Puerto predeterminado de PostgreSQL

if not db_host or not db_port:
    print("Error: No se pudo extraer DB_HOST y DB_PORT de DATABASE_URL.")
    exit(1)

print(f"DB_HOST={db_host}")
print(f"DB_PORT={db_port}")
')"

    # Verificar que DB_HOST y DB_PORT fueron extraídos correctamente
    if [ -z "$DB_HOST" ] || [ -z "$DB_PORT" ]; then
        echo "Error: No se pudo extraer DB_HOST y DB_PORT de DATABASE_URL."
        exit 1
    fi
}

# Extraer DB_HOST y DB_PORT
extract_db_host_port

# Debugging info (solo mostrar si es necesario)
# echo "DATABASE_URL: $DATABASE_URL"
# echo "DB_HOST: $DB_HOST"
# echo "DB_PORT: $DB_PORT"

# Esperar a que la base de datos esté disponible
echo "Esperando a que la base de datos esté disponible en $DB_HOST:$DB_PORT..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 0.1
done
echo "Base de datos está disponible."

# NOTA: Migraciones deshabilitadas permanentemente debido a historial corrupto
# La base de datos ya tiene todas las tablas y campos necesarios
echo "⚠️  Migraciones deshabilitadas - BD ya configurada correctamente"
# if [ "$SKIP_MIGRATIONS" = "true" ]; then
#     echo "⚠️  SKIP_MIGRATIONS=true - Saltando migraciones (modo de emergencia)"
# else
#     echo "Aplicando migraciones..."
#     python manage.py migrate
# fi

# Add this section to run populate_fake_data.py in dev environment only
if [ "$ENVIRONMENT" = "development" ] || [ "$DJANGO_ENV" = "development" ]; then
  echo "Ambiente de desarrollo detectado. Poblando datos falsos..."
  python populate_fake_data.py
fi

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

# Verificar si se pasaron argumentos al contenedor (ej: comando de cron job)
if [ "$#" -gt 0 ]; then
    # Si hay argumentos, ejecutarlos directamente (para cron jobs)
    echo "Ejecutando comando: $@"
    # Usar eval para ejecutar el comando correctamente si contiene espacios
    eval exec "$@"
else
    # Si no hay argumentos, ejecutar comportamiento por defecto (web service)
    # Recolectar archivos estáticos
    echo "Recolectando archivos estáticos..."
    python manage.py collectstatic --noinput

    # Iniciar Gunicorn para servir la aplicación, usando el puerto asignado por Render
    PORT=${PORT:-8000}
    # Workers: plan Render Standard (2GB RAM, 1 CPU). 3 workers (regla 2*CPU+1)
    # caben de sobra en 2GB (~250MB c/u) y eliminan el cuello de "1 worker que
    # encola todo". --max-requests recicla cada worker para evitar fugas de memoria.
    WEB_WORKERS=${WEB_WORKERS:-3}
    echo "Iniciando Gunicorn en 0.0.0.0:$PORT con $WEB_WORKERS workers, timeout 120s, log-level warning..."
    exec gunicorn aremko_project.wsgi:application --bind 0.0.0.0:$PORT --workers $WEB_WORKERS --timeout 120 --max-requests 1000 --max-requests-jitter 100 --log-level warning
fi
