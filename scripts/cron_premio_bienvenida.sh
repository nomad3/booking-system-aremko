#!/bin/bash
set -e

echo "=============================================="
echo "🎁 CRON JOB: Procesamiento de Premios de Bienvenida"
echo "Fecha/Hora: $(date)"
echo "=============================================="

# Cambiar al directorio de la aplicación
cd /app

# Configurar la variable de entorno correcta
export DJANGO_SETTINGS_MODULE=aremko_project.settings

# Verificar configuración
echo "DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"
echo "PWD=$(pwd)"

# Aplicar migraciones si es necesario
echo ""
echo "➜ Aplicando migraciones..."
python manage.py migrate --noinput

# Ejecutar comando de procesamiento de premios de bienvenida
echo ""
echo "➜ Procesando premios de bienvenida..."
python manage.py procesar_premios_bienvenida

echo ""
echo "=============================================="
echo "✅ CRON JOB COMPLETADO EXITOSAMENTE"
echo "=============================================="