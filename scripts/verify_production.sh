#!/bin/bash
#
# Script de Verificación Post-Deploy
# Verifica que el deploy se completó correctamente y las vulnerabilidades fueron resueltas
#

set -e

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  🔍 VERIFICACIÓN POST-DEPLOY - AREMKO BOOKING SYSTEM${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Fecha: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ============================================================
# 1. VERIFICAR CONECTIVIDAD CON PRODUCCIÓN
# ============================================================
echo -e "${GREEN}1. VERIFICANDO CONECTIVIDAD CON PRODUCCIÓN...${NC}"

PROD_URL="https://www.aremko.cl"

if curl -s --head "$PROD_URL" | head -n 1 | grep "HTTP" > /dev/null; then
    echo -e "   ${GREEN}✅ Sitio accesible: $PROD_URL${NC}"
else
    echo -e "   ${RED}❌ No se puede acceder a $PROD_URL${NC}"
    exit 1
fi

# ============================================================
# 2. VERIFICAR ENDPOINTS CRÍTICOS
# ============================================================
echo ""
echo -e "${GREEN}2. VERIFICANDO ENDPOINTS CRÍTICOS...${NC}"

# Array de endpoints a verificar
declare -a endpoints=(
    "/admin/"
    "/control_gestion/reportes/"
    "/ventas/servicios-vendidos/"
)

for endpoint in "${endpoints[@]}"; do
    url="${PROD_URL}${endpoint}"
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$url")

    if [ "$status_code" == "200" ] || [ "$status_code" == "302" ] || [ "$status_code" == "301" ]; then
        echo -e "   ${GREEN}✅ $endpoint - Status: $status_code${NC}"
    else
        echo -e "   ${YELLOW}⚠️  $endpoint - Status: $status_code${NC}"
    fi
done

# ============================================================
# 3. INSTRUCCIONES PARA VERIFICAR EN RENDER SHELL
# ============================================================
echo ""
echo -e "${GREEN}3. VERIFICAR VERSIONES EN RENDER SHELL${NC}"
echo -e "${YELLOW}   Para verificar las versiones de paquetes instalados:${NC}"
echo ""
echo -e "   ${BLUE}A) Desde Render Dashboard:${NC}"
echo "      1. Ir a: https://dashboard.render.com"
echo "      2. Seleccionar servicio 'aremko-booking-system-prod'"
echo "      3. Click en 'Shell' (pestaña superior)"
echo "      4. Ejecutar los siguientes comandos:"
echo ""
echo -e "   ${BLUE}B) Comandos a ejecutar en Render Shell:${NC}"
echo ""
cat << 'HEREDOC'
# Verificar versión de Django
python -c "import django; print(f'Django: {django.__version__}')"

# Verificar versión de requests
python -c "import requests; print(f'requests: {requests.__version__}')"

# Verificar versión de Pillow
python -c "import PIL; print(f'Pillow: {PIL.__version__}')"

# Verificar versión de djangorestframework
python -c "import rest_framework; print(f'DRF: {rest_framework.__version__}')"

# Verificar todas las versiones críticas
pip list | grep -E "Django|requests|Pillow|djangorestframework|gunicorn"

# Ver pip freeze completo (opcional)
pip freeze > /tmp/production_requirements.txt
cat /tmp/production_requirements.txt
HEREDOC

# ============================================================
# 4. VERSIONES ESPERADAS
# ============================================================
echo ""
echo -e "${GREEN}4. VERSIONES ESPERADAS${NC}"
echo -e "${YELLOW}   Las siguientes versiones deberían estar instaladas:${NC}"
echo ""
echo "   Django:                 >= 4.2.17"
echo "   requests:               >= 2.32.0"
echo "   Pillow:                 >= 10.4.0"
echo "   djangorestframework:    >= 3.15.2"
echo "   gunicorn:               >= 22.0.0"
echo "   whitenoise:             >= 6.8.2"
echo ""

# ============================================================
# 5. VERIFICACIÓN DE LOGS EN RENDER
# ============================================================
echo -e "${GREEN}5. REVISAR LOGS DE DEPLOY EN RENDER${NC}"
echo -e "${YELLOW}   Para verificar que el deploy fue exitoso:${NC}"
echo ""
echo "   1. Ir a Render Dashboard > Servicio"
echo "   2. Click en 'Logs' (pestaña superior)"
echo "   3. Buscar las siguientes líneas:"
echo ""
echo -e "      ${GREEN}✅ Líneas que indican éxito:${NC}"
echo "         - 'Successfully installed Django-4.2.XX'"
echo "         - 'Successfully installed requests-2.32.X'"
echo "         - 'Successfully installed Pillow-10.4.X'"
echo "         - 'Running migrations...'"
echo "         - 'Starting service...'"
echo ""
echo -e "      ${RED}❌ Líneas que indican error:${NC}"
echo "         - 'ERROR:'"
echo "         - 'FAILED'"
echo "         - 'ModuleNotFoundError'"
echo "         - 'ImportError'"
echo ""

# ============================================================
# 6. TESTING DE FUNCIONALIDADES
# ============================================================
echo -e "${GREEN}6. TESTING MANUAL DE FUNCIONALIDADES${NC}"
echo -e "${YELLOW}   Probar manualmente las siguientes funcionalidades:${NC}"
echo ""
echo "   ${BLUE}A) Panel de Administración:${NC}"
echo "      URL: https://www.aremko.cl/admin/"
echo "      - Login con credenciales de admin"
echo "      - Verificar que carga sin errores 500"
echo ""
echo "   ${BLUE}B) Control de Gestión:${NC}"
echo "      URL: https://www.aremko.cl/control_gestion/reportes/"
echo "      - Debe cargar sin error 500 (corregido)"
echo "      - Verificar navegación entre secciones"
echo ""
echo "   ${BLUE}C) Módulo de Ventas:${NC}"
echo "      URL: https://www.aremko.cl/ventas/servicios-vendidos/"
echo "      - Cargar reportes"
echo "      - Filtrar por fechas"
echo ""
echo "   ${BLUE}D) Subida de Archivos (Pillow):${NC}"
echo "      - Admin > Servicios > Subir imagen"
echo "      - Verificar que procesa correctamente"
echo ""

# ============================================================
# 7. VERIFICAR GITHUB DEPENDABOT
# ============================================================
echo -e "${GREEN}7. VERIFICAR GITHUB DEPENDABOT${NC}"
echo -e "${YELLOW}   GitHub tardará algunas horas en re-escanear:${NC}"
echo ""
echo "   1. Ir a: https://github.com/nomad3/booking-system-aremko/security/dependabot"
echo "   2. Esperar 1-4 horas para que GitHub re-escanee"
echo "   3. Verificar que las alertas críticas desaparezcan"
echo ""
echo -e "   ${BLUE}Antes: 35 vulnerabilidades (4 críticas, 12 altas)${NC}"
echo -e "   ${GREEN}Esperado: 0-5 vulnerabilidades restantes (menores)${NC}"
echo ""

# ============================================================
# 8. BACKUP DE BD DE PRODUCCIÓN
# ============================================================
echo -e "${GREEN}8. BACKUP DE BASE DE DATOS (RECOMENDADO)${NC}"
echo -e "${YELLOW}   Crear backup manual post-deploy exitoso:${NC}"
echo ""
echo "   1. Ir a: https://dashboard.render.com"
echo "   2. Seleccionar: PostgreSQL Database"
echo "   3. Click en: 'Backups' > 'Create Manual Backup'"
echo "   4. Label: 'post-security-update-2025-11-09'"
echo ""

# ============================================================
# 9. RESUMEN
# ============================================================
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ VERIFICACIÓN BÁSICA COMPLETADA${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}PRÓXIMOS PASOS:${NC}"
echo "  1. Verificar versiones en Render Shell"
echo "  2. Probar funcionalidades críticas manualmente"
echo "  3. Revisar logs de deploy en Render"
echo "  4. Esperar 1-4 horas para GitHub Dependabot re-escaneo"
echo "  5. Crear backup manual de BD post-deploy"
echo ""
echo -e "${GREEN}Si todo funciona correctamente:${NC}"
echo "  ✅ Vulnerabilidades resueltas"
echo "  ✅ Sistema actualizado y seguro"
echo "  ✅ No se requiere rollback"
echo ""
echo -e "${RED}Si hay errores:${NC}"
echo "  ❌ Revisar logs en Render"
echo "  ❌ Considerar rollback desde backup"
echo "  ❌ Contactar soporte si persisten problemas"
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
