# Guía de Verificación Manual - Sistema de Comandas

## Pasos para Verificar el Sistema de Comandas

### 1. Ejecutar Diagnóstico Automático

```bash
# Activar entorno virtual (si existe)
source venv/bin/activate  # o el nombre de tu entorno

# Ejecutar el diagnóstico
python3 manage.py shell < diagnostico_comandas_simple.py
```

### 2. Verificación Manual en el Admin

#### Paso 1: Acceder al Admin
1. Ir a `/admin/`
2. Iniciar sesión con credenciales de administrador

#### Paso 2: Crear una Comanda desde VentaReserva
1. Ir a **Ventas y Reservas** → **Venta/Reservas**
2. Elegir una reserva confirmada
3. Hacer clic en el botón **"➕ Agregar Comanda con Productos"**

#### Paso 3: Verificar el Formulario
El formulario debe mostrar:
- [ ] **Venta/Reserva**: Pre-seleccionada (campo autocomplete)
- [ ] **Estado**: "pendiente" por defecto
- [ ] **Fecha/Hora Entrega Objetivo**: Campo de fecha/hora
- [ ] **Usuario que Solicita**: Pre-seleccionado con "Deborah"
- [ ] **Usuario que Procesa**: Pre-seleccionado con "Ernesto"
- [ ] **NO** debe aparecer el campo "Notas Generales"

#### Paso 4: Agregar Productos
1. Hacer clic en **"Agregar otro Detalle de Comanda"**
2. En el formulario inline verificar:
   - [ ] **Producto**: Campo con autocomplete (buscar por nombre)
   - [ ] **Cantidad**: Campo numérico
   - [ ] **Especificaciones**: Campo de texto limitado a 30 caracteres
   - [ ] **Precio Unitario**: Campo de solo lectura (gris)

#### Paso 5: Guardar y Verificar
1. Agregar al menos 1 producto
2. Hacer clic en **"GUARDAR"**
3. Verificar:
   - [ ] ✅ NO aparece Error 500
   - [ ] ✅ El popup se cierra automáticamente
   - [ ] ✅ La página principal se recarga

#### Paso 6: Verificar Datos Guardados
1. En la lista de comandas del VentaReserva, verificar la nueva comanda
2. Hacer clic en la comanda para editarla
3. Verificar:
   - [ ] El precio unitario se llenó automáticamente con el precio base del producto
   - [ ] Los datos se guardaron correctamente

### 3. Verificar ReservaProducto

```bash
# En el shell de Django
python3 manage.py shell

from ventas.models import Comanda, ReservaProducto

# Obtener la última comanda
ultima_comanda = Comanda.objects.latest('id')
print(f"Comanda ID: {ultima_comanda.id}")

# Verificar ReservaProducto creados
if ultima_comanda.venta_reserva:
    for detalle in ultima_comanda.detalles.all():
        rp = ReservaProducto.objects.filter(
            venta_reserva=ultima_comanda.venta_reserva,
            producto=detalle.producto
        ).first()
        if rp:
            print(f"✅ ReservaProducto existe para {detalle.producto.nombre}")
            print(f"   Cantidad: {rp.cantidad}")
            print(f"   Precio: ${rp.precio_unitario_venta}")
            print(f"   Notas: {rp.notas}")
        else:
            print(f"❌ NO existe ReservaProducto para {detalle.producto.nombre}")
```

### 4. Problemas Comunes y Soluciones

#### Error 500 al Guardar
- **Causa**: Problema con la creación de ReservaProducto
- **Revisar**: Logs en Render para ver el traceback completo
- **Solución**: Verificar que venta_reserva no sea None

#### Usuarios No Pre-seleccionados
- **Causa**: Los usernames son case-sensitive
- **Verificar**:
  ```sql
  SELECT username FROM auth_user WHERE username ILIKE '%deborah%' OR username ILIKE '%ernesto%';
  ```

#### Precio Unitario No se Auto-llena
- **Causa**: El campo está en readonly pero el modelo no guarda el valor
- **Verificar**: Que el método save() de DetalleComanda se ejecute

### 5. Checklist Final

- [ ] ✅ El popup se abre sin errores
- [ ] ✅ El formulario carga rápidamente
- [ ] ✅ Los campos autocomplete funcionan (no dropdowns largos)
- [ ] ✅ Usuarios pre-seleccionados correctamente
- [ ] ✅ Se pueden agregar productos
- [ ] ✅ El precio se auto-llena desde producto.precio_base
- [ ] ✅ Se guarda sin Error 500
- [ ] ✅ Se crean los ReservaProducto correspondientes
- [ ] ✅ El popup se cierra y recarga la página principal

### 6. Si Todo Funciona

Si todas las verificaciones pasan, el sistema de comandas está funcionando correctamente.

### 7. Si Hay Problemas

1. Revisar logs en Render
2. Ejecutar el diagnóstico automático
3. Revisar el documento `COMANDAS_TROUBLESHOOTING.md` para soluciones conocidas