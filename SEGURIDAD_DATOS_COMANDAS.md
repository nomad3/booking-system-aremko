# 🛡️ Seguridad de Datos - Sistema de Comandas

## ✅ RESUMEN EJECUTIVO

**¿Las tablas actuales se modifican?**
- ❌ **NO**. Ninguna tabla existente se modifica.

**¿Se agregan nuevas tablas?**
- ✅ **SÍ**. Se crean 2 tablas nuevas:
  - `ventas_comanda`
  - `ventas_detallecomanda`

**¿Los datos actuales corren riesgo?**
- ❌ **NO**. Cero riesgo. La migración es 100% aditiva.

---

## 📊 Análisis Detallado de Cambios

### **TABLAS EXISTENTES - Estado: INTACTAS**

| Tabla | ¿Se modifica? | ¿Se elimina? | Impacto |
|-------|---------------|--------------|---------|
| `ventas_producto` | ❌ NO | ❌ NO | Solo se referencia (FK) |
| `ventas_ventareserva` | ❌ NO | ❌ NO | Solo se referencia (FK) |
| `ventas_reservaproducto` | ❌ NO | ❌ NO | No se toca para nada |
| `ventas_cliente` | ❌ NO | ❌ NO | No se toca para nada |
| `ventas_pago` | ❌ NO | ❌ NO | No se toca para nada |
| `auth_user` | ❌ NO | ❌ NO | Solo se referencia (FK) |
| **TODAS LAS DEMÁS** | ❌ NO | ❌ NO | Completamente intactas |

### **TABLAS NUEVAS - Estado: SE CREAN**

| Tabla | Acción | Contenido Inicial |
|-------|--------|-------------------|
| `ventas_comanda` | ✅ CREATE | Vacía (0 registros) |
| `ventas_detallecomanda` | ✅ CREATE | Vacía (0 registros) |

---

## 🔗 Relaciones con Tablas Existentes

### Diagrama de Relaciones

```
┌─────────────────────┐
│  VentaReserva       │ ← EXISTENTE (no se modifica)
│  (tabla actual)     │
└──────────┬──────────┘
           │
           │ FK: venta_reserva_id
           │ ON DELETE: CASCADE
           ↓
┌─────────────────────┐
│  Comanda            │ ← NUEVA (se crea)
│  (tabla nueva)      │
└──────────┬──────────┘
           │
           │ FK: comanda_id
           │ ON DELETE: CASCADE
           ↓
┌─────────────────────┐
│  DetalleComanda     │ ← NUEVA (se crea)
│  (tabla nueva)      │
└──────────┬──────────┘
           │
           │ FK: producto_id
           │ ON DELETE: PROTECT
           ↓
┌─────────────────────┐
│  Producto           │ ← EXISTENTE (no se modifica)
│  (tabla actual)     │
└─────────────────────┘
```

### Comportamiento de Foreign Keys

#### 1. **Comanda → VentaReserva**
```python
venta_reserva = ForeignKey(VentaReserva, on_delete=models.CASCADE)
```
**¿Qué significa?**
- Una Comanda pertenece a una VentaReserva
- Si eliminas una VentaReserva, se eliminan sus Comandas
- **¿Es seguro?** ✅ SÍ. Es el comportamiento lógico esperado.
- **¿Afecta datos actuales?** ❌ NO. Solo afecta a nuevas comandas creadas.

#### 2. **Comanda → Usuario (quien solicita)**
```python
usuario_solicita = ForeignKey(User, on_delete=models.SET_NULL, null=True)
```
**¿Qué significa?**
- Registra qué usuario creó la comanda
- Si eliminas el usuario, el campo queda en `NULL`
- **¿Es seguro?** ✅ SÍ. Mantiene registro histórico.
- **¿Afecta datos actuales?** ❌ NO. Solo referencia usuarios.

#### 3. **Comanda → Usuario (quien procesa)**
```python
usuario_procesa = ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
```
**¿Qué significa?**
- Registra qué usuario procesó la comanda
- Si eliminas el usuario, el campo queda en `NULL`
- **¿Es seguro?** ✅ SÍ. Mantiene registro histórico.
- **¿Afecta datos actuales?** ❌ NO. Solo referencia usuarios.

