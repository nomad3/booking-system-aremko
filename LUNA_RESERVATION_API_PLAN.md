# Plan de Implementación: API de Reservas para Luna

## Resumen Ejecutivo

Este documento describe el plan para permitir que **Luna** (agente conversacional AI por WhatsApp) cree reservas completas a través de una API REST, siguiendo el mismo flujo que usa el sitio web.

**Contexto**: Luna conversa con clientes vía WhatsApp, recopila información sobre servicios deseados, fechas, y datos personales, y luego crea la reserva en el sistema automáticamente.

**Alcance**: Solo **CREAR** reservas. NO incluye modificar ni eliminar.

**⚠️ IMPORTANTE**:
- Esta implementación NO requiere migraciones de base de datos
- Usamos modelos y tablas existentes
- Cualquier migración futura se ejecutará manualmente en Render shell
- Backup completo de BD y código antes de comenzar (ver `BACKUP_BEFORE_LUNA_API.md`)

---

## 1. Análisis del Flujo Actual

### Flujo Web Existente

```
1. Usuario selecciona servicios → Se agregan al carrito (session)
2. Usuario ve carrito → Se calculan descuentos por packs
3. Usuario va a checkout → Ingresa datos personales
4. Usuario confirma → Se crea VentaReserva + ReservaServicio + Cliente
5. Usuario paga → Se procesa pago y confirma reserva
```

### Componentes Clave Identificados

**Modelos:**
- `Cliente`: Datos del cliente (nombre, email, teléfono, documento)
- `VentaReserva`: Reserva principal (total, estado_pago, estado_reserva)
- `ReservaServicio`: Servicios individuales (servicio, fecha, hora, cantidad_personas)
- `Pago`: Registro de pagos (monto, método, fecha)

**Validaciones Críticas:**
- Disponibilidad de slot (no bloqueado, no reservado)
- Capacidad del servicio (min/max personas)
- Datos del cliente completos y válidos
- Teléfono normalizado (formato chileno +56)

**Reglas de Negocio:**
- Precio se congela al momento de reservar (`precio_unitario_venta`)
- Cabañas se cobran por unidad fija
- Otros servicios se cobran por cantidad de personas
- Descuentos por packs se aplican automáticamente
- Martes cerrados (tuesday: [])

---

## 2. Diseño de API para Luna

### Principios de Diseño

1. **Stateless**: No usar sesiones. Todo en el request.
2. **Simple**: Endpoints mínimos necesarios.
3. **Validación estricta**: Validar todo antes de crear.
4. **Transaccional**: Todo-o-nada en creación.
5. **Idempotente**: Usar IDs únicos para evitar duplicados.

### Arquitectura Propuesta

```
Cliente real
    ↓
    ↓ WhatsApp
    ↓
Luna (AI Agent conversacional)
    ↓ (recopila: servicio, fecha, hora, datos personales)
    ↓
    ↓ HTTP POST /api/luna/reservas/create
    ↓
API Endpoint (nuevo - sin migraciones)
    ↓
    ├─ Validar disponibilidad
    ├─ Validar cliente
    ├─ Calcular totales
    ├─ Crear reserva (transacción con modelos existentes)
    └─ Retornar confirmación a Luna
        ↓
    Luna confirma al cliente vía WhatsApp
        ↓
    Cliente recibe número de reserva e instrucciones de pago
```

---

## 3. Endpoints Necesarios

### 3.1. Crear Reserva Completa

**Endpoint**: `POST /api/luna/reservas/create`

**Autenticación**: API Key en header `X-Luna-API-Key`

**Request Body**:
```json
{
  "idempotency_key": "unique-id-from-luna",
  "cliente": {
    "nombre": "Juan Pérez",
    "email": "juan@example.com",
    "telefono": "+56912345678",
    "documento_identidad": "12345678-9",
    "region_id": 1,
    "comuna_id": 10
  },
  "servicios": [
    {
      "servicio_id": 12,
      "fecha": "2026-04-01",
      "hora": "14:30",
      "cantidad_personas": 2
    },
    {
      "servicio_id": 11,
      "fecha": "2026-04-01",
      "hora": "17:00",
      "cantidad_personas": 3
    }
  ],
  "metodo_pago": "pendiente",
  "notas": "Cliente contactado via WhatsApp"
}
```

