# Plan de Implementación: Sistema de Comandas

## 📋 Resumen Ejecutivo

Sistema de comandas para gestionar pedidos de productos asociados a reservas, similar al flujo de trabajo de un restaurante. Las comandas serán visibles para todo el personal y permitirán seguimiento del estado desde la solicitud hasta la entrega.

---

## 🎯 Objetivos

1. **Crear comandas** desde el módulo de ventas al agregar productos a una reserva
2. **Visualizar comandas** en tiempo real con toda la información necesaria
3. **Gestionar estados** (Pendiente → En Proceso → Entregada)
4. **Trazabilidad** de quién toma y procesa cada comanda
5. **Interfaz simple** accesible desde "Control de Gestión"

---

## 📊 Análisis de Contexto Actual

### Estructura Existente
- ✅ **Modelo Producto**: Tiene nombre, precio, inventario, categoría
- ✅ **Modelo ReservaProducto**: Vincula productos con VentaReserva
- ✅ **Sección "Control de Gestión"**: Ya existe Agenda Operativa
- ✅ **Sistema de permisos**: Ya implementado con `@staff_required`

### Lo que Falta
- ❌ **Modelo Comanda**: Para gestionar pedidos independientes
- ❌ **Campo para notas/especificaciones**: Sabores, personalizaciones
- ❌ **Gestión de estados**: Workflow Pendiente → En Proceso → Entregada
- ❌ **Vista de listado**: Interface para el personal
- ❌ **Auditoría**: Quién toma/procesa cada comanda

---

## 🗄️ Diseño de Modelos

### 1. Modelo `Comanda`

```python
class Comanda(models.Model):
    """
    Comanda de productos para una reserva.
    Similar a una orden de restaurante.
    """
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('procesando', 'En Proceso'),
        ('entregada', 'Entregada'),
        ('cancelada', 'Cancelada'),
    ]

    # Relaciones
    venta_reserva = models.ForeignKey(
        'VentaReserva',
        on_delete=models.CASCADE,
        related_name='comandas',
        verbose_name='Reserva'
    )

    # Información temporal
    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora de Solicitud'
    )
    hora_solicitud = models.TimeField(
        auto_now_add=True,
        verbose_name='Hora de Solicitud',
        help_text='Hora específica para ordenamiento rápido'
    )

    # Estado y gestión
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado',
        db_index=True  # Para filtrar rápidamente
    )

    # Notas generales de la comanda
    notas_generales = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas Generales',
        help_text='Indicaciones especiales para toda la comanda'
    )

    # Auditoría
    usuario_solicita = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='comandas_solicitadas',
        verbose_name='Usuario que Solicita'
    )

    usuario_procesa = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comandas_procesadas',
        verbose_name='Usuario que Procesa'
    )

    fecha_inicio_proceso = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Inicio de Proceso'
    )

    fecha_entrega = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Entrega'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Comanda'
        verbose_name_plural = 'Comandas'
        ordering = ['-fecha_solicitud']
        indexes = [
            models.Index(fields=['estado', '-fecha_solicitud']),
            models.Index(fields=['venta_reserva', 'estado']),
        ]

    def __str__(self):
        return f"Comanda #{self.id} - {self.venta_reserva.cliente.nombre} - {self.get_estado_display()}"

    def tiempo_espera(self):
        """Calcula el tiempo de espera en minutos"""
        from django.utils import timezone
        if self.estado == 'entregada' and self.fecha_entrega:
            delta = self.fecha_entrega - self.fecha_solicitud
        elif self.estado == 'procesando' and self.fecha_inicio_proceso:
            delta = timezone.now() - self.fecha_solicitud
        else:
            delta = timezone.now() - self.fecha_solicitud
        return int(delta.total_seconds() / 60)

    def marcar_procesando(self, usuario):
        """Marca la comanda como en proceso"""
        from django.utils import timezone
        self.estado = 'procesando'
        self.usuario_procesa = usuario
        self.fecha_inicio_proceso = timezone.now()
        self.save()

    def marcar_entregada(self):
        """Marca la comanda como entregada"""
        from django.utils import timezone
        self.estado = 'entregada'
        self.fecha_entrega = timezone.now()
        self.save()
```

