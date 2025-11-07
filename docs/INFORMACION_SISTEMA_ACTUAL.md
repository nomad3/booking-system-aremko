# 📋 Información del Sistema Actual - Booking System Aremko

**Generado para**: Integración con módulo de Control de Gestión  
**Fecha**: Noviembre 2025  
**Rama**: feature/control-gestion

---

## 📘 Modelo de Reserva

### Modelo Principal
- **App**: `ventas`
- **Modelo**: `VentaReserva` (`ventas.models.VentaReserva`)

### Campos Principales del Modelo VentaReserva

| Campo | Tipo | Descripción |
|------|------|-------------|
| `id` | AutoField | ID/Número único de reserva (auto-incremental) |
| `cliente` | ForeignKey(Cliente) | Relación con el cliente que hizo la reserva |
| `fecha_creacion` | DateTimeField | Fecha/hora cuando se creó el registro (auto_now_add=True) |
| `fecha_reserva` | DateTimeField | Fecha/hora cuando se realizó la venta/reserva (puede ser null) |
| `total` | DecimalField | Total de la reserva |
| `pagado` | DecimalField | Monto pagado hasta el momento |
| `saldo_pendiente` | DecimalField | Saldo pendiente de pago |
| `estado_pago` | CharField | Estado de pago: 'pendiente', 'pagado', 'parcial', 'cancelado' |
| `estado_reserva` | CharField | **Estado de reserva: 'pendiente', 'checkin', 'checkout'** |
| `codigo_giftcard` | CharField | Código de giftcard si aplica |
| `cobrado` | BooleanField | Indica si fue cobrado |
| `numero_documento_fiscal` | CharField | Número de documento fiscal |
| `comentarios` | TextField | Comentarios adicionales |

### Modelo de Servicios Reservados
- **Modelo**: `ReservaServicio` (`ventas.models.ReservaServicio`)
- **Relación**: ManyToMany entre `VentaReserva` y `Servicio` a través de este modelo intermedio

### Campos del Modelo ReservaServicio

| Campo | Tipo | Descripción |
|------|------|-------------|
| `id` | AutoField | ID único del servicio reservado |
| `venta_reserva` | ForeignKey(VentaReserva) | Relación con la reserva principal |
| `servicio` | ForeignKey(Servicio) | Tipo de servicio reservado |
| `fecha_agendamiento` | DateField | **Fecha del check-in** (fecha cuando se realiza el servicio) |
| `hora_inicio` | CharField(max_length=5) | Hora de inicio en formato 'HH:MM' |
| `cantidad_personas` | PositiveIntegerField | Número de personas para el servicio |
| `proveedor_asignado` | ForeignKey(Proveedor) | Proveedor asignado (ej. masajista específico) |

### Propiedades y Métodos Importantes

**VentaReserva:**
- `calcular_total()`: Calcula el total de la reserva sumando servicios y productos
- `total_servicios`: Property que calcula el total de servicios
- `total_productos`: Property que calcula el total de productos
- `agregar_servicio(servicio, fecha_agendamiento, cantidad_personas)`: Agrega un servicio a la reserva

**ReservaServicio:**
- `fecha_hora_completa`: Property que combina fecha_agendamiento + hora_inicio en DateTime
- `calcular_precio()`: Calcula el precio según tipo de servicio
- `subtotal`: Property con el subtotal del servicio

### Estados de Reserva

**estado_reserva:** ⭐ **CAMPO CLAVE PARA INTEGRACIÓN**
- `'pendiente'`: Reserva creada pero aún no se ha hecho check-in
- `'checkin'`: Cliente ha hecho check-in (gatilla tareas de preparación)
- `'checkout'`: Cliente ha completado el servicio (gatilla tareas de NPS y premio D+3)

**estado_pago:**
- `'pendiente'`: Sin pago
- `'pagado'`: Completamente pagado
- `'parcial'`: Parcialmente pagado
- `'cancelado'`: Reserva cancelada

### Notas Importantes para Integración

