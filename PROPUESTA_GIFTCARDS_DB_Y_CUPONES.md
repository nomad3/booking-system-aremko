# 🎁 Propuesta: GiftCards en Base de Datos + Sistema de Cupones de Descuento

## 📋 Análisis de Situación Actual

### ✅ Lo que funciona:
- 16 experiencias hardcodeadas en `giftcard_views.py`
- Wizard de 6 pasos funcionando correctamente
- Landing page responsive con diseño elegante
- Mensajes personalizados con IA
- Integración con checkout y pagos

### ❌ Limitaciones actuales:
- No se pueden editar precios sin tocar código
- No se pueden subir/cambiar imágenes sin deployment
- No hay sistema de cupones/códigos de descuento
- Agregar/quitar experiencias requiere modificar código
- No hay estadísticas de qué experiencias se venden más

---

## 🎯 Propuesta de Solución

### 1️⃣ Crear Modelo `GiftCardExperiencia` en Base de Datos

```python
class GiftCardExperiencia(models.Model):
    """
    Modelo para gestionar las experiencias disponibles en GiftCards
    Reemplaza el array hardcodeado en giftcard_views.py
    """

    CATEGORIA_CHOICES = [
        ('tinas', 'Tinas Calientes'),
        ('masajes', 'Masajes'),
        ('alojamientos', 'Alojamientos'),
        ('celebraciones', 'Celebraciones'),
        ('libre', 'Monto Libre'),
    ]

    # Identificación
    codigo = models.SlugField(max_length=100, unique=True)  # ej: 'tinas_masajes_finde'
    nombre = models.CharField(max_length=200)  # ej: 'Tina + Masajes (Vie-Sáb)'
    categoria = models.CharField(max_length=50, choices=CATEGORIA_CHOICES)

    # Descripciones
    descripcion_corta = models.CharField(max_length=500)
    descripcion_giftcard = models.TextField()  # Texto que va en la GiftCard

    # Precio
    monto_fijo = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        help_text="Precio fijo. Usar 0 para 'Monto Libre'"
    )

    # Montos sugeridos (solo para monto libre)
    montos_sugeridos = models.JSONField(
        default=list,
        blank=True,
        help_text="Array de montos sugeridos: [30000, 50000, 75000]"
    )

    # Imagen
    imagen = models.ImageField(
        upload_to='giftcards/experiencias/',
        help_text="Imagen principal de la experiencia"
    )

    # Control
    activo = models.BooleanField(
        default=True,
        help_text="Si está inactivo, no aparece en el wizard"
    )
    orden = models.PositiveIntegerField(
        default=0,
        help_text="Orden de aparición (menor primero)"
    )

    # Estadísticas
    veces_vendida = models.PositiveIntegerField(default=0, editable=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    # Badges/etiquetas
    es_nuevo = models.BooleanField(default=False, help_text="Muestra badge 'NUEVO'")
    es_popular = models.BooleanField(default=False, help_text="Muestra badge 'POPULAR'")

    class Meta:
        verbose_name = "Experiencia de GiftCard"
        verbose_name_plural = "Experiencias de GiftCards"
        ordering = ['categoria', 'orden', 'nombre']

    def __str__(self):
        return f"{self.nombre} (${self.monto_fijo:,.0f})"
```

### 2️⃣ Crear Modelo `CuponDescuento` para Códigos Promocionales

