# Organización y Escalabilidad del Sistema de Comandas

## 🎯 Problemática Identificada

**Pregunta clave**: ¿Cómo organizar comandas cuando hay cientos de registros de varios días?

**Problemas a resolver**:
1. Performance: No cargar cientos de comandas antiguas innecesariamente
2. Usabilidad: El personal necesita ver SOLO lo relevante de HOY
3. Historial: Los administradores necesitan buscar comandas antiguas
4. Limpieza: ¿Qué hacer con comandas entregadas de hace días?

---

## ✅ Solución Propuesta: Sistema de Dos Vistas

### **1. Vista Operativa "Cocina" (Por Defecto)**

**URL**: `/ventas/comandas/`

**Propósito**: Operación diaria del personal

**Muestra SOLO**:
- ✅ Comandas de HOY (fecha actual)
- ✅ Estados: Pendiente + En Proceso
- ✅ Auto-refresh cada 30 segundos
- ✅ Ordenadas por prioridad y hora

**Organización**:
```
┌─────────────────────────────────────┐
│  🍽️ COMANDAS ACTIVAS - Hoy         │
│                                     │
│  📊 Estadísticas                    │
│  [5] Pendientes  [3] En Proceso    │
│                                     │
│  🔴 URGENTE (>20 min espera)        │
│  ├─ Comanda #125 - 25 min          │
│  └─ Comanda #123 - 22 min          │
│                                     │
│  🟠 MEDIA PRIORIDAD (10-20 min)     │
│  ├─ Comanda #126 - 15 min          │
│  └─ Comanda #127 - 12 min          │
│                                     │
│  🟢 NUEVAS (<10 min)                │
│  ├─ Comanda #128 - 5 min           │
│  ├─ Comanda #129 - 3 min           │
│  └─ Comanda #130 - 1 min           │
└─────────────────────────────────────┘
```

**Query optimizado**:
```python
comandas = Comanda.objects.filter(
    fecha_solicitud__date=timezone.now().date(),  # Solo hoy
    estado__in=['pendiente', 'procesando']        # Solo activas
).select_related('venta_reserva__cliente', 'usuario_procesa')
 .prefetch_related('detalles__producto')
 .order_by('estado', 'fecha_solicitud')[:50]     # Máximo 50
```

**Características**:
- ⚡ Súper rápida (solo comandas de hoy activas)
- 🔄 Auto-refresh cada 30 segundos
- 📱 Optimizada para tablets en cocina/bar
- 🎨 Colores por urgencia (rojo/naranja/verde)

---

### **2. Vista Administrativa "Historial"**

**URL**: `/ventas/comandas/historial/`

**Propósito**: Búsqueda, análisis y auditoría

**Funcionalidades**:
- 📅 Filtro por rango de fechas
- 🔍 Búsqueda por cliente, número de comanda
- 📊 Filtro por estado (todas, entregadas, canceladas)
- 👤 Filtro por usuario que procesó
- 📄 Paginación (20-50 por página)
- 📥 Exportar a Excel

**Organización**:
```
┌─────────────────────────────────────────────────┐
│  📋 HISTORIAL DE COMANDAS                       │
│                                                 │
│  🔍 Filtros:                                   │
│  Desde: [11/02/2026] Hasta: [12/02/2026]       │
│  Estado: [Todas ▼] Usuario: [Todos ▼]         │
│  Cliente: [________] [Buscar]                  │
│                                                 │
│  📊 Resumen del período:                       │
│  Total: 156 | Promedio entrega: 12 min        │
│                                                 │
│  📄 Resultados (Página 1 de 8):                │
│  ┌─────────────────────────────────────┐       │
│  │ #125 | 11/02 14:30 | Juan Pérez     │       │
│  │ Estado: Entregada | 15 min          │       │
│  │ 2x Café, 1x Jugo Natural            │       │
│  └─────────────────────────────────────┘       │
│  ┌─────────────────────────────────────┐       │
│  │ #124 | 11/02 14:15 | María López    │       │
│  │ Estado: Entregada | 10 min          │       │
│  │ 1x Sandwich, 1x Agua                │       │
│  └─────────────────────────────────────┘       │
│                                                 │
│  [← Anterior] [1][2][3]...[8] [Siguiente →]   │
│  [📥 Exportar a Excel]                         │
└─────────────────────────────────────────────────┘
```

