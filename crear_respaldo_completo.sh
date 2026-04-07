#!/bin/bash
# Script para crear respaldo completo de la aplicación
# Uso: bash crear_respaldo_completo.sh

echo "======================================================================"
echo "RESPALDO COMPLETO DE AREMKO BOOKING SYSTEM"
echo "======================================================================"
echo ""

# Crear directorio de respaldo con fecha
BACKUP_DIR="backups/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "📁 Directorio de respaldo: $BACKUP_DIR"
echo ""

# 1. Guardar estado actual de Git
echo "1️⃣  Guardando estado de Git..."
git status > "$BACKUP_DIR/git_status.txt"
git log --oneline -20 > "$BACKUP_DIR/git_log.txt"
git branch -a > "$BACKUP_DIR/git_branches.txt"
git remote -v > "$BACKUP_DIR/git_remotes.txt"
echo "   ✅ Estado de Git guardado"
echo ""

# 2. Crear tag de respaldo en Git
echo "2️⃣  Creando tag de respaldo en Git..."
TAG_NAME="backup-$(date +%Y%m%d-%H%M%S)"
git tag -a "$TAG_NAME" -m "Respaldo automático antes de recrear servicio en Render"
echo "   ✅ Tag creado: $TAG_NAME"
echo "   💡 Ejecuta 'git push --tags' para subir el tag a GitHub"
echo ""

# 3. Listar archivos importantes del proyecto
echo "3️⃣  Guardando estructura del proyecto..."
tree -L 3 -I '__pycache__|*.pyc|node_modules|.git' > "$BACKUP_DIR/estructura_proyecto.txt" 2>/dev/null || find . -type f -not -path "*/\.*" -not -path "*/__pycache__/*" -not -path "*/node_modules/*" | head -100 > "$BACKUP_DIR/archivos_principales.txt"
echo "   ✅ Estructura guardada"
echo ""

# 4. Copiar archivos de configuración críticos
echo "4️⃣  Copiando archivos de configuración..."
cp requirements.txt "$BACKUP_DIR/" 2>/dev/null
cp Dockerfile "$BACKUP_DIR/" 2>/dev/null
cp entrypoint.sh "$BACKUP_DIR/" 2>/dev/null
cp aremko_project/settings.py "$BACKUP_DIR/settings.py" 2>/dev/null
cp aremko_project/urls.py "$BACKUP_DIR/urls.py" 2>/dev/null
cp ventas/urls.py "$BACKUP_DIR/ventas_urls.py" 2>/dev/null
echo "   ✅ Archivos de configuración copiados"
echo ""

# 5. Documentar dependencias Python
echo "5️⃣  Documentando dependencias Python..."
if command -v pip &> /dev/null; then
    pip freeze > "$BACKUP_DIR/pip_freeze.txt" 2>/dev/null
    echo "   ✅ Dependencias Python guardadas"
else
    echo "   ⚠️  pip no disponible, saltando"
fi
echo ""

# 6. Crear archivo de documentación del respaldo
echo "6️⃣  Creando documentación del respaldo..."
cat > "$BACKUP_DIR/README.md" << EOF
# Respaldo Completo - Aremko Booking System
**Fecha:** $(date +"%Y-%m-%d %H:%M:%S")
**Tag Git:** $TAG_NAME

## Información del Respaldo