```python
class CuponDescuento(models.Model):
    """
    Sistema de cupones de descuento para GiftCards
    Ejemplo: código 'MADRE' da $10.000 de descuento
    """

    TIPO_DESCUENTO_CHOICES = [
        ('fijo', 'Monto Fijo'),      # Ej: $10.000 de descuento
        ('porcentaje', 'Porcentaje'), # Ej: 15% de descuento
    ]

    APLICABLE_A_CHOICES = [
        ('todas', 'Todas las experiencias'),
        ('categoria', 'Solo una categoría específica'),
        ('experiencia', 'Solo experiencias específicas'),
    ]

    # Identificación
    codigo = models.CharField(
        max_length=50,
        unique=True,
        help_text="Código que el usuario debe ingresar (ej: MADRE, VERANO2024)"
    )
    nombre = models.CharField(
        max_length=200,
        help_text="Nombre descriptivo interno"
    )
    descripcion = models.TextField(
        blank=True,
        help_text="Descripción del cupón para el usuario"
    )

    # Tipo de descuento
    tipo_descuento = models.CharField(
        max_length=20,
        choices=TIPO_DESCUENTO_CHOICES,
        default='fijo'
    )
    valor_descuento = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        help_text="Monto fijo (pesos) o porcentaje según tipo"
    )

    # A qué se aplica
    aplicable_a = models.CharField(
        max_length=20,
        choices=APLICABLE_A_CHOICES,
        default='todas'
    )
    categoria_aplicable = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Si aplicable_a='categoria', especificar cuál"
    )
    experiencias_aplicables = models.ManyToManyField(
        'GiftCardExperiencia',
        blank=True,
        help_text="Si aplicable_a='experiencia', seleccionar cuáles"
    )

    # Restricciones
    monto_minimo_compra = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        help_text="Monto mínimo de compra para usar el cupón"
    )
    descuento_maximo = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        null=True,
        blank=True,
        help_text="Descuento máximo (para % muy altos)"
    )

    # Validez temporal
    fecha_inicio = models.DateTimeField(
        help_text="Desde cuándo es válido el cupón"
    )
    fecha_fin = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Hasta cuándo es válido (opcional = sin límite)"
    )

    # Límites de uso
    usos_maximos_totales = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Máximo de veces que se puede usar en total (opcional)"
    )
    usos_maximos_por_cliente = models.PositiveIntegerField(
        default=1,
        help_text="Veces que un mismo cliente puede usarlo"
    )

    # Control
    activo = models.BooleanField(
        default=True,
        help_text="Si está inactivo, no se puede usar"
    )

    # Estadísticas
    veces_usado = models.PositiveIntegerField(default=0, editable=False)
    monto_total_descontado = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        editable=False
    )

    # Metadatos
    creado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='cupones_creados'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cupón de Descuento"
        verbose_name_plural = "Cupones de Descuento"
        ordering = ['-activo', '-fecha_creacion']

    def __str__(self):
        if self.tipo_descuento == 'fijo':
            return f"{self.codigo} - ${self.valor_descuento:,.0f}"
        else:
            return f"{self.codigo} - {self.valor_descuento}%"

    def es_valido(self):
        """Verifica si el cupón está dentro de su período de validez"""
        from django.utils import timezone
        ahora = timezone.now()

        if not self.activo:
            return False, "El cupón no está activo"

        if self.fecha_inicio > ahora:
            return False, "El cupón aún no está vigente"

        if self.fecha_fin and self.fecha_fin < ahora:
            return False, "El cupón ha expirado"

        if self.usos_maximos_totales and self.veces_usado >= self.usos_maximos_totales:
            return False, "Se alcanzó el límite de usos del cupón"

        return True, "Cupón válido"

    def calcular_descuento(self, monto_compra):
        """Calcula el monto de descuento para una compra dada"""
        if monto_compra < self.monto_minimo_compra:
            return 0, f"La compra debe ser mínimo de ${self.monto_minimo_compra:,.0f}"

        if self.tipo_descuento == 'fijo':
            descuento = self.valor_descuento
        else:  # porcentaje
            descuento = (monto_compra * self.valor_descuento) / 100

        # Aplicar descuento máximo si está configurado
        if self.descuento_maximo and descuento > self.descuento_maximo:
            descuento = self.descuento_maximo

        # No puede ser mayor al monto de compra
        if descuento > monto_compra:
            descuento = monto_compra

        return descuento, None


class UsoCupon(models.Model):
    """
    Registro de uso de cupones para control y estadísticas
    """
    cupon = models.ForeignKey(
        'CuponDescuento',
        on_delete=models.CASCADE,
        related_name='usos'
    )
    giftcard = models.ForeignKey(
        'GiftCard',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    venta_reserva = models.ForeignKey(
        'VentaReserva',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    monto_original = models.DecimalField(max_digits=10, decimal_places=0)
    monto_descuento = models.DecimalField(max_digits=10, decimal_places=0)
    monto_final = models.DecimalField(max_digits=10, decimal_places=0)
    fecha_uso = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Uso de Cupón"
        verbose_name_plural = "Usos de Cupones"
        ordering = ['-fecha_uso']

    def __str__(self):
        return f"{self.cupon.codigo} - ${self.monto_descuento:,.0f} ({self.fecha_uso.date()})"
```

