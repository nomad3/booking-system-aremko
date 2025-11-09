# ⚡ Sistema de Cambio Rápido de Estados - Control de Gestión

## 🎯 Objetivo

Permitir a los usuarios cambiar el estado de sus tareas de forma **simple y rápida** sin tener que ir al admin de Django.

---

## 🔄 Flujo Actual vs Nuevo

### ❌ Antes (Lento)
1. Usuario ve tarea en "Mi Día"
2. Click en "Ver Detalles" → Va al admin
3. Cambiar estado en dropdown
4. Guardar
5. Volver a "Mi Día"
**Tiempo: ~30-60 segundos**

### ✅ Ahora (Rápido)
1. Usuario ve tarea en "Mi Día"
2. Click en botón de acción (▶️ Iniciar / ✅ Completar / 🚫 Bloquear)
3. Confirmación rápida
4. Estado cambia instantáneamente
5. Notificación de éxito
**Tiempo: ~2-3 segundos**

---

## 🛠️ Implementación Técnica

### 1. Endpoint AJAX

**URL**: `POST /control_gestion/tarea/<task_id>/cambiar-estado/`

**Request**:
```json
{
  "nuevo_estado": "IN_PROGRESS" | "DONE" | "BLOCKED" | "BACKLOG"
}
```

**Response**:
```json
{
  "ok": true,
  "task_id": 123,
  "estado_anterior": "BACKLOG",
  "nuevo_estado": "IN_PROGRESS",
  "mensaje": "Tarea cambiada a 'En curso'"
}
```

**Código**: `control_gestion/views.py` → `cambiar_estado_tarea()`

### 2. Botones de Acción Rápida

En la vista "Mi Día" (`mi_dia.html`), cada tarea muestra botones según su estado:

#### Estado: BACKLOG
- **▶️ Iniciar** → Cambia a `IN_PROGRESS`

#### Estado: IN_PROGRESS
- **✅ Completar** → Cambia a `DONE`
- **🚫 Bloquear** → Cambia a `BLOCKED`

#### Estado: BLOCKED
- **▶️ Reanudar** → Cambia a `IN_PROGRESS`

### 3. JavaScript (AJAX)

El JavaScript:
1. Escucha clicks en botones `.btn-cambiar-estado`
2. Muestra confirmación
3. Llama al endpoint AJAX
4. Muestra notificación toast (éxito/error)
5. Recarga la página después de 1 segundo

**Ubicación**: `control_gestion/templates/control_gestion/mi_dia.html`

---

## 🔐 Permisos

El endpoint verifica permisos:
- ✅ **Owner**: Puede cambiar sus propias tareas
- ✅ **SUPERVISION**: Puede cambiar cualquier tarea
- ✅ **ADMIN/SUPERUSER**: Puede cambiar cualquier tarea
- ❌ **Otros**: No pueden cambiar tareas ajenas

---

## 📋 Validaciones

1. **WIP=1**: Si intentas iniciar una tarea pero ya tienes una en curso, el signal lanzará `ValidationError`
2. **Permisos**: Solo puedes cambiar tus propias tareas (excepto SUPERVISION/ADMIN)
3. **Estados válidos**: Solo acepta `BACKLOG`, `IN_PROGRESS`, `BLOCKED`, `DONE`

---

## 🎨 UX/UI

### Notificaciones Toast
- **Verde** (success): Estado cambiado exitosamente
- **Rojo** (error): Error al cambiar estado

### Estados de Botón
- **Normal**: Botón clickeable
- **Loading**: "⏳ Procesando..." (deshabilitado)
- **Error**: Restaura texto original

### Feedback Visual
- Botón se deshabilita durante la petición
- Notificación aparece en esquina superior derecha
- Página se recarga automáticamente después de éxito

---

## 🧪 Cómo Probar

### Test Manual

1. Ir a `/control_gestion/mi-dia/`
2. Ver tarea en estado `BACKLOG`
3. Click en **▶️ Iniciar**
4. Confirmar
5. Ver notificación verde: "Tarea cambiada a 'En curso'"
6. Página se recarga → Tarea ahora muestra botones de "Completar" y "Bloquear"

### Test de Permisos

1. Login como usuario normal (no SUPERVISION)
2. Intentar cambiar tarea de otro usuario
3. Debe mostrar error: "No tienes permiso para modificar esta tarea"

### Test de WIP=1

1. Tener una tarea en `IN_PROGRESS`
2. Intentar iniciar otra tarea
3. Debe mostrar error del signal: "WIP=1: Ya tienes una tarea 'En curso'..."

---

## 📊 Logs Automáticos

Cada cambio de estado crea un `TaskLog`:
- **Actor**: Usuario que hizo el cambio
- **Action**: `STATE_CHANGED`
- **Note**: "Estado cambiado de X a Y"

---

## 🚀 Próximos Pasos (Opcional)

### Mejoras Futuras

1. **Actualización sin recargar**: Usar JavaScript para actualizar solo la tarjeta de la tarea
2. **Botones en vista Equipo**: Agregar acciones rápidas también en `/control_gestion/equipo/`
3. **Historial visual**: Mostrar cambios de estado en timeline
4. **Notificaciones push**: Avisar cuando alguien cambia estado de tu tarea
5. **Atajos de teclado**: `C` para completar, `B` para bloquear, etc.

---

## 📝 Notas Técnicas

- **CSRF Token**: Se obtiene automáticamente de las cookies
- **Error Handling**: Todos los errores se muestran en toast
- **Validación**: Se valida tanto en frontend (confirmación) como backend (permisos, WIP=1)
- **Performance**: La petición AJAX es rápida (< 200ms típicamente)

---

**Última actualización**: Noviembre 2025  
**Estado**: ✅ Implementado y funcional

