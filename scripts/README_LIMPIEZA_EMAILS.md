# Guía de Limpieza de Emails Duplicados en Render

## 📋 Descripción del Problema
Aproximadamente 450 clientes quedaron registrados con el email genérico `cliente@aremko.cl`. Este documento explica cómo ejecutar los scripts para limpiar estos emails duplicados en el entorno de producción de Render.

## 🎯 Objetivo
Eliminar el email `cliente@aremko.cl` de todos los clientes afectados, dejando el campo email vacío (NULL).

## 📁 Scripts Disponibles

### 1. **Script Python/Django** (RECOMENDADO)
- **Archivo:** `limpiar_emails_duplicados.py`
- **Ventajas:**
  - Usa el ORM de Django
  - Transacciones automáticas
  - Logging detallado
  - Manejo de errores integrado

### 2. **Script SQL** (ALTERNATIVA)
- **Archivo:** `limpiar_emails_duplicados.sql`
- **Ventajas:**
  - Ejecución directa en la base de datos
  - Mayor control sobre la transacción
  - Permite crear respaldos temporales

## 🚀 Instrucciones de Ejecución en Render

### Opción A: Ejecutar Script Python en Render Shell

1. **Acceder a Render Dashboard**
   - Ingresar a https://dashboard.render.com
   - Seleccionar el servicio web de Django

2. **Abrir Shell de Render**
   - En la pestaña del servicio, hacer clic en "Shell"
   - Esperar a que se conecte la terminal

3. **Navegar al directorio de scripts**
   ```bash
   cd /app/scripts
   ```

4. **Ejecutar el script Python**
   ```bash
   python limpiar_emails_duplicados.py
   ```

5. **Verificar los resultados**
   - El script mostrará un resumen detallado
   - Verificará automáticamente que no queden emails duplicados

### Opción B: Ejecutar mediante Django Management Command

1. **Copiar el script a management/commands**
   ```bash
   cp scripts/limpiar_emails_duplicados.py ventas/management/commands/
   ```

2. **Ejecutar como comando de Django**
   ```bash
   python manage.py limpiar_emails_duplicados
   ```

### Opción C: Ejecutar Script SQL Directamente

1. **Acceder a la base de datos PostgreSQL**

   En el Shell de Render:
   ```bash
   python manage.py dbshell
   ```

   O usar las credenciales de la base de datos:
   ```bash
   psql $DATABASE_URL
   ```

2. **Ejecutar el script SQL paso a paso**

   ⚠️ **IMPORTANTE:** Ejecutar cada sección del script SQL en orden:

   a. Primero, verificar los datos:
   ```sql
   SELECT COUNT(*) FROM ventas_cliente WHERE email = 'cliente@aremko.cl';
   ```

   b. Crear respaldo temporal:
   ```sql
   CREATE TEMP TABLE respaldo_emails_duplicados AS
   SELECT id, nombre, email, telefono, created_at
   FROM ventas_cliente
   WHERE email = 'cliente@aremko.cl';
   ```

   c. Ejecutar la actualización:
   ```sql
   BEGIN TRANSACTION;
   UPDATE ventas_cliente SET email = NULL WHERE email = 'cliente@aremko.cl';
   -- Verificar el resultado
   SELECT COUNT(*) FROM ventas_cliente WHERE email = 'cliente@aremko.cl';
   COMMIT; -- Solo si el resultado es 0
   ```

## 🔍 Verificación Post-Ejecución

### Desde Django Shell
```python
from ventas.models import Cliente

# Verificar que no quedan emails duplicados
clientes_con_email_duplicado = Cliente.objects.filter(email='cliente@aremko.cl').count()
print(f"Clientes con email duplicado: {clientes_con_email_duplicado}")  # Debe ser 0

# Ver estadísticas
total_clientes = Cliente.objects.count()
clientes_sin_email = Cliente.objects.filter(email__isnull=True).count()
print(f"Total clientes: {total_clientes}")
print(f"Clientes sin email: {clientes_sin_email}")
```

### Desde SQL
```sql
-- Verificar que no quedan emails duplicados
SELECT COUNT(*) FROM ventas_cliente WHERE email = 'cliente@aremko.cl';

-- Ver estadísticas generales
SELECT
    COUNT(CASE WHEN email IS NULL THEN 1 END) as sin_email,
    COUNT(CASE WHEN email IS NOT NULL THEN 1 END) as con_email,
    COUNT(*) as total
FROM ventas_cliente;
```

## ⚠️ Consideraciones Importantes

1. **Backup**: Render mantiene backups automáticos diarios. Verificar que existe un backup reciente antes de ejecutar.

2. **Horario de Ejecución**: Preferiblemente ejecutar en horario de bajo tráfico.

3. **Transacciones**: Ambos scripts usan transacciones para poder revertir en caso de error.

4. **Validación del Modelo**: El modelo Cliente tiene `email` como campo opcional (`null=True, blank=True`), por lo que es seguro establecerlo a NULL.

5. **Impacto en el Sistema**:
   - No afecta la identificación de clientes (usan teléfono como identificador único)
   - No afecta las reservas existentes
   - Los clientes sin email no recibirán comunicaciones por email

## 📊 Resultado Esperado

Después de ejecutar el script:
- ✅ ~450 clientes tendrán su email establecido a NULL
- ✅ No quedará ningún cliente con el email `cliente@aremko.cl`
- ✅ Los clientes mantendrán todos sus otros datos intactos
- ✅ El sistema continuará funcionando normalmente

## 🆘 Troubleshooting

### Error: "Permission denied"
- Verificar que tienes permisos de escritura en la base de datos
- Contactar al administrador de Render si es necesario

### Error: "Transaction rollback"
- El script revierte automáticamente los cambios si hay un error
- Revisar los logs para identificar el problema
- Intentar nuevamente después de resolver el issue

### El script no encuentra clientes
- Verificar que el email exacto es `cliente@aremko.cl`
- Revisar si ya fue ejecutado anteriormente

## 📝 Logs y Auditoría

El script Python genera un log detallado con:
- Fecha y hora de ejecución
- Cantidad de registros encontrados
- Cantidad de registros actualizados
- Verificación post-actualización

Guardar estos logs para auditoría futura.

## 🔄 Reversión (Si es necesario)

Si necesitas revertir los cambios y tienes el respaldo SQL:
```sql
UPDATE ventas_cliente
SET email = 'cliente@aremko.cl'
WHERE id IN (SELECT id FROM respaldo_emails_duplicados);
```

**Nota:** La tabla temporal solo existe durante la sesión actual de PostgreSQL.

---

**Última actualización:** 2025-12-05
**Autor:** Sistema de Booking Aremko