### 2. Modelo `DetalleComanda`

```python
class DetalleComanda(models.Model):
    """
    Detalle de productos en una comanda.
    Permite especificaciones individuales por producto.
    """
    comanda = models.ForeignKey(
        'Comanda',
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Comanda'
    )

    producto = models.ForeignKey(
        'Producto',
        on_delete=models.PROTECT,  # No permitir eliminar producto si está en comanda
        verbose_name='Producto'
    )

    cantidad = models.PositiveIntegerField(
        default=1,
        verbose_name='Cantidad'
    )

    # Especificaciones del producto
    especificaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name='Especificaciones',
        help_text='Ej: Sabor frutilla, sin azúcar, con endulzante, bien frío, etc.'
    )

    # Precio al momento de la comanda (snapshot)
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        verbose_name='Precio Unitario'
    )

    class Meta:
        verbose_name = 'Detalle de Comanda'
        verbose_name_plural = 'Detalles de Comanda'
        ordering = ['id']

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre}"

    def subtotal(self):
        """Calcula el subtotal de este item"""
        return self.cantidad * self.precio_unitario

    def save(self, *args, **kwargs):
        # Capturar precio actual del producto si no está definido
        if not self.precio_unitario:
            self.precio_unitario = self.producto.precio_base
        super().save(*args, **kwargs)
```

---

## 🏗️ Plan de Implementación por Fases

### **FASE 1: Modelos y Migraciones** (2-3 horas)

#### 1.1 Crear los modelos
- [ ] Agregar clase `Comanda` a `ventas/models.py`
- [ ] Agregar clase `DetalleComanda` a `ventas/models.py`
- [ ] Importar en `__init__.py` si es necesario

#### 1.2 Crear migración manual
```bash
# Archivo: ventas/migrations/0080_comandas_system.py
```

**Contenido de la migración:**
```python
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0079_cliente_performance_indexes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Crear tabla Comanda
        migrations.CreateModel(
            name='Comanda',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_solicitud', models.DateTimeField(auto_now_add=True, verbose_name='Fecha y Hora de Solicitud')),
                ('hora_solicitud', models.TimeField(auto_now_add=True, verbose_name='Hora de Solicitud')),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('procesando', 'En Proceso'), ('entregada', 'Entregada'), ('cancelada', 'Cancelada')], db_index=True, default='pendiente', max_length=20, verbose_name='Estado')),
                ('notas_generales', models.TextField(blank=True, help_text='Indicaciones especiales para toda la comanda', null=True, verbose_name='Notas Generales')),
                ('fecha_inicio_proceso', models.DateTimeField(blank=True, null=True, verbose_name='Inicio de Proceso')),
                ('fecha_entrega', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de Entrega')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('usuario_procesa', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comandas_procesadas', to=settings.AUTH_USER_MODEL, verbose_name='Usuario que Procesa')),
                ('usuario_solicita', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comandas_solicitadas', to=settings.AUTH_USER_MODEL, verbose_name='Usuario que Solicita')),
                ('venta_reserva', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comandas', to='ventas.ventareserva', verbose_name='Reserva')),
            ],
            options={
                'verbose_name': 'Comanda',
                'verbose_name_plural': 'Comandas',
                'ordering': ['-fecha_solicitud'],
            },
        ),

        # Crear tabla DetalleComanda
        migrations.CreateModel(
            name='DetalleComanda',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad', models.PositiveIntegerField(default=1, verbose_name='Cantidad')),
                ('especificaciones', models.TextField(blank=True, help_text='Ej: Sabor frutilla, sin azúcar, con endulzante, bien frío, etc.', null=True, verbose_name='Especificaciones')),
                ('precio_unitario', models.DecimalField(decimal_places=0, max_digits=10, verbose_name='Precio Unitario')),
                ('comanda', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='ventas.comanda', verbose_name='Comanda')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ventas.producto', verbose_name='Producto')),
            ],
            options={
                'verbose_name': 'Detalle de Comanda',
                'verbose_name_plural': 'Detalles de Comanda',
                'ordering': ['id'],
            },
        ),

        # Crear índices compuestos para performance
        migrations.AddIndex(
            model_name='comanda',
            index=models.Index(fields=['estado', '-fecha_solicitud'], name='ventas_coma_estado_fecha_idx'),
        ),
        migrations.AddIndex(
            model_name='comanda',
            index=models.Index(fields=['venta_reserva', 'estado'], name='ventas_coma_reserva_estado_idx'),
        ),
    ]
```

