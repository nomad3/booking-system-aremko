# 📝 Próximos Pasos - Etapa 1: Control de Gestión

## ✅ Completado Hasta Ahora

- [x] **1.1 Crear app y estructura** ✅
  - App `control_gestion` creada
  - Estructura de carpetas completa
  - Agregada a INSTALLED_APPS
  - URLs configuradas

- [x] **1.2 Modelos creados** ✅
  - `Task` (tarea operativa)
  - `ChecklistItem` (checklist items)
  - `TaskLog` (logs de acciones)
  - `CustomerSegment` (segmentos de clientes)
  - `DailyReport` (reportes diarios)

**Commit realizado**: `adb1673`

---

## 🚀 Próximos Comandos a Ejecutar (En Tu Terminal)

### Paso 1.3: Generar y Aplicar Migraciones

```bash
# Asegúrate de estar en el directorio del proyecto
cd /Users/jorgeaguilera/Documents/GitHub/booking-system-aremko

# Activar tu entorno virtual si lo usas
source venv_import/bin/activate  # O el que uses

# Generar migraciones
python manage.py makemigrations control_gestion

# Verificar que NO se generaron migraciones en ventas
# Debería decir algo como:
# Migrations for 'control_gestion':
#   control_gestion/migrations/0001_initial.py
#     - Create model Task
#     - Create model ChecklistItem
#     ... etc

# Aplicar migraciones
python manage.py migrate control_gestion

# Verificar tablas creadas
python manage.py dbshell
\dt control_gestion*  # PostgreSQL
# O .tables si es SQLite

# Salir del dbshell
\q  # PostgreSQL
.exit  # SQLite
```

### ✅ Checkpoint 1.3: Validar Migraciones

Deberías ver algo como:

```
Migrations for 'control_gestion':
  control_gestion/migrations/0001_initial.py
    - Create model CustomerSegment
    - Create model DailyReport
    - Create model Task
    - Create model TaskLog
    - Create model ChecklistItem
    - Add index control_gestion_task_swimlane_queue_idx on fields swimlane, queue_position of model task
    - Add index control_gestion_task_owner_state_idx on fields owner, state of model task
    - Add index control_gestion_task_state_promise_idx on fields state, promise_due_at of model task
```

**IMPORTANTE**: Verifica que **NO** se hayan generado migraciones en `ventas/migrations/`. Si aparecen, házmelo saber.

### Qué hacer después de ejecutar estos comandos:

1. **Si todo sale bien**:
   - Copia el output de los comandos
   - Pégalo aquí y dime "migraciones ok"
   - Continuaré con el paso 1.4 (Admin con inlines y acciones)

2. **Si hay errores**:
   - Copia el mensaje de error completo
   - Pégalo aquí y lo resolveremos juntos

---

## 📊 Estado Actual del Plan

### Etapa 1 - MVP en Admin (3 días)

- [x] **1.1** Crear app y estructura base ✅
- [x] **1.2** Crear modelos ✅
- [ ] **1.3** Generar y aplicar migraciones ⬅️ **ESTÁS AQUÍ**
- [ ] **1.4** Crear admin con inlines
- [ ] **1.5** Implementar signals (WIP=1)
- [ ] **1.6** Tests básicos
- [ ] **1.7** Fixtures y datos semilla

---

## 🎯 Resumen de lo Creado

### Archivos Nuevos:

```
control_gestion/
├── __init__.py                     ✅ Config de app
├── apps.py                         ✅ AppConfig con import de signals
├── models.py                       ✅ 5 modelos completos
├── admin.py                        ✅ Básico (se expandirá)
├── views.py                        ✅ Placeholder
├── urls.py                         ✅ URLs (se expandirán)
├── signals.py                      ✅ Placeholder
├── management/
│   ├── __init__.py
│   └── commands/
│       └── __init__.py
└── tests/
    └── __init__.py
```

### Archivos Modificados:

- `aremko_project/settings.py`: Agregado `control_gestion` a INSTALLED_APPS
- `aremko_project/urls.py`: Agregado `path('control_gestion/', include('control_gestion.urls'))`

### Características de los Modelos:

✅ **Task**:
- Sin ForeignKey a `ventas` (usa CharField para `reservation_id`)
- Campos: swimlane, owner, state, priority, queue_position
- Contexto: reservation_id, customer_phone_last9, segment_tag
- Ubicación: location_ref, service_type
- Timestamps: created_at, updated_at, promise_due_at

✅ **ChecklistItem**:
- Relación con Task
- Campos: text, done

✅ **TaskLog**:
- Histórico de acciones sobre Task
- Campos: when, actor, action, note

✅ **CustomerSegment**:
- Definición de segmentos
- Campos: name, min_spend, max_spend, benefit

✅ **DailyReport**:
- Reportes generados por IA
- Campos: date, generated_at, summary

---

## ⚠️ Puntos de Validación

Antes de continuar, asegúrate de:

1. ✅ Migraciones solo en `control_gestion` (NO en `ventas`)
2. ✅ Tablas creadas en la base de datos
3. ✅ Sin errores en la consola
4. ✅ Admin accesible (aunque básico)

---

**Última actualización**: 7 de noviembre, 2025  
**Rama**: `feature/control-gestion`  
**Commit**: `adb1673`

