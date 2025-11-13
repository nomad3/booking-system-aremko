# 🔍 Análisis: Sistema de Responsables de Tareas

**Fecha**: 13 de noviembre, 2025
**Usuario consultante**: Jorge
**Problema**: ¿De dónde vienen los responsables de las tareas? ¿Cómo configurar para asignar a Ernesto en lugar de Jorge?

---

## 📊 Situación Actual

### Tareas Observadas en Screenshot

| ID | Tarea | Área | Responsable Actual | Cola |
|----|-------|------|-------------------|------|
| 179 | Monitoreo ºC 12-22h (cada hora) | Comercial | Jorge | #2 |
| 177 | Preparar servicio – Desayuno (Reserva #3889 - 09:30) | Operación | Jorge | #1 |
| 178 | Preparar servicio – Descuento_Servicios (Reserva #3889 - 09:30) | Operación | Jorge | #1 |
| 180 | Alimentar Animales | Operación | Ernesto | #1 |
| 181 | JUEVES – Mantención Mayor Tinas y Sistemas | Operación | ErnestoRecepcion | #1 |
| 182 | Apertura AM – limpieza y preparación tinas/salas | Operación | ErnestoRecepcion | #1 |

**Observación**: Jorge aparece como responsable de tareas que deberían ser de Operación (177, 178) y la tarea 179 de Comercial.

---

## 🏗️ Arquitectura del Sistema de Asignación

El sistema tiene **3 mecanismos** diferentes para asignar responsables a tareas:

### 1️⃣ Tareas Automáticas por Reservas (Comandos de Django)

#### A) Preparación de Servicios (Tareas 177, 178)
**Archivo**: `control_gestion/management/commands/gen_preparacion_servicios.py`

**Lógica de asignación** (líneas 100-106):
```python
# Obtener usuario de operaciones
ops_user = User.objects.filter(groups__name="OPERACIONES").first()
if not ops_user:
    ops_user = User.objects.first()  # ⚠️ FALLBACK al primer usuario
    self.stdout.write(self.style.WARNING(
        "⚠️  Grupo OPERACIONES no encontrado, usando primer usuario"
    ))
```

**Asignación** (línea 213):
```python
owner=ops_user,
created_by=ops_user,
```

**¿Cuándo se ejecuta?**
- Cron job cada 15 minutos
- Crea tareas **1 hora antes** del inicio del servicio
- Solo para reservas con estado: `pendiente`, `checkin`, `checkout`

#### B) Vaciado de Tinas
**Archivo**: `control_gestion/management/commands/gen_vaciado_tinas.py`

**Misma lógica de asignación**:
```python
ops_user = User.objects.filter(groups__name="OPERACIONES").first()
if not ops_user:
    ops_user = User.objects.first()  # ⚠️ FALLBACK
```

**¿Cuándo se ejecuta?**
- Cron job cada 15 minutos
- Crea tareas de vaciado cuando un servicio termina
- Solo si NO hay otro servicio inmediatamente después

---

### 2️⃣ Tareas Recurrentes (Plantillas - TaskTemplate)

#### Ejemplo: Tareas 180, 181, 182
**Archivo**: `control_gestion/models_templates.py`

**Lógica de asignación** (líneas 385-390):
```python
# Determinar responsable
owner = self.asignar_a_usuario
if not owner and self.asignar_a_grupo:
    owner = User.objects.filter(groups__name=self.asignar_a_grupo).first()
if not owner:
    owner = User.objects.first()  # ⚠️ FALLBACK
```

**Configuración**:
- Cada plantilla tiene 2 campos:
  - `asignar_a_usuario`: Usuario específico (tiene prioridad)
  - `asignar_a_grupo`: Nombre del grupo (ej: "OPERACIONES", "RECEPCION")

**¿Cuándo se ejecuta?**
- Cron job diario
- Genera tareas según frecuencia configurada (diaria, mensual, etc.)

---

### 3️⃣ Tareas Manuales

**Creadas por usuarios** directamente en la interfaz.

---

## 🔑 Grupos de Usuarios

El sistema utiliza **Grupos de Django** para organizar equipos:

### Grupos Requeridos

| Grupo | Área | Responsabilidades |
|-------|------|-------------------|
| `OPERACIONES` | Operación | Preparar servicios, vaciar tinas, rutinas diarias, mantenciones |
| `RECEPCION` | Recepción | Atención clientes, check-in, check-out |
| `COMERCIAL` | Comercial | Ventas, marketing, seguimiento clientes |
| `ATENCION` | Atención Cliente | Soporte, resolver incidencias |
| `SUPERVISION` | Marketing y Supervisión | Supervisión general, auditorías |

---

## 🎯 Diagnóstico del Problema

### ¿Por qué Jorge es responsable de tareas 177, 178, 179?

Hay **3 causas posibles**:

#### Causa 1: Grupo OPERACIONES no existe o está vacío ⚠️
```python
# Si no hay usuarios en grupo OPERACIONES:
ops_user = User.objects.first()  # Toma el primer usuario (probablemente Jorge)
```

#### Causa 2: Jorge es el primer (o único) usuario en grupo OPERACIONES
```python
ops_user = User.objects.filter(groups__name="OPERACIONES").first()
# Si Jorge está en OPERACIONES y es el primero, lo asigna a él
```

#### Causa 3: Las plantillas de tareas recurrentes tienen a Jorge como responsable
- Verificar configuración en Django Admin > Control Gestión > Plantillas de Tareas Recurrentes

---

## ✅ Soluciones

### Solución 1: Verificar y Configurar Grupos (RECOMENDADO)

#### Paso 1: Verificar si existen los grupos

**Opción A: Django Admin**
1. Django Admin → Authentication and Authorization → Groups
2. Buscar grupo "OPERACIONES"
3. Ver usuarios asignados

**Opción B: Django Shell (Render)**
```bash
# En Render Shell
python manage.py shell
```

```python
from django.contrib.auth.models import Group, User

# Verificar grupo OPERACIONES
try:
    ops_group = Group.objects.get(name='OPERACIONES')
    print(f"✅ Grupo OPERACIONES existe")
    print(f"   Usuarios: {list(ops_group.user_set.values_list('username', flat=True))}")
except Group.DoesNotExist:
    print("❌ Grupo OPERACIONES NO existe")

# Verificar todos los grupos
print("\n📋 Grupos existentes:")
for group in Group.objects.all():
    users = list(group.user_set.values_list('username', flat=True))
    print(f"   {group.name}: {users if users else '(vacío)'}")
```

#### Paso 2: Crear grupo OPERACIONES si no existe

```python
from django.contrib.auth.models import Group

# Crear grupo
grupo_ops, created = Group.objects.get_or_create(name='OPERACIONES')
if created:
    print("✅ Grupo OPERACIONES creado")
else:
    print("ℹ️  Grupo OPERACIONES ya existía")
```

#### Paso 3: Agregar Ernesto al grupo OPERACIONES

**Opción A: Django Admin**
1. Django Admin → Users → Buscar "Ernesto"
2. Editar usuario
3. En sección "Groups":
   - Seleccionar "OPERACIONES"
   - Click en flecha → para agregarlo
4. Guardar

**Opción B: Django Shell**
```python
from django.contrib.auth.models import Group, User

# Obtener usuario y grupo
ernesto = User.objects.get(username='Ernesto')  # Ajustar username exacto
ops_group = Group.objects.get(name='OPERACIONES')

# Agregar Ernesto al grupo
ernesto.groups.add(ops_group)
print(f"✅ {ernesto.username} agregado a grupo OPERACIONES")

# Verificar
print(f"   Grupos de {ernesto.username}: {list(ernesto.groups.values_list('name', flat=True))}")
```

#### Paso 4: (Opcional) Remover Jorge de grupo OPERACIONES

**Solo si Jorge NO debería estar en Operaciones:**

```python
from django.contrib.auth.models import Group, User

jorge = User.objects.get(username='Jorge')  # Ajustar username exacto
ops_group = Group.objects.get(name='OPERACIONES')

jorge.groups.remove(ops_group)
print(f"✅ {jorge.username} removido de grupo OPERACIONES")
```

---

### Solución 2: Configurar Plantillas de Tareas

Para tareas recurrentes (como "Monitoreo ºC 12-22h"):

#### Paso 1: Identificar la plantilla en Django Admin

1. Django Admin → Control Gestión → Plantillas de Tareas Recurrentes
2. Buscar plantilla "Monitoreo ºC 12-22h"

#### Paso 2: Cambiar asignación

**Opción A: Asignar a grupo**
- Campo "Asignar a grupo": `OPERACIONES` (o `COMERCIAL`)
- Dejar campo "Asignar a usuario específico" vacío

**Opción B: Asignar a usuario específico**
- Campo "Asignar a usuario específico": Seleccionar "Ernesto"
- Esto ignora el grupo

#### Paso 3: Guardar cambios

Las nuevas tareas generadas usarán la nueva configuración.

---

### Solución 3: Reasignar Tareas Existentes

Para tareas que YA están creadas (177, 178, 179):

#### Opción A: Cambiar desde interfaz web

1. Control Gestión → Vista de tareas
2. Editar tarea
3. Cambiar responsable a Ernesto

#### Opción B: Cambiar masivamente en Django Shell

```python
from control_gestion.models import Task
from django.contrib.auth.models import User

# Obtener usuarios
ernesto = User.objects.get(username='Ernesto')
jorge = User.objects.get(username='Jorge')

# Reasignar todas las tareas de Jorge en swimlane OPERACION a Ernesto
tareas_operacion = Task.objects.filter(
    owner=jorge,
    swimlane='OPS'
)

print(f"📋 Tareas de Jorge en Operación: {tareas_operacion.count()}")

# Reasignar
tareas_operacion.update(owner=ernesto)
print(f"✅ Reasignadas {tareas_operacion.count()} tareas a Ernesto")
```

---

## 🧪 Verificación

### Script completo de diagnóstico

```python
# En Render Shell: python manage.py shell

from django.contrib.auth.models import Group, User
from control_gestion.models import Task
from django.db.models import Count

print("=" * 80)
print("🔍 DIAGNÓSTICO DE RESPONSABLES DE TAREAS")
print("=" * 80)

# 1. Grupos existentes
print("\n📋 GRUPOS EXISTENTES:")
for group in Group.objects.all():
    users = list(group.user_set.values_list('username', flat=True))
    print(f"   {group.name}: {users if users else '(vacío)'}")

# 2. Verificar grupo OPERACIONES
print("\n🔍 VERIFICAR GRUPO OPERACIONES:")
try:
    ops_group = Group.objects.get(name='OPERACIONES')
    ops_users = list(ops_group.user_set.values_list('username', flat=True))
    print(f"   ✅ Grupo existe")
    print(f"   👥 Usuarios: {ops_users if ops_users else '(vacío - PROBLEMA!)'}")

    if ops_users:
        first_user = User.objects.filter(groups__name="OPERACIONES").first()
        print(f"   ⭐ Primer usuario (usado para asignar tareas): {first_user.username}")
except Group.DoesNotExist:
    print("   ❌ Grupo OPERACIONES NO EXISTE (PROBLEMA!)")
    first_user = User.objects.first()
    print(f"   ⚠️  Se usará primer usuario del sistema: {first_user.username}")

# 3. Tareas por responsable y área
print("\n📊 TAREAS POR RESPONSABLE Y ÁREA:")
tareas_por_owner = Task.objects.filter(state='BACKLOG').values(
    'owner__username', 'swimlane'
).annotate(
    total=Count('id')
).order_by('owner__username', 'swimlane')

for item in tareas_por_owner:
    print(f"   {item['owner__username']} ({item['swimlane']}): {item['total']} tareas")

# 4. Resumen
print("\n" + "=" * 80)
print("💡 RECOMENDACIONES:")
if not Group.objects.filter(name='OPERACIONES').exists():
    print("   1. ⚠️  CREAR grupo OPERACIONES")
    print("   2. Agregar Ernesto al grupo OPERACIONES")
else:
    ops_group = Group.objects.get(name='OPERACIONES')
    if ops_group.user_set.count() == 0:
        print("   1. ⚠️  AGREGAR usuarios al grupo OPERACIONES (está vacío)")
    else:
        print("   1. ✅ Grupo OPERACIONES configurado correctamente")

print("   2. Verificar plantillas de tareas en Django Admin")
print("   3. Reasignar tareas existentes si es necesario")
print("=" * 80)
```

---

## 📋 Checklist de Configuración

### ✅ Para que Ernesto sea el responsable de tareas de Operación:

- [ ] **Paso 1**: Verificar que grupo OPERACIONES existe
- [ ] **Paso 2**: Agregar Ernesto al grupo OPERACIONES
- [ ] **Paso 3**: (Opcional) Remover Jorge del grupo OPERACIONES si no debería estar
- [ ] **Paso 4**: Verificar plantillas de tareas recurrentes en Django Admin
- [ ] **Paso 5**: Reasignar tareas existentes pendientes (Backlog)
- [ ] **Paso 6**: Esperar a que se generen nuevas tareas automáticamente con cron
- [ ] **Paso 7**: Verificar en interfaz que nuevas tareas se asignan correctamente

---

## 🔄 Flujo de Asignación Automática

```
┌─────────────────────────────────────────────────────────────────┐
│                     CRON JOB (cada 15 min)                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
         ┌──────▼──────┐              ┌──────▼──────┐
         │ Preparación │              │   Vaciado   │
         │  Servicios  │              │    Tinas    │
         └──────┬──────┘              └──────┬──────┘
                │                             │
                └──────────────┬──────────────┘
                               │
                ┌──────────────▼──────────────┐
                │ ¿Grupo OPERACIONES existe?  │
                └──────────────┬──────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
             ┌──────▼──────┐      ┌──────▼──────┐
             │     SÍ      │      │     NO      │
             └──────┬──────┘      └──────┬──────┘
                    │                     │
        ┌───────────▼───────────┐  ┌─────▼─────────┐
        │ Asignar al PRIMER     │  │ Asignar al    │
        │ usuario del grupo     │  │ PRIMER usuario│
        │ OPERACIONES           │  │ del sistema   │
        └───────────┬───────────┘  └─────┬─────────┘
                    │                     │
                    └──────────┬──────────┘
                               │
                     ┌─────────▼─────────┐
                     │  Crear Task con:  │
                     │  owner=ops_user   │
                     │  swimlane=OPS     │
                     └───────────────────┘
```

---

## 📖 Documentación Relacionada

- `docs/SOLUCION_TAREAS_NO_SE_GENERAN.md` - Troubleshooting de tareas
- `docs/CREAR_USUARIOS_GRUPOS.md` - Guía de creación de grupos
- `control_gestion/models.py` - Modelo Task
- `control_gestion/models_templates.py` - Modelo TaskTemplate

---

## 🎯 Resumen Ejecutivo

### Problema
Jorge aparece como responsable de tareas que deberían ser de Ernesto (operación).

### Causa Raíz
Sistema asigna al **primer usuario** del grupo OPERACIONES. Puede ser que:
1. Grupo OPERACIONES no existe → usa primer usuario del sistema (Jorge)
2. Jorge es el primer usuario en grupo OPERACIONES
3. Plantillas configuradas con Jorge como responsable

### Solución
1. Crear/verificar grupo OPERACIONES
2. Agregar Ernesto al grupo OPERACIONES
3. Asegurarse que Ernesto sea el primer usuario del grupo (o remover a Jorge)
4. Verificar plantillas de tareas en Django Admin
5. Reasignar tareas pendientes existentes

### Tiempo Estimado
10-15 minutos en Django Admin o Shell

---

**📅 Fecha de análisis**: 13 de noviembre, 2025
**🤖 Generado con**: Claude Code
https://claude.com/claude-code
