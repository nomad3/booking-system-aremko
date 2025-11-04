# Directorio de Respaldos

Este directorio está destinado a almacenar respaldos del sistema.

## ⚠️ IMPORTANTE

- **NO COMMITEAR** archivos de respaldo al repositorio
- Los respaldos pueden contener información sensible
- Use servicios externos para almacenar respaldos (S3, Google Cloud, etc.)

## Uso

```bash
# Crear respaldo completo
../scripts/backup.sh

# Respaldar solo base de datos
python ../manage.py backup_database
```

Los respaldos se guardarán en este directorio con nombres que incluyen fecha y hora.