**Response (Success 201)**:
```json
{
  "success": true,
  "reserva": {
    "id": 1234,
    "numero": "RES-2026-1234",
    "cliente": {
      "id": 567,
      "nombre": "Juan Pérez",
      "telefono": "+56912345678"
    },
    "servicios": [
      {
        "id": 890,
        "servicio_nombre": "Tina Calbuco",
        "fecha": "2026-04-01",
        "hora": "14:30",
        "cantidad_personas": 2,
        "precio_unitario": 25000,
        "subtotal": 50000
      },
      {
        "id": 891,
        "servicio_nombre": "Tina Osorno",
        "fecha": "2026-04-01",
        "hora": "17:00",
        "cantidad_personas": 3,
        "precio_unitario": 25000,
        "subtotal": 75000
      }
    ],
    "descuentos": [],
    "total": 125000,
    "pagado": 0,
    "saldo_pendiente": 125000,
    "estado_pago": "pendiente",
    "estado_reserva": "pendiente",
    "fecha_creacion": "2026-03-31T10:30:00Z",
    "url_detalle": "https://aremko.cl/reserva/1234/",
    "instrucciones_pago": "Transferencia bancaria a cuenta..."
  }
}
```

**Response (Error 400)**:
```json
{
  "success": false,
  "error": "validation_error",
  "errores": [
    {
      "campo": "servicios[0].hora",
      "mensaje": "El horario 14:30 no está disponible para Tina Calbuco en 2026-04-01"
    },
    {
      "campo": "cliente.telefono",
      "mensaje": "El teléfono debe estar en formato +56XXXXXXXXX"
    }
  ]
}
```

**Response (Error 409 Conflict)**:
```json
{
  "success": false,
  "error": "slot_unavailable",
  "mensaje": "Uno o más horarios ya no están disponibles",
  "slots_no_disponibles": [
    {
      "servicio_id": 12,
      "fecha": "2026-04-01",
      "hora": "14:30",
      "razon": "Ya reservado"
    }
  ]
}
```

---

### 3.2. Consultar Regiones y Comunas

**Endpoint**: `GET /api/luna/regiones`

**Response**:
```json
{
  "success": true,
  "regiones": [
    {
      "id": 1,
      "nombre": "Región de Los Lagos",
      "comunas": [
        {"id": 10, "nombre": "Puerto Varas"},
        {"id": 11, "nombre": "Puerto Montt"},
        {"id": 12, "nombre": "Frutillar"}
      ]
    }
  ]
}
```

---

### 3.3. Validar Disponibilidad (Pre-validación)

**Endpoint**: `POST /api/luna/reservas/validar`

**Purpose**: Luna puede validar antes de confirmar con el cliente

**Request Body**:
```json
{
  "servicios": [
    {
      "servicio_id": 12,
      "fecha": "2026-04-01",
      "hora": "14:30",
      "cantidad_personas": 2
    }
  ]
}
```

**Response**:
```json
{
  "success": true,
  "disponibilidad": [
    {
      "servicio_id": 12,
      "disponible": true,
      "capacidad_disponible": 8,
      "precio_estimado": 50000
    }
  ],
  "total_estimado": 50000,
  "descuentos_aplicables": [],
  "total_con_descuentos": 50000
}
```

---

## 4. Validaciones Implementadas

### 4.1. Validaciones de Servicio

```python
Para cada servicio en la solicitud:

1. Servicio existe y está activo
   - Servicio.objects.get(id=servicio_id, activo=True, publicado_web=True)

2. Fecha no es martes (cerrado)
   - fecha.strftime('%A').lower() != 'tuesday'

3. Slot está en horarios configurados
   - hora in servicio.slots_disponibles[day_name]

4. Servicio no bloqueado por día completo
   - not ServicioBloqueo.servicio_bloqueado_en_fecha(servicio_id, fecha)

5. Slot individual no bloqueado
   - not ServicioSlotBloqueo.slot_bloqueado(servicio_id, fecha, hora)

6. Capacidad disponible
   - reservas_existentes = ReservaServicio.objects.filter(
       servicio=servicio, fecha_agendamiento=fecha, hora_inicio=hora
     ).aggregate(total_personas=Sum('cantidad_personas'))
   - total_personas + cantidad_personas_nueva <= servicio.capacidad_maxima

7. Cantidad personas cumple mínimo y máximo
   - servicio.capacidad_minima <= cantidad_personas <= servicio.capacidad_maxima
```

