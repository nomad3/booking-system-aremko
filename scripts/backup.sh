#!/bin/bash

# Script de respaldo completo para booking-system-aremko
# Autor: Sistema automatizado
# Fecha: $(date +%Y-%m-%d)

set -e  # Salir si hay errores

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuración
BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="booking_system_backup_${TIMESTAMP}"

echo -e "${GREEN}=== INICIANDO RESPALDO DE BOOKING-SYSTEM-AREMKO ===${NC}"
echo -e "Fecha: $(date)"
echo ""

# Crear directorio de respaldos si no existe
if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    echo -e "${YELLOW}Directorio de respaldos creado: $BACKUP_DIR${NC}"
fi

# Crear directorio para este respaldo
CURRENT_BACKUP_DIR="${BACKUP_DIR}/${BACKUP_NAME}"
mkdir -p "$CURRENT_BACKUP_DIR"

echo -e "${GREEN}1. RESPALDANDO CÓDIGO FUENTE...${NC}"
# Excluir archivos innecesarios
tar -czf "${CURRENT_BACKUP_DIR}/code.tar.gz" \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='env' \
    --exclude='node_modules' \
    --exclude='media/*' \
    --exclude='staticfiles/*' \
    --exclude='backups' \
    --exclude='.env' \
    --exclude='*.log' \
    .

echo -e "   ✓ Código respaldado en: ${CURRENT_BACKUP_DIR}/code.tar.gz"

echo -e "\n${GREEN}2. RESPALDANDO ARCHIVOS DE CONFIGURACIÓN...${NC}"
# Respaldar archivos importantes por separado
if [ -f ".env" ]; then
    cp .env "${CURRENT_BACKUP_DIR}/.env.backup"
    echo -e "   ✓ Archivo .env respaldado"
fi

if [ -f ".env.production" ]; then
    cp .env.production "${CURRENT_BACKUP_DIR}/.env.production.backup"
    echo -e "   ✓ Archivo .env.production respaldado"
fi

echo -e "\n${GREEN}3. RESPALDANDO ARCHIVOS MEDIA...${NC}"
if [ -d "media" ] && [ "$(ls -A media)" ]; then
    tar -czf "${CURRENT_BACKUP_DIR}/media.tar.gz" media/
    echo -e "   ✓ Archivos media respaldados"
else
    echo -e "   ${YELLOW}No hay archivos media para respaldar${NC}"
fi

echo -e "\n${GREEN}4. GENERANDO INFORMACIÓN DEL SISTEMA...${NC}"
cat > "${CURRENT_BACKUP_DIR}/system_info.txt" << EOF
INFORMACIÓN DEL RESPALDO
========================
Fecha: $(date)
Hostname: $(hostname)
Usuario: $(whoami)
Directorio: $(pwd)

VERSIONES:
Python: $(python --version 2>&1)
Django: $(python -c "import django; print(f'Django {django.get_version()}')" 2>&1)
Git Branch: $(git branch --show-current 2>&1)
Git Commit: $(git rev-parse HEAD 2>&1)

ARCHIVOS EN EL PROYECTO:
$(find . -type f -name "*.py" | wc -l) archivos Python
$(find . -type f -name "*.html" | wc -l) archivos HTML
$(find . -type f -name "*.js" | wc -l) archivos JavaScript
$(find . -type f -name "*.css" | wc -l) archivos CSS

TAMAÑO DEL PROYECTO:
$(du -sh . 2>/dev/null | cut -f1)
EOF

echo -e "   ✓ Información del sistema generada"

echo -e "\n${GREEN}5. RESPALDANDO DEPENDENCIAS...${NC}"
if [ -f "requirements.txt" ]; then
    cp requirements.txt "${CURRENT_BACKUP_DIR}/requirements.txt"
    echo -e "   ✓ requirements.txt respaldado"
fi

if command -v pip &> /dev/null; then
    pip freeze > "${CURRENT_BACKUP_DIR}/pip_freeze.txt" 2>&1
    echo -e "   ✓ pip freeze generado"
fi

echo -e "\n${GREEN}6. LISTANDO MIGRACIONES APLICADAS...${NC}"
if command -v python &> /dev/null && [ -f "manage.py" ]; then
    python manage.py showmigrations --list > "${CURRENT_BACKUP_DIR}/migrations_status.txt" 2>&1 || \
    echo "Error al obtener migraciones" > "${CURRENT_BACKUP_DIR}/migrations_status.txt"
    echo -e "   ✓ Estado de migraciones guardado"
fi

echo -e "\n${GREEN}7. RESPALDANDO BASE DE DATOS (DUMPDATA)...${NC}"
if command -v python &> /dev/null && [ -f "manage.py" ]; then
    # Dump de ventas
    python manage.py dumpdata ventas --indent 2 > "${CURRENT_BACKUP_DIR}/ventas_data.json" 2>&1 && \
    echo -e "   ✓ Datos de ventas exportados" || \
    echo -e "   ${YELLOW}No se pudo exportar datos de ventas${NC}"

    # Dump de control_gestion
    python manage.py dumpdata control_gestion --indent 2 > "${CURRENT_BACKUP_DIR}/control_gestion_data.json" 2>&1 && \
    echo -e "   ✓ Datos de control_gestion exportados" || \
    echo -e "   ${YELLOW}No se pudo exportar datos de control_gestion${NC}"

    # Dump de usuarios
    python manage.py dumpdata auth.User --indent 2 > "${CURRENT_BACKUP_DIR}/users_data.json" 2>&1 && \
    echo -e "   ✓ Datos de usuarios exportados" || \
    echo -e "   ${YELLOW}No se pudo exportar datos de usuarios${NC}"

    # Crear archivo con instrucciones de restauración
    cat > "${CURRENT_BACKUP_DIR}/RESTORE_INSTRUCTIONS.md" << 'HEREDOC'
# Instrucciones de Restauración

## Restaurar Código
```bash
tar -xzf code.tar.gz -C /ruta/destino/
```

## Restaurar Configuración
```bash
cp .env.backup /ruta/proyecto/.env
```

## Restaurar Base de Datos
```bash
python manage.py loaddata ventas_data.json
python manage.py loaddata control_gestion_data.json
python manage.py loaddata users_data.json
```

## Restaurar Dependencias
```bash
pip install -r requirements.txt
# O usar el snapshot exacto:
pip install -r pip_freeze.txt
```

## Restaurar Media
```bash
tar -xzf media.tar.gz -C /ruta/proyecto/
```

## Backup de BD de Producción (Render)
Para respaldar la BD de producción:
1. Ir a Render Dashboard > PostgreSQL Database
2. Click en "Manual Backup"
3. O usar pg_dump con DATABASE_URL desde variables de entorno
HEREDOC
    echo -e "   ✓ Instrucciones de restauración creadas"
fi

echo -e "\n${GREEN}8. COMPRIMIENDO RESPALDO COMPLETO...${NC}"
cd "$BACKUP_DIR"
tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
cd ..

# Calcular tamaño del respaldo
BACKUP_SIZE=$(du -sh "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" | cut -f1)

echo -e "\n${GREEN}=== RESPALDO COMPLETADO ===${NC}"
echo -e "Archivo: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
echo -e "Tamaño: $BACKUP_SIZE"
echo -e "\n${YELLOW}Para restaurar, usa:${NC}"
echo -e "tar -xzf ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

# Limpiar directorio temporal
rm -rf "$CURRENT_BACKUP_DIR"

echo -e "\n${GREEN}✓ Proceso completado exitosamente${NC}"