**Query con filtros**:
```python
comandas = Comanda.objects.all()

# Filtro por rango de fechas (default: últimos 7 días)
fecha_desde = request.GET.get('fecha_desde', timezone.now().date() - timedelta(days=7))
fecha_hasta = request.GET.get('fecha_hasta', timezone.now().date())
comandas = comandas.filter(fecha_solicitud__date__range=[fecha_desde, fecha_hasta])

# Otros filtros opcionales
if estado := request.GET.get('estado'):
    comandas = comandas.filter(estado=estado)

if usuario_id := request.GET.get('usuario'):
    comandas = comandas.filter(usuario_procesa_id=usuario_id)

if cliente := request.GET.get('cliente'):
    comandas = comandas.filter(venta_reserva__cliente__nombre__icontains=cliente)

# Paginación
comandas = comandas.order_by('-fecha_solicitud')
paginator = Paginator(comandas, 20)  # 20 por página
```

---

## 📊 Estrategia de Datos por Volumen

### Escenario 1: Operación Pequeña (< 50 comandas/día)
**Solución**: Vista simple con tabs
```
[Activas] [Hoy Completadas] [Historial]
```
- Sin paginación en "Activas"
- Paginación solo en "Historial"

### Escenario 2: Operación Media (50-200 comandas/día)
**Solución**: Vistas separadas + Auto-archivo
```
Vista Cocina: Solo activas de HOY
Vista Historial: Paginada con filtros
Auto-archivo: Comandas >7 días se marcan como "archivadas"
```

### Escenario 3: Operación Grande (>200 comandas/día)
**Solución**: Sistema completo con limpieza automática
```
Vista Cocina: Solo activas de HOY
Vista Historial: Filtros obligatorios + Paginación
Limpieza: Comandas >30 días se eliminan automáticamente
Reportes: Dashboard con estadísticas agregadas
```

---

## 🗂️ Gestión del Ciclo de Vida de Comandas

### Estado de las Comandas

| Estado | Tiempo de Vida | Acción |
|--------|----------------|--------|
| **Pendiente** | Hasta que alguien la tome | Visible en Vista Cocina |
| **Procesando** | Hasta que se marque entregada | Visible en Vista Cocina |
| **Entregada HOY** | Resto del día | Oculta de Vista Cocina, pero en historial de hoy |
| **Entregada >1 día** | Hasta 30 días | Solo en Vista Historial |
| **Antigua >30 días** | Indefinido | Opcional: Archivar o eliminar |

### Auto-limpieza Programada (Opcional)

**Comando cron diario** (ejecutar a las 3:00 AM):
```python
# ventas/management/commands/limpiar_comandas_antiguas.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from ventas.models import Comanda

class Command(BaseCommand):
    help = 'Limpia comandas antiguas para mantener la BD optimizada'

    def handle(self, *args, **options):
        fecha_limite = timezone.now() - timedelta(days=30)

        # Opción 1: Eliminar (más agresivo)
        comandas_antiguas = Comanda.objects.filter(
            fecha_solicitud__lt=fecha_limite,
            estado='entregada'
        )
        total = comandas_antiguas.count()
        comandas_antiguas.delete()

        self.stdout.write(
            self.style.SUCCESS(f'✅ Eliminadas {total} comandas antiguas')
        )
```

**Añadir a cron**:
```python
# En ventas/urls.py - Cron jobs
path('cron/limpiar-comandas/', cron_views.cron_limpiar_comandas, name='cron_limpiar_comandas'),
```

---

## 🎨 Diseño de Interfaz Propuesto

### Navegación Principal

```
┌────────────────────────────────────────────┐
│  AREMKO - Control de Gestión              │
├────────────────────────────────────────────┤
│  [📅 Agenda] [🍽️ Comandas] [📦 Inventario] │
└────────────────────────────────────────────┘

Al hacer click en "Comandas":

┌────────────────────────────────────────────┐
│  🍽️ Sistema de Comandas                    │
│  [🔥 Vista Cocina] [📋 Historial]          │
└────────────────────────────────────────────┘

Por defecto: Vista Cocina (comandas activas de hoy)
```

