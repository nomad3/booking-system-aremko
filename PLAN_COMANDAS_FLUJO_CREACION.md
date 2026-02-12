# 🍽️ Flujo de Creación de Comandas - Análisis UX

## 🎯 Pregunta Clave

**¿Dónde y cuándo se crean las comandas?**

---

## 🔄 Análisis de Escenarios Reales

### Escenario 1: Cliente con Reserva en Curso
```
Cliente → En cabaña/tinas/masaje → Pide café → Personal toma pedido
```
**Necesidad**: Crear comanda RÁPIDO sin interrumpir atención

### Escenario 2: Cliente Walk-in (Sin reserva previa)
```
Cliente → Llega sin reserva → Se crea reserva → Pide productos
```
**Necesidad**: Crear comanda desde la reserva nueva

### Escenario 3: Reserva ya existía, cliente pide después
```
Reserva creada hace horas/días → Cliente llega → Pide productos
```
**Necesidad**: Agregar comanda a reserva existente

---

## ✅ Solución Propuesta: 3 Puntos de Acceso

### **PUNTO 1: Desde Admin de VentaReserva (Editar Reserva)**

**Ubicación**: Al editar una VentaReserva en Django Admin

**Vista**:
```
┌─────────────────────────────────────────────────┐
│  Cambiar venta reserva                          │
├─────────────────────────────────────────────────┤
│  Cliente: Juan Pérez                            │
│  Fecha: 12/02/2026                              │
│  Estado: Pagado                                 │
│                                                  │
│  ┌────────────────────────────────────┐         │
│  │ 📦 SERVICIOS                       │         │
│  │ - Tinas Hot Tub (2 personas)      │         │
│  │ - Masaje Relajante                │         │
│  └────────────────────────────────────┘         │
│                                                  │
│  ┌────────────────────────────────────┐         │
│  │ 🛍️ PRODUCTOS                       │         │
│  │ (Aquí van los productos normales)  │         │
│  └────────────────────────────────────┘         │
│                                                  │
│  ┌────────────────────────────────────┐         │
│  │ 🍽️ COMANDAS                        │         │
│  │                                     │         │
│  │ Comandas de esta reserva:           │         │
│  │                                     │         │
│  │ ┌──────────────────────────────┐   │         │
│  │ │ Comanda #125 - 14:30         │   │         │
│  │ │ Estado: Entregada            │   │         │
│  │ │ 2x Café, 1x Jugo Natural     │   │         │
│  │ └──────────────────────────────┘   │         │
│  │                                     │         │
│  │ [➕ Agregar Nueva Comanda]         │         │
│  │                                     │         │
│  └────────────────────────────────────┘         │
│                                                  │
│  [Guardar] [Guardar y continuar] [Eliminar]    │
└─────────────────────────────────────────────────┘
```

**Flujo**:
1. Personal abre la reserva en admin
2. Ve sección "COMANDAS" al final (después de servicios/productos)
3. Click en [➕ Agregar Nueva Comanda]
4. Se abre modal/inline para agregar productos con especificaciones
5. Guarda la comanda (queda asociada a la reserva)
6. **Automáticamente aparece en Vista Cocina**

**Implementación**:
```python
# En ventas/admin.py

class ComandaInline(admin.StackedInline):  # O TabularInline
    model = Comanda
    extra = 0  # No mostrar formularios vacíos por defecto
    readonly_fields = ('fecha_solicitud', 'hora_solicitud', 'estado', 'tiempo_espera_display')
    fields = ('estado', 'notas_generales', 'fecha_solicitud', 'hora_solicitud', 'tiempo_espera_display')
    can_delete = False  # No permitir eliminar desde aquí

    def tiempo_espera_display(self, obj):
        if obj.pk:
            return f"{obj.tiempo_espera()} minutos"
        return "-"
    tiempo_espera_display.short_description = "Tiempo Espera"

class VentaReservaAdmin(admin.ModelAdmin):
    # ... configuración existente ...

    inlines = [
        ReservaServicioInline,
        ReservaProductoInline,
        GiftCardInline,
        PagoInline,
        ComandaInline,  # ← NUEVO
    ]

    # Agregar botón rápido en la parte superior
    def render_change_form(self, request, context, *args, **kwargs):
        obj = context.get('original')
        if obj and obj.pk:
            context['show_comanda_button'] = True
            context['reserva_id'] = obj.pk
        return super().render_change_form(request, context, *args, **kwargs)
```

**Ventajas**:
- ✅ Contexto completo de la reserva
- ✅ Se ve todo en un solo lugar
- ✅ Natural para recepción

**Desventajas**:
- ⚠️ Requiere cargar toda la reserva (puede ser lento)
- ⚠️ Varios clicks para llegar

---

### **PUNTO 2: Botón Rápido "Tomar Pedido"**

**Ubicación**: En Control de Gestión, junto a Vista Cocina

