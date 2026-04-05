# Migración Manual: Sistema de Comandas por WhatsApp

**Fecha:** 2026-04-05
**Commit:** db25103
**Descripción:** Agregar campos para sistema de comandas de clientes vía WhatsApp

---

## ⚠️ IMPORTANTE

Esta migración **DEBE ejecutarse manualmente** desde la shell de Render ya que las migraciones automáticas están deshabilitadas.

---

## 📋 Cambios en la Base de Datos

### Tabla `ventas_producto`
- **Campo nuevo:** `comanda_cliente` (BOOLEAN, DEFAULT FALSE)
- **Campo nuevo:** `orden_comanda` (INTEGER, DEFAULT 0)

### Tabla `ventas_comanda`
- **Actualización:** Campo `estado` ahora permite 4 valores nuevos
- **Campo nuevo:** `token_acceso` (VARCHAR(64), UNIQUE, NULL, INDEX)
- **Campo nuevo:** `creada_por_cliente` (BOOLEAN, DEFAULT FALSE, INDEX)
- **Campo nuevo:** `fecha_vencimiento_link` (TIMESTAMP, NULL)
- **Campo nuevo:** `flow_order_id` (VARCHAR(100), NULL)
- **Campo nuevo:** `flow_token` (VARCHAR(255), NULL)

---

## 🔧 Instrucciones de Ejecución en Render

### Paso 1: Conectar a Shell de Render

```bash
# Desde el dashboard de Render:
# 1. Ir a tu servicio web
# 2. Click en "Shell" en el menú izquierdo
# 3. Ejecutar:
python manage.py shell
```

### Paso 2: Ejecutar Comandos SQL

Una vez en la shell de Python de Django, ejecutar:

```python
from django.db import connection

# Obtener cursor para ejecutar SQL
cursor = connection.cursor()

# ========================================
# TABLA: ventas_producto
# ========================================

print("Agregando campos a ventas_producto...")

# Agregar campo comanda_cliente
cursor.execute("""
    ALTER TABLE ventas_producto
    ADD COLUMN IF NOT EXISTS comanda_cliente BOOLEAN DEFAULT FALSE;
""")

# Agregar campo orden_comanda
cursor.execute("""
    ALTER TABLE ventas_producto
    ADD COLUMN IF NOT EXISTS orden_comanda INTEGER DEFAULT 0;
""")

# Crear índice para búsquedas rápidas
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_producto_comanda_cliente
    ON ventas_producto(comanda_cliente, orden_comanda);
""")

print("✓ Campos agregados a ventas_producto")

# ========================================
# TABLA: ventas_comanda
# ========================================

print("Agregando campos a ventas_comanda...")

# Agregar campo token_acceso
cursor.execute("""
    ALTER TABLE ventas_comanda
    ADD COLUMN IF NOT EXISTS token_acceso VARCHAR(64) UNIQUE NULL;
""")

# Agregar índice para token_acceso
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_comanda_token_acceso
    ON ventas_comanda(token_acceso);
""")

# Agregar campo creada_por_cliente
cursor.execute("""
    ALTER TABLE ventas_comanda
    ADD COLUMN IF NOT EXISTS creada_por_cliente BOOLEAN DEFAULT FALSE;
""")

# Agregar índice para creada_por_cliente
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_comanda_creada_por_cliente
    ON ventas_comanda(creada_por_cliente);
""")

# Agregar campo fecha_vencimiento_link
cursor.execute("""
    ALTER TABLE ventas_comanda
    ADD COLUMN IF NOT EXISTS fecha_vencimiento_link TIMESTAMP NULL;
""")

# Agregar campo flow_order_id
cursor.execute("""
    ALTER TABLE ventas_comanda
    ADD COLUMN IF NOT EXISTS flow_order_id VARCHAR(100) NULL;
""")

# Agregar campo flow_token
cursor.execute("""
    ALTER TABLE ventas_comanda
    ADD COLUMN IF NOT EXISTS flow_token VARCHAR(255) NULL;
""")

print("✓ Campos agregados a ventas_comanda")

# ========================================
# COMMIT
# ========================================

connection.commit()

print("\n" + "="*50)
print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
print("="*50)
print("\nCambios aplicados:")
print("  - ventas_producto: 2 campos nuevos + 1 índice")
print("  - ventas_comanda: 5 campos nuevos + 2 índices")
print("\nNota: Los nuevos estados de Comanda ya están")
print("      definidos en el modelo y no requieren cambios en BD")
print("      (el campo 'estado' ya es VARCHAR con suficiente espacio)")
```