1. **Fecha de Reserva vs Fecha de Check-in:**
   - `VentaReserva.fecha_reserva`: Fecha cuando se creó/hizo la reserva (puede ser días/semanas antes)
   - `ReservaServicio.fecha_agendamiento`: **Fecha del check-in** (fecha cuando se realiza el servicio)
   - El sistema usa `fecha_agendamiento` para determinar cuándo generar premios (3 días después del check-in)

2. **Relación con Servicios:**
   - Una `VentaReserva` puede tener múltiples `ReservaServicio`
   - Cada `ReservaServicio` tiene su propia `fecha_agendamiento` y `hora_inicio`
   - Los servicios se relacionan a través de ManyToMany con tabla intermedia

3. **Integración con Control de Gestión:**
   - El recepcionista cambia `estado_reserva` de 'pendiente' a 'checkin'
   - Esto gatilla señales (signals) que crean tareas automáticas
   - Al cambiar a 'checkout', se crean tareas de NPS y premio D+3

---

## 👤 Modelo de Cliente

### Modelo Principal
- **App**: `ventas`
- **Modelo**: `Cliente` (`ventas.models.Cliente`)

### Campos Principales del Modelo Cliente

| Campo | Tipo | Descripción |
|------|------|-------------|
| `id` | AutoField | ID único del cliente |
| `nombre` | CharField(max_length=100) | Nombre completo del cliente |
| `email` | EmailField | Email del cliente (puede ser null/blank) |
| `telefono` | CharField(max_length=20, unique=True) | **Número de celular** (formato internacional con +, ej: +56912345678) |
| `documento_identidad` | CharField | ID/DNI/Passport/RUT |
| `pais` | CharField | País del cliente |
| `ciudad` | CharField | Ciudad (campo legacy) |
| `region` | ForeignKey(Region) | Región de Chile |
| `comuna` | ForeignKey(Comuna) | Comuna de Chile |
| `created_at` | DateTimeField | Fecha de creación del registro |

### Sistema de Tramos (Nivel/Rango del Cliente)

**IMPORTANTE**: El tramo/nivel NO está almacenado directamente en el modelo `Cliente`. Se calcula dinámicamente basado en el gasto total del cliente.

#### Cálculo de Tramos
- **Servicio**: `TramoService` (`ventas.services.tramo_service`)
- **Método**: `TramoService.calcular_tramo(gasto_total)`
- **Fórmula**: `tramo = int(gasto_total / 50000) + 1` (si hay resto)
- **Tramo Size**: $50,000 CLP por tramo

**Ejemplos:**
- Tramo 1: $0 - $50,000
- Tramo 2: $50,001 - $100,000
- Tramo 3: $100,001 - $150,000
- Tramo 5-8: Premios de "Tinas Gratis con Masajes"
- Tramo 10: Hito VIP ($500,000)
- Tramo 17-20: Premios Elite

#### Modelo de Historial de Tramos
- **Modelo**: `HistorialTramo` (`ventas.models.HistorialTramo`)
- Registra los cambios de tramo del cliente

**Campos:**
- `cliente`: ForeignKey(Cliente)
- `tramo_desde`: IntegerField (tramo anterior)
- `tramo_hasta`: IntegerField (nuevo tramo)
- `fecha_cambio`: DateTimeField (auto_now_add)
- `gasto_en_momento`: DecimalField (gasto total al momento del cambio)
- `premio_generado`: ForeignKey(ClientePremio, null=True)

#### Métodos para Obtener Tramo Actual

```python
from ventas.services.tramo_service import TramoService
from ventas.models import Cliente

# Calcular tramo actual de un cliente
cliente = Cliente.objects.get(id=1)
gasto_total = TramoService.calcular_gasto_cliente(cliente)
tramo_actual = TramoService.calcular_tramo(float(gasto_total))

# Obtener último tramo del historial
ultimo_historial = HistorialTramo.objects.filter(
    cliente=cliente
).order_by('-fecha_cambio').first()
tramo_actual = ultimo_historial.tramo_hasta if ultimo_historial else 0
```

### Normalización de Teléfono

El modelo `Cliente` tiene un método `normalize_phone()` que normaliza números a formato internacional:
- Formato estándar: `+56XXXXXXXXX` (Chile)
- Siempre incluye el signo `+` al inicio
- Valida números chilenos (56 + 9 dígitos para móvil, 56 + 1 + 8 dígitos para fijo)
- Se ejecuta automáticamente en el `save()` del modelo