#### 4. **DetalleComanda → Producto**
```python
producto = ForeignKey(Producto, on_delete=models.PROTECT)
```
**¿Qué significa?**
- Un detalle de comanda referencia un Producto
- **NO permite eliminar un Producto** si tiene comandas asociadas
- **¿Es seguro?** ✅ SÍ. Protege integridad de datos.
- **¿Afecta datos actuales?** ❌ NO. Solo protege productos futuros.

---

## 📝 Contenido de la Migración

### Archivo: `ventas/migrations/0080_comandas_system.py`

```python
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0079_cliente_performance_indexes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ========================================
        # OPERACIÓN 1: Crear tabla Comanda
        # ========================================
        migrations.CreateModel(
            name='Comanda',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('fecha_solicitud', models.DateTimeField(auto_now_add=True)),
                ('hora_solicitud', models.TimeField(auto_now_add=True)),
                ('estado', models.CharField(
                    max_length=20,
                    choices=[
                        ('pendiente', 'Pendiente'),
                        ('procesando', 'En Proceso'),
                        ('entregada', 'Entregada'),
                        ('cancelada', 'Cancelada')
                    ],
                    default='pendiente',
                    db_index=True
                )),
                ('notas_generales', models.TextField(blank=True, null=True)),
                ('fecha_inicio_proceso', models.DateTimeField(blank=True, null=True)),
                ('fecha_entrega', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),

                # Foreign Keys
                ('venta_reserva', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='comandas',
                    to='ventas.ventareserva'
                )),
                ('usuario_solicita', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='comandas_solicitadas',
                    to=settings.AUTH_USER_MODEL
                )),
                ('usuario_procesa', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='comandas_procesadas',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Comanda',
                'verbose_name_plural': 'Comandas',
                'ordering': ['-fecha_solicitud'],
            },
        ),

        # ========================================
        # OPERACIÓN 2: Crear tabla DetalleComanda
        # ========================================
        migrations.CreateModel(
            name='DetalleComanda',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('cantidad', models.PositiveIntegerField(default=1)),
                ('especificaciones', models.TextField(blank=True, null=True)),
                ('precio_unitario', models.DecimalField(decimal_places=0, max_digits=10)),

                # Foreign Keys
                ('comanda', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='detalles',
                    to='ventas.comanda'
                )),
                ('producto', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to='ventas.producto'
                )),
            ],
            options={
                'verbose_name': 'Detalle de Comanda',
                'verbose_name_plural': 'Detalles de Comanda',
                'ordering': ['id'],
            },
        ),

        # ========================================
        # OPERACIÓN 3: Crear índices para performance
        # ========================================
        migrations.AddIndex(
            model_name='comanda',
            index=models.Index(
                fields=['estado', '-fecha_solicitud'],
                name='ventas_coma_estado_fecha_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='comanda',
            index=models.Index(
                fields=['venta_reserva', 'estado'],
                name='ventas_coma_reserva_estado_idx'
            ),
        ),
    ]
```

### ¿Qué hace cada operación?

1. **CreateModel(Comanda)**
   - ✅ Crea tabla nueva `ventas_comanda`
   - ❌ NO modifica ninguna tabla existente
   - ✅ Agrega FKs que SOLO apuntan a tablas existentes (no las modifican)

2. **CreateModel(DetalleComanda)**
   - ✅ Crea tabla nueva `ventas_detallecomanda`
   - ❌ NO modifica ninguna tabla existente
   - ✅ Agrega FKs que SOLO apuntan a tablas existentes

3. **AddIndex**
   - ✅ Crea índices en la tabla nueva `ventas_comanda`
   - ❌ NO modifica ninguna tabla existente
   - ✅ Mejora performance de queries

---

## 🔄 Proceso de Reversión (Si es necesario)

### ¿Cómo deshacer la migración?

Si por alguna razón quisieras deshacer los cambios:

```bash
# Volver a la migración anterior
python manage.py migrate ventas 0079

# Esto:
# ✅ Elimina las 2 tablas nuevas (ventas_comanda, ventas_detallecomanda)
# ✅ Mantiene todas las tablas existentes intactas
# ✅ Elimina los índices creados
```