### 4.2. Validaciones de Cliente

```python
1. Teléfono en formato válido
   - Regex: ^\+56[0-9]{9}$
   - Normalización: ClienteService.normalizar_telefono()

2. Email válido (si se proporciona)
   - Django EmailValidator

3. Nombre no vacío
   - len(nombre.strip()) > 0

4. Documento identidad válido (RUT chileno)
   - Validación con dígito verificador

5. Región y comuna existen
   - Region.objects.filter(id=region_id).exists()
   - Comuna.objects.filter(id=comuna_id, region_id=region_id).exists()
```

### 4.3. Validación de Idempotencia

```python
1. Verificar idempotency_key único
   - Check cache or DB for existing key
   - If exists: Return existing reserva_id
   - Prevents duplicate reservations from retries

2. TTL: 24 horas
   - After 24h, key can be reused
```

---

## 5. Lógica de Cálculo de Totales

```python
def calcular_total_reserva(servicios):
    subtotal = 0
    items = []

    for servicio_data in servicios:
        servicio = Servicio.objects.get(id=servicio_data['servicio_id'])
        cantidad = servicio_data['cantidad_personas']

        # Cabañas: precio fijo
        if servicio.tipo_servicio == 'cabana':
            precio_item = servicio.precio_base
        # Otros: precio por persona
        else:
            precio_item = servicio.precio_base * cantidad

        subtotal += precio_item
        items.append({
            'servicio': servicio,
            'cantidad': cantidad,
            'precio_unitario': servicio.precio_base,
            'subtotal': precio_item
        })

    # Detectar descuentos por packs
    descuentos = PackDescuentoService.detectar_packs_aplicables(items)
    total_descuentos = sum(d['monto'] for d in descuentos)

    total = subtotal - total_descuentos

    return {
        'subtotal': subtotal,
        'descuentos': descuentos,
        'total_descuentos': total_descuentos,
        'total': total,
        'items': items
    }
```

---

## 6. Implementación de Endpoint Principal

### Archivo: `ventas/views/luna_api_views.py`