### Paso 3: Salir de la Shell

```python
exit()
```

---

## ✅ Verificación Post-Migración

### Verificar que los campos existen:

```python
from django.db import connection

cursor = connection.cursor()

# Verificar ventas_producto
cursor.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'ventas_producto'
    AND column_name IN ('comanda_cliente', 'orden_comanda');
""")

print("Campos en ventas_producto:")
for row in cursor.fetchall():
    print(f"  - {row[0]}: {row[1]} (nullable: {row[2]}, default: {row[3]})")

# Verificar ventas_comanda
cursor.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'ventas_comanda'
    AND column_name IN ('token_acceso', 'creada_por_cliente', 'fecha_vencimiento_link', 'flow_order_id', 'flow_token');
""")

print("\nCampos en ventas_comanda:")
for row in cursor.fetchall():
    print(f"  - {row[0]}: {row[1]} (nullable: {row[2]}, default: {row[3]})")
```

Si todos los campos aparecen, la migración fue exitosa.

---

## 🔄 Rollback (En caso de error)

Si algo sale mal, ejecutar:

```python
from django.db import connection

cursor = connection.cursor()

# ROLLBACK ventas_producto
cursor.execute("ALTER TABLE ventas_producto DROP COLUMN IF EXISTS comanda_cliente;")
cursor.execute("ALTER TABLE ventas_producto DROP COLUMN IF EXISTS orden_comanda;")
cursor.execute("DROP INDEX IF EXISTS idx_producto_comanda_cliente;")

# ROLLBACK ventas_comanda
cursor.execute("ALTER TABLE ventas_comanda DROP COLUMN IF EXISTS token_acceso;")
cursor.execute("ALTER TABLE ventas_comanda DROP COLUMN IF EXISTS creada_por_cliente;")
cursor.execute("ALTER TABLE ventas_comanda DROP COLUMN IF EXISTS fecha_vencimiento_link;")
cursor.execute("ALTER TABLE ventas_comanda DROP COLUMN IF EXISTS flow_order_id;")
cursor.execute("ALTER TABLE ventas_comanda DROP COLUMN IF EXISTS flow_token;")
cursor.execute("DROP INDEX IF EXISTS idx_comanda_token_acceso;")
cursor.execute("DROP INDEX IF EXISTS idx_comanda_creada_por_cliente;")

connection.commit()

print("✓ Rollback completado")
```

---

## 📝 Notas Adicionales

1. **Estados nuevos:** Los estados `borrador`, `pendiente_pago`, `pago_confirmado` y `pago_fallido` están definidos en el código Python (ESTADO_CHOICES). No requieren cambios en la BD ya que el campo `estado` es VARCHAR(20) con espacio suficiente.

2. **Índices:** Se crearon índices en:
   - `ventas_producto(comanda_cliente, orden_comanda)` - Para búsquedas rápidas de productos disponibles
   - `ventas_comanda(token_acceso)` - Para acceso rápido por token
   - `ventas_comanda(creada_por_cliente)` - Para filtrar comandas de clientes

3. **Valores por defecto:**
   - `comanda_cliente = FALSE` - Los productos existentes NO estarán disponibles por defecto
   - `orden_comanda = 0` - Orden predeterminado
   - `creada_por_cliente = FALSE` - Comandas existentes son del personal

4. **Compatibilidad:** Todos los campos nuevos son NULL o tienen valores por defecto, por lo que no afectarán datos existentes.

---

## 🚀 Siguiente Paso

Después de ejecutar esta migración exitosamente:

1. Reiniciar el servicio en Render (si es necesario)
2. Verificar que no hay errores en los logs
3. Continuar con **Fase 2: Vistas Backend** del plan de implementación

---

**Preparado por:** Claude Code
**Revisado por:** [Tu nombre]
**Ejecutado el:** [Fecha de ejecución]
**Resultado:** [ ] Éxito  [ ] Error  [ ] Rollback