**¿Se pierden datos?**
- ✅ Solo se pierden las comandas creadas (si las hubiera)
- ❌ NO se pierden datos de VentaReserva, Producto, Cliente, etc.
- ❌ NO se afectan datos de ninguna tabla existente

---

## ✅ Checklist de Seguridad

Antes de ejecutar la migración, verifica:

- [x] ✅ Migración solo hace CREATE (no ALTER ni DROP)
- [x] ✅ No se modifican tablas existentes
- [x] ✅ No se eliminan columnas
- [x] ✅ No se eliminan datos
- [x] ✅ Foreign Keys usan CASCADE/SET_NULL/PROTECT apropiados
- [x] ✅ Se puede revertir con `migrate ventas 0079`
- [x] ✅ Respaldo de BD no es estrictamente necesario (pero recomendado)

---

## 🎯 Recomendaciones de Seguridad

### Antes de ejecutar la migración:

1. **Opcional pero recomendado**: Backup de la BD
   ```bash
   # PostgreSQL
   pg_dump nombre_bd > backup_antes_comandas.sql

   # O usar panel de Render/Railway
   ```

2. **Verificar migración anterior**:
   ```bash
   python manage.py showmigrations ventas
   ```
   Debe mostrar:
   ```
   [X] 0079_cliente_performance_indexes
   [ ] 0080_comandas_system  ← Esta es nueva
   ```

3. **Ejecutar migración**:
   ```bash
   python manage.py migrate ventas 0080
   ```

4. **Verificar que se crearon las tablas**:
   ```bash
   python manage.py dbshell
   \dt ventas_comanda
   \dt ventas_detallecomanda
   ```

### Si algo sale mal:

```bash
# Revertir
python manage.py migrate ventas 0079

# Verificar
python manage.py showmigrations ventas
```

---

## 📊 Comparación: Antes vs Después

### ANTES de la migración:

```
Tablas del sistema:
- ventas_cliente
- ventas_producto
- ventas_ventareserva
- ventas_reservaproducto
- ventas_pago
- ... (todas las demás)

Total: ~40 tablas
```

### DESPUÉS de la migración:

```
Tablas del sistema:
- ventas_cliente               ← Intacta
- ventas_producto              ← Intacta
- ventas_ventareserva          ← Intacta
- ventas_reservaproducto       ← Intacta
- ventas_pago                  ← Intacta
- ... (todas las demás)        ← Intactas
- ventas_comanda               ← NUEVA
- ventas_detallecomanda        ← NUEVA

Total: ~42 tablas (+2 nuevas)
```

---

## 🔐 Garantías de Seguridad

### ✅ Garantizado:

1. **No se pierden datos existentes**
2. **No se modifican estructuras existentes**
3. **Se puede revertir fácilmente**
4. **Foreign Keys protegen integridad**
5. **Migración es idempotente** (se puede ejecutar múltiples veces sin problemas)

### ⚠️ Único escenario de impacto:

**Si en el futuro intentas eliminar un Producto que tiene comandas:**
- Django te dará error: `ProtectedError`
- Esto es **bueno** porque protege la integridad
- Solución: Eliminar primero las comandas o marcar producto como inactivo

---

## 📝 Conclusión

### Respuestas Finales:

**¿Se modifican tablas actuales?**
- ❌ **NO**. Cero modificaciones.

**¿Se agregan nuevas tablas?**
- ✅ **SÍ**. 2 tablas nuevas independientes.

**¿Corren riesgo los datos actuales?**
- ❌ **NO**. Riesgo = 0%.

**¿Es reversible?**
- ✅ **SÍ**. 100% reversible.

**¿Necesito backup?**
- ⚠️ **Opcional**. Recomendado por buenas prácticas, pero no estrictamente necesario.

---

## 🚀 Siguiente Paso

Si estás conforme con el análisis de seguridad, podemos proceder con:

1. ✅ Crear los modelos en `ventas/models.py`
2. ✅ Crear la migración `0080_comandas_system.py`
3. ✅ Ejecutar la migración
4. ✅ Verificar que todo funcionó correctamente

**¿Procedemos?** 😊
