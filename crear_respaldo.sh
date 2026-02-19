#!/bin/bash

# Script de respaldo completo
# Fecha: 2026-02-18

FECHA=$(date +%Y%m%d_%H%M%S)
NOMBRE_RESPALDO="respaldo_aremko_${FECHA}"
DIR_ACTUAL=$(pwd)

echo "=== CREANDO RESPALDO COMPLETO ==="
echo "Fecha: $(date)"
echo "Directorio: $DIR_ACTUAL"
echo ""

# Crear directorio temporal para el respaldo
mkdir -p ~/Desktop/${NOMBRE_RESPALDO}

# Verificar estado de git
echo "1. Verificando estado de git..."
git status --short

# Guardar información del último commit
echo "" > ~/Desktop/${NOMBRE_RESPALDO}/ultimo_commit.txt
echo "Último commit:" >> ~/Desktop/${NOMBRE_RESPALDO}/ultimo_commit.txt
git log -1 >> ~/Desktop/${NOMBRE_RESPALDO}/ultimo_commit.txt

# Crear archivo tar.gz excluyendo directorios innecesarios
echo ""
echo "2. Creando archivo comprimido..."
tar -czf ~/Desktop/${NOMBRE_RESPALDO}.tar.gz \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.DS_Store' \
    --exclude='staticfiles' \
    --exclude='media' \
    --exclude='.env' \
    --exclude='*.log' \
    --exclude='node_modules' \
    .

# Calcular tamaño
TAMANO=$(du -h ~/Desktop/${NOMBRE_RESPALDO}.tar.gz | cut -f1)

echo ""
echo "=== RESPALDO COMPLETADO ==="
echo "Archivo: ~/Desktop/${NOMBRE_RESPALDO}.tar.gz"
echo "Tamaño: $TAMANO"
echo ""
echo "IMPORTANTE: No olvides respaldar la base de datos también"
echo ""

# Limpiar directorio temporal
rm -rf ~/Desktop/${NOMBRE_RESPALDO}