---

## 🔄 Integración con el Sistema Actual

### Cambios en `giftcard_views.py`:

**ANTES (línea 391):**
```python
experiencias = [
    {
        'id': 'tinas',
        'categoria': 'tinas',
        'nombre': 'Tina para 2',
        ...
    },
    ...
]
```

**DESPUÉS:**
```python
from ventas.models import GiftCardExperiencia

# Obtener experiencias activas desde la BD
experiencias_db = GiftCardExperiencia.objects.filter(activo=True).order_by('orden')

# Convertir a formato compatible con el wizard existente
experiencias = []
for exp in experiencias_db:
    experiencias.append({
        'id': exp.codigo,
        'categoria': exp.categoria,
        'nombre': exp.nombre,
        'descripcion': exp.descripcion_corta,
        'descripcion_giftcard': exp.descripcion_giftcard,
        'imagen': exp.imagen.url if exp.imagen else 'images/default.jpg',
        'monto_fijo': int(exp.monto_fijo),
        'montos_sugeridos': exp.montos_sugeridos or [],
        'es_nuevo': exp.es_nuevo,
        'es_popular': exp.es_popular,
    })
```

### Nuevo endpoint API para validar cupones:

```python
@require_http_methods(["POST"])
def validar_cupon(request):
    """
    API endpoint para validar un cupón de descuento
    POST /api/giftcard/validar-cupon/
    Body: {"codigo": "MADRE", "monto": 95000, "experiencia_id": "tinas_masajes_semana"}
    """
    try:
        data = json.loads(request.body)
        codigo = data.get('codigo', '').upper().strip()
        monto = Decimal(data.get('monto', 0))
        experiencia_id = data.get('experiencia_id')

        # Buscar cupón
        try:
            cupon = CuponDescuento.objects.get(codigo__iexact=codigo)
        except CuponDescuento.DoesNotExist:
            return JsonResponse({
                'valido': False,
                'mensaje': 'Cupón no válido'
            }, status=400)

        # Validar vigencia
        es_valido, mensaje = cupon.es_valido()
        if not es_valido:
            return JsonResponse({
                'valido': False,
                'mensaje': mensaje
            }, status=400)

        # Validar si aplica a esta experiencia
        if cupon.aplicable_a == 'categoria':
            experiencia = GiftCardExperiencia.objects.get(codigo=experiencia_id)
            if experiencia.categoria != cupon.categoria_aplicable:
                return JsonResponse({
                    'valido': False,
                    'mensaje': f'Este cupón solo aplica a {cupon.categoria_aplicable}'
                }, status=400)

        elif cupon.aplicable_a == 'experiencia':
            experiencia = GiftCardExperiencia.objects.get(codigo=experiencia_id)
            if experiencia not in cupon.experiencias_aplicables.all():
                return JsonResponse({
                    'valido': False,
                    'mensaje': 'Este cupón no aplica a esta experiencia'
                }, status=400)

        # Calcular descuento
        descuento, error = cupon.calcular_descuento(monto)
        if error:
            return JsonResponse({
                'valido': False,
                'mensaje': error
            }, status=400)

        return JsonResponse({
            'valido': True,
            'codigo': cupon.codigo,
            'descuento': float(descuento),
            'monto_original': float(monto),
            'monto_final': float(monto - descuento),
            'mensaje': f'¡Cupón aplicado! Ahorras ${descuento:,.0f}'
        })

    except Exception as e:
        return JsonResponse({
            'valido': False,
            'mensaje': str(e)
        }, status=500)
```

