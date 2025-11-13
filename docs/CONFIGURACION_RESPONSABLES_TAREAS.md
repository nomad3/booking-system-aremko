# 🎛️ Sistema de Configuración de Responsables para Tareas Automáticas

**Fecha**: 13 de noviembre, 2025
**Versión**: 2.0
**Estado**: ✅ Implementado

---

## 🎯 Objetivo

**Problema anterior**: Los responsables de las tareas automáticas estaban hardcodeados en el código Python, requiriendo modificar código fuente para cambiar asignaciones.

**Solución**: Sistema de configuración centralizado en Django Admin que permite configurar responsables sin tocar código.

---

## 🏗️ Arquitectura

### Nuevo Modelo: `TaskOwnerConfig`

Ubicación: `control_gestion/models.py` (líneas 365-521)

**Propósito**: Configurar desde Django Admin quién debe ser responsable de cada tipo de tarea generada automáticamente.

### Tipos de Tareas Configurables

| Tipo | Descripción | Comando que lo usa |
|------|-------------|-------------------|
| `preparacion_servicio` | Preparación de Servicio (1h antes) | `gen_preparacion_servicios.py` |
| `vaciado_tina` | Vaciado de Tina (después del servicio) | `gen_vaciado_tinas.py` |
| `apertura_am` | Apertura AM - Limpieza | `gen_daily_opening.py` |
| `reporte_diario` | Reporte Diario | `gen_daily_reports.py` |
| `monitoreo` | Monitoreo General | *(futuro)* |
| `mantencion` | Mantención y Reparaciones | *(futuro)* |
| `alimentacion` | Alimentación de Animales | *(futuro)* |
| `otros` | Otros (por defecto) | *(cualquier comando)* |

---

## ⚙️ Cómo Funciona

### Lógica de Asignación (Prioridad)

```
1. Usuario específico (si está configurado)
     ↓ si no existe
2. Primer usuario del grupo (si está configurado)
     ↓ si no existe o grupo vacío
3. Usuario fallback (si está configurado)
     ↓ si no existe
4. Primer usuario del sistema (último recurso)
```

### Ejemplo de Uso en Código

**Antes (hardcodeado)**:
```python
# gen_preparacion_servicios.py (líneas 100-106)
ops_user = User.objects.filter(groups__name="OPERACIONES").first()
if not ops_user:
    ops_user = User.objects.first()
```

**Después (configurable)**:
```python
# gen_preparacion_servicios.py (líneas 100-119)
from control_gestion.models import TaskOwnerConfig

ops_user = TaskOwnerConfig.obtener_responsable_por_tipo('preparacion_servicio')
if not ops_user:
    # Fallback al comportamiento anterior
    ops_user = User.objects.filter(groups__name="OPERACIONES").first()
    if not ops_user:
        ops_user = User.objects.first()
```

---

## 📖 Guía de Uso

### Configuración Inicial (Django Admin)

#### Paso 1: Acceder a la Configuración

1. Django Admin → **Control Gestión** → **Configuraciones de Responsables**
2. Click en **"Agregar Configuración de Responsable"**

#### Paso 2: Configurar Preparación de Servicios

**Escenario**: Asignar tareas de "Preparación de Servicio" a Ernesto

1. **Tipo de Tarea**: Seleccionar `Preparación de Servicio (1h antes)`
2. **Asignar a Usuario**: Seleccionar `Ernesto`
3. **Asignar a Grupo**: (dejar vacío o poner `OPERACIONES` como respaldo)
4. **Usuario Fallback**: (opcional) Seleccionar usuario alternativo
5. **Activo**: ✅ Marcado
6. **Notas**: "Ernesto es el encargado de operaciones"
7. Click en **"Guardar"**

**Resultado**: Django Admin mostrará:
```
✅ Configuración guardada. Responsable será: Ernesto
```

#### Paso 3: Configurar Vaciado de Tinas

**Escenario**: Asignar a grupo OPERACIONES (primer usuario del grupo)

1. **Tipo de Tarea**: Seleccionar `Vaciado de Tina (después del servicio)`
2. **Asignar a Usuario**: (dejar vacío)
3. **Asignar a Grupo**: Escribir `OPERACIONES`
4. **Usuario Fallback**: Seleccionar `Ernesto`
5. **Activo**: ✅ Marcado
6. **Notas**: "Usa primer usuario disponible del grupo OPERACIONES"
7. Click en **"Guardar"**