#### 1.3 Ejecutar migración
```bash
python manage.py migrate ventas 0080
```

---

### **FASE 2: Admin de Django** (1-2 horas)

#### 2.1 Configurar Inline para DetalleComanda
```python
# En ventas/admin.py

class DetalleComandaInline(admin.TabularInline):
    model = DetalleComanda
    extra = 1
    fields = ['producto', 'cantidad', 'especificaciones', 'precio_unitario']
    readonly_fields = []

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "producto":
            # Ordenar productos alfabéticamente
            kwargs["queryset"] = Producto.objects.order_by('nombre')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
```

#### 2.2 Configurar Admin para Comanda
```python
@admin.register(Comanda)
class ComandaAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'hora_solicitud', 'cliente_nombre', 'estado_badge',
        'total_items', 'tiempo_espera_display', 'usuario_procesa'
    )
    list_filter = ('estado', 'fecha_solicitud', 'usuario_procesa')
    search_fields = ('id', 'venta_reserva__cliente__nombre', 'notas_generales')
    readonly_fields = ('fecha_solicitud', 'hora_solicitud', 'fecha_inicio_proceso', 'fecha_entrega', 'tiempo_espera_display')
    inlines = [DetalleComandaInline]

    fieldsets = (
        ('Información de la Comanda', {
            'fields': ('venta_reserva', 'estado', 'notas_generales')
        }),
        ('Gestión', {
            'fields': ('usuario_solicita', 'usuario_procesa', 'fecha_solicitud', 'hora_solicitud', 'fecha_inicio_proceso', 'fecha_entrega', 'tiempo_espera_display')
        }),
    )

    def cliente_nombre(self, obj):
        return obj.venta_reserva.cliente.nombre
    cliente_nombre.short_description = 'Cliente'

    def estado_badge(self, obj):
        colores = {
            'pendiente': '#ff9800',
            'procesando': '#2196f3',
            'entregada': '#4caf50',
            'cancelada': '#f44336'
        }
        return format_html(
            '<span style="background:{}; color:white; padding:4px 12px; border-radius:12px; font-weight:600; font-size:11px;">{}</span>',
            colores.get(obj.estado, '#999'),
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'

    def total_items(self, obj):
        return obj.detalles.count()
    total_items.short_description = 'Items'

    def tiempo_espera_display(self, obj):
        minutos = obj.tiempo_espera()
        if minutos < 10:
            color = 'green'
        elif minutos < 20:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color:{}; font-weight:600;">{} min</span>',
            color, minutos
        )
    tiempo_espera_display.short_description = 'Tiempo Espera'

    def save_model(self, request, obj, form, change):
        if not change:  # Nueva comanda
            obj.usuario_solicita = request.user
        super().save_model(request, obj, form, change)
```

---

### **FASE 3: Vistas y URLs** (2-3 horas)