---

## 🎨 Cambios en el Frontend (Wizard)

### Agregar campo de cupón en Step 1 (después de elegir experiencia):

```html
<!-- Nuevo campo de cupón después de elegir experiencia -->
<div id="cuponSection" style="display: none;" class="mt-4">
    <div class="card border-success">
        <div class="card-body">
            <h6 class="card-title">
                <i class="fas fa-tag text-success me-2"></i>
                ¿Tienes un código de descuento?
            </h6>
            <div class="input-group">
                <input
                    type="text"
                    class="form-control"
                    id="codigoCupon"
                    placeholder="Ej: MADRE"
                    maxlength="50"
                >
                <button
                    class="btn btn-success"
                    type="button"
                    onclick="aplicarCupon()"
                >
                    Aplicar
                </button>
            </div>
            <div id="cuponFeedback" class="mt-2"></div>
        </div>
    </div>
</div>

<!-- Resumen con descuento -->
<div id="resumenPrecio" class="mt-3">
    <div class="d-flex justify-content-between">
        <span>Precio:</span>
        <span id="precioOriginal">$95.000</span>
    </div>
    <div class="d-flex justify-content-between text-success" id="lineaDescuento" style="display: none !important;">
        <span>Descuento (<span id="codigoCuponAplicado"></span>):</span>
        <span id="montoDescuento">-$10.000</span>
    </div>
    <hr>
    <div class="d-flex justify-content-between fw-bold">
        <span>Total:</span>
        <span id="precioFinal">$95.000</span>
    </div>
</div>

<script>
let cuponAplicado = null;

function aplicarCupon() {
    const codigo = document.getElementById('codigoCupon').value.trim();
    const feedback = document.getElementById('cuponFeedback');

    if (!codigo) {
        feedback.innerHTML = '<small class="text-danger">Ingresa un código</small>';
        return;
    }

    // Obtener monto actual
    const monto = wizardData.monto;
    const experienciaId = wizardData.experiencia;

    feedback.innerHTML = '<small class="text-muted"><i class="fas fa-spinner fa-spin"></i> Validando...</small>';

    fetch('/api/giftcard/validar-cupon/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            codigo: codigo,
            monto: monto,
            experiencia_id: experienciaId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.valido) {
            cuponAplicado = data;
            feedback.innerHTML = `<small class="text-success"><i class="fas fa-check-circle"></i> ${data.mensaje}</small>`;

            // Actualizar resumen
            document.getElementById('lineaDescuento').style.display = 'flex';
            document.getElementById('codigoCuponAplicado').textContent = data.codigo;
            document.getElementById('montoDescuento').textContent = `-$${data.descuento.toLocaleString('es-CL')}`;
            document.getElementById('precioFinal').textContent = `$${data.monto_final.toLocaleString('es-CL')}`;

            // Guardar en wizardData
            wizardData.cupon = data.codigo;
            wizardData.descuento = data.descuento;
            wizardData.montoFinal = data.monto_final;

        } else {
            feedback.innerHTML = `<small class="text-danger"><i class="fas fa-times-circle"></i> ${data.mensaje}</small>`;
            limpiarCupon();
        }
    })
    .catch(error => {
        feedback.innerHTML = '<small class="text-danger">Error al validar cupón</small>';
        console.error('Error:', error);
    });
}

function limpiarCupon() {
    cuponAplicado = null;
    document.getElementById('lineaDescuento').style.display = 'none';
    document.getElementById('precioFinal').textContent = document.getElementById('precioOriginal').textContent;
    wizardData.cupon = null;
    wizardData.descuento = 0;
    wizardData.montoFinal = wizardData.monto;
}
</script>
```

---

## 📊 Admin de Django

### Configuración del admin para los nuevos modelos:

