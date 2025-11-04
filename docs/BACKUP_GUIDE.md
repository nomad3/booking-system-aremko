# Guía de Respaldo - Booking System Aremko

## 📋 Descripción General

Esta guía documenta los procedimientos para crear respaldos completos del sistema de reservas Aremko, incluyendo código, base de datos y archivos media.

## 🚀 Respaldo Rápido (Todo en Uno)

### En Local:
```bash
cd /path/to/booking-system-aremko
chmod +x scripts/backup.sh
./scripts/backup.sh
```

### En Render (Producción):
```bash
# 1. Conectar a Render Shell
# 2. Ejecutar:
cd /app
bash scripts/backup.sh
```

El script creará un archivo comprimido en `backups/` con:
- Código fuente completo
- Archivos de configuración
- Archivos media
- Información del sistema
- Estado de migraciones

## 💾 Respaldo de Base de Datos

### Usando Django Command (Recomendado):
```bash
# Formato custom (más eficiente, comprimido)
python manage.py backup_database

# Formato SQL plano
python manage.py backup_database --format=sql

# Guardar en directorio específico
python manage.py backup_database --output-dir=/path/to/backups
```

### Usando pg_dump directamente:
```bash
# Obtener credenciales de .env o Render Dashboard
pg_dump -h [HOST] -U [USER] -d [DATABASE] -f backup.dump -Fc

# Con variables de entorno
export PGPASSWORD='your-password'
pg_dump -h your-host -U your-user -d your-database -f backup.dump -Fc
```

## 📁 Estructura de Respaldos

```
backups/
├── booking_system_backup_YYYYMMDD_HHMMSS.tar.gz
│   ├── code.tar.gz              # Código fuente
│   ├── media.tar.gz             # Archivos subidos
│   ├── .env.backup              # Variables de entorno
│   ├── system_info.txt          # Información del sistema
│   └── migrations_status.txt    # Estado de migraciones
└── db/
    └── database_backup_YYYYMMDD_HHMMSS.dump
```

## 🔄 Restauración

### 1. Restaurar Código:
```bash
# Extraer respaldo
tar -xzf backups/booking_system_backup_YYYYMMDD_HHMMSS.tar.gz

# Extraer código
cd booking_system_backup_YYYYMMDD_HHMMSS
tar -xzf code.tar.gz -C /path/to/restore

# Restaurar archivos media
tar -xzf media.tar.gz -C /path/to/restore

# Restaurar configuración
cp .env.backup /path/to/restore/.env
```

### 2. Restaurar Base de Datos:

#### Formato Custom (.dump):
```bash
pg_restore -h [HOST] -U [USER] -d [DATABASE] --clean --no-owner backup.dump
```

#### Formato SQL:
```bash
psql -h [HOST] -U [USER] -d [DATABASE] < backup.sql
```

#### En Render:
1. Subir archivo de respaldo a un servicio temporal (ej: transfer.sh)
2. En Render Shell:
```bash
wget [URL_DEL_ARCHIVO]
pg_restore -d $DATABASE_URL --clean --no-owner backup.dump
```

## 🔐 Seguridad

1. **Encriptar respaldos sensibles**:
```bash
# Encriptar
gpg -c backup.tar.gz

# Desencriptar
gpg -d backup.tar.gz.gpg > backup.tar.gz
```

2. **Almacenamiento seguro**:
- NO commitear respaldos al repositorio
- Usar servicios cloud seguros (S3, Google Cloud Storage)
- Mantener múltiples copias en diferentes ubicaciones

3. **Rotación de respaldos**:
- Mantener últimos 7 respaldos diarios
- Mantener últimos 4 respaldos semanales
- Mantener últimos 12 respaldos mensuales

## 📅 Programación Automática

### En servidor Linux:
```bash
# Editar crontab
crontab -e

# Respaldo diario a las 3 AM
0 3 * * * cd /path/to/project && ./scripts/backup.sh

# Respaldo de BD cada 6 horas
0 */6 * * * cd /path/to/project && python manage.py backup_database
```

### En Render:
Usar Render Cron Jobs para programar respaldos automáticos.

## ⚠️ Consideraciones Importantes

1. **Espacio en disco**: Verificar espacio antes de respaldar
2. **Permisos**: Asegurar permisos correctos en archivos restaurados
3. **Versiones**: Verificar compatibilidad de versiones al restaurar
4. **Testing**: Siempre probar restauración en ambiente de prueba

## 🛠️ Troubleshooting

### Error: pg_dump not found
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client

# MacOS
brew install postgresql

# Render
# pg_dump ya está disponible
```

### Error: Permission denied
```bash
chmod +x scripts/backup.sh
sudo chown -R $(whoami) backups/
```

### Error: No space left on device
```bash
# Verificar espacio
df -h

# Limpiar respaldos antiguos
find backups/ -name "*.tar.gz" -mtime +30 -delete
```

## 📞 Soporte

Para asistencia con respaldos en producción:
- Revisar logs en Render Dashboard
- Contactar al equipo de desarrollo
- Documentar cualquier error específico

---

**Última actualización**: $(date +%Y-%m-%d)