### Vista Cocina - Organización por Urgencia

**Agrupación dinámica por tiempo de espera**:

```python
def organizar_comandas_por_urgencia(comandas):
    """Organiza comandas en 3 grupos según tiempo de espera"""
    urgentes = []     # >20 min
    medias = []       # 10-20 min
    nuevas = []       # <10 min

    for comanda in comandas:
        tiempo = comanda.tiempo_espera()
        if tiempo > 20:
            urgentes.append(comanda)
        elif tiempo >= 10:
            medias.append(comanda)
        else:
            nuevas.append(comanda)

    return {
        'urgentes': urgentes,
        'medias': medias,
        'nuevas': nuevas
    }
```

**Template con secciones**:
```html
{% if urgentes %}
<div class="seccion-urgente">
    <h2>🔴 URGENTE - Más de 20 minutos</h2>
    {% for comanda in urgentes %}
        <!-- Card de comanda -->
    {% endfor %}
</div>
{% endif %}

{% if medias %}
<div class="seccion-media">
    <h2>🟠 PRIORIDAD MEDIA - 10-20 minutos</h2>
    {% for comanda in medias %}
        <!-- Card de comanda -->
    {% endfor %}
</div>
{% endif %}

{% if nuevas %}
<div class="seccion-nueva">
    <h2>🟢 NUEVAS - Menos de 10 minutos</h2>
    {% for comanda in nuevas %}
        <!-- Card de comanda -->
    {% endfor %}
</div>
{% endif %}
```

---

## 📱 Vista Móvil/Tablet Optimizada

**Consideraciones**:
- La Vista Cocina se usará en tablets/celulares
- Necesita ser responsive
- Botones grandes para tocar fácilmente
- Colores contrastantes

**Breakpoints**:
```css
/* Móvil: 1 columna */
@media (max-width: 768px) {
    .comandas-grid {
        grid-template-columns: 1fr;
    }
}

/* Tablet: 2 columnas */
@media (min-width: 769px) and (max-width: 1024px) {
    .comandas-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}

/* Desktop: 3 columnas */
@media (min-width: 1025px) {
    .comandas-grid {
        grid-template-columns: repeat(3, 1fr);
    }
}
```

---

## 🔍 Sistema de Búsqueda Avanzada

**En Vista Historial**, incluir:

```
┌─────────────────────────────────────────┐
│  🔍 Búsqueda Avanzada                   │
├─────────────────────────────────────────┤
│  Por fecha:                             │
│  ○ Hoy                                  │
│  ○ Ayer                                 │
│  ○ Últimos 7 días                       │
│  ● Rango personalizado:                 │
│    [11/02/2026] - [12/02/2026]         │
│                                         │
│  Por estado:                            │
│  ☑ Pendientes  ☑ Procesando            │
│  ☑ Entregadas  ☐ Canceladas            │
│                                         │
│  Por cliente:                           │
│  [Nombre del cliente_______] 🔍        │
│                                         │
│  Por producto:                          │
│  [Nombre del producto______] 🔍        │
│                                         │
│  Por usuario:                           │
│  [Usuario que procesó_____] ▼          │
│                                         │
│  [Limpiar Filtros] [Buscar]            │
└─────────────────────────────────────────┘
```

---

## 📊 Dashboard de Estadísticas (Bonus)

**URL**: `/ventas/comandas/dashboard/`

**Muestra**:
- Comandas por día (gráfico de barras)
- Productos más pedidos (top 10)
- Tiempo promedio de entrega por día
- Performance por usuario (quién es más rápido)
- Horarios pico (cuándo hay más pedidos)

**Utilidad**:
- Identificar patrones
- Optimizar staffing
- Detectar problemas de performance
- Análisis de inventario

---

## 🎯 Recomendación Final

### Implementación por Fases:

