#!/bin/bash
# ============================================================
# SCRIPT DE RESPALDO - AREMKO BOOKING SYSTEM
# Fecha: 02/12/2024
# ============================================================

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================================"
echo "🔧 INICIANDO RESPALDO DE AREMKO BOOKING SYSTEM"
echo "============================================================"

# Variables
FECHA=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups"
BACKUP_NAME="aremko_backup_${FECHA}"
EXCLUDE_FILE=".backup_exclude"

# Crear directorio de backups si no existe
if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    echo -e "${GREEN}✅ Directorio de backups creado${NC}"
fi

# Crear archivo de exclusiones
cat > $EXCLUDE_FILE << EOF
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
pip-log.txt
pip-delete-this-directory.txt
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.gitignore
.mypy_cache
.pytest_cache
.hypothesis
*.sqlite3
*.db
media/
staticfiles/
.env
.env.local
.env.*.local
node_modules/
npm-debug.log
yarn-error.log
.DS_Store
*.swp
*.swo
*~
.vscode/
.idea/
*.sublime-project
*.sublime-workspace
EOF

echo -e "${YELLOW}📋 Información del respaldo:${NC}"
echo "   - Nombre: $BACKUP_NAME"
echo "   - Directorio: $BACKUP_DIR"
echo "   - Fecha: $(date)"
echo ""

# Listar archivos importantes
echo -e "${YELLOW}📂 Verificando archivos críticos...${NC}"
CRITICAL_FILES=(
    "manage.py"
    "requirements.txt"
    "aremko_project/settings.py"
    "ventas/models.py"
    "ventas/admin.py"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "   ${GREEN}✓${NC} $file"
    else
        echo -e "   ${RED}✗${NC} $file (NO ENCONTRADO)"
    fi
done
echo ""

# Contar migraciones
MIGRATIONS_COUNT=$(ls ventas/migrations/*.py 2>/dev/null | wc -l)
echo -e "${YELLOW}📊 Estadísticas:${NC}"
echo "   - Migraciones: $MIGRATIONS_COUNT archivos"
echo "   - Tamaño total: $(du -sh . | cut -f1)"
echo ""

# Crear el archivo tar
echo -e "${YELLOW}📦 Creando archivo de respaldo...${NC}"
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" \
    --exclude-from=$EXCLUDE_FILE \
    . 2>/dev/null

# Verificar si el backup se creó correctamente
if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(ls -lh "$BACKUP_DIR/$BACKUP_NAME.tar.gz" | awk '{print $5}')
    echo -e "${GREEN}✅ Respaldo creado exitosamente${NC}"
    echo "   - Archivo: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
    echo "   - Tamaño: $BACKUP_SIZE"

    # Crear archivo de información
    cat > "$BACKUP_DIR/$BACKUP_NAME.info" << EOF
RESPALDO DE AREMKO BOOKING SYSTEM
==================================
Fecha: $(date)
Archivo: $BACKUP_NAME.tar.gz
Tamaño: $BACKUP_SIZE
Migraciones: $MIGRATIONS_COUNT
Commit actual: $(git rev-parse --short HEAD 2>/dev/null || echo "N/A")
Branch: $(git branch --show-current 2>/dev/null || echo "N/A")

Archivos incluidos:
- Código fuente Python
- Templates HTML
- Archivos estáticos
- Migraciones
- Configuraciones (sin .env)
- Scripts de utilidad
- Documentación

Para restaurar:
1. Extraer: tar -xzf $BACKUP_NAME.tar.gz
2. Instalar deps: pip install -r requirements.txt
3. Configurar .env
4. Ejecutar migraciones: python manage.py migrate
5. Cargar datos: python manage.py loaddata backup.json (si existe)
EOF

    echo -e "${GREEN}📄 Archivo de información creado${NC}"
    echo ""

    # Listar últimos 5 backups
    echo -e "${YELLOW}📋 Últimos backups disponibles:${NC}"
    ls -lht "$BACKUP_DIR"/*.tar.gz 2>/dev/null | head -5 | awk '{print "   - " $9 " (" $5 ")"}'

else
    echo -e "${RED}❌ Error al crear el respaldo${NC}"
    exit 1
fi

# Limpiar archivo temporal
rm -f $EXCLUDE_FILE

echo ""
echo "============================================================"
echo -e "${GREEN}✅ RESPALDO COMPLETADO EXITOSAMENTE${NC}"
echo "============================================================"
echo ""
echo -e "${YELLOW}⚠️  RECORDATORIO:${NC}"
echo "   1. Respalda también la base de datos desde Render"
echo "   2. Guarda el archivo .env en un lugar seguro"
echo "   3. Documenta cualquier configuración especial"
echo "   4. Considera subir el backup a un almacenamiento cloud"
echo ""

# Preguntar si desea comprimir para envío
read -p "¿Deseas crear una versión comprimida para envío por email? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Crear versión más pequeña sin migraciones ni documentación pesada
    echo -e "${YELLOW}📧 Creando versión ligera...${NC}"
    tar -czf "$BACKUP_DIR/${BACKUP_NAME}_light.tar.gz" \
        --exclude-from=$EXCLUDE_FILE \
        --exclude="ventas/migrations/*" \
        --exclude="*.md" \
        --exclude="docs/*" \
        --exclude="backups/*" \
        . 2>/dev/null

    LIGHT_SIZE=$(ls -lh "$BACKUP_DIR/${BACKUP_NAME}_light.tar.gz" | awk '{print $5}')
    echo -e "${GREEN}✅ Versión ligera creada${NC}"
    echo "   - Archivo: $BACKUP_DIR/${BACKUP_NAME}_light.tar.gz"
    echo "   - Tamaño: $LIGHT_SIZE (optimizado para email)"
fi

echo ""
echo "Fin del script de respaldo."