```python
from django.contrib import admin
from .models import GiftCardExperiencia, CuponDescuento, UsoCupon

@admin.register(GiftCardExperiencia)
class GiftCardExperienciaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'monto_fijo', 'activo', 'orden', 'veces_vendida', 'es_nuevo', 'es_popular')
    list_filter = ('categoria', 'activo', 'es_nuevo', 'es_popular')
    search_fields = ('nombre', 'codigo', 'descripcion_corta')
    list_editable = ('activo', 'orden', 'es_nuevo', 'es_popular')
    prepopulated_fields = {'codigo': ('nombre',)}

    fieldsets = (
        ('Información Básica', {
            'fields': ('codigo', 'nombre', 'categoria', 'activo')
        }),
        ('Descripciones', {
            'fields': ('descripcion_corta', 'descripcion_giftcard')
        }),
        ('Precio', {
            'fields': ('monto_fijo', 'montos_sugeridos')
        }),
        ('Imagen', {
            'fields': ('imagen',)
        }),
        ('Presentación', {
            'fields': ('orden', 'es_nuevo', 'es_popular')
        }),
        ('Estadísticas', {
            'fields': ('veces_vendida',),
            'classes': ('collapse',)
        })
    )

    readonly_fields = ('veces_vendida',)


@admin.register(CuponDescuento)
class CuponDescuentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo_descuento', 'valor_descuento', 'activo', 'fecha_inicio', 'fecha_fin', 'veces_usado', 'monto_total_descontado')
    list_filter = ('activo', 'tipo_descuento', 'aplicable_a', 'fecha_inicio')
    search_fields = ('codigo', 'nombre', 'descripcion')
    list_editable = ('activo',)

    fieldsets = (
        ('Identificación', {
            'fields': ('codigo', 'nombre', 'descripcion', 'activo')
        }),
        ('Descuento', {
            'fields': ('tipo_descuento', 'valor_descuento', 'descuento_maximo')
        }),
        ('Aplicación', {
            'fields': ('aplicable_a', 'categoria_aplicable', 'experiencias_aplicables')
        }),
        ('Restricciones', {
            'fields': ('monto_minimo_compra', 'usos_maximos_totales', 'usos_maximos_por_cliente')
        }),
        ('Validez', {
            'fields': ('fecha_inicio', 'fecha_fin')
        }),
        ('Estadísticas', {
            'fields': ('veces_usado', 'monto_total_descontado'),
            'classes': ('collapse',)
        })
    )

    readonly_fields = ('veces_usado', 'monto_total_descontado', 'creado_por')

    def save_model(self, request, obj, form, change):
        if not change:  # Si es creación
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(UsoCupon)
class UsoCuponAdmin(admin.ModelAdmin):
    list_display = ('cupon', 'cliente', 'monto_descuento', 'fecha_uso')
    list_filter = ('cupon', 'fecha_uso')
    search_fields = ('cupon__codigo', 'cliente__nombre')
    readonly_fields = ('cupon', 'giftcard', 'venta_reserva', 'cliente', 'monto_original', 'monto_descuento', 'monto_final', 'fecha_uso')

    def has_add_permission(self, request):
        return False  # No se crean manualmente, se crean automáticamente al usar cupón
```

---

## 🚀 Plan de Implementación

### Fase 1: Preparación (30 min)
1. ✅ Crear los modelos en `models.py`
2. ✅ Generar la migración: `python manage.py makemigrations`
3. ✅ Revisar el archivo de migración generado
4. ✅ Commit y push a GitHub

### Fase 2: Migración en Render (15 min)
1. Ir a Render Dashboard → Shell
2. Ejecutar: `python manage.py migrate`
3. Verificar que las tablas se crearon correctamente
4. Ejecutar script para migrar las 16 experiencias hardcodeadas a la BD

### Fase 3: Configurar Admin (15 min)
1. Agregar configuración de admin en `admin.py`
2. Deploy y verificar que el admin funciona
3. Subir imágenes para cada experiencia desde el admin

### Fase 4: Actualizar Views y Templates (1 hora)
1. Modificar `giftcard_wizard()` para leer desde BD
2. Crear endpoint `validar_cupon()`
3. Agregar campo de cupón en el wizard HTML
4. Agregar JavaScript para validación de cupones
5. Testing completo del flujo

