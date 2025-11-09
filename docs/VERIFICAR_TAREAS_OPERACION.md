# 🔧 Script de Verificación: Tareas de Operación

## Problema Resuelto

Las tareas de OPERACION ahora se crean **automáticamente** al hacer check-in de una reserva.

### Cambio Implementado

**Antes**: Las tareas de Operación solo se creaban mediante el comando `gen_preparacion_servicios` (cada 15 minutos).

**Ahora**: Las tareas de Operación se crean **inmediatamente** al cambiar el estado de reserva a `checkin`, con `promise_due_at` = 1 hora antes del servicio.

---

## ✅ Cómo Verificar que Funciona

### 1. Verificar que existe el grupo OPERACIONES

```python
python manage.py shell

from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model

User = get_user_model()

# Verificar grupo OPERACIONES
ops_group = Group.objects.filter(name='OPERACIONES').first()
if ops_group:
    print(f"✅ Grupo OPERACIONES existe")
    usuarios = ops_group.user_set.all()
    print(f"   Usuarios en grupo: {usuarios.count()}")
    for u in usuarios:
        print(f"   - {u.username}")
else:
    print("❌ Grupo OPERACIONES NO existe")
    print("   Crear desde Admin → Groups → Add group")
```

### 2. Crear grupo y usuario si no existen

```python
# Crear grupo
ops_group, created = Group.objects.get_or_create(name='OPERACIONES')
if created:
    print(f"✅ Grupo OPERACIONES creado")

# Crear usuario de operaciones
ops_user, created = User.objects.get_or_create(
    username='ops_user',
    defaults={
        'is_staff': True,
        'email': 'ops@aremko.cl'
    }
)
if created:
    ops_user.set_password('password_segura')  # Cambiar!
    ops_user.save()
    print(f"✅ Usuario ops_user creado")

# Asignar usuario al grupo
ops_user.groups.add(ops_group)
print(f"✅ Usuario asignado al grupo OPERACIONES")
```

### 3. Probar creación automática de tareas

```python
from ventas.models import VentaReserva
from control_gestion.models import Task

# Obtener una reserva en estado pendiente con servicios
reserva = VentaReserva.objects.filter(
    estado_reserva='pendiente'
).prefetch_related('reservaservicios').first()

if reserva:
    print(f"Reserva #{reserva.id}: {reserva.reservaservicios.count()} servicio(s)")
    
    # Cambiar a checkin
    reserva.estado_reserva = 'checkin'
    reserva.save()
    
    # Verificar tareas creadas
    tareas = Task.objects.filter(reservation_id=str(reserva.id))
    print(f"\n✅ Tareas creadas: {tareas.count()}")
    
    for tarea in tareas:
        print(f"  - [{tarea.get_swimlane_display()}] {tarea.title}")
        if tarea.swimlane == 'OPS':
            print(f"    Promise: {tarea.promise_due_at}")
else:
    print("❌ No hay reservas pendientes con servicios")
```

### 4. Verificar en Admin

1. Ir a Admin → Control de Gestión → Tareas
2. Filtrar por Área → Operación
3. Deberías ver tareas "Preparar servicio – [Nombre] (Reserva #[ID])"

---

## 🔍 Troubleshooting

### Problema: No se crean tareas de Operación

**Causas posibles**:

1. **Grupo OPERACIONES no existe o no tiene usuarios**
   - Solución: Crear grupo y asignar usuarios (ver script arriba)

2. **Reserva no tiene servicios asociados**
   - Verificar: `reserva.reservaservicios.count() > 0`

3. **Servicio no tiene hora_inicio o fecha_agendamiento**
   - Verificar: Los servicios deben tener estos campos completos

4. **Error en parsing de hora**
   - El signal tiene fallback que crea tarea genérica si falla

### Verificar logs

```python
import logging
logging.getLogger('control_gestion.signals').setLevel(logging.DEBUG)
```

Luego cambiar estado de reserva y revisar logs para ver mensajes como:
- `✅ Tarea OPERACION creada para servicio '...'`
- `Error creando tarea OPERACION...`

---

## 📝 Nota sobre el Comando gen_preparacion_servicios

El comando `gen_preparacion_servicios` sigue siendo útil para:
- Crear tareas para servicios que ya están en check-in pero faltan tareas
- Crear tareas para reservas en estado 'pendiente' (antes del check-in)
- Re-crear tareas si se eliminaron por error

**Recomendación**: Mantener el cron cada 15 minutos como respaldo, pero ahora las tareas principales se crean automáticamente al check-in.