---

### Verificar Configuración

#### Opción 1: Acción de Admin "Probar asignación"

1. Django Admin → Control Gestión → Configuraciones de Responsables
2. Seleccionar configuraciones a probar
3. En menú "Acción" → Seleccionar **"🧪 Probar asignación de responsable"**
4. Click en **"Ir"**

**Resultado**:
```
✅ Preparación de Servicio (1h antes): Ernesto (Ernesto Pérez)
✅ Vaciado de Tina (después del servicio): Ernesto (Ernesto Pérez)
```

#### Opción 2: Ejecutar Comando con Dry-Run

```bash
# En Render Shell
python manage.py gen_preparacion_servicios --dry-run
```

**Output esperado**:
```
✅ Usando responsable configurado: Ernesto
```

---

## 🎨 Interfaz de Django Admin

### Vista de Lista

| Tipo de Tarea | Asignado a | Activo | Última actualización |
|---------------|------------|--------|----------------------|
| Preparación de Servicio (1h antes) | 👤 Ernesto | ✅ | 13/11/2025 14:30 |
| Vaciado de Tina (después del servicio) | 👥 OPERACIONES (2 usuarios) | ✅ | 13/11/2025 14:35 |
| Apertura AM - Limpieza | ❌ Sin configurar | ❌ | - |

### Formulario de Edición

```
┌─────────────────────────────────────────────────────────────┐
│ TIPO DE TAREA                                               │
├─────────────────────────────────────────────────────────────┤
│ Tipo de tarea: [Preparación de Servicio (1h antes)     ▼]  │
│                                                             │
│ ASIGNACIÓN DEL RESPONSABLE                                  │
├─────────────────────────────────────────────────────────────┤
│ Prioridad de asignación:                                    │
│ 1. Usuario específico (si está configurado)                │
│ 2. Primer usuario del grupo (si está configurado)          │
│ 3. Usuario fallback (si está configurado)                  │
│ 4. Primer usuario del sistema (último recurso)             │
│                                                             │
│ Asignar a Usuario: [Ernesto                            ▼]  │
│ Asignar a Grupo:   [OPERACIONES                           ] │
│ Usuario Fallback:  [Jorge                              ▼]  │
│                                                             │
│ CONFIGURACIÓN                                               │
├─────────────────────────────────────────────────────────────┤
│ ☑ Activo                                                    │
│                                                             │
│ Notas: ┌─────────────────────────────────────────────┐     │
│        │ Ernesto es el responsable principal de     │     │
│        │ preparar servicios. Jorge es backup.       │     │
│        └─────────────────────────────────────────────┘     │
│                                                             │
│ [Guardar y continuar editando] [Guardar] [Eliminar]       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flujo de Asignación

```
┌──────────────────────────────────────────────────────────────┐
│         CRON JOB EJECUTA COMANDO                             │
│   (gen_preparacion_servicios, gen_vaciado_tinas, etc.)     │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  TaskOwnerConfig.obtener_responsable_por_tipo('tipo')       │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────┴──────────┐
         │  ¿Existe config?     │
         └───────────┬──────────┘
                     │
         ┌───────────┴──────────┐
         │                      │
    ┌────▼────┐           ┌────▼────┐
    │   SÍ    │           │   NO    │
    └────┬────┘           └────┬────┘
         │                     │
         ▼                     ▼
┌────────────────┐    ┌────────────────┐
│ obtener_       │    │ FALLBACK:      │
│ responsable()  │    │ Grupo          │
└────────┬───────┘    │ OPERACIONES    │
         │            └────────┬───────┘
         │                     │
         └─────────┬───────────┘
                   │
                   ▼
        ┌──────────────────┐
        │ Asignar usuario  │
        │ a nueva tarea    │
        └──────────────────┘
