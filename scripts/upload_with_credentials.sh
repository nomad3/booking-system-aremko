#!/bin/bash

echo "================================================================================"
echo "SUBIR IMÁGENES DE EMPRESAS A CLOUDINARY"
echo "================================================================================"
echo ""

# Solicitar credenciales
echo "Por favor ingresa las credenciales de Cloudinary:"
echo ""

read -p "Cloud Name [dtuncr1pi]: " CLOUD_NAME
CLOUD_NAME=${CLOUD_NAME:-dtuncr1pi}

read -p "API Key: " API_KEY
read -sp "API Secret: " API_SECRET
echo ""
echo ""

# Exportar variables de entorno temporalmente
export CLOUDINARY_CLOUD_NAME="$CLOUD_NAME"
export CLOUDINARY_API_KEY="$API_KEY"
export CLOUDINARY_API_SECRET="$API_SECRET"

echo "✅ Credenciales configuradas temporalmente"
echo ""
echo "Ejecutando script de carga..."
echo ""

# Ejecutar el script de Python
python3 scripts/upload_images_simple.py

# Las variables de entorno solo duran esta sesión
echo ""
echo "================================================================================"
echo "Nota: Las credenciales solo se usaron para esta ejecución"
echo "No se guardaron permanentemente"
echo "================================================================================"
