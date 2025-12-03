#!/bin/bash
# Script para ejecutar migraciones en Render

echo "🚀 Iniciando migraciones..."
python manage.py migrate

echo "📝 Poblando contenido SEO..."
python populate_seo_content.py

echo "✅ Migraciones completadas"