# Estado del Sistema - Pre-implementación Sistema de Pagos a Masajistas

## Fecha: 2025-12-23

## 🔍 Estado Actual del Sistema

### ✅ Funcionalidades Implementadas

1. **Sistema de Tips y Resúmenes**
   - Migración 0069: ConfiguracionResumen
   - Migración 0070: ConfiguracionTips
   - Botones de Resumen y Tips en listado de reservas
   - Generación condicional de tips según servicios

2. **Modelos Actuales Relevantes**

#### Modelo Proveedor (Actual)
```python
class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
```

#### Modelo ReservaServicio (Actual)
```python
class ReservaServicio(models.Model):
    venta_reserva = models.ForeignKey(VentaReserva, ...)
    servicio = models.ForeignKey(Servicio, ...)
    fecha_agendamiento = models.DateField()
    hora_inicio = models.CharField(max_length=5)
    cantidad_personas = models.PositiveIntegerField(default=1)
    proveedor_asignado = models.ForeignKey(Proveedor, ...)  # Ya existe relación con masajista
```

### 📊 Última Migración Aplicada
- **0070_agregar_configuracion_tips**

## 🎯 Sistema de Pagos a Masajistas - A Implementar

### Requerimientos del Cliente

1. **Gestión de Comisiones**
   - Masajistas reciben 30% o 40% según acuerdo
   - Porcentaje puede variar por masajista y tiempo
   - Descuento del 14.5% por retención de impuestos

2. **Funcionalidades Necesarias**
   - Listar servicios NO pagados por masajista
   - Calcular montos a pagar con porcentajes
   - Registrar pagos con comprobante bancario
   - Marcar servicios como pagados

3. **Ubicación en el Sistema**
   - Nuevo módulo en Servicios y Proveedores
   - Interfaz para gestión de pagos
   - Registro histórico de pagos

### 📋 Cambios a Implementar

#### 1. Nuevos Campos en Proveedor
- `porcentaje_comision` (decimal): % que recibe el masajista
- `es_masajista` (boolean): identificar masajistas
- `rut` (string): para efectos tributarios
- `banco`, `tipo_cuenta`, `numero_cuenta`: datos bancarios

#### 2. Nuevo Modelo: PagoMasajista
- Registro de cada pago realizado
- Periodo de servicios incluidos
- Montos bruto, retención y neto
- Comprobante de transferencia (imagen)
- Relación con servicios pagados

#### 3. Nuevo Modelo: DetalleServicioPago
- Relaciona servicios con pagos
- Guarda el detalle de cada servicio en el pago

#### 4. Modificaciones en ReservaServicio
- `pagado_a_proveedor` (boolean): marca si ya se pagó
- `pago_proveedor` (FK): referencia al pago

### 🔒 Backup Realizado

- **Archivo**: `/Users/jorgeaguilera/Documents/backups/backup_aremko_20251223_104125.tar.gz`
- **Tamaño**: 1.4M
- **Incluye**:
  - Código fuente completo
  - Todas las migraciones
  - Archivos de configuración
  - Scripts auxiliares
- **NO incluye**:
  - Base de datos (respaldada en Render)
  - Archivos media
  - Variables de entorno (.env)

## 📝 Notas Importantes

1. **Base de Datos**: El usuario está respaldando la BD en Render
2. **Migraciones**: Todas las migraciones hasta la 0070 están aplicadas
3. **Git Status**: Código está al día con el repositorio

## ⚠️ Precauciones

1. Probar primero en ambiente de desarrollo
2. Validar cálculos de porcentajes y retenciones
3. Asegurar que los comprobantes se guarden correctamente
4. Implementar validaciones para evitar pagos duplicados

## 🚀 Próximos Pasos

1. ✅ Backup completo realizado
2. ⏳ Esperar confirmación de backup de BD en Render
3. 📝 Crear migración 0071 para sistema de pagos
4. 🔨 Implementar modelos y lógica de negocio
5. 🎨 Crear vistas y templates
6. 🧪 Pruebas exhaustivas
7. 🚀 Deploy a producción

---

**Documento creado antes de implementar el Sistema de Pagos a Masajistas**
**Usar como referencia en caso de necesitar rollback**