```python
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.cache import cache
from datetime import datetime, timedelta

from ventas.models import (
    Servicio, Cliente, VentaReserva, ReservaServicio,
    ServicioBloqueo, ServicioSlotBloqueo, Region, Comuna
)
from ventas.services.cliente_service import ClienteService
from ventas.services.pack_descuento_service import PackDescuentoService
from ventas.calendar_utils import verificar_disponibilidad


class LunaAPIKeyAuthentication:
    """Custom authentication for Luna API"""
    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_LUNA_API_KEY')
        expected_key = getattr(settings, 'LUNA_API_KEY', None)

        if not api_key or api_key != expected_key:
            raise AuthenticationFailed('Invalid Luna API Key')

        # Return None for user since Luna is not a user
        return (None, None)


@api_view(['POST'])
@authentication_classes([LunaAPIKeyAuthentication])
def crear_reserva(request):
    """
    Crear una reserva completa desde Luna

    POST /api/luna/reservas/create
    """

    # 1. Extraer datos
    idempotency_key = request.data.get('idempotency_key')
    cliente_data = request.data.get('cliente')
    servicios_data = request.data.get('servicios', [])
    metodo_pago = request.data.get('metodo_pago', 'pendiente')
    notas = request.data.get('notas', '')

    # 2. Validar idempotencia
    if idempotency_key:
        cache_key = f"luna_reserva_{idempotency_key}"
        existing_reserva_id = cache.get(cache_key)

        if existing_reserva_id:
            # Ya existe, devolver la reserva existente
            reserva = VentaReserva.objects.get(id=existing_reserva_id)
            return Response(
                serializar_reserva(reserva),
                status=status.HTTP_200_OK
            )

    # 3. Validar datos básicos
    errores = []

    if not cliente_data:
        errores.append({
            'campo': 'cliente',
            'mensaje': 'Datos del cliente son requeridos'
        })

    if not servicios_data or len(servicios_data) == 0:
        errores.append({
            'campo': 'servicios',
            'mensaje': 'Debe incluir al menos un servicio'
        })

    if errores:
        return Response({
            'success': False,
            'error': 'validation_error',
            'errores': errores
        }, status=status.HTTP_400_BAD_REQUEST)

    # 4. Validar cliente
    cliente_validado, cliente_errores = validar_datos_cliente(cliente_data)
    if cliente_errores:
        errores.extend(cliente_errores)

    # 5. Validar servicios y disponibilidad
    servicios_validados = []
    for idx, servicio_data in enumerate(servicios_data):
        servicio_validado, servicio_errores = validar_servicio(
            servicio_data,
            idx
        )

        if servicio_errores:
            errores.extend(servicio_errores)
        else:
            servicios_validados.append(servicio_validado)

    if errores:
        return Response({
            'success': False,
            'error': 'validation_error',
            'errores': errores
        }, status=status.HTTP_400_BAD_REQUEST)

    # 6. Calcular totales con descuentos
    calculo = calcular_total_reserva(servicios_validados)

    # 7. Crear reserva en transacción
    try:
        with transaction.atomic():
            # Crear o actualizar cliente
            cliente, created = ClienteService.crear_o_actualizar_cliente(
                cliente_validado
            )

            # Crear VentaReserva
            venta = VentaReserva.objects.create(
                cliente=cliente,
                total=calculo['total'],
                estado_pago='pendiente',
                estado_reserva='pendiente',
                fecha_reserva=timezone.now(),
                notas_admin=f"Creada por Luna AI. {notas}"
            )

            # Crear ReservaServicio para cada servicio
            for item in calculo['items']:
                ReservaServicio.objects.create(
                    venta_reserva=venta,
                    servicio=item['servicio'],
                    fecha_agendamiento=item['fecha'],
                    hora_inicio=item['hora'],
                    cantidad_personas=item['cantidad'],
                    precio_unitario_venta=item['precio_unitario']
                )

            # Aplicar descuentos si existen
            if calculo['descuentos']:
                for descuento in calculo['descuentos']:
                    # Crear ReservaServicio especial con precio negativo
                    ReservaServicio.objects.create(
                        venta_reserva=venta,
                        servicio=descuento['servicio_descuento'],
                        fecha_agendamiento=venta.fecha_reserva.date(),
                        hora_inicio='00:00',
                        cantidad_personas=1,
                        precio_unitario_venta=-descuento['monto']
                    )

            # Recalcular total final
            venta.calcular_total()
            venta.save()

            # Guardar idempotency key
            if idempotency_key:
                cache.set(cache_key, venta.id, timeout=86400)  # 24 horas

            # Retornar respuesta de éxito
            return Response(
                serializar_reserva(venta),
                status=status.HTTP_201_CREATED
            )

    except Exception as e:
        return Response({
            'success': False,
            'error': 'creation_error',
            'mensaje': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def validar_datos_cliente(cliente_data):
    """Validar datos del cliente"""
    errores = []

    # Teléfono
    telefono = cliente_data.get('telefono', '').strip()
    if not telefono:
        errores.append({
            'campo': 'cliente.telefono',
            'mensaje': 'El teléfono es requerido'
        })
    else:
        # Normalizar y validar formato
        telefono_normalizado = ClienteService.normalizar_telefono(telefono)
        if not telefono_normalizado:
            errores.append({
                'campo': 'cliente.telefono',
                'mensaje': 'Formato de teléfono inválido. Use +56XXXXXXXXX'
            })
        cliente_data['telefono'] = telefono_normalizado

    # Nombre
    nombre = cliente_data.get('nombre', '').strip()
    if not nombre or len(nombre) < 3:
        errores.append({
            'campo': 'cliente.nombre',
            'mensaje': 'El nombre es requerido (mínimo 3 caracteres)'
        })

    # Email (opcional pero debe ser válido si se proporciona)
    email = cliente_data.get('email', '').strip()
    if email:
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(email)
        except ValidationError:
            errores.append({
                'campo': 'cliente.email',
                'mensaje': 'Email inválido'
            })

    # Región y Comuna
    region_id = cliente_data.get('region_id')
    comuna_id = cliente_data.get('comuna_id')

    if not region_id:
        errores.append({
            'campo': 'cliente.region_id',
            'mensaje': 'La región es requerida'
        })

    if not comuna_id:
        errores.append({
            'campo': 'cliente.comuna_id',
            'mensaje': 'La comuna es requerida'
        })

    if region_id and comuna_id:
        # Verificar que existan
        if not Region.objects.filter(id=region_id).exists():
            errores.append({
                'campo': 'cliente.region_id',
                'mensaje': f'Región {region_id} no existe'
            })

        if not Comuna.objects.filter(
            id=comuna_id,
            region_id=region_id
        ).exists():
            errores.append({
                'campo': 'cliente.comuna_id',
                'mensaje': f'Comuna {comuna_id} no existe o no pertenece a la región {region_id}'
            })

    return cliente_data, errores


def validar_servicio(servicio_data, index):
    """Validar un servicio individual"""
    errores = []
    prefix = f'servicios[{index}]'

    # Servicio ID
    servicio_id = servicio_data.get('servicio_id')
    if not servicio_id:
        errores.append({
            'campo': f'{prefix}.servicio_id',
            'mensaje': 'El servicio_id es requerido'
        })
        return None, errores

    # Obtener servicio
    try:
        servicio = Servicio.objects.get(
            id=servicio_id,
            activo=True,
            publicado_web=True
        )
    except Servicio.DoesNotExist:
        errores.append({
            'campo': f'{prefix}.servicio_id',
            'mensaje': f'Servicio {servicio_id} no existe o no está disponible'
        })
        return None, errores

    # Fecha
    fecha_str = servicio_data.get('fecha')
    if not fecha_str:
        errores.append({
            'campo': f'{prefix}.fecha',
            'mensaje': 'La fecha es requerida'
        })
        return None, errores

    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        errores.append({
            'campo': f'{prefix}.fecha',
            'mensaje': 'Formato de fecha inválido. Use YYYY-MM-DD'
        })
        return None, errores

    # Verificar fecha no es pasada
    if fecha < datetime.now().date():
        errores.append({
            'campo': f'{prefix}.fecha',
            'mensaje': 'La fecha no puede ser en el pasado'
        })

    # Verificar no es martes (cerrado)
    day_name = fecha.strftime('%A').lower()
    if day_name == 'tuesday':
        errores.append({
            'campo': f'{prefix}.fecha',
            'mensaje': f'Los martes estamos cerrados. La fecha {fecha_str} es martes.'
        })

    # Hora
    hora = servicio_data.get('hora')
    if not hora:
        errores.append({
            'campo': f'{prefix}.hora',
            'mensaje': 'La hora es requerida'
        })
        return None, errores

    # Validar formato HH:MM
    try:
        datetime.strptime(hora, '%H:%M')
    except ValueError:
        errores.append({
            'campo': f'{prefix}.hora',
            'mensaje': 'Formato de hora inválido. Use HH:MM'
        })

    # Cantidad personas
    cantidad_personas = servicio_data.get('cantidad_personas', 1)
    try:
        cantidad_personas = int(cantidad_personas)
    except (TypeError, ValueError):
        errores.append({
            'campo': f'{prefix}.cantidad_personas',
            'mensaje': 'cantidad_personas debe ser un número'
        })
        return None, errores

    # Validar capacidad
    if cantidad_personas < servicio.capacidad_minima:
        errores.append({
            'campo': f'{prefix}.cantidad_personas',
            'mensaje': f'La cantidad mínima es {servicio.capacidad_minima}'
        })

    if cantidad_personas > servicio.capacidad_maxima:
        errores.append({
            'campo': f'{prefix}.cantidad_personas',
            'mensaje': f'La capacidad máxima es {servicio.capacidad_maxima}'
        })

    if errores:
        return None, errores

    # Verificar disponibilidad
    disponibilidad_errores = verificar_disponibilidad_completa(
        servicio,
        fecha,
        hora,
        cantidad_personas,
        prefix
    )

    if disponibilidad_errores:
        errores.extend(disponibilidad_errores)
        return None, errores

    # Servicio validado
    return {
        'servicio': servicio,
        'fecha': fecha,
        'hora': hora,
        'cantidad': cantidad_personas,
        'precio_unitario': servicio.precio_base
    }, []


def verificar_disponibilidad_completa(servicio, fecha, hora, cantidad, prefix):
    """Verificar disponibilidad completa del slot"""
    errores = []

    day_name = fecha.strftime('%A').lower()

    # 1. Verificar slot en horarios configurados
    slots_disponibles = servicio.slots_disponibles
    if not isinstance(slots_disponibles, dict):
        errores.append({
            'campo': f'{prefix}.servicio_id',
            'mensaje': 'El servicio no tiene horarios configurados'
        })
        return errores

    slots_dia = slots_disponibles.get(day_name, [])
    if hora not in slots_dia:
        errores.append({
            'campo': f'{prefix}.hora',
            'mensaje': f'El horario {hora} no está disponible para este servicio en {day_name}'
        })
        return errores

    # 2. Verificar bloqueo de día completo
    if ServicioBloqueo.servicio_bloqueado_en_fecha(servicio.id, fecha):
        errores.append({
            'campo': f'{prefix}.fecha',
            'mensaje': f'El servicio está bloqueado para la fecha {fecha}'
        })
        return errores

    # 3. Verificar bloqueo de slot individual
    from ventas.models import ServicioSlotBloqueo
    if ServicioSlotBloqueo.slot_bloqueado(servicio.id, fecha, hora):
        errores.append({
            'campo': f'{prefix}.hora',
            'mensaje': f'El horario {hora} está bloqueado para {fecha}'
        })
        return errores

    # 4. Verificar capacidad disponible
    from django.db.models import Sum
    reservas_existentes = ReservaServicio.objects.filter(
        servicio=servicio,
        fecha_agendamiento=fecha,
        hora_inicio=hora
    ).exclude(
        venta_reserva__estado_reserva='cancelada'
    ).aggregate(
        total=Sum('cantidad_personas')
    )['total'] or 0

    max_simultaneos = getattr(servicio, 'max_servicios_simultaneos', 1)
    capacidad_total = servicio.capacidad_maxima * max_simultaneos

    if reservas_existentes + cantidad > capacidad_total:
        errores.append({
            'campo': f'{prefix}.cantidad_personas',
            'mensaje': f'Solo hay espacio para {capacidad_total - reservas_existentes} personas en este horario'
        })

    return errores


def serializar_reserva(venta):
    """Serializar VentaReserva para respuesta"""
    servicios_reservados = []

    for reserva_servicio in venta.reservaservicio_set.all():
        # Skip discount services
        if reserva_servicio.precio_unitario_venta and reserva_servicio.precio_unitario_venta < 0:
            continue

        servicios_reservados.append({
            'id': reserva_servicio.id,
            'servicio_nombre': reserva_servicio.servicio.nombre,
            'fecha': reserva_servicio.fecha_agendamiento.strftime('%Y-%m-%d'),
            'hora': reserva_servicio.hora_inicio,
            'cantidad_personas': reserva_servicio.cantidad_personas,
            'precio_unitario': float(reserva_servicio.precio_unitario_venta or reserva_servicio.servicio.precio_base),
            'subtotal': float(reserva_servicio.calcular_precio())
        })

    return {
        'success': True,
        'reserva': {
            'id': venta.id,
            'numero': f'RES-{venta.fecha_creacion.year}-{venta.id}',
            'cliente': {
                'id': venta.cliente.id,
                'nombre': venta.cliente.nombre,
                'telefono': venta.cliente.telefono,
                'email': venta.cliente.email
            },
            'servicios': servicios_reservados,
            'descuentos': [],  # TODO: Extract from negative price services
            'total': float(venta.total),
            'pagado': float(venta.pagado),
            'saldo_pendiente': float(venta.saldo_pendiente),
            'estado_pago': venta.estado_pago,
            'estado_reserva': venta.estado_reserva,
            'fecha_creacion': venta.fecha_creacion.isoformat(),
            'url_detalle': f'https://aremko.cl/reserva/{venta.id}/',
            'instrucciones_pago': 'Transferencia bancaria. Detalles se enviarán por email.'
        }
    }
```

