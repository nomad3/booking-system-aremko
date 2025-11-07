# 👥 Crear Usuarios y Grupos para Control de Gestión

**Para**: Etapa 3 - Integración con Reservas  
**Requisito**: Necesario para que tareas automáticas se asignen correctamente

---

## 🎯 Grupos Necesarios

El sistema de Control de Gestión requiere estos grupos para asignar tareas automáticamente:

| Grupo | Descripción | Tareas Asignadas |
|-------|-------------|------------------|
| **OPERACIONES** | Personal operativo del spa | Preparar servicios, rutinas diarias, limpieza |
| **RECEPCION** | Recepcionistas | Check-in, bienvenida, coordinación |
| **VENTAS** | Equipo comercial/ventas | Premios D+3, seguimiento comercial |
| **ATENCION** | Atención al cliente | NPS, encuestas, feedback post-visita |

**Opcionales** (para futuro):
- **MUCAMA**: Limpieza y aseo
- **SUPERVISION**: Marketing y supervisión

---

## 📝 Instrucciones: Crear Grupos

### Opción A: Desde el Admin de Django

1. Acceder al Admin: `http://localhost:8000/admin/` o tu URL de producción

2. Ir a **Authentication and Authorization** → **Groups**

3. Click en **"Add group"** (Agregar grupo)

4. Crear cada grupo:

#### Grupo 1: OPERACIONES
- **Name**: `OPERACIONES` (exactamente así, mayúsculas)
- **Permissions**: (opcional, no necesario por ahora)
- Guardar

#### Grupo 2: RECEPCION
- **Name**: `RECEPCION`
- Guardar

#### Grupo 3: VENTAS
- **Name**: `VENTAS`
- Guardar

#### Grupo 4: ATENCION
- **Name**: `ATENCION`
- Guardar

---

### Opción B: Desde Django Shell

```python
python manage.py shell

# En el shell de Django:
from django.contrib.auth.models import Group

# Crear grupos
grupos = ['OPERACIONES', 'RECEPCION', 'VENTAS', 'ATENCION']

for nombre_grupo in grupos:
    grupo, created = Group.objects.get_or_create(name=nombre_grupo)
    if created:
        print(f"✅ Grupo '{nombre_grupo}' creado")
    else:
        print(f"ℹ️  Grupo '{nombre_grupo}' ya existe")

# Verificar
print(f"\nTotal grupos: {Group.objects.count()}")
for g in Group.objects.all():
    print(f"  - {g.name}")
```

---

## 👤 Instrucciones: Crear Usuarios

### Crear Usuarios de Prueba/Operativos

1. Ir a **Users** en el Admin

2. Click en **"Add user"** (Agregar usuario)

3. Crear usuario para cada área:

#### Usuario 1: Operaciones
- **Username**: `ops_user` (o el nombre que prefieras)
- **Password**: (tu contraseña segura)
- Guardar y continuar editando
- En **Groups**: Seleccionar **OPERACIONES**
- **Permisos** (opcional):
  - Staff status: ✅ (si quieres que acceda al admin)
  - Superuser: ❌ (a menos que lo necesites)
- Guardar

#### Usuario 2: Recepción
- **Username**: `recepcion_user`
- **Groups**: **RECEPCION**
- Staff status: ✅

#### Usuario 3: Ventas
- **Username**: `ventas_user`
- **Groups**: **VENTAS**
- Staff status: ✅

#### Usuario 4: Atención
- **Username**: `atencion_user`
- **Groups**: **ATENCION**
- Staff status: ✅

---

### Desde Django Shell

