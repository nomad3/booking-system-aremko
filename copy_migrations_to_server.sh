#!/bin/bash
# Script para copiar las migraciones al servidor

echo "==================================="
echo "Copiando migraciones al servidor..."
echo "==================================="

# Cambiar estos valores según tu configuración
SERVIDOR="tu-servidor.render.com"  # Cambia esto por tu servidor real
USUARIO="root"  # Cambia si tu usuario es diferente
RUTA_SERVIDOR="/app/ventas/migrations/"

# Archivos a copiar
cd ~/Documents/github/booking-system-aremko

echo "Copiando migración 0069..."
scp ventas/migrations/0069_agregar_configuracion_resumen.py ${USUARIO}@${SERVIDOR}:${RUTA_SERVIDOR}

echo "Copiando migración 0070..."
scp ventas/migrations/0070_agregar_configuracion_tips.py ${USUARIO}@${SERVIDOR}:${RUTA_SERVIDOR}

echo "==================================="
echo "¡Archivos copiados!"
echo "==================================="
echo ""
echo "Ahora en el servidor ejecuta:"
echo "1. chmod 644 ventas/migrations/0069_agregar_configuracion_resumen.py"
echo "2. chmod 644 ventas/migrations/0070_agregar_configuracion_tips.py"
echo "3. python manage.py migrate ventas 0069"
echo "4. python manage.py migrate ventas 0070"