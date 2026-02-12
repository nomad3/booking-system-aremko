# 📋 Análisis de Casos de Uso - Sistema de Comandas

## 🎯 Flujo de Trabajo Real en Aremko

### **FASE 1: Reserva Anticipada (WhatsApp)**

**Momento**: Cliente reserva días/horas antes

**Productos típicos**:
- ❌ Servicios: tinas, masajes, cabañas → **NO son comandas**
- ✅ Productos: tablas de queso, cecinas → **¿Van como comandas?**
- ❌ Desayunos: tienen hora agendada → **Son servicios, NO comandas**

**¿Estos productos van como comanda?**
- 🤔 **OPCIÓN A**: NO, se agregan como ReservaProducto simple
- 🤔 **OPCIÓN B**: SÍ, se crea comanda con fecha futura de entrega

---

### **FASE 2: Cliente en el Lugar (Post Check-in)**

#### Caso 2A: Pedido Inmediato
```
Cliente está en tina → Pide café
Vendedora recibe WhatsApp → Crea comanda
Cocina ve comanda → Prepara
Personal entrega → Marca entregada
```
**Claridad**: ✅ Este es el caso perfecto para comandas

#### Caso 2B: Pedido Programado
```
16:00 → Cliente pide "tabla quesos para mi tina de 21:00"
Vendedora recibe WhatsApp → Crea comanda con hora objetivo 21:00
Cocina ve comanda → Prepara cerca de las 21:00
Personal entrega a las 21:00 → Marca entregada
```
**Claridad**: ✅ Comanda con hora de entrega objetivo

---

## 🔍 Pregunta Clave que Planteas

### **¿Qué pasa con productos agregados para días futuros?**

**Escenario**:
- Hoy Lunes vendedora agrega tabla de quesos para reserva del Viernes
- ¿Aparece en Vista Cocina el Viernes?
- ¿O se crea la comanda el mismo día de entrega?

---

## 💡 Análisis y Propuesta

### **CONCEPTO CLAVE: Separar VENTA de OPERACIÓN**

```
┌─────────────────────────────────────────────────┐
│                 FLUJO PROPUESTO                  │
└─────────────────────────────────────────────────┘

VENTA (Contabilidad)          OPERACIÓN (Cocina)
      ↓                              ↓
ReservaProducto                  Comanda
- Se cobra                       - Se prepara
- Afecta total                   - Se entrega
- Fecha de venta                 - Fecha/hora entrega
```

### **SOLUCIÓN PROPUESTA: Sistema Híbrido Integrado**

#### 1. **Comanda SIEMPRE crea ReservaProducto automáticamente**

Cuando se crea una Comanda:
```python
def save(self):
    super().save()

    # Auto-crear ReservaProducto por cada DetalleComanda
    for detalle in self.detalles.all():
        ReservaProducto.objects.get_or_create(
            venta_reserva=self.venta_reserva,
            producto=detalle.producto,
            cantidad=detalle.cantidad,
            precio_unitario_venta=detalle.precio_unitario,
            fecha_entrega=self.fecha_entrega_objetivo  # NUEVO CAMPO
        )
```

**Resultado**:
- ✅ Comanda se usa para seguimiento operativo
- ✅ ReservaProducto se usa para cobro
- ✅ No hay duplicación de trabajo
- ✅ Un solo punto de entrada (crear comanda)

---

#### 2. **Agregar campo `fecha_entrega_objetivo` a Comanda**

```python
class Comanda:
    # ... campos existentes ...

    fecha_entrega_objetivo = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha/Hora Entrega Objetivo',
        help_text='Para cuándo se necesita este pedido. Si es vacío, es para ahora.'
    )
```

**Uso**:
- Cliente pide "tabla para las 21:00" → `fecha_entrega_objetivo = hoy 21:00`
- Cliente pide "tabla para el viernes" → `fecha_entrega_objetivo = viernes 16:00`
- Cliente pide "café ahora" → `fecha_entrega_objetivo = NULL` (inmediato)

