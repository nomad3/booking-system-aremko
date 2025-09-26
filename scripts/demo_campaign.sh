#!/bin/bash

# Demo Script para Campañas de Email - Aremko CRM
# Este script demuestra cómo usar el sistema de campañas drip

echo "🚀 DEMO: Sistema de Campañas Drip - Aremko CRM"
echo "=============================================="

# Verificar que estamos en el directorio correcto
if [ ! -f "manage.py" ]; then
    echo "❌ Error: Este script debe ejecutarse desde el directorio raíz del proyecto"
    exit 1
fi

echo ""
echo "📊 1. Diagnosticando estado actual de la cola..."
python3 manage.py diagnose_campaign_queue

echo ""
echo "📧 2. Enviando email de prueba..."
read -p "Ingresa tu email para la prueba: " TEST_EMAIL
python3 manage.py send_campaign_test_email \
    --email "$TEST_EMAIL" \
    --nombre "Usuario Demo" \
    --empresa "Empresa Demo"

echo ""
echo "🔍 3. Verificando si hay archivo CSV de ejemplo..."
if [ ! -f "docs/campaign_csv_example.csv" ]; then
    echo "❌ No se encontró el archivo CSV de ejemplo"
    exit 1
fi

echo "✅ CSV de ejemplo encontrado"
echo ""
echo "📁 4. Contenido del CSV de ejemplo:"
cat docs/campaign_csv_example.csv

echo ""
echo "🌱 5. Modo simulación: Sembrando cola desde CSV (sin crear registros reales)..."
python3 manage.py seed_campaign_from_csv \
    --csv-file docs/campaign_csv_example.csv \
    --subject "🏨 Demo: Reuniones que Inspiran en Aremko Hotel Spa" \
    --template-file templates/emails/prospecting_campaign.html \
    --dry-run

echo ""
echo "❓ ¿Quieres sembrar la cola REAL con estos contactos? (y/N)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    echo ""
    echo "🌱 Sembrando cola REAL..."
    python3 manage.py seed_campaign_from_csv \
        --csv-file docs/campaign_csv_example.csv \
        --subject "🏨 Reuniones que Inspiran: Descubre el Secreto de los Equipos Más Exitosos en Los Lagos" \
        --template-file templates/emails/prospecting_campaign.html
    
    echo ""
    echo "📊 Estado después de sembrar:"
    python3 manage.py diagnose_campaign_queue
    
    echo ""
    echo "📤 Enviando primer email manualmente..."
    python3 manage.py send_next_campaign_drip
    
    echo ""
    echo "📊 Estado después del primer envío:"
    python3 manage.py diagnose_campaign_queue
    
    echo ""
    echo "✅ ¡Listo! El cron job enviará 1 email cada 10 minutos automáticamente."
    echo "Para monitorear: python3 manage.py diagnose_campaign_queue"
else
    echo ""
    echo "ℹ️  No se creó la cola real. Para hacerlo manualmente:"
    echo "python3 manage.py seed_campaign_from_csv --csv-file tu_archivo.csv --subject 'Tu asunto' --template-file template.html"
fi

echo ""
echo "🎉 Demo completado. Revisa la guía completa en docs/GUIA_CAMPANAS_EMAIL.md"