```

---

## 🧪 Casos de Uso

### Caso 1: Cambiar Responsable de Preparación a Ernesto

**Situación**: Jorge está asignado pero debería ser Ernesto

**Solución**:
1. Django Admin → Configuraciones de Responsables
2. Click en "Preparación de Servicio"
3. Cambiar "Asignar a Usuario" de `Jorge` a `Ernesto`
4. Guardar

**Resultado**: A partir de la próxima ejecución del cron (15 minutos), las nuevas tareas se asignan a Ernesto.

**Nota**: Las tareas YA creadas mantienen su responsable anterior. Para cambiarlas:
- Opción A: Editarlas manualmente en Django Admin
- Opción B: Usar script de reasignación masiva (ver documentación anterior)

### Caso 2: Usar Grupo como Responsable

**Situación**: Quiero que el sistema elija automáticamente del grupo OPERACIONES

**Solución**:
1. Django Admin → Configuraciones de Responsables
2. Tipo: "Vaciado de Tina"
3. **Dejar vacío** "Asignar a Usuario"
4. "Asignar a Grupo": `OPERACIONES`
5. "Usuario Fallback": Seleccionar backup
6. Guardar

**Resultado**: Sistema asignará al **primer usuario** del grupo OPERACIONES.

### Caso 3: Respaldo por Si Falla

**Situación**: Configurar plan B si el responsable principal no está disponible

**Solución**:
1. "Asignar a Usuario": `Ernesto` (prioridad 1)
2. "Asignar a Grupo": `OPERACIONES` (prioridad 2, si Ernesto no existe)
3. "Usuario Fallback": `Jorge` (prioridad 3, último recurso)

**Resultado**: Sistema intentará en orden:
1. Ernesto → Si no existe/fue eliminado
2. Primer usuario de OPERACIONES → Si grupo vacío
3. Jorge (fallback) → Si todo falla
4. Primer usuario del sistema

### Caso 4: Desactivar Configuración Temporalmente

**Situación**: Quiero volver al comportamiento por defecto sin eliminar la configuración

**Solución**:
1. Django Admin → Editar configuración
2. Desmarcar **"Activo"**
3. Guardar

**Resultado**: Sistema usa fallback (grupo OPERACIONES) hasta reactivar.

---

## 📊 Beneficios del Nuevo Sistema

### ✅ Antes vs Después

| Aspecto | Antes (Hardcodeado) | Después (Configurable) |
|---------|---------------------|------------------------|
| **Cambiar responsable** | Modificar código Python + redeploy | Click en Django Admin (30 seg) |
| **Ver asignaciones** | Leer código fuente | Vista de lista en Admin |
| **Probar configuración** | Ejecutar comando manualmente | Botón "Probar asignación" |
| **Usuario sin permisos de código** | Imposible cambiar | Admin puede configurar |
| **Documentación** | En comentarios de código | En campo "Notas" |
| **Fallback** | Hardcodeado una sola vez | 3 niveles configurables |
| **Auditoría** | No hay registro | Fechas created_at/updated_at |

---

## 🛠️ Comandos Actualizados

### Comandos que YA usan TaskOwnerConfig

✅ **gen_preparacion_servicios.py** - Preparación de Servicios
- Tipo: `preparacion_servicio`
- Líneas: 100-119

✅ **gen_vaciado_tinas.py** - Vaciado de Tinas
- Tipo: `vaciado_tina`
- Líneas: 82-101

### Comandos que AÚN no usan TaskOwnerConfig

Estos comandos todavía usan el método anterior (grupo hardcodeado):

⏳ **gen_daily_opening.py** - Apertura AM
- Tipo disponible: `apertura_am`
- Requiere actualización

⏳ **gen_daily_reports.py** - Reportes Diarios
- Tipo disponible: `reporte_diario`
- Requiere actualización

---

## 🔧 Migración a Producción

### Paso 1: Crear Migración

```bash
# En Render Shell
python manage.py makemigrations control_gestion
python manage.py migrate
```

**Salida esperada**:
```
Migrations for 'control_gestion':
  control_gestion/migrations/0XXX_add_task_owner_config.py
    - Create model TaskOwnerConfig
```

### Paso 2: Crear Configuraciones Iniciales

**Opción A: Django Admin** (Recomendado)
1. Crear configuración para "Preparación de Servicio"
2. Crear configuración para "Vaciado de Tina"

**Opción B: Django Shell**
```python
from control_gestion.models import TaskOwnerConfig
from django.contrib.auth.models import User

# Obtener Ernesto
ernesto = User.objects.get(username='Ernesto')