---

## 7. Plan de Implementación por Fases

### ⚠️ Prerequisitos Antes de Comenzar

**CRÍTICO - Hacer backup completo**:
1. ✅ Crear backup manual de base de datos en Render
2. ✅ Descargar backup localmente
3. ✅ Crear tag de git: `git tag pre-luna-api-v1.0`
4. ✅ Respaldar variables de entorno
5. ✅ Documentar estado de migraciones: `python manage.py showmigrations`
6. ✅ Revisar checklist completo en `BACKUP_BEFORE_LUNA_API.md`

**Ventana de implementación recomendada**: Martes tarde (cuando estamos cerrados, bajo tráfico)

---

### Fase 1: Infraestructura Base (2-3 días)

**Tareas:**
1. Crear archivo `ventas/views/luna_api_views.py`
2. Implementar autenticación `LunaAPIKeyAuthentication`
3. Agregar variable de entorno `LUNA_API_KEY` en Render
4. Configurar URLs en `ventas/urls.py`:
   ```python
   path('api/luna/reservas/create', luna_api_views.crear_reserva),
   path('api/luna/regiones', luna_api_views.listar_regiones),
   path('api/luna/reservas/validar', luna_api_views.validar_disponibilidad),
   ```

**Verificaciones**:
- ✅ NO se requieren migraciones (usamos modelos existentes)
- ✅ Solo se agregan archivos nuevos
- ✅ No se modifica la estructura de BD

