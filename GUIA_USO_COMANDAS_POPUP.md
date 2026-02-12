# 📖 Guía de Uso: Sistema de Comandas con Popup

## 🎯 Flujo Completo para Agregar Comanda con Productos

### **Desde la Edición de una Reserva**

```
1. Admin → Ventas y CRM → Venta reservas
2. Click en una reserva existente (debe tener ID)
3. Scrollear hasta sección "GESTIÓN DE COMANDAS"
4. Click en botón verde: "➕ Agregar Comanda con Productos"
```

---

### **Se Abre Ventana Popup**

La ventana emergente mostrará el formulario completo de comanda:

#### **Paso 1: Información Básica**
- **Reserva**: Ya pre-seleccionada automáticamente ✅
- **Estado**: Pendiente (default)
- **Fecha/Hora Entrega Objetivo**:
  - Dejar vacío → Inmediato (⚡)
  - Seleccionar HOY + hora → Programado mismo día (🟠/🟢)
  - Seleccionar fecha futura → Programado futuro (🟢)
- **Notas Generales**: Ej: "Cliente en tina 3", "Para llevar a cabaña 5"

#### **Paso 2: Guardar y Continuar**
- Click en **"Guardar y continuar editando"**
- La comanda se crea con ID
- Ahora aparece la sección **"DETALLES DE COMANDA"**

#### **Paso 3: Agregar Productos**
En la sección "Detalles de Comanda":
- **Producto**: Seleccionar del dropdown
- **Cantidad**: Número de unidades
- **Especificaciones**: Ej: "Sin azúcar", "Bien frío", "Para 2 personas"
- **Precio Unitario**: Se llena automáticamente

Puedes agregar múltiples productos:
- Click en "Agregar otro Detalle de comanda"
- Repetir para cada producto

#### **Paso 4: Guardar Final**
- Click en **"Guardar"**
- La ventana popup se cierra automáticamente
- La página de VentaReserva se actualiza sola

---

## ✅ Qué Sucede Automáticamente

### 1. **ReservaProducto se crea solo**
Los productos de la comanda se agregan automáticamente a la sección "PRODUCTOS DE LA RESERVA" de la venta.

### 2. **Usuario Solicita asignado**
El sistema guarda quién creó la comanda.

### 3. **Actualización en tiempo real**
Al cerrar el popup, verás la comanda en la sección "COMANDAS" con:
- ID de la comanda
- Estado con color
- Total de productos
- Fecha objetivo
- Tiempo de espera
- Botón "Editar / Ver Productos"

---

## 🔄 Editar una Comanda Existente

Si necesitas modificar una comanda o ver sus productos:

```
1. En VentaReserva, sección "COMANDAS"
2. Click en botón "✏️ Editar / Ver Productos"
3. Se abre popup con la comanda
4. Modifica lo que necesites
5. Agregar/quitar productos
6. Guardar → cierra y actualiza
```

---

## 🎨 Indicadores Visuales

### **Estados de Comanda (badges)**
- 🟠 **Pendiente**: Naranja - Aún no tomada
- 🔵 **Procesando**: Azul - Cocina trabajando
- 🟢 **Entregada**: Verde - Completada
- 🔴 **Cancelada**: Rojo - Anulada

### **Entrega Objetivo (en listado de comandas)**
- ⚡ **Inmediato**: Gris - Sin hora programada
- 🟢 **Programada**: Verde - Falta más de 2 horas
- 🟠 **Próxima**: Naranja - Falta menos de 2 horas
- 🔴 **Retrasada**: Rojo - Ya pasó la hora

---

## 🧪 Ejemplo Práctico

### **Caso: Cliente pide tabla de quesos para su tina de las 21:00**

#### En VentaReserva del cliente:
```
1. Expandir "Gestión de Comandas"
2. Click "Agregar Comanda con Productos"
```

#### En Popup:
```
3. Reserva: [Ya seleccionada]
4. Estado: Pendiente
5. Fecha entrega objetivo: HOY a las 21:00
6. Notas: "Para tina de las 21:00"
7. Guardar y continuar editando
```

#### Agregar Productos:
```
8. Producto: Tabla de Quesos
9. Cantidad: 1
10. Especificaciones: "Para 2 personas, sin frutos secos"
11. Precio: 15000 (auto)
12. Click "Agregar otro Detalle" si hay más productos
```

#### Finalizar:
```
13. Guardar
14. Popup cierra
15. VentaReserva muestra nueva comanda
16. Productos aparecen en "PRODUCTOS DE LA RESERVA"
```

---

## 📊 Vista desde Admin de Comandas

También puedes ver/gestionar todas las comandas desde:

```
Admin → Ventas y CRM → Comandas
```

Aquí verás:
- Listado completo de todas las comandas
- Filtros por: Estado, Fecha solicitud, Fecha objetivo, Usuario
- Búsqueda por: ID, Nombre cliente, Notas
- Indicadores de urgencia con colores
- Tiempo de espera en minutos

---

## ⚠️ Notas Importantes

### ✅ Ventajas del Sistema Popup
1. **Sin duplicación**: No ingresas productos dos veces
2. **Automático**: ReservaProducto se crea solo
3. **Rápido**: Popup cierra y actualiza automáticamente
4. **Intuitivo**: Flujo familiar de Django Admin
5. **Completo**: Acceso a todas las funciones

### ⚠️ Limitaciones
1. **Requiere guardar reserva primero**: La VentaReserva debe tener ID
2. **No nested inline**: Por eso usamos popup (limitación de Django)
3. **Requiere JavaScript**: Browser debe tener JS habilitado

---

## 🔧 Troubleshooting

### **Problema**: Botón no aparece
**Solución**: Asegúrate de que la reserva ya está guardada (tiene ID)

### **Problema**: Popup no cierra automáticamente
**Solución**:
- Verificar que JavaScript está habilitado
- Refrescar manualmente (F5) después de guardar

### **Problema**: Venta_reserva no pre-seleccionada
**Solución**:
- Verificar que el botón se clickeó desde VentaReserva
- Si abriste directo desde Admin→Comandas, selecciona manualmente

---

## 🚀 Próximos Pasos

Una vez que las comandas estén creadas:

### **FASE 2** (Próxima implementación):
- **Vista Cocina**: Pantalla para cocina/bar con comandas activas del día
- **Vista Historial**: Búsqueda de comandas pasadas
- **Notificaciones**: Alertas cuando se acerca hora objetivo

---

¡Sistema listo para usar! 🎉