---

#### 3. **Vista Cocina filtra por fecha de entrega**

```python
# Vista Cocina muestra comandas de HOY según hora objetivo
comandas_hoy = Comanda.objects.filter(
    Q(fecha_entrega_objetivo__date=hoy) |  # Programadas para hoy
    Q(fecha_entrega_objetivo__isnull=True, fecha_solicitud__date=hoy),  # Inmediatas de hoy
    estado__in=['pendiente', 'procesando']
)
```

**Resultado**:
- ✅ Viernes a las 16:00 → Cocina ve "tabla quesos para 21:00" (4 horas antes)
- ✅ Comanda programada para Viernes NO aparece el Lunes
- ✅ Comandas inmediatas aparecen de inmediato

---

## 🎯 Respuestas a tus Preguntas

### **¿Productos para días futuros aparecen como comanda en día correspondiente?**

**Respuesta**: ✅ **SÍ**, usando `fecha_entrega_objetivo`

**Ejemplo**:
```
Lunes 10:00 → Vendedora crea comanda "tabla quesos"
              fecha_entrega_objetivo = Viernes 20:00

Lunes-Jueves → NO aparece en Vista Cocina
Viernes 16:00 → Aparece en Vista Cocina (4h antes de entrega)
Viernes 20:00 → Personal entrega
```

---

### **¿Cada vez que se agregan productos se crea comanda?**

**Respuesta**: ✅ **SÍ**, incluso para días futuros

**Beneficios**:
- ✅ Seguimiento desde que se pide hasta que se entrega
- ✅ Cocina/bar sabe qué preparar y cuándo
- ✅ No se olvidan pedidos programados
- ✅ Historial completo de pedidos

---

### **¿Qué pasa si vendedora NO quiere crear comanda?**

**Respuesta**: Puede agregar ReservaProducto directo (método actual)

**Casos**:
- Producto ya entregado (legacy)
- Corrección de precio
- Producto que no requiere preparación

**Pero**: Lo normal será crear siempre comanda

---

## 🔄 Flujos Completos

### **FLUJO A: Producto Inmediato**

```
1. Cliente en tina pide café (16:30)
2. Vendedora recibe WhatsApp
3. Vendedora crea Comanda:
   - Productos: 1x Café
   - Especificaciones: Sin azúcar
   - Fecha entrega objetivo: AHORA (NULL o 16:30)
4. Auto-crea ReservaProducto (para cobro)
5. Cocina ve inmediatamente en Vista Cocina
6. Cocina prepara y entrega
7. Marca como Entregada
```

**Timeline**:
```
16:30 → Comanda creada (Pendiente)
16:35 → Cocina toma comanda (Procesando)
16:40 → Entregada
```

---

### **FLUJO B: Producto Programado Mismo Día**

```
1. Cliente en recepción (16:00) pide "tabla para mi tina de 21:00"
2. Vendedora recibe pedido
3. Vendedora crea Comanda:
   - Productos: 1x Tabla Quesos
   - Especificaciones: Para 2 personas
   - Fecha entrega objetivo: HOY 21:00
4. Auto-crea ReservaProducto
5. Vista Cocina muestra con hora objetivo
6. Cocina prepara cerca de las 21:00
7. Entrega a las 21:00
8. Marca como Entregada
```

**Timeline**:
```
16:00 → Comanda creada (Pendiente)
20:30 → Cocina toma comanda (Procesando)
20:50 → Prepara
21:00 → Entrega
21:00 → Marca Entregada
```

---

### **FLUJO C: Producto Programado Días Futuros**

```
1. Lunes cliente reserva para Viernes (incluye tabla quesos)
2. Vendedora crea Comanda:
   - Productos: 1x Tabla Quesos
   - Fecha entrega objetivo: VIERNES 20:00
3. Auto-crea ReservaProducto (ya se cobra en la reserva)
4. Lunes-Jueves: NO aparece en Vista Cocina
5. Viernes 16:00: Aparece en Vista Cocina
6. Cocina prepara
7. Entrega y marca como Entregada
```

