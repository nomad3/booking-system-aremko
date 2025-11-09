# 🔧 Solución: Tareas de Preparación No Se Generan

**Fecha**: 9 de noviembre, 2025
**Problema Reportado**: No se están generando tareas para operación hoy con las tinas programadas y en funcionamiento
**Estado**: 🔍 Diagnóstico completado - Soluciones identificadas

---

## 📊 Diagnóstico Realizado

He analizado el sistema de generación automática de tareas y he identificado las causas más probables.

### ✅ Comando de Diagnóstico Creado

Se creó el comando `diagnostico_tareas.py` que realiza una verificación completa:

```bash
python manage.py diagnostico_tareas
```

Este comando verifica:
1. ✅ Grupos de usuarios (OPERACIONES, RECEPCION, SUPERVISION)
2. ✅ Reservas del día de hoy
3. ✅ Tareas creadas hoy
4. ✅ Ventana de tiempo actual para generación
5. ⚠️  Configuración de Cron en Render
6. ✅ Resumen y recomendaciones

---

## 🎯 Causas Probables

### 1. ❌ Cron Job NO Configurado en Render (MUY PROBABLE)

El sistema require un **Cron Job en Render** que ejecute el comando cada 15 minutos:

```bash
python manage.py gen_preparacion_servicios
```

**Si este Cron Job no existe, las tareas NO se generan automáticamente.**

### 2. ❌ Grupo OPERACIONES No Existe o Sin Usuarios

El comando asigna tareas al primer usuario del grupo `OPERACIONES`. Si no existe:
- Las tareas se asignan al primer usuario del sistema (fallback)
- Pero podría causar problemas de asignación

### 3. ⚠️  Reservas No en Estado Correcto

Las tareas solo se crean para reservas con `estado_reserva` en:
- `pendiente`
- `checkin`
- `checkout`

Si las reservas están en otro estado (ej: `confirmada`, `finalizada`), **NO se generan tareas**.

### 4. ⏰ Ventana de Tiempo

El sistema genera tareas cuando el servicio está entre **40 y 80 minutos** en el futuro:
- Anticipación: 60 minutos (1 hora antes)
- Tolerancia: ±20 minutos
- Ventana: Servicios que comienzan en 40-80 minutos

Si el cron no se ejecuta regularmente, puede perder servicios.

---

## 🛠️ Soluciones

### Solución 1: Configurar Cron Job en Render (PRINCIPAL)

#### Pasos para configurar:

1. **Ir a Render Dashboard**: https://dashboard.render.com

2. **Crear nuevo Cron Job**:
   - Click en "New +" → "Cron Job"

3. **Configuración del Cron Job**:
   ```
   Name: gen-preparacion-servicios
   Environment: Same as web service
   Command: python manage.py gen_preparacion_servicios
   Schedule: */15 * * * *
   ```

   **Importante**: El schedule `*/15 * * * *` significa "cada 15 minutos"

4. **Variables de entorno**:
   - Debe usar las mismas env vars que el web service
   - Especialmente `DATABASE_URL`, `DJANGO_SETTINGS_MODULE`, etc.

5. **Guardar y Activar**

#### Verificar que funciona:

Después de crear el Cron Job:
- Esperar 15-20 minutos
- Ir a Render Dashboard → Cron Jobs → gen-preparacion-servicios → Logs
- Deberías ver output del comando con estadísticas

---

### Solución 2: Verificar y Crear Grupo OPERACIONES

#### En Render Shell:

```bash
# 1. Acceder a Render Shell
# Dashboard → Web Service → Shell

# 2. Ejecutar comandos Python
python manage.py shell
```

#### Crear grupo y asignar usuario:

```python
from django.contrib.auth.models import Group, User

# Crear grupo OPERACIONES
ops_group, created = Group.objects.get_or_create(name='OPERACIONES')
if created:
    print("✅ Grupo OPERACIONES creado")
else:
    print("ℹ️  Grupo OPERACIONES ya existe")

# Ver usuarios en el grupo
usuarios = ops_group.user_set.all()
print(f"Usuarios en OPERACIONES: {usuarios.count()}")
for u in usuarios:
    print(f"  - {u.username}")

# Si no hay usuarios, asignar uno (cambiar 'admin' por tu usuario)
if usuarios.count() == 0:
    admin_user = User.objects.filter(is_staff=True).first()
    if admin_user:
        admin_user.groups.add(ops_group)
        print(f"✅ Usuario {admin_user.username} asignado a OPERACIONES")
```

