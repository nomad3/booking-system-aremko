# Análisis del Problema: Premios Incorrectos (Caso Premio #54)

## 📋 Descripción del Problema

**Cliente afectado:** Francisca Cuevas Parga
**Premio generado:** #54 - Descuento de Bienvenida (Primera Compra)
**Problema:** Se generó premio de "Primera Compra" para clienta con 8 servicios históricos

## 📊 Datos del Cliente

```
Cliente: Francisca Cuevas Parga
Teléfono: +56940714351
Email: facuevas1@uc.cl
Ciudad: Valdivia
Días como cliente: 1555 días (desde 09/08/2021)
```

### Historial de Servicios

- **Total servicios:** 9
  - Servicios actuales (VentaReserva): 1
  - Servicios históricos: 8

### Historial de Compras

- **Gasto total:** $409,000
  - Gasto histórico: $0 (problema identificado)
  - Gasto actual: $409,000

**Ticket promedio:** $45,444

### Categorías Favoritas

1. Tinas Calientes: $100,000 (3 servicios)
2. Cabañas: $139,000 (2 servicios)
3. Masajes: $80,000 (2 servicios)

## 🔍 Análisis de la Causa Raíz

### 1. Comando `procesar_premios_bienvenida.py` (Líneas 93-103)

```python
# Verificar si esta es su PRIMERA reserva de servicio
primera_reserva = ReservaServicio.objects.filter(
    venta_reserva__cliente=cliente
).order_by('fecha_agendamiento', 'id').first()

if not primera_reserva or primera_reserva.fecha_agendamiento != fecha_objetivo:
    stats['no_es_primera_reserva'] += 1
    continue
```

**❌ PROBLEMA:** Solo busca en la tabla `ReservaServicio` que pertenece al sistema ACTUAL.
**❌ NO considera** la tabla de servicios históricos.

### 2. Signal `actualizar_tramo_y_premios_on_pago` (ventas/signals.py)

```python
@receiver(post_save, sender=VentaReserva)
def actualizar_tramo_y_premios_on_pago(sender, instance, created, raw, using, update_fields, **kwargs):
    """
    Signal que detecta cuando una VentaReserva es pagada y actualiza el tramo del cliente.

    NOTA: El premio de bienvenida ahora se genera con delay de 3 días después del check-in
    mediante el comando: python manage.py procesar_premios_bienvenida
    """
```

**El signal NO genera premios de bienvenida**, solo actualiza tramos y genera premios por hitos.

### 3. Método `TramoService.es_cliente_nuevo()` (Correcto ✅)

```python
@classmethod
def es_cliente_nuevo(cls, cliente: Cliente) -> bool:
    """
    Determina si un cliente es "nuevo" para el sistema de premios

    Definición: Cliente sin servicios previos (ni actuales ni históricos)
    """
    try:
        datos_360 = CRMService.get_customer_360(cliente.id)
        total_servicios = datos_360['metricas']['total_servicios']
        return total_servicios == 0  # ✅ Considera históricos
    except Exception as e:
        logger.error(f"Error verificando si cliente {cliente.id} es nuevo: {e}")
        return False
```

**✅ Este método SÍ considera servicios históricos**, pero NO se está usando en el comando de premios.

### 4. Método `TramoService.calcular_gasto_cliente()` (Problema Parcial ⚠️)

```python
@classmethod
def calcular_gasto_cliente(cls, cliente: Cliente) -> Decimal:
    """
    Calcula el gasto total de un cliente (histórico + actual)
    Usa CRMService para obtener datos consistentes
    """
    try:
        datos_360 = CRMService.get_customer_360(cliente.id)
        gasto_total = datos_360['metricas']['gasto_total']
        return Decimal(str(gasto_total))
    except Exception as e:
        logger.error(f"Error calculando gasto de cliente {cliente.id}: {e}")
        return Decimal('0')
```

**⚠️ PROBLEMA SECUNDARIO:** En el caso de Francisca:
- `gasto_total` = $409,000 ✅
- `gasto_historico` = $0 ❌ (debería ser $369,000)
- `gasto_actual` = $409,000 ❌ (debería ser $40,000)

Esto sugiere que hay un problema en `CRMService.get_customer_360()` o en cómo se están importando los históricos.

## 🎯 Impacto del Problema

### Cliente afectado directamente:
- **Francisca Cuevas Parga**: Recibió premio de "Primera Compra" cuando debería recibir premio de **Tramo 9** ($400,000-$450,000)

### Otros clientes potencialmente afectados:
- Cualquier cliente con servicios históricos que haya tenido un check-in en los últimos 3 días
- El comando `procesar_premios_bienvenida.py` se ejecuta diariamente, por lo que este error es SISTEMÁTICO

## ✅ Solución Requerida

### 1. Modificar `procesar_premios_bienvenida.py`