**Vista**:
```
┌─────────────────────────────────────────────┐
│  Control de Gestión                         │
├─────────────────────────────────────────────┤
│  [📅 Agenda] [🍽️ Comandas] [📦 Inventario]  │
└─────────────────────────────────────────────┘

Al hacer click en "Comandas":

┌─────────────────────────────────────────────┐
│  🍽️ Sistema de Comandas                     │
│  [🔥 Vista Cocina] [📋 Historial]           │
│                                              │
│  [➕ Tomar Pedido Rápido]  ← BOTÓN NUEVO    │
└─────────────────────────────────────────────┘
```

**Formulario Modal Rápido**:
```
┌─────────────────────────────────────────────┐
│  📝 Tomar Pedido                             │
├─────────────────────────────────────────────┤
│                                              │
│  Cliente/Reserva: [Buscar...        ] 🔍    │
│  (Autocomplete por nombre cliente/ID)       │
│                                              │
│  Productos:                                  │
│  ┌────────────────────────────────────────┐ │
│  │ Producto      | Cant | Especificaciones││ │
│  ├────────────────────────────────────────┤ │
│  │ [Café       ▼]│ [1] │ [Sin azúcar    ] ││ │
│  │ [Jugo Nat.  ▼]│ [1] │ [Frutilla      ] ││ │
│  │ [Agua       ▼]│ [2] │ [              ] ││ │
│  └────────────────────────────────────────┘ │
│  [+ Agregar Producto]                        │
│                                              │
│  Notas generales:                            │
│  [________________________________]          │
│  [________________________________]          │
│                                              │
│  [Cancelar] [✅ Enviar a Cocina]            │
└─────────────────────────────────────────────┘
```

**Flujo**:
1. Personal en cualquier parte (cocina, recepción, piso)
2. Click en "Tomar Pedido Rápido"
3. Busca cliente o reserva (autocomplete)
4. Agrega productos con especificaciones
5. "Enviar a Cocina"
6. Modal se cierra, comanda aparece en Vista Cocina

**Implementación**:
```python
# ventas/views/comandas_view.py

@login_required
def tomar_pedido_rapido(request):
    """Vista para tomar pedido rápido"""
    if request.method == 'POST':
        venta_reserva_id = request.POST.get('venta_reserva_id')
        notas_generales = request.POST.get('notas_generales')

        # Crear comanda
        comanda = Comanda.objects.create(
            venta_reserva_id=venta_reserva_id,
            notas_generales=notas_generales,
            usuario_solicita=request.user,
            estado='pendiente'
        )

        # Agregar detalles
        # ... (procesar productos del POST)

        return JsonResponse({'success': True, 'comanda_id': comanda.id})

    # GET: mostrar formulario
    context = {
        'productos': Producto.objects.filter(publicado_web=True).order_by('nombre')
    }
    return render(request, 'ventas/comandas/tomar_pedido.html', context)
```

**Ventajas**:
- ✅ Súper rápido (3-4 clicks)
- ✅ No requiere abrir la reserva completa
- ✅ Ideal para personal de piso

**Desventajas**:
- ⚠️ Requiere buscar la reserva primero
- ⚠️ No ve contexto completo de la reserva

---

### **PUNTO 3: Desde Listado de VentaReservas**

**Ubicación**: En el listado de admin de VentaReservas

**Vista**:
```
┌──────────────────────────────────────────────────────────────────┐
│  Venta reservas                                                   │
├──────────────────────────────────────────────────────────────────┤
│  ID | Cliente      | Fecha       | Total    | Acciones          │
├──────────────────────────────────────────────────────────────────┤
│  156│ Juan Pérez   │ 12/02/2026  │ $85,000  │ [📋][💰][🍽️]     │
│  155│ María López  │ 12/02/2026  │ $120,000 │ [📋][💰][🍽️]     │
│  154│ Pedro Silva  │ 11/02/2026  │ $95,000  │ [📋][💰][🍽️]     │
└──────────────────────────────────────────────────────────────────┘

[📋] = Ver reserva
[💰] = Ver cotización/resumen
[🍽️] = Tomar pedido rápido  ← NUEVO
```

**Flujo**:
1. Personal ve lista de reservas de hoy
2. Identifica la reserva del cliente
3. Click en botón 🍽️ directamente
4. Se abre modal de pedido rápido (pre-seleccionada la reserva)
5. Agrega productos
6. Envía a cocina

**Implementación**:
```python
# En ventas/admin.py, dentro de VentaReservaAdmin

def acciones_rapidas(self, obj):
    """Botones de acción rápida en el listado"""
    return format_html(
        '<a class="button" href="{}" title="Ver reserva">📋</a> '
        '<a class="button" href="{}" target="_blank" title="Cotización">💰</a> '
        '<a class="button comanda-rapida" data-reserva-id="{}" title="Tomar pedido">🍽️</a>',
        reverse('admin:ventas_ventareserva_change', args=[obj.pk]),
        reverse('ventas:generar_cotizacion', args=[obj.pk]),
        obj.pk
    )
acciones_rapidas.short_description = 'Acciones'

list_display = (
    # ... campos existentes ...
    'acciones_rapidas',  # ← NUEVO
)
```

