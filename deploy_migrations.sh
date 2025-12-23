#!/bin/bash

# Script para desplegar las migraciones 0069 y 0070 a Render
# Ejecutar este script desde tu Mac local, NO desde Render

echo "=================================================="
echo "🚀 DEPLOY DE MIGRACIONES 0069 y 0070"
echo "=================================================="

# Cambiar al directorio del proyecto
cd ~/Documents/github/booking-system-aremko

# Verificar que estamos en el directorio correcto
if [ ! -f "manage.py" ]; then
    echo "❌ Error: No estás en el directorio del proyecto"
    echo "   Por favor, verifica la ruta"
    exit 1
fi

echo ""
echo "📁 Verificando archivos de migración..."
echo "------------------------------------------"

# Verificar que existen los archivos
if [ ! -f "ventas/migrations/0069_agregar_configuracion_resumen.py" ]; then
    echo "❌ No se encuentra: 0069_agregar_configuracion_resumen.py"
    exit 1
fi

if [ ! -f "ventas/migrations/0070_agregar_configuracion_tips.py" ]; then
    echo "❌ No se encuentra: 0070_agregar_configuracion_tips.py"
    exit 1
fi

echo "✅ Archivos de migración encontrados"

# Corregir permisos
echo ""
echo "🔧 Corrigiendo permisos de archivos..."
echo "------------------------------------------"
chmod 644 ventas/migrations/0069_agregar_configuracion_resumen.py
chmod 644 ventas/migrations/0070_agregar_configuracion_tips.py
echo "✅ Permisos corregidos a 644"

# Verificar estado de Git
echo ""
echo "📊 Estado actual de Git:"
echo "------------------------------------------"
git status --short ventas/migrations/

# Agregar archivos a Git
echo ""
echo "📝 Agregando archivos a Git..."
echo "------------------------------------------"
git add ventas/migrations/0069_agregar_configuracion_resumen.py
git add ventas/migrations/0070_agregar_configuracion_tips.py
echo "✅ Archivos agregados al staging"

# Hacer commit
echo ""
echo "💾 Haciendo commit..."
echo "------------------------------------------"
git commit -m "fix: agregar migraciones 0069 y 0070 para ConfiguracionResumen y ConfiguracionTips

- Migración 0069: Crea modelo ConfiguracionResumen y campo informacion_adicional en Servicio
- Migración 0070: Crea modelo ConfiguracionTips para tips post-pago
- Corregidos permisos de archivos a 644

🤖 Generated with Claude Code (https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

if [ $? -ne 0 ]; then
    echo "⚠️ No hay cambios para commit (puede que ya estén commiteados)"
else
    echo "✅ Commit creado exitosamente"
fi

# Hacer push
echo ""
echo "🔄 Haciendo push a GitHub..."
echo "------------------------------------------"
echo "Ejecutando: git push origin main"
git push origin main

# Verificar si el push fue exitoso
if [ $? -eq 0 ]; then
    echo "✅ Push exitoso a GitHub"
    echo ""
    echo "=================================================="
    echo "✅ DEPLOY INICIADO"
    echo "=================================================="
    echo ""
    echo "Render detectará automáticamente el push y comenzará el deploy."
    echo "Esto puede tomar 2-5 minutos."
    echo ""
    echo "📋 DESPUÉS DEL DEPLOY, ejecuta esto en la Shell de Render:"
    echo "------------------------------------------"
    echo "# 1. Verificar que los archivos existen:"
    echo "ls -la ventas/migrations/ | grep -E '006[89]|0070'"
    echo ""
    echo "# 2. Ver las migraciones pendientes:"
    echo "python manage.py showmigrations ventas | tail -10"
    echo ""
    echo "# 3. Aplicar las migraciones:"
    echo "python manage.py migrate ventas 0069"
    echo "python manage.py migrate ventas 0070"
    echo ""
    echo "# 4. Verificar que se aplicaron:"
    echo "python manage.py showmigrations ventas | tail -5"
    echo ""
    echo "=================================================="
    echo "🎯 Si todo sale bien, los Tips estarán funcionando!"
    echo "=================================================="
else
    echo "❌ Error al hacer push"
    echo "   Verifica tu conexión y permisos de GitHub"
    echo ""
    echo "Posibles soluciones:"
    echo "1. Verificar que estés en la rama correcta: git branch"
    echo "2. Verificar el remoto: git remote -v"
    echo "3. Si usas otra rama: git push origin [tu-rama]"
    exit 1
fi