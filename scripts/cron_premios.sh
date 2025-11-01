#!/bin/bash
set -e

echo "=============================================="
echo "🚀 CRON JOB: Envío de Premios Aprobados"
echo "=============================================="

# Aplicar migraciones si es necesario
echo "Aplicando migraciones..."
python manage.py migrate --noinput

# Ejecutar comando de envío de premios
echo "Ejecutando envío de premios..."
python manage.py enviar_premios_aprobados

echo "=============================================="
echo "✅ CRON JOB COMPLETADO"
echo "=============================================="