### Fase 5: Crear Cupones de Ejemplo (10 min)
1. Crear cupón "MADRE" con $10.000 de descuento
2. Crear cupón "VERANO2024" con 15% de descuento
3. Probar en el wizard

---

## 💡 Ejemplos de Cupones que Podrías Crear

### 1. Día de la Madre
```
Código: MADRE
Tipo: Monto fijo
Valor: $10.000
Aplicable a: Todas las experiencias
Monto mínimo: $50.000
Vigencia: 01/05/2025 - 31/05/2025
Usos máximos: 100
```

### 2. Verano 2024
```
Código: VERANO2024
Tipo: Porcentaje
Valor: 15%
Aplicable a: Solo categoría 'tinas'
Descuento máximo: $20.000
Monto mínimo: $80.000
Vigencia: 15/12/2024 - 15/03/2025
```

### 3. Primera Compra
```
Código: BIENVENIDA
Tipo: Monto fijo
Valor: $5.000
Aplicable a: Todas
Usos por cliente: 1
Sin fecha de fin
```

### 4. Black Friday
```
Código: BLACKFRIDAY
Tipo: Porcentaje
Valor: 25%
Aplicable a: Todas excepto 'Monto Libre'
Descuento máximo: $40.000
Vigencia: 29/11/2024 (solo 1 día)
Usos máximos: 50
```

### 5. Cumpleaños Aremko
```
Código: CUMPLE5AREMKO
Tipo: Monto fijo
Valor: $15.000
Aplicable a: Solo experiencias de 'alojamientos'
Monto mínimo: $100.000
Vigencia: Semana del aniversario
Usos máximos: 200
```

---

## 📈 Beneficios de la Implementación

### Para el Negocio:
- ✅ **Flexibilidad de precios:** Cambiar precios sin tocar código ni deployar
- ✅ **Campañas de marketing:** Crear cupones para fechas especiales
- ✅ **Estadísticas:** Saber qué experiencias se venden más
- ✅ **A/B Testing:** Probar diferentes precios fácilmente
- ✅ **Control de inventario:** Activar/desactivar experiencias según disponibilidad

### Para Marketing:
- ✅ **Campañas estacionales:** Cupones por Día de la Madre, Navidad, etc.
- ✅ **Incentivos de conversión:** "Usa código MADRE y ahorra $10.000"
- ✅ **Remarketing:** Enviar cupones a clientes que abandonaron carrito
- ✅ **Afiliados:** Crear cupones únicos por influencer/partner
- ✅ **Medición de ROI:** Saber exactamente cuánto descuento se dio y cuántas ventas generó

### Para Operaciones:
- ✅ **Gestión visual:** Subir/cambiar imágenes desde el admin
- ✅ **Sin downtime:** Cambios sin necesidad de deploy
- ✅ **Auditoría:** Registro completo de quién usó qué cupón y cuándo
- ✅ **Control de fraude:** Límites de uso por cliente y totales

---

## ⚠️ Consideraciones Importantes

### 1. Imágenes
- Las imágenes se subirán a `media/giftcards/experiencias/`
- Necesitas configurar storage en Render (S3 o similar para producción)
- Por ahora pueden usar el filesystem de Render (se pierde en redeploy)

### 2. Migración de datos
- Script para migrar las 16 experiencias actuales a la BD
- Mantener IDs consistentes para no romper links existentes

### 3. Compatibilidad
- El código actual seguirá funcionando durante la transición
- Puedes probar con BD en desarrollo antes de migrar producción

### 4. Performance
- Cachear la lista de experiencias activas (no consultar BD en cada request)
- Índices en campos `codigo`, `activo`, `categoria`

---

## 🎯 Siguiente Paso

¿Quieres que proceda con la implementación?

**Opción A:** Implementar todo (Experiencias + Cupones)
**Opción B:** Solo Experiencias en BD primero, Cupones después
**Opción C:** Revisar/ajustar la propuesta antes de implementar

¿Cuál prefieres?