#### 3.1 Crear vista de listado de comandas
```python
# ventas/views/comandas_view.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from ..models import Comanda, DetalleComanda

@login_required
def listado_comandas(request):
    """
    Vista principal del sistema de comandas.
    Muestra comandas pendientes y en proceso.
    """
    # Filtros
    estado_filtro = request.GET.get('estado', 'activas')  # activas, todas, pendientes, procesando, entregadas

    # Query base
    comandas = Comanda.objects.select_related(
        'venta_reserva__cliente',
        'usuario_solicita',
        'usuario_procesa'
    ).prefetch_related('detalles__producto')

    # Aplicar filtros
    if estado_filtro == 'activas':
        comandas = comandas.filter(estado__in=['pendiente', 'procesando'])
    elif estado_filtro != 'todas':
        comandas = comandas.filter(estado=estado_filtro)

    # Ordenar: primero pendientes, luego por hora
    comandas = comandas.order_by(
        models.Case(
            models.When(estado='pendiente', then=0),
            models.When(estado='procesando', then=1),
            default=2
        ),
        '-fecha_solicitud'
    )

    # Estadísticas
    stats = {
        'pendientes': Comanda.objects.filter(estado='pendiente').count(),
        'procesando': Comanda.objects.filter(estado='procesando').count(),
        'entregadas_hoy': Comanda.objects.filter(
            estado='entregada',
            fecha_entrega__date=timezone.now().date()
        ).count()
    }

    context = {
        'comandas': comandas,
        'stats': stats,
        'estado_filtro': estado_filtro,
    }

    return render(request, 'ventas/comandas/listado.html', context)


@login_required
def tomar_comanda(request, comanda_id):
    """Marca una comanda como 'en proceso' y asigna al usuario actual"""
    comanda = get_object_or_404(Comanda, id=comanda_id)

    if comanda.estado == 'pendiente':
        comanda.marcar_procesando(request.user)
        return JsonResponse({'success': True, 'message': 'Comanda tomada'})

    return JsonResponse({'success': False, 'message': 'La comanda ya fue tomada'})


@login_required
def entregar_comanda(request, comanda_id):
    """Marca una comanda como entregada"""
    comanda = get_object_or_404(Comanda, id=comanda_id)

    if comanda.estado == 'procesando':
        comanda.marcar_entregada()
        return JsonResponse({'success': True, 'message': 'Comanda entregada'})

    return JsonResponse({'success': False, 'message': 'La comanda no está en proceso'})


@login_required
def detalle_comanda(request, comanda_id):
    """Vista detallada de una comanda"""
    comanda = get_object_or_404(
        Comanda.objects.select_related('venta_reserva__cliente')
                       .prefetch_related('detalles__producto'),
        id=comanda_id
    )

    context = {
        'comanda': comanda,
    }

    return render(request, 'ventas/comandas/detalle.html', context)
```

#### 3.2 Agregar URLs
```python
# En ventas/urls.py

from .views import comandas_view

urlpatterns = [
    # ... otras URLs ...

    # Sistema de Comandas
    path('comandas/', comandas_view.listado_comandas, name='comandas_listado'),
    path('comandas/<int:comanda_id>/', comandas_view.detalle_comanda, name='comandas_detalle'),
    path('comandas/<int:comanda_id>/tomar/', comandas_view.tomar_comanda, name='comandas_tomar'),
    path('comandas/<int:comanda_id>/entregar/', comandas_view.entregar_comanda, name='comandas_entregar'),
]
```

---

### **FASE 4: Templates** (3-4 horas)