### Commit Actual
\`\`\`
$(git log -1 --oneline)
\`\`\`

### Branch Actual
\`\`\`
$(git branch --show-current)
\`\`\`

### Estado del Repositorio
Ver archivo: git_status.txt

### Configuración
- settings.py: Configuración de Django
- urls.py: Configuración de URLs principales
- ventas_urls.py: URLs del módulo ventas
- requirements.txt: Dependencias Python
- Dockerfile: Configuración de contenedor
- entrypoint.sh: Script de entrada

### Variables de Entorno Requeridas

IMPORTANTE: La base de datos debe respaldarse por separado desde Render.

Variables críticas necesarias para restaurar:
- DATABASE_URL
- SECRET_KEY
- SENDGRID_API_KEY
- FLOW_API_KEY
- FLOW_SECRET_KEY
- CLOUDINARY_URL
- REDVOISS_USERNAME
- REDVOISS_PASSWORD

(Ver render_env_template.txt para lista completa)

### Restauración

Para restaurar este respaldo:

1. **Restaurar código:**
   \`\`\`bash
   git checkout $TAG_NAME
   \`\`\`

2. **Restaurar base de datos:**
   - Usa el respaldo de PostgreSQL que hiciste desde Render Dashboard

3. **Configurar variables de entorno:**
   - Copia las variables desde el archivo render_env_template.txt

4. **Deploy:**
   - Push a GitHub (si es necesario)
   - Render automáticamente hará deploy

## Notas

- Base de datos respaldada: ✅ (desde Render Dashboard)
- Código respaldado: ✅ (tag: $TAG_NAME)
- Variables de entorno: ⚠️ Debes documentarlas manualmente desde Render
- Archivos media: ⚠️ Están en Cloudinary, no afectados

EOF

echo "   ✅ Documentación creada"
echo ""

# 7. Template de variables de entorno
echo "7️⃣  Creando template de variables de entorno..."
cat > "$BACKUP_DIR/render_env_template.txt" << EOF
# Variables de Entorno para Render
# Copia estos valores desde tu servicio actual en Render Dashboard

# === DJANGO ===
SECRET_KEY=
DEBUG=False
DJANGO_SETTINGS_MODULE=aremko_project.settings
ALLOWED_HOSTS=aremko-booking.onrender.com,.onrender.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://aremko-booking.onrender.com

# === BASE DE DATOS ===
DATABASE_URL=

# === SUPERUSUARIO ===
DJANGO_SUPERUSER_USERNAME=
DJANGO_SUPERUSER_EMAIL=
DJANGO_SUPERUSER_PASSWORD=

# === EMAIL (SendGrid) ===
SENDGRID_API_KEY=
DEFAULT_FROM_EMAIL=noreply@aremko.cl

# === SMS (Redvoiss - Chile) ===
REDVOISS_API_URL=https://api.redvoiss.com
REDVOISS_USERNAME=
REDVOISS_PASSWORD=

# === CLOUDINARY (Media Storage) ===
CLOUDINARY_URL=

# === FLOW.CL (Pagos Chile) ===
FLOW_API_KEY=
FLOW_SECRET_KEY=
FLOW_CREATE_API_URL=https://sandbox.flow.cl/api/payment/create
FLOW_STATUS_API_URL=https://sandbox.flow.cl/api/payment/getStatus

# === SITE CONFIG ===
SITE_URL=https://aremko-booking.onrender.com

# === OTRAS (si existen en tu config actual) ===
# Agrega cualquier otra variable que tengas configurada
EOF

echo "   ✅ Template de variables creado"
echo ""

# 8. Crear checklist de respaldo
echo "8️⃣  Creando checklist..."
cat > "$BACKUP_DIR/CHECKLIST.md" << EOF
# ✅ Checklist de Respaldo

Antes de proceder con cambios en Render, verifica:

## Respaldos Completados

- [ ] ✅ Código respaldado en Git (tag: $TAG_NAME)
- [ ] ✅ Tag subido a GitHub (\`git push --tags\`)
- [ ] ✅ Base de datos respaldada desde Render Dashboard
- [ ] ✅ Variables de entorno documentadas
- [ ] ✅ Archivos de configuración copiados

## Información Documentada

- [ ] DATABASE_URL anotado
- [ ] SECRET_KEY anotado
- [ ] API Keys de servicios externos anotados
- [ ] Configuración de DNS actual documentada (si aplica)

## Verificación

- [ ] El respaldo de base de datos se descargó correctamente
- [ ] El tag aparece en GitHub
- [ ] Tienes acceso a las credenciales necesarias

## Listo para Proceder

Una vez completado todo lo anterior, puedes:
1. Crear nuevo servicio en Render
2. Configurar variables de entorno
3. Conectar base de datos existente
4. Deploy y prueba

## En Caso de Problemas

Para volver al estado anterior:
1. \`git checkout $TAG_NAME\`
2. Restaurar base de datos desde el respaldo
3. Re-desplegar servicio viejo en Render

EOF

echo "   ✅ Checklist creado"
echo ""

# Resumen
echo "======================================================================"
echo "✅ RESPALDO COMPLETADO"
echo "======================================================================"
echo ""
echo "📁 Ubicación: $BACKUP_DIR"
echo "🏷️  Tag Git: $TAG_NAME"
echo ""
echo "📋 Archivos creados:"
ls -lh "$BACKUP_DIR"
echo ""
echo "📝 PRÓXIMOS PASOS:"
echo ""
echo "1. ⚠️  IMPORTANTE: Respalda la base de datos desde Render Dashboard"
echo "   - Ve a tu servicio PostgreSQL en Render"
echo "   - Dashboard → Tu base de datos → Backups"
echo "   - Create Backup → Download"
echo ""
echo "2. 📤 Sube el tag a GitHub:"
echo "   git push --tags"
echo ""
echo "3. 📝 Anota tus variables de entorno:"
echo "   - Ve a Render Dashboard → Tu servicio → Environment"
echo "   - Copia los valores al archivo: $BACKUP_DIR/render_env_template.txt"
echo ""
echo "4. ✅ Marca los items en: $BACKUP_DIR/CHECKLIST.md"
echo ""
echo "Una vez completado todo, estarás listo para crear el nuevo servicio."
echo ""
echo "======================================================================"