**Criterio de Éxito:**
- Endpoints responden con autenticación correcta
- Rechazan requests sin API key válida
- Sistema existente sigue funcionando sin cambios

---

### Fase 2: Validaciones (3-4 días)

**Tareas:**
1. Implementar `validar_datos_cliente()`
2. Implementar `validar_servicio()`
3. Implementar `verificar_disponibilidad_completa()`
4. Escribir tests unitarios para cada validación
5. Probar edge cases:
   - Teléfonos con diferentes formatos
   - Fechas pasadas, martes, slots no disponibles
   - Capacidad excedida
   - Servicios inactivos

**Criterio de Éxito:**
- Todos los tests pasan
- Validaciones rechazan datos inválidos con mensajes claros
- Validaciones aceptan datos válidos

---

### Fase 3: Creación de Reservas (3-4 días)

**Tareas:**
1. Implementar `calcular_total_reserva()`
2. Implementar lógica transaccional en `crear_reserva()`
3. Integrar con `ClienteService` existente
4. Implementar serialización de respuesta `serializar_reserva()`
5. Agregar logging para auditoría
6. Implementar idempotencia con cache

**Criterio de Éxito:**
- Crea VentaReserva correctamente
- Crea ReservaServicio para cada servicio
- Cliente se crea o actualiza correctamente
- Totales se calculan correctamente
- Requests duplicados no crean reservas duplicadas