#### 4.1 Template principal de listado
```html
<!-- ventas/templates/ventas/comandas/listado.html -->
{% extends "admin/base_site.html" %}
{% load static %}
{% load humanize %}

{% block title %}Sistema de Comandas{% endblock %}

{% block extrastyle %}
<style>
    .comandas-container {
        padding: 20px;
        background: #f5f5f5;
        min-height: 100vh;
    }

    .comandas-header {
        background: white;
        padding: 20px;
        margin-bottom: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 15px;
        margin-bottom: 20px;
    }

    .stat-card {
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }

    .stat-number {
        font-size: 36px;
        font-weight: 700;
        margin-bottom: 5px;
    }

    .stat-label {
        color: #666;
        font-size: 14px;
    }

    .comanda-card {
        background: white;
        margin-bottom: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        overflow: hidden;
        transition: transform 0.2s;
    }

    .comanda-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }

    .comanda-header {
        padding: 15px 20px;
        border-bottom: 2px solid #f0f0f0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .comanda-header.pendiente {
        background: #fff3e0;
        border-left: 4px solid #ff9800;
    }

    .comanda-header.procesando {
        background: #e3f2fd;
        border-left: 4px solid #2196f3;
    }

    .comanda-body {
        padding: 20px;
    }

    .producto-item {
        padding: 10px 0;
        border-bottom: 1px solid #f0f0f0;
        display: flex;
        justify-content: space-between;
    }

    .producto-item:last-child {
        border-bottom: none;
    }

    .especificaciones {
        color: #666;
        font-size: 13px;
        font-style: italic;
        margin-top: 5px;
    }

    .comanda-actions {
        padding: 15px 20px;
        background: #f8f8f8;
        display: flex;
        gap: 10px;
        justify-content: flex-end;
    }

    .btn {
        padding: 10px 20px;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }

    .btn-primary {
        background: #2196f3;
        color: white;
    }

    .btn-success {
        background: #4caf50;
        color: white;
    }

    .btn:hover {
        opacity: 0.9;
        transform: scale(1.02);
    }

    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
    }

    .badge-pendiente { background: #ff9800; color: white; }
    .badge-procesando { background: #2196f3; color: white; }
    .badge-entregada { background: #4caf50; color: white; }

    .tiempo-espera {
        font-weight: 600;
        font-size: 18px;
    }

    .tiempo-ok { color: #4caf50; }
    .tiempo-medio { color: #ff9800; }
    .tiempo-urgente { color: #f44336; }
</style>
{% endblock %}

{% block content %}
<div class="comandas-container">
    <div class="comandas-header">
        <h1>🍽️ Sistema de Comandas</h1>
        <div>
            <a href="?estado=activas" class="btn btn-primary">Activas</a>
            <a href="?estado=todas" class="btn">Todas</a>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-number" style="color: #ff9800;">{{ stats.pendientes }}</div>
            <div class="stat-label">Pendientes</div>
        </div>
        <div class="stat-card">
            <div class="stat-number" style="color: #2196f3;">{{ stats.procesando }}</div>
            <div class="stat-label">En Proceso</div>
        </div>
        <div class="stat-card">
            <div class="stat-number" style="color: #4caf50;">{{ stats.entregadas_hoy }}</div>
            <div class="stat-label">Entregadas Hoy</div>
        </div>
    </div>

    {% for comanda in comandas %}
    <div class="comanda-card">
        <div class="comanda-header {{ comanda.estado }}">
            <div>
                <strong>Comanda #{{ comanda.id }}</strong> -
                {{ comanda.venta_reserva.cliente.nombre }} -
                {{ comanda.hora_solicitud|time:"H:i" }}
                <span class="badge badge-{{ comanda.estado }}">{{ comanda.get_estado_display }}</span>
            </div>
            <div class="tiempo-espera
                {% if comanda.tiempo_espera < 10 %}tiempo-ok
                {% elif comanda.tiempo_espera < 20 %}tiempo-medio
                {% else %}tiempo-urgente{% endif %}">
                {{ comanda.tiempo_espera }} min
            </div>
        </div>

        <div class="comanda-body">
            {% for detalle in comanda.detalles.all %}
            <div class="producto-item">
                <div>
                    <strong>{{ detalle.cantidad }}x {{ detalle.producto.nombre }}</strong>
                    {% if detalle.especificaciones %}
                    <div class="especificaciones">{{ detalle.especificaciones }}</div>
                    {% endif %}
                </div>
                <div>${{ detalle.subtotal|intcomma }}</div>
            </div>
            {% endfor %}

            {% if comanda.notas_generales %}
            <div style="margin-top: 15px; padding: 10px; background: #fff9c4; border-radius: 4px;">
                <strong>📝 Notas:</strong> {{ comanda.notas_generales }}
            </div>
            {% endif %}
        </div>

        <div class="comanda-actions">
            {% if comanda.estado == 'pendiente' %}
            <button class="btn btn-primary" onclick="tomarComanda({{ comanda.id }})">
                Tomar Comanda
            </button>
            {% elif comanda.estado == 'procesando' %}
            <span style="color: #666;">Procesando por: <strong>{{ comanda.usuario_procesa }}</strong></span>
            <button class="btn btn-success" onclick="entregarComanda({{ comanda.id }})">
                Marcar Entregada
            </button>
            {% endif %}
        </div>
    </div>
    {% empty %}
    <div class="comanda-card">
        <div class="comanda-body" style="text-align: center; color: #999;">
            No hay comandas {{ estado_filtro }}
        </div>
    </div>
    {% endfor %}
</div>

<script>
function tomarComanda(comandaId) {
    if (confirm('¿Deseas tomar esta comanda?')) {
        fetch(`/ventas/comandas/${comandaId}/tomar/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': '{{ csrf_token }}',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert(data.message);
            }
        });
    }
}

