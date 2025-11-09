# 🔗 Integración Control de Gestión ↔️ Sistema de Reservas

**Rama**: `feature/control-gestion`  
**Fecha**: Noviembre 2025  
**Estado**: ✅ Implementada

---

## 📋 Resumen de la Integración

El módulo de Control de Gestión se integra con el sistema de reservas existente mediante **signals** que detectan cambios en el estado de las reservas y crean tareas automáticas para el equipo.

### 🎯 Principio Clave

**NO se modifican modelos existentes**. La integración es **read-only** desde Control de Gestión hacia Ventas.

---

## 🔄 Flujo de Integración

```
VentaReserva (ventas)
    |
    | estado_reserva cambia
    |
    v
Signal: capture_old_estado (pre_save)
    |
    | Guardar estado anterior
    |
    v
Signal: react_to_reserva_change (post_save)
    |
    | Detectar transición
    |
    v
Crear Task(s) automáticas
    |
    |-->  RECEPCION: Bienvenida (check-in)
    |-->  RECEPCION: Checkout completado (checkout)
    |-->  ATENCION: NPS post-visita (checkout)
    |-->  COMERCIAL: Premio D+3 (checkout)
    |
    ⚠️ OPERACION: Preparar servicios → vía gen_preparacion_servicios (1 hora antes)
```

---

## 🎬 Transiciones Detectadas

### 1️⃣ Transición: `pendiente` → `checkin`

**Cuándo**: El recepcionista marca que el cliente llegó e hizo check-in

**Tareas creadas**:

#### Tarea 1: Recepción
- **Título**: "Check-in confirmado – Reserva #[ID]"
- **Swimlane**: RECEPCION
- **Descripción**:
  ```
  Dar la bienvenida al cliente, entregar indicaciones del spa,
  validar pago y documento si aplica, coordinar con Operaciones.
  ```
- **Prioridad**: NORMAL
- **Cola**: Posición 1

#### Tarea(s) 2+: Operación (una por cada servicio)
- **Título**: "Preparar servicio – [Nombre Servicio] (Reserva #[ID])"
- **Swimlane**: OPERACION
- **Descripción**:
  ```
  ⏰ SERVICIO COMIENZA A LAS [hora_inicio]
  📅 Fecha: [fecha_agendamiento]
  👤 Cliente: [nombre_cliente]
  
  🔧 TAREAS DE PREPARACIÓN (completar 1 hora antes):
  • Limpiar y sanitizar tina/sala
  • Llenar tina con agua caliente
  • Verificar temperatura (36-38°C)
  • Preparar toallas y amenidades
  • Verificar que todo funcione correctamente
  • Área lista y presentable para las [hora_inicio]
  ```
- **Prioridad**: NORMAL
- **Cola**: Posición 1
- **Contexto**: service_type, reservation_id, segment_tag
- **⚠️ IMPORTANTE**: Estas tareas NO se crean automáticamente al check-in. Se crean mediante el comando `gen_preparacion_servicios` que debe ejecutarse cada 15 minutos vía cron.

**Ejemplo**:
```
Reserva #3851 con 2 servicios:
→ Al check-in se crea:
  1. RECEPCION: Check-in confirmado

→ 1 hora antes de cada servicio (vía gen_preparacion_servicios):
  2. OPERACION: Preparar Tina Hidromasaje (creada a las 15:00 si servicio es 16:00)
  3. OPERACION: Preparar Masaje Relajante (creada según hora del servicio)
```

---

### 2️⃣ Transición: `checkin` → `checkout`

**Cuándo**: El cliente termina su visita y hace checkout

**Tareas creadas**:

#### Tarea 1: NPS Post-Visita
- **Título**: "NPS post-visita – Reserva #[ID]"
- **Swimlane**: ATENCION
- **Descripción**:
  ```
  Contactar al cliente por WhatsApp o llamada para:
  - Pedir calificación NPS (0-10)
  - Solicitar comentarios de la experiencia
  - Registrar feedback en CRM
  - Agradecer la visita
  ```