```python
python manage.py shell

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()

# Obtener grupos
ops_group = Group.objects.get(name='OPERACIONES')
rx_group = Group.objects.get(name='RECEPCION')
ventas_group = Group.objects.get(name='VENTAS')
atencion_group = Group.objects.get(name='ATENCION')

# Crear usuarios
usuarios = [
    ('ops_user', ops_group, 'Usuario', 'Operaciones'),
    ('recepcion_user', rx_group, 'Usuario', 'Recepción'),
    ('ventas_user', ventas_group, 'Usuario', 'Ventas'),
    ('atencion_user', atencion_group, 'Usuario', 'Atención'),
]

for username, group, first_name, last_name in usuarios:
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'first_name': first_name,
            'last_name': last_name,
            'is_staff': True,
            'email': f'{username}@aremko.cl'
        }
    )
    
    if created:
        user.set_password('aremko2025')  # Cambiar por password segura
        user.save()
        print(f"✅ Usuario '{username}' creado")
    else:
        print(f"ℹ️  Usuario '{username}' ya existe")
    
    # Agregar al grupo
    user.groups.add(group)
    print(f"   → Agregado al grupo '{group.name}'")

print("\n✅ Usuarios y grupos configurados")
```

**⚠️ IMPORTANTE**: Cambia `'aremko2025'` por una contraseña segura.

---

## ✅ Verificación

### Verificar que grupos existen:

```python
from django.contrib.auth.models import Group

grupos_necesarios = ['OPERACIONES', 'RECEPCION', 'VENTAS', 'ATENCION']

for nombre in grupos_necesarios:
    existe = Group.objects.filter(name=nombre).exists()
    print(f"{nombre}: {'✅' if existe else '❌'}")
```

### Verificar que usuarios están en grupos:

```python
for nombre in grupos_necesarios:
    grupo = Group.objects.get(name=nombre)
    usuarios = grupo.user_set.count()
    print(f"{nombre}: {usuarios} usuario(s)")
    
    for user in grupo.user_set.all():
        print(f"  - {user.username}")
```

---

## 🧪 Probar la Integración

Una vez creados usuarios y grupos:

### Prueba 1: Check-in Manual

1. Ir a Admin → Ventas → VentaReserva
2. Seleccionar una reserva en estado 'pendiente'
3. Cambiar `estado_reserva` a **'checkin'**
4. Guardar
5. Ir a Admin → Control de Gestión → Tareas
6. **Verificar**: Deben aparecer tareas nuevas:
   - RECEPCION: "Check-in confirmado..."
   - OPERACION: "Preparar servicio..." (una por cada servicio)

### Prueba 2: Checkout Manual

1. Cambiar la misma reserva a **'checkout'**
2. Guardar
3. Verificar tareas:
   - ATENCION: "NPS post-visita..."
   - COMERCIAL: "Verificar premio D+3..." (con fecha futura)

### Prueba 3: Verificar Tramo

1. Ver detalles de una tarea creada
2. Campo `segment_tag` debe mostrar: "Tramo X"
3. Si está vacío, el cliente no tiene historial de tramos

---

## 🔄 Workflow Completo

```
1. Cliente reserva online → VentaReserva creada (estado: pendiente)

2. Cliente llega al spa → Recepcionista cambia a: checkin
   └─> ✅ Se crean tareas automáticas:
       ├─> RECEPCION: Dar bienvenida
       └─> OPERACION: Preparar tinas/salas

3. Cliente completa visita → Recepcionista cambia a: checkout
   └─> ✅ Se crean tareas automáticas:
       ├─> ATENCION: NPS post-visita (hoy)
       └─> COMERCIAL: Premio D+3 (programada +3 días)

4. Sistema muestra tareas en Admin por área
   └─> Cada responsable ve sus tareas en "Mi día"
```

---

## 🎯 Checklist de Configuración

Antes de usar la integración en producción:

- [ ] Grupos creados (OPERACIONES, RECEPCION, VENTAS, ATENCION)
- [ ] Al menos 1 usuario por grupo
- [ ] Usuarios tienen `is_staff=True` para acceder admin
- [ ] Test manual check-in → verificar tareas creadas
- [ ] Test manual checkout → verificar tareas con promise_due_at
- [ ] Verificar logs en consola/archivo
- [ ] Verificar que segment_tag muestra tramo correcto

---

**Última actualización**: 7 de noviembre, 2025  
**Estado**: ✅ Lista para configurar  
**Commit**: Etapa 3 - Integración con Reservas

