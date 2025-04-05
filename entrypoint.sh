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

# Debugging: Imprimir DB_HOST y DB_PORT (Eliminar en producción)
echo "DATABASE_URL: $DATABASE_URL"
echo "DB_HOST: $DB_HOST"
echo "DB_PORT: $DB_PORT"

# Esperar a que la base de datos esté disponible
echo "Esperando a que la base de datos esté disponible en $DB_HOST:$DB_PORT..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 0.1
done
echo "Base de datos está disponible."

# Aplicar migraciones de Django
echo "Aplicando migraciones..."
python manage.py migrate

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

# Recolectar archivos estáticos
echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# Iniciar Gunicorn para servir la aplicación, binding explicitly to port 8000, 1 worker, debug logging
echo "Iniciando Gunicorn en 0.0.0.0:8000 con 1 worker, timeout 120s, log-level debug..."
exec gunicorn aremko_project.wsgi:application --bind 0.0.0.0:8000 --workers 1 --timeout 120 --log-level debug