- **Prioridad**: NORMAL
- **Cuándo**: Inmediatamente

#### Tarea(s) 2+: Premio D+3 (una por servicio)
- **Título**: "Verificar premio D+3 – Reserva #[ID]"
- **Swimlane**: COMERCIAL
- **Descripción**:
  ```
  Enviar premio según tramo del cliente ([Tramo X]):
  - Enviar por WhatsApp con mensaje personalizado
  - Enviar por Email con vale digital
  - (Opcional) SMS de respaldo
  - Registrar envío en sistema de premios
  - Validar que cliente recibió correctamente

  Servicio: [Nombre]
  Check-in fue: [fecha_agendamiento]
  ```
- **Prioridad**: NORMAL
- **promise_due_at**: ⭐ **fecha_agendamiento + 3 días** ⭐

**Ejemplo**:
```
Reserva #3851 checkout el 06/11/2025:
→ Crea 3 tareas:
  1. ATENCION: NPS post-visita (inmediato)
  2. COMERCIAL: Premio D+3 (programada para 09/11/2025) - Servicio 1
  3. COMERCIAL: Premio D+3 (programada para 09/11/2025) - Servicio 2
```

---

## 🧩 Componentes de la Integración

### 1. Signals (control_gestion/signals.py)

```python
@receiver(pre_save, sender='ventas.VentaReserva')
def capture_old_estado(sender, instance, **kwargs):
    """Guarda estado_reserva anterior"""
    # Almacena old.estado_reserva en caché

@receiver(post_save, sender='ventas.VentaReserva')
def react_to_reserva_change(sender, instance, created, **kwargs):
    """Detecta transiciones y crea tareas"""
    # Compara old vs new estado_reserva
    # Crea Task según la transición
```

### 2. Helpers

**`_get_last9_digits(phone)`**: Extrae últimos 9 dígitos del teléfono  
**`_get_user_by_group(group_name)`**: Obtiene usuario del grupo

### 3. Integración con TramoService

```python
from ventas.services.tramo_service import TramoService

gasto_total = TramoService.calcular_gasto_cliente(cliente)
tramo_actual = TramoService.calcular_tramo(float(gasto_total))
segment_tag = f"Tramo {tramo_actual}"
```

Esto permite etiquetar las tareas con el nivel del cliente.

---

## 👥 Grupos de Usuarios Necesarios

Para que la integración funcione, deben existir estos grupos en Django:

| Grupo | Descripción | Tareas Asignadas |
|-------|-------------|------------------|
| `OPERACIONES` | Personal operativo | Preparar servicios, rutinas diarias |
| `RECEPCION` | Recepcionistas | Check-in, atención inicial |
| `VENTAS` | Equipo comercial | Premios D+3, seguimiento ventas |
| `ATENCION` | Atención al cliente | NPS, encuestas, feedback |

**Fallback**: Si un grupo no existe, se asigna al primer usuario disponible.

### Crear Grupos (Admin Django):

```
Admin → Authentication and Authorization → Groups → Add group

Nombres exactos:
- OPERACIONES
- RECEPCION
- VENTAS
- ATENCION
```

---

## 📊 Datos de Contexto en Task

Cada tarea automática incluye:

| Campo | Ejemplo | Origen |
|-------|---------|--------|
| `reservation_id` | "3851" | `VentaReserva.id` |
| `customer_phone_last9` | "965996740" | `Cliente.telefono` (últimos 9) |
| `segment_tag` | "Tramo 7" | `TramoService.calcular_tramo()` |
| `service_type` | "tina" | `Servicio.tipo_servicio` |
| `promise_due_at` | "2025-11-09 12:00" | fecha_agendamiento + 3 días |

Esto permite:
- Filtrar tareas por reserva
- Identificar al cliente rápidamente
- Personalizar acciones según tramo
- Programar tareas futuras

---

## 🧪 Testing de Integración

### Test Manual 1: Check-in