**FASE 1 (MVP)**: Vista Cocina básica
- Solo comandas activas de HOY
- Sin paginación (máximo 50)
- Ordenadas por tiempo de espera
- Auto-refresh

**FASE 2**: Vista Historial
- Búsqueda por fecha
- Paginación
- Filtros básicos

**FASE 3**: Optimizaciones
- Agrupación por urgencia
- Auto-limpieza
- Exportar a Excel

**FASE 4**: Analytics
- Dashboard con gráficos
- Reportes automáticos

---

## 💾 Queries Optimizados

### Query para Vista Cocina (Ultra rápida)
```python
from django.utils import timezone

def get_comandas_activas():
    """Comandas activas solo de hoy - Super optimizada"""
    hoy = timezone.now().date()

    return Comanda.objects.filter(
        fecha_solicitud__date=hoy,
        estado__in=['pendiente', 'procesando']
    ).select_related(
        'venta_reserva__cliente',
        'usuario_procesa'
    ).prefetch_related(
        'detalles__producto'
    ).order_by(
        models.Case(
            models.When(estado='pendiente', then=0),
            models.When(estado='procesando', then=1),
        ),
        'fecha_solicitud'
    )[:50]  # Máximo 50 comandas activas
```

### Query para Vista Historial (Con filtros)
```python
def get_comandas_historial(filtros):
    """Comandas históricas con paginación"""
    comandas = Comanda.objects.all()

    # Fecha por defecto: últimos 7 días
    if not filtros.get('fecha_desde'):
        filtros['fecha_desde'] = timezone.now().date() - timedelta(days=7)

    if not filtros.get('fecha_hasta'):
        filtros['fecha_hasta'] = timezone.now().date()

    comandas = comandas.filter(
        fecha_solicitud__date__range=[
            filtros['fecha_desde'],
            filtros['fecha_hasta']
        ]
    )

    # Filtros opcionales
    if filtros.get('estado'):
        comandas = comandas.filter(estado=filtros['estado'])

    if filtros.get('cliente'):
        comandas = comandas.filter(
            venta_reserva__cliente__nombre__icontains=filtros['cliente']
        )

    return comandas.select_related(
        'venta_reserva__cliente'
    ).order_by('-fecha_solicitud')
```

---

## 🎨 Propuesta de URLs Final

```python
# Sistema de Comandas
urlpatterns = [
    # Vista principal (Cocina - Activas de hoy)
    path('comandas/',
         comandas_view.vista_cocina,
         name='comandas_cocina'),

    # Vista Historial
    path('comandas/historial/',
         comandas_view.historial_comandas,
         name='comandas_historial'),

    # Dashboard de estadísticas
    path('comandas/dashboard/',
         comandas_view.dashboard_comandas,
         name='comandas_dashboard'),

    # Acciones
    path('comandas/<int:comanda_id>/tomar/',
         comandas_view.tomar_comanda,
         name='comandas_tomar'),

    path('comandas/<int:comanda_id>/entregar/',
         comandas_view.entregar_comanda,
         name='comandas_entregar'),

    path('comandas/<int:comanda_id>/cancelar/',
         comandas_view.cancelar_comanda,
         name='comandas_cancelar'),

    # Detalle
    path('comandas/<int:comanda_id>/',
         comandas_view.detalle_comanda,
         name='comandas_detalle'),

    # Exportar
    path('comandas/exportar/',
         comandas_view.exportar_excel,
         name='comandas_exportar'),
]
```

---

## ✅ Ventajas de esta Arquitectura

1. ⚡ **Performance**: Vista Cocina carga solo ~10-50 registros máximo
2. 🎯 **Foco**: Personal ve solo lo relevante (hoy, activas)
3. 📊 **Análisis**: Admins tienen historial completo con filtros
4. 🧹 **Limpieza**: Auto-archivado mantiene BD ligera
5. 📱 **UX**: Interface adaptada al uso (cocina vs administración)
6. 🔍 **Búsqueda**: Historial permite encontrar cualquier comanda antigua
7. 📈 **Escalable**: Funciona con 10 o 1000 comandas/día

---

¿Te parece bien esta organización? ¿Quieres ajustar algo?