**Timeline**:
```
Lunes 10:00 → Comanda creada (Pendiente)
↓ (4 días oculta)
Viernes 16:00 → Aparece en Vista Cocina
Viernes 19:30 → Cocina toma (Procesando)
Viernes 20:00 → Entregada
```

---

## 🎨 Diseño de Interfaz

### **Crear Comanda (Formulario)**

```
┌─────────────────────────────────────────────┐
│ Crear Comanda                               │
├─────────────────────────────────────────────┤
│ Reserva: [Juan Pérez - #156      ] 🔍      │
│                                             │
│ ⏰ Entrega:                                 │
│ ○ Ahora (inmediato)                        │
│ ○ Hoy a las [21:00  ]                      │
│ ● Fecha específica: [12/02 ▼] [20:00 ▼]   │
│                                             │
│ 🛒 Productos:                              │
│ ┌─────────────────────────────────────┐   │
│ │ [Café       ▼] [2] [Sin azúcar    ] │   │
│ │ [Tabla Queso▼] [1] [Para 2 person.] │   │
│ └─────────────────────────────────────┘   │
│ [+ Agregar producto]                       │
│                                             │
│ Notas: [_____________________________]     │
│                                             │
│ [Cancelar] [✅ Crear Comanda]              │
└─────────────────────────────────────────────┘
```

---

### **Vista Cocina (Con hora objetivo)**

```
┌─────────────────────────────────────────────┐
│ 🍽️ COMANDAS ACTIVAS - Viernes 12/02        │
├─────────────────────────────────────────────┤
│ 🔴 URGENTE (pasó la hora objetivo)          │
│ ┌─────────────────────────────────────────┐ │
│ │ #125 | 20:00 ⏰ | Juan Pérez            │ │
│ │ Retrasada: 15 min                       │ │
│ │ • 1x Tabla Quesos (para 2)              │ │
│ │ [Marcar Entregada]                      │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ 🟠 PRÓXIMAS (en las próximas 2 horas)       │
│ ┌─────────────────────────────────────────┐ │
│ │ #126 | 21:00 🕐 | María López           │ │
│ │ Falta: 45 min para entrega              │ │
│ │ • 2x Café (sin azúcar)                  │ │
│ │ [Tomar Comanda]                         │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ 🟢 PENDIENTES (más de 2 horas)              │
│ ┌─────────────────────────────────────────┐ │
│ │ #127 | 22:30 🕥 | Pedro Silva           │ │
│ │ Falta: 3h 15min                         │ │
│ │ • 1x Tabla Cecinas                      │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

---

## ✅ Ventajas de esta Solución

1. ✅ **Un solo punto de entrada**: Todo producto va vía comanda
2. ✅ **Auto-sincronización**: Comanda crea ReservaProducto automáticamente
3. ✅ **Programación**: Comandas aparecen el día/hora correcta
4. ✅ **Seguimiento completo**: Desde solicitud hasta entrega
5. ✅ **No duplicación**: Personal solo crea comanda, no dos cosas
6. ✅ **Flexibilidad**: Inmediato, mismo día, o días futuros
7. ✅ **Historial**: Sabes cuándo se pidió y cuándo se entregó

---

## 🚀 Implementación

### **Cambios Necesarios**:

1. ✅ Agregar campo `fecha_entrega_objetivo` a Comanda
2. ✅ Auto-crear ReservaProducto cuando se guarda Comanda
3. ✅ Vista Cocina filtra por fecha objetivo
4. ✅ Mostrar tiempo faltante/retrasado según hora objetivo
5. ✅ Ordenar por urgencia (retrasadas primero, luego por hora)

---

¿Te parece bien esta solución? ¿Implementamos estos cambios?