```python
# En Django Admin o shell
from ventas.models import VentaReserva

# Obtener una reserva en estado pendiente
reserva = VentaReserva.objects.get(id=3851)

# Cambiar a checkin
reserva.estado_reserva = 'checkin'
reserva.save()

# Verificar tareas creadas
from control_gestion.models import Task
tareas = Task.objects.filter(reservation_id='3851')

# Deberías ver:
# - 1 tarea RECEPCION (Check-in confirmado)
# - N tareas OPERACION (una por servicio)
```

### Test Manual 2: Checkout

```python
# Cambiar a checkout
reserva.estado_reserva = 'checkout'
reserva.save()

# Verificar tareas post-visita
tareas_post = Task.objects.filter(reservation_id='3851', state='BACKLOG')

# Deberías ver:
# - 1 tarea ATENCION (NPS)
# - N tareas COMERCIAL (Premio D+3 con promise_due_at)
```

### Verificar promise_due_at

```python
premio_tasks = Task.objects.filter(
    reservation_id='3851',
    swimlane='COM'
)

for task in premio_tasks:
    print(f"Tarea: {task.title}")
    print(f"Promesa: {task.promise_due_at}")
    # Debe ser fecha_agendamiento + 3 días
```

---

## 🚨 Consideraciones Importantes

### ✅ LO QUE HACE la Integración:

1. **LEE** datos de `ventas.VentaReserva`, `ventas.ReservaServicio`, `ventas.Cliente`
2. **ESCUCHA** cambios en `estado_reserva`
3. **CREA** tareas en `control_gestion.Task`
4. **USA** `TramoService` para obtener tramo del cliente

### ❌ LO QUE NO HACE:

1. **NO modifica** ningún modelo de `ventas`
2. **NO cambia** estados de reservas
3. **NO altera** datos de clientes
4. **NO interfiere** con signals existentes de `ventas`

### 🛡️ Seguridad

- Los signals están en `control_gestion/signals.py` (no en `ventas/signals.py`)
- Si hay error al crear Task, NO bloquea el save de VentaReserva
- Try/catch en todas las operaciones
- Logging completo para debugging

---

## 📝 Logs Generados

Cuando se detecta una transición:

```
INFO: Reserva #3851 → CHECKIN. Creando tareas automáticas...
INFO: ✅ Tarea RECEPCION creada para reserva #3851
INFO: ✅ 2 tarea(s) OPERACION creadas para reserva #3851
```

```
INFO: Reserva #3851 → CHECKOUT. Creando tareas post-visita...
INFO: ✅ Tarea NPS creada para reserva #3851
INFO: ✅ 2 tarea(s) PREMIO D+3 creadas para reserva #3851
```

---

## 🔧 Troubleshooting

### Problema: No se crean tareas automáticas

**Causas posibles**:
1. Los grupos (OPERACIONES, RECEPCION, etc.) no existen → Crear en Admin
2. No hay usuarios en los grupos → Asignar usuarios
3. Signal no está conectado → Verificar `apps.py` importa signals

**Solución**:
```python
# Verificar que signal está conectado
from control_gestion import signals
```

### Problema: Error al calcular tramo

**Causa**: TramoService no disponible o cliente sin historial

**Efecto**: Task se crea igual, pero `segment_tag` queda vacío

**Solución**: No crítico, la tarea se crea igual

### Problema: promise_due_at incorrecta

**Causa**: fecha_agendamiento no válida

**Efecto**: Se usa "ahora + 3 días" como fallback

**Solución**: Verificar que ReservaServicio tiene fecha_agendamiento válida

---

## 📈 Próximos Pasos

### Etapa 4: Vistas y Webhooks
- Vista "Mi día" para ver mis tareas
- Webhook `cliente_en_sitio` para pedidos urgentes
- Webhook `ai_ingest_message` para crear tareas desde mensajes

### Etapa 5: Comandos y Rutinas
- `gen_daily_opening`: Tareas rutinarias automáticas
- `gen_daily_reports`: Resumen diario con IA

---

**Última actualización**: 7 de noviembre, 2025  
**Archivos**: `control_gestion/signals.py` (392 líneas)  
**Tests**: Requiere testing manual con reservas reales  
**Estado**: ✅ Lista para testing en producción