**Ventajas**:
- ✅ Muy rápido desde el listado
- ✅ Visual: ve todas las reservas de un vistazo
- ✅ Ideal para días con muchas reservas

**Desventajas**:
- ⚠️ Requiere JavaScript para el modal

---

## 🎯 Recomendación: Implementar los 3 Puntos

### **Flujo Completo Propuesto:**

```
┌─────────────────────────────────────────────────────────────┐
│                    CREAR COMANDA                             │
└─────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓

┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  OPCIÓN 1   │    │  OPCIÓN 2   │    │  OPCIÓN 3   │
│             │    │             │    │             │
│ Desde Admin │    │   Botón     │    │ Desde       │
│  Reserva    │    │  "Tomar     │    │ Listado     │
│  (Inline)   │    │  Pedido"    │    │ Reservas    │
└─────────────┘    └─────────────┘    └─────────────┘
      │                   │                   │
      └───────────────────┼───────────────────┘
                          ↓
                 ┌─────────────────┐
                 │  COMANDA CREADA │
                 └─────────────────┘
                          ↓
                 ┌─────────────────┐
                 │  VISTA COCINA   │
                 │  (Auto-aparece) │
                 └─────────────────┘
```

---

## 📱 Separación de Módulos

### **MÓDULO OPERATIVO** (Control de Gestión)
```
URL: /ventas/comandas/

Funciones:
├── 🔥 Vista Cocina (ver comandas activas)
├── 📋 Historial (buscar comandas antiguas)
└── ➕ Tomar Pedido Rápido (crear comanda rápida)
```

### **MÓDULO ADMIN** (Django Admin)
```
URL: /admin/ventas/ventareserva/

Funciones:
├── Ver/Editar reserva completa
├── Inline de Comandas (ver comandas de esta reserva)
└── Botón crear comanda desde reserva
```

---

## 🎨 Priorización de Implementación

### **FASE 1 (MVP)**: Opción 1 - Inline en Admin
**Por qué primero:**
- ✅ Más fácil de implementar (usa sistema existente de inlines)
- ✅ No requiere nueva UI
- ✅ Funciona desde día 1

**Código:**
```python
# Agregar inline a VentaReservaAdmin
inlines = [
    # ... existentes ...
    ComandaInline,  # Solo esto
]
```

### **FASE 2**: Vista Cocina + Historial
**Por qué segundo:**
- ✅ Es donde el personal VA A VER las comandas
- ✅ Crítico para operación diaria

### **FASE 3**: Opción 2 - Botón "Tomar Pedido Rápido"
**Por qué tercero:**
- ✅ Mejora UX
- ✅ Agiliza proceso
- ✅ Requiere más desarrollo (modal, AJAX)

### **FASE 4 (Opcional)**: Opción 3 - Botones en Listado
**Por qué opcional:**
- ✅ Nice to have
- ✅ Similar a Opción 2
- ⚠️ Puede ser confuso si hay demasiados botones

---

## 🔄 Flujo de Datos Completo

### Ciclo de Vida de una Comanda:

```
1. CREACIÓN (Desde Admin/Tomar Pedido)
   ↓
2. PENDIENTE (Aparece en Vista Cocina - Rojo si >20min)
   ↓
3. Personal de cocina click "Tomar Comanda"
   ↓
4. PROCESANDO (Cambia color a azul)
   ↓
5. Personal prepara pedido
   ↓
6. Personal click "Marcar Entregada"
   ↓
7. ENTREGADA (Se oculta de Vista Cocina, va a Historial)
   ↓
8. Si pasaron >30 días → Auto-eliminada (opcional)
```

---

## ✅ Decisión Final Recomendada

### **Implementar en este orden:**

1. **PRIMERO**: Inline en Admin de VentaReserva
   - Razón: Fácil, rápido, funcional desde día 1

2. **SEGUNDO**: Vista Cocina + Historial
   - Razón: Core del sistema operativo

3. **TERCERO**: Botón "Tomar Pedido Rápido" en Control de Gestión
   - Razón: Optimiza UX para personal

4. **CUARTO** (opcional): Botones en listado
   - Razón: Mejora nice-to-have

---

## 📝 Resumen de Ubicaciones

| Función | Ubicación | URL | Quién lo usa |
|---------|-----------|-----|--------------|
| **Crear Comanda** | Admin VentaReserva (inline) | `/admin/ventas/ventareserva/X/change/` | Recepción |
| **Crear Comanda** | Botón "Tomar Pedido" | `/ventas/comandas/tomar-pedido/` | Todos |
| **Ver Comandas Activas** | Vista Cocina | `/ventas/comandas/` | Cocina/Bar |
| **Buscar Historial** | Vista Historial | `/ventas/comandas/historial/` | Administración |
| **Procesar Comanda** | Vista Cocina (botones) | `/ventas/comandas/X/tomar/` | Cocina/Bar |

---

¿Te parece bien este flujo? ¿Empezamos por el inline en Admin?