### Métodos del Modelo Cliente

- `numero_visitas()`: Retorna el número de VentaReserva asociadas
- `gasto_total()`: Calcula el gasto total basado en VentaReserva

---

## 🔗 Relaciones Importantes

### VentaReserva → Cliente
```python
venta_reserva.cliente  # ForeignKey directo
```

### VentaReserva → ReservaServicio
```python
venta_reserva.reservaservicios.all()  # Related name
# O también:
ReservaServicio.objects.filter(venta_reserva=venta_reserva)
```

### Cliente → VentaReserva
```python
cliente.ventareserva_set.all()  # Default related name
```

### Cliente → HistorialTramo
```python
cliente.historial_tramos.all()  # Related name
```

---

## 📝 Ejemplo de Uso

```python
from ventas.models import VentaReserva, ReservaServicio, Cliente
from ventas.services.tramo_service import TramoService

# Obtener una reserva
reserva = VentaReserva.objects.get(id=3851)

# Información básica
print(f"Reserva #{reserva.id}")
print(f"Cliente: {reserva.cliente.nombre}")
print(f"Teléfono: {reserva.cliente.telefono}")
print(f"Fecha reserva: {reserva.fecha_reserva}")
print(f"Estado: {reserva.estado_reserva}")

# Obtener servicios reservados
servicios = reserva.reservaservicios.all()
for servicio in servicios:
    print(f"Servicio: {servicio.servicio.nombre}")
    print(f"Fecha check-in: {servicio.fecha_agendamiento}")
    print(f"Hora inicio: {servicio.hora_inicio}")

# Obtener tramo del cliente
cliente = reserva.cliente
gasto_total = TramoService.calcular_gasto_cliente(cliente)
tramo_actual = TramoService.calcular_tramo(float(gasto_total))
print(f"Tramo actual: {tramo_actual}")
```

---

## 🎯 Resumen para Integración con Control de Gestión

### Para el Módulo de Control de Gestión:

1. **Modelo de Reserva**: `ventas.models.VentaReserva`
   - **ID**: `id` (AutoField)
   - **Cliente**: `cliente` (ForeignKey a Cliente)
   - **Fecha/hora inicio**: Acceder a través de `ReservaServicio.fecha_agendamiento` + `hora_inicio`
   - **Fecha/hora término**: Calcular desde `fecha_agendamiento` + `servicio.duracion`
   - **Estado**: `estado_reserva` ('pendiente', 'checkin', 'checkout')
   - **⭐ Transiciones gatillan signals**:
     - 'pendiente' → 'checkin': Crear tareas de recepción y operación
     - 'checkin' → 'checkout': Crear tareas de NPS y premio D+3

2. **Modelo de Cliente**: `ventas.models.Cliente`
   - **Celular**: `telefono` (formato internacional con +56)
   - **Nivel/Tramo**: Calcular usando `TramoService.calcular_tramo(gasto_total)`
   - **Historial de tramos**: Modelo separado `HistorialTramo`
   - **Para tareas**: Usar últimos 9 dígitos del teléfono (`Task.customer_phone_last9`)

3. **Integración vía Signals**:
   - Módulo `control_gestion` escucha cambios en `VentaReserva.estado_reserva`
   - NO modifica modelos de `ventas`, solo LECTURA
   - Crea `Task` automáticamente según transiciones

---

## 🚨 Consideraciones Importantes

1. **NO modificar modelos existentes**: El módulo de control_gestion es completamente independiente
2. **Solo lectura**: Los signals de control_gestion solo leen datos de ventas, no modifican
3. **Identificadores**: Usar CharField para `reservation_id` y `customer_phone_last9` (no ForeignKey)
4. **Tramos**: Calcular dinámicamente, no almacenar en Task
5. **Fechas**: `fecha_agendamiento` (check-in) ≠ `fecha_reserva` (creación de reserva)

---

**Última actualización**: Noviembre 2025  
**Generado para**: Módulo de Control de Gestión  
**Sistema**: Booking System Aremko  
**Versión Django**: 4.2