---

### Fase 4: Endpoints Auxiliares (2 días)

**Tareas:**
1. Implementar `GET /api/luna/regiones`
2. Implementar `POST /api/luna/reservas/validar` (pre-validación)
3. Documentar respuestas de error estándar

**Criterio de Éxito:**
- Luna puede obtener lista de regiones/comunas
- Luna puede pre-validar antes de confirmar

---

### Fase 5: Testing e Integración (3-4 días)

**Tareas:**
1. Crear scripts de prueba end-to-end
2. Probar con datos reales en staging
3. Documentar ejemplos de uso para Luna
4. Crear monitoreo y alertas
5. Escribir documentación API completa

**Criterio de Éxito:**
- Reservas se crean exitosamente desde API
- Aparecen correctamente en admin Django
- Clientes reciben confirmaciones
- Luna puede manejar errores correctamente

---

### Fase 6: Deploy y Configuración de Luna (1-2 días)

**Tareas:**
1. Deploy a producción en Render
2. Configurar Luna con nuevo endpoint
3. Actualizar prompt de Luna con instrucciones
4. Probar reservas reales con Luna
5. Monitorear primeras reservas

**Criterio de Éxito:**
- Luna crea reservas exitosamente
- Clientes reciben confirmación
- No hay errores en logs

---

## 8. Consideraciones de Seguridad

1. **Rate Limiting**: Máximo 10 requests/minuto por IP
2. **API Key Rotation**: Cambiar cada 3 meses
3. **Logging**: Registrar todas las requests para auditoría
4. **Validación estricta**: No confiar en datos de entrada
5. **Transacciones atómicas**: Todo-o-nada en creación
6. **Idempotencia**: Prevenir duplicados con idempotency_key