**Cambiar líneas 93-103:**

```python
# ANTES (INCORRECTO)
primera_reserva = ReservaServicio.objects.filter(
    venta_reserva__cliente=cliente
).order_by('fecha_agendamiento', 'id').first()

if not primera_reserva or primera_reserva.fecha_agendamiento != fecha_objetivo:
    stats['no_es_primera_reserva'] += 1
    continue

# DESPUÉS (CORRECTO)
# Verificar si es cliente nuevo usando TramoService (considera históricos)
es_nuevo = TramoService.es_cliente_nuevo(cliente)

if not es_nuevo:
    stats['no_es_primera_reserva'] += 1
    self.stdout.write(
        f"  ⏭️  {cliente.nombre[:40]:<40} - No es cliente nuevo (tiene servicios previos)"
    )
    continue

# Verificar que el check-in haya sido hace X días
primera_reserva = ReservaServicio.objects.filter(
    venta_reserva__cliente=cliente
).order_by('fecha_agendamiento', 'id').first()

if not primera_reserva or primera_reserva.fecha_agendamiento != fecha_objetivo:
    # Este cliente tuvo su primer check-in en otra fecha
    continue
```

### 2. Anular Premio #54 y Generar el Correcto

```python
# 1. Anular Premio #54
premio_54 = ClientePremio.objects.get(id=54)
premio_54.estado = 'cancelado'
premio_54.notas = 'Cancelado por error: cliente tenía servicios históricos'
premio_54.save()

# 2. Calcular tramo correcto
cliente = premio_54.cliente
gasto_total = TramoService.calcular_gasto_cliente(cliente)  # $409,000
tramo_actual = TramoService.calcular_tramo(float(gasto_total))  # Tramo 9

# 3. Generar premio por hito si corresponde
# Tramo 9 está en rango de Tramos 9-12 (VIP)
resultado = TramoService.actualizar_tramo_cliente(cliente)
```

### 3. Investigar Problema con Gastos Históricos

Revisar por qué `CRMService.get_customer_360()` retorna:
- `gasto_historico` = $0 cuando debería ser ~$369,000
- `gasto_actual` = $409,000 cuando debería ser ~$40,000

Posibles causas:
- Los servicios históricos no tienen precio asociado
- La lógica de suma en `CRMService` está incorrecta
- Los servicios históricos están en otra tabla que no se está consultando

## 📝 Checklist de Corrección

- [ ] Modificar `procesar_premios_bienvenida.py` para usar `TramoService.es_cliente_nuevo()`
- [ ] Anular Premio #54 (estado = 'cancelado')
- [ ] Actualizar tramo de Francisca Cuevas Parga
- [ ] Generar premio correcto por Tramo 9 (si aplica)
- [ ] Investigar problema con cálculo de gastos históricos
- [ ] Ejecutar comando corregido en modo `--dry-run` para verificar
- [ ] Buscar otros premios de bienvenida generados incorrectamente
- [ ] Corregir casos similares si existen

## 🚨 Prevención

1. **Test unitario** para `procesar_premios_bienvenida.py`:
   - Caso: Cliente con servicios históricos
   - Expectativa: No genera premio de bienvenida

2. **Logging mejorado:**
   - Registrar total de servicios al evaluar elegibilidad
   - Registrar si se está usando históricos o no

3. **Validación en Admin:**
   - Mostrar advertencia si se aprueba premio de bienvenida para cliente con historial
   - Agregar columna "Total Servicios" en listado de premios pendientes

## 📊 Datos de Tramos para Referencia

```python
TRAMO_SIZE = 50,000  # Cada tramo es de $50,000
HITOS_PREMIO = [5, 10, 15, 20]  # Tramos que generan premios automáticamente

Tramo 1: $0 - $50,000
Tramo 2: $50,001 - $100,000
...
Tramo 9: $400,001 - $450,000  # ← Cliente Francisca debería estar aquí
...
```

### Rangos de Premios por Tramo

- **Tramos 5-8:** Vale $60K en tinas con masajes x2
- **Tramos 9-12:** 1 noche gratis en cabaña (VIP) ← Premio correcto para Francisca
- **Tramos 13-16:** Vale Premium Alojamiento con Tinas
- **Tramos 17-20:** 1 Noche Gratis en Cabaña (ELITE)

## 🔗 Archivos Relacionados

- `ventas/management/commands/procesar_premios_bienvenida.py` (líneas 93-103)
- `ventas/services/tramo_service.py` (método `es_cliente_nuevo`, líneas 146-164)
- `ventas/services/tramo_service.py` (método `calcular_gasto_cliente`, líneas 52-69)
- `ventas/services/crm_service.py` (método `get_customer_360`)
- `ventas/signals.py` (signal `actualizar_tramo_y_premios_on_pago`, líneas 548-600)