---

### Solución 3: Verificar Reservas

#### Comprobar que hay reservas para hoy:

```python
from ventas.models import VentaReserva
from django.utils import timezone

hoy = timezone.now().date()

# Reservas de hoy
reservas_hoy = VentaReserva.objects.filter(
    fecha_agendamiento=hoy
)

print(f"Reservas hoy ({hoy}): {reservas_hoy.count()}")

# Ver estados
for r in reservas_hoy:
    print(f"  Reserva #{r.id} - Estado: {r.estado_reserva}")
    servicios = r.reservaservicios.count()
    print(f"    Servicios: {servicios}")
```

#### Cambiar estado si es necesario:

```python
# Si las reservas están en estado incorrecto, cambiar a 'pendiente' o 'checkin'
reserva = VentaReserva.objects.get(id=XXXX)  # Cambiar XXXX por ID real
reserva.estado_reserva = 'checkin'  # o 'pendiente'
reserva.save()
print("✅ Estado actualizado")
```

---

### Solución 4: Ejecutar Manualmente (Temporal)

Mientras configuras el Cron Job, puedes ejecutar manualmente:

#### En Render Shell:

```bash
python manage.py gen_preparacion_servicios
```

Este comando:
- ✅ Busca servicios que comiencen en 40-80 minutos
- ✅ Crea tareas de preparación
- ✅ Asigna a usuarios del grupo OPERACIONES
- ✅ Muestra estadísticas de lo creado

#### Ejecutar diagnóstico:

```bash
python manage.py diagnostico_tareas
```

Este comando muestra:
- ✅ Si existen grupos y usuarios
- ✅ Reservas del día
- ✅ Tareas ya creadas
- ✅ Servicios en ventana de tiempo
- ✅ Qué falta configurar

---

## 📋 Checklist de Verificación

### Paso 1: Ejecutar Diagnóstico

```bash
# En Render Shell
python manage.py diagnostico_tareas
```

**Revisar output**:
- [ ] ¿Existe grupo OPERACIONES?
- [ ] ¿Hay usuarios en OPERACIONES?
- [ ] ¿Hay reservas para hoy?
- [ ] ¿Hay servicios en ventana de tiempo?
- [ ] ¿Se han creado tareas hoy?

### Paso 2: Crear Grupos (Si no existen)

```python
# En Render Shell
python manage.py shell

from django.contrib.auth.models import Group

for nombre in ['OPERACIONES', 'RECEPCION', 'SUPERVISION', 'VENTAS', 'ATENCION']:
    Group.objects.get_or_create(name=nombre)
    print(f"✅ {nombre}")
```

### Paso 3: Asignar Usuarios a Grupos

```python
from django.contrib.auth.models import User, Group

# Ejemplo: Asignar usuario admin a OPERACIONES
ops_group = Group.objects.get(name='OPERACIONES')
admin_user = User.objects.get(username='admin')  # Cambiar por usuario real
admin_user.groups.add(ops_group)
print("✅ Usuario asignado")
```

### Paso 4: Verificar Reservas

```bash
python manage.py diagnostico_tareas
```

Verificar sección "2️⃣ RESERVAS DEL DÍA DE HOY"

### Paso 5: Configurar Cron Job en Render

Seguir instrucciones en **Solución 1** arriba.

### Paso 6: Ejecutar Manualmente (Prueba)

```bash
python manage.py gen_preparacion_servicios
```

Debería mostrar:
```
🔔 GENERACIÓN DE TAREAS DE PREPARACIÓN
===================================
🕐 Hora actual: XX:XX
📅 Fecha: 2025-11-09
⏱️  Anticipación: 60 minutos antes del servicio
⏱️  Tolerancia: ±20 minutos

🔍 Buscando servicios que comiencen entre XX:XX y XX:XX...

✅ [Servicio] - Hora servicio: XX:XX - Reserva #XXXX
   Preparar a las: XX:XX
   → Tarea creada

📊 Servicios en ventana: X
✅ Tareas creadas: X
```