# Configurar preparación de servicios
TaskOwnerConfig.objects.create(
    tipo_tarea='preparacion_servicio',
    asignar_a_usuario=ernesto,
    asignar_a_grupo='OPERACIONES',
    activo=True,
    notas='Ernesto responsable principal de preparación'
)

# Configurar vaciado de tinas
TaskOwnerConfig.objects.create(
    tipo_tarea='vaciado_tina',
    asignar_a_grupo='OPERACIONES',
    usuario_fallback=ernesto,
    activo=True,
    notas='Usar grupo OPERACIONES, Ernesto como backup'
)

print("✅ Configuraciones creadas")
```

### Paso 3: Verificar

```bash
python manage.py gen_preparacion_servicios --dry-run
```

**Salida esperada**:
```
✅ Usando responsable configurado: Ernesto
```

---

## 🎓 API del Modelo

### Métodos Principales

#### `obtener_responsable()`
Obtiene el usuario responsable según la configuración del objeto.

```python
config = TaskOwnerConfig.objects.get(tipo_tarea='preparacion_servicio')
responsable = config.obtener_responsable()
print(responsable.username)  # Output: Ernesto
```

#### `obtener_responsable_por_tipo(tipo_tarea)` (Método de Clase)
Obtiene el responsable directamente por tipo de tarea.

```python
from control_gestion.models import TaskOwnerConfig

# Uso típico en comandos
responsable = TaskOwnerConfig.obtener_responsable_por_tipo('preparacion_servicio')
if not responsable:
    responsable = User.objects.first()  # Fallback manual
```

#### `get_asignado_display()`
Retorna string legible de la asignación.

```python
config.get_asignado_display()
# Output: "Ernesto (usuario)"
# o: "OPERACIONES (grupo)"
# o: "Jorge (fallback)"
```

---

## 📝 Mejores Prácticas

### ✅ DO

1. **Siempre configurar usuario fallback** para tareas críticas
2. **Usar grupos** para asignaciones que rotan entre varios usuarios
3. **Documentar en campo "Notas"** el razonamiento de la configuración
4. **Probar asignación** antes de activar (botón "Probar asignación")
5. **Mantener activo=True** para configuraciones en uso

### ❌ DON'T

1. **No eliminar** configuraciones, solo desactívalas
2. **No configurar usuario que no existe** (validar primero)
3. **No dejar todos los campos vacíos** (al menos grupo o fallback)
4. **No olvidar migrar** después de deploy

---

## 🔮 Futuras Mejoras

### Planeadas

- [ ] **Interfaz visual de asignaciones** en dashboard de control de gestión
- [ ] **Notificaciones** cuando falla la asignación
- [ ] **Rotación automática** entre usuarios de un grupo (round-robin)
- [ ] **Asignación por horario** (ej: turno mañana vs tarde)
- [ ] **Histórico de cambios** (auditoría de quién cambió qué)

### Ideas

- **Asignación inteligente** basada en carga de trabajo actual
- **Sugerencias de IA** para asignaciones óptimas
- **Webhooks** para notificar cambios de configuración

---

## 📖 Documentación Relacionada

- `docs/ANALISIS_RESPONSABLES_TAREAS.md` - Análisis del sistema anterior
- `control_gestion/models.py` - Modelo TaskOwnerConfig (líneas 365-521)
- `control_gestion/admin.py` - Admin de TaskOwnerConfig (líneas 574-683)

---

## 🎯 Resumen Ejecutivo

### Problema Resuelto
Cambiar responsables de tareas automáticas requería modificar código y hacer redeploy.

### Solución Implementada
Sistema de configuración en Django Admin que permite cambiar asignaciones con 3 clicks.

### Beneficios
- ✅ Sin tocar código
- ✅ Cambios instantáneos
- ✅ 3 niveles de fallback
- ✅ Interfaz intuitiva
- ✅ Prueba antes de activar
- ✅ Auditoría automática

### Próximos Pasos
1. Crear migración en producción
2. Configurar "Preparación de Servicio" → Ernesto
3. Configurar "Vaciado de Tina" → Grupo OPERACIONES
4. Verificar que funciona correctamente

---

**📅 Fecha de implementación**: 13 de noviembre, 2025
**🤖 Generado con**: Claude Code
https://claude.com/claude-code