---

## 9. Monitoreo y Alertas

**Métricas a Monitorear:**
- Número de reservas creadas por hora
- Tasa de error (4xx, 5xx)
- Tiempo de respuesta promedio
- Slots no disponibles por conflicto

**Alertas:**
- Tasa de error > 10%
- Tiempo de respuesta > 5 segundos
- Más de 5 conflictos de disponibilidad en 1 hora

---

## 10. Documentación para Luna

### Prompt Actualizado para Luna

```
You are Luna, an AI assistant for Aremko Spa in Puerto Varas, Chile.

## Your Role

You chat with customers via WhatsApp to:
1. Answer questions about services
2. Check availability in real-time
3. **CREATE RESERVATIONS directly in the system**

## Reservation Flow (via WhatsApp Conversation)

1. **Customer asks** about booking a service (tinaja, masaje, cabaña)
2. **You check availability**: GET /ventas/get-available-hours/?servicio_id={ID}&fecha={DATE}
3. **You present** available options to customer in friendly Spanish
4. **You collect** required information through conversation:
   - Full name (nombre completo)
   - Email address
   - Phone number (must be Chilean format +56XXXXXXXXX)
   - ID document (RUT chileno)
   - City (comuna - default: Puerto Varas if not specified)
5. **You confirm** all details with customer before creating
6. **You create** reservation: POST /api/luna/reservas/create
7. **You inform** customer of:
   - Reservation number
   - Total amount to pay
   - Payment instructions (bank transfer details)
   - Confirmation that they'll receive SMS/email

## Creating a Reservation

POST https://aremko.cl/api/luna/reservas/create
Headers:
  X-Luna-API-Key: {YOUR_API_KEY}
  Content-Type: application/json

Body:
{
  "idempotency_key": "unique-conversation-id-timestamp",
  "cliente": {
    "nombre": "Full Name",
    "email": "email@example.com",
    "telefono": "+56912345678",
    "documento_identidad": "12345678-9",
    "region_id": 1,
    "comuna_id": 10
  },
  "servicios": [
    {
      "servicio_id": 12,
      "fecha": "2026-04-01",
      "hora": "14:30",
      "cantidad_personas": 2
    }
  ],
  "metodo_pago": "pendiente",
  "notas": "Booked via WhatsApp conversation {conversation_id}"
}

## Important Rules

- ALWAYS check availability before creating reservation
- ALWAYS confirm all details with customer before creating
- Use idempotency_key to prevent duplicates (use conversation_id + timestamp)
- For region_id, use 1 (Los Lagos)
- For comuna_id, use 10 (Puerto Varas) unless customer specifies
- Phone MUST be in format +56XXXXXXXXX
- Validate Chilean RUT format for documento_identidad
- NEVER create reservation for Tuesday (closed)
- Always inform customer of total price before creating
- After creating, provide reservation number and payment instructions

## Error Handling

If slot becomes unavailable:
- Apologize and check other available times
- Suggest alternative tubs or dates

If validation fails:
- Explain the issue clearly
- Help customer correct the information

If creation fails:
- Apologize and ask customer to try again
- If persists, provide phone number for manual booking
```

---

## 11. Estimación de Esfuerzo

| Fase | Días Estimados | Prioridad |
|------|----------------|-----------|
| Fase 1: Infraestructura | 2-3 | Alta |
| Fase 2: Validaciones | 3-4 | Alta |
| Fase 3: Creación | 3-4 | Alta |
| Fase 4: Auxiliares | 2 | Media |
| Fase 5: Testing | 3-4 | Alta |
| Fase 6: Deploy | 1-2 | Alta |
| **TOTAL** | **14-19 días** | - |

---

## 12. Próximos Pasos

1. **Revisar y aprobar este plan**
2. **Crear branch**: `feature/luna-reservation-api`
3. **Comenzar Fase 1**: Infraestructura base
4. **Testing incremental** después de cada fase
5. **Deploy a staging** después de Fase 3
6. **Deploy a producción** después de Fase 6

---

## Resumen

Este plan permite que Luna cree reservas completas siguiendo el mismo flujo y validaciones que usa el sitio web actual, manteniendo la integridad de datos y proporcionando una experiencia confiable para los clientes.