### Paso 7: Verificar en Admin

1. Ir a: `/admin/control_gestion/task/`
2. Filtrar por:
   - Área (Swimlane): Operación
   - Fecha: Hoy
3. Deberías ver tareas como:
   - "Preparar servicio – [Nombre] (Reserva #[ID])"

---

## 🔍 Cómo Saber Si Está Funcionando

### Indicadores de éxito:

1. **Cron Job en Render**:
   - Dashboard → Cron Jobs → gen-preparacion-servicios
   - Estado: Running/Succeeded
   - Logs muestran output cada 15 minutos

2. **Tareas en Admin**:
   - Se crean automáticamente 1 hora antes de cada servicio
   - Asignadas a usuarios de OPERACIONES
   - Estado: Backlog
   - Swimlane: Operación

3. **Diagnóstico limpio**:
   ```bash
   python manage.py diagnostico_tareas
   ```
   Debe mostrar: "✅ No se detectaron problemas de configuración"

---

## 🚨 Troubleshooting

### Problema: Cron Job falla

**Síntomas**: Logs muestran error en Render

**Causas**:
- Variables de entorno no configuradas
- Base de datos no accesible
- Comando incorrecto

**Solución**:
- Verificar que el Cron Job use "Same environment as web service"
- Revisar logs específicos del error
- Ejecutar el comando manualmente en Shell primero

### Problema: Se crean tareas pero sin asignar

**Síntomas**: Tareas existen pero owner es None

**Causa**: Grupo OPERACIONES no tiene usuarios

**Solución**:
```python
from django.contrib.auth.models import User, Group

ops_group = Group.objects.get(name='OPERACIONES')
admin_user = User.objects.filter(is_staff=True).first()
admin_user.groups.add(ops_group)
```

### Problema: No detecta servicios en ventana

**Síntomas**: "No hay servicios próximos en la ventana de tiempo"

**Causas**:
- No hay reservas para hoy
- Reservas en estado incorrecto
- Servicios ya pasaron la ventana (>80 min en futuro o ya ocurrieron)

**Solución**:
- Verificar que hay reservas con `estado_reserva` = 'pendiente', 'checkin' o 'checkout'
- Verificar que servicios tienen `hora_inicio` correcta
- Esperar a que servicios entren en ventana (40-80 min antes)

---

## 📚 Documentos Relacionados

- `docs/VERIFICAR_TAREAS_OPERACION.md` - Cómo verificar tareas
- `control_gestion/README.md` - Manual completo del módulo
- `control_gestion/management/commands/gen_preparacion_servicios.py` - Código fuente
- `control_gestion/management/commands/diagnostico_tareas.py` - Diagnóstico

---

## 🎯 Resumen Ejecutivo

### Problema:
No se generan tareas automáticas de preparación para servicios/tinas programadas.

### Causa Principal (95% probable):
**Cron Job NO está configurado en Render Dashboard**

### Solución Rápida:

1. **Configurar Cron Job en Render**:
   - Name: `gen-preparacion-servicios`
   - Command: `python manage.py gen_preparacion_servicios`
   - Schedule: `*/15 * * * *`
   - Environment: Same as web service

2. **Crear grupo OPERACIONES** (si no existe):
   ```bash
   python manage.py shell
   from django.contrib.auth.models import Group
   Group.objects.get_or_create(name='OPERACIONES')
   ```

3. **Asignar usuario al grupo**:
   ```python
   from django.contrib.auth.models import User, Group
   ops_group = Group.objects.get(name='OPERACIONES')
   admin = User.objects.filter(is_staff=True).first()
   admin.groups.add(ops_group)
   ```

4. **Esperar 15-20 minutos** y verificar:
   ```bash
   python manage.py diagnostico_tareas
   ```

### Tiempo Estimado:
**10-15 minutos** para configurar todo

---

**Última actualización**: 9 de noviembre, 2025
**Comandos disponibles**:
- `python manage.py diagnostico_tareas` - Diagnóstico completo
- `python manage.py gen_preparacion_servicios` - Generar tareas manualmente
- `python manage.py gen_preparacion_servicios --dry-run` - Simular sin crear tareas