function entregarComanda(comandaId) {
    if (confirm('¿Marcar esta comanda como entregada?')) {
        fetch(`/ventas/comandas/${comandaId}/entregar/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': '{{ csrf_token }}',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert(data.message);
            }
        });
    }
}

// Auto-refresh cada 30 segundos para comandas activas
{% if estado_filtro == 'activas' %}
setInterval(() => {
    location.reload();
}, 30000);
{% endif %}
</script>
{% endblock %}
```

---

### **FASE 5: Integración con VentaReserva** (1-2 horas)

#### 5.1 Agregar botón en admin de VentaReserva
```python
# En ventas/admin.py, dentro de VentaReservaAdmin

def generar_comanda_link(self, obj):
    """Botón para generar comanda desde la reserva"""
    if obj.pk:
        url = reverse('admin:ventas_comanda_add') + f'?venta_reserva={obj.pk}'
        return format_html(
            '<a class="button" href="{}" target="_blank">🍽️ Generar Comanda</a>',
            url
        )
    return '-'
generar_comanda_link.short_description = 'Comanda'

# Agregar a list_display
list_display = (
    # ... campos existentes ...
    'generar_comanda_link',
)
```

---

### **FASE 6: Testing y Ajustes** (1-2 horas)

#### Checklist de Testing
- [ ] Crear comanda desde admin de VentaReserva
- [ ] Agregar productos con especificaciones
- [ ] Visualizar en listado de comandas
- [ ] Tomar comanda (cambio a "procesando")
- [ ] Marcar como entregada
- [ ] Verificar tiempos de espera
- [ ] Probar filtros (activas, todas, etc.)
- [ ] Verificar permisos de usuarios
- [ ] Testing en móvil/tablet
- [ ] Auto-refresh funcional

---

## 📱 Características Adicionales (Opcionales)

### Notificaciones
- Sonido cuando llega nueva comanda
- Badge en menú con contador de pendientes
- Notificaciones push (futuro)

### Reportes
- Comandas por hora
- Tiempo promedio de entrega
- Productos más solicitados
- Performance por usuario

### Impresión
- Botón para imprimir comanda
- Formato ticket térmico
- Envío automático a impresora de cocina

---

## ⏱️ Estimación de Tiempos

| Fase | Tiempo Estimado |
|------|-----------------|
| Fase 1: Modelos y Migraciones | 2-3 horas |
| Fase 2: Admin Django | 1-2 horas |
| Fase 3: Vistas y URLs | 2-3 horas |
| Fase 4: Templates | 3-4 horas |
| Fase 5: Integración | 1-2 horas |
| Fase 6: Testing | 1-2 horas |
| **TOTAL** | **10-16 horas** |

---

## 🚀 Orden de Implementación Recomendado

1. ✅ Crear modelos `Comanda` y `DetalleComanda`
2. ✅ Crear y ejecutar migración manual `0080_comandas_system.py`
3. ✅ Configurar admin básico (sin inline primero)
4. ✅ Probar crear comanda desde admin
5. ✅ Agregar inline de DetalleComanda
6. ✅ Crear vista de listado básica
7. ✅ Crear template con estilos
8. ✅ Implementar acciones (tomar/entregar)
9. ✅ Agregar botón en VentaReserva
10. ✅ Testing completo
11. ✅ Optimizaciones y mejoras visuales

---

## 📝 Notas Importantes

- ✅ **Migración manual**: El archivo de migración está listo para copiar y ejecutar
- ✅ **Permisos**: Usar decorador `@login_required` en todas las vistas
- ✅ **Performance**: Índices compuestos en campos más consultados
- ✅ **UX**: Auto-refresh cada 30 segundos en vista de comandas activas
- ✅ **Auditoría**: Registro completo de quién hace qué y cuándo
- ✅ **Escalabilidad**: Preparado para agregar impresión y notificaciones

---

## 🎨 Ubicación en el Sistema

El acceso estará en **Control de Gestión**, junto a:
- 📅 Agenda Operativa
- 🍽️ **Sistema de Comandas** ← NUEVO
- 📦 Gestión de Inventario

---

¿Deseas que comience con la implementación? ¿Alguna modificación al plan?
