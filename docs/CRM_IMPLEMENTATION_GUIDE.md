# 📊 Guía de Implementación CRM con IA - Aremko

## ✅ Lo que YA está implementado

### 1. **Base de Datos** ✅
- ✅ Tabla `crm_service_history` con 26,158 servicios históricos (2020-2024)
- ✅ 3,053 clientes en `ventas_cliente`
- ✅ 961 clientes con historial
- ✅ $1,246,535,130 CLP en ingresos históricos

### 2. **Backend (Django)** ✅
- ✅ **Modelo `ServiceHistory`** en `ventas/models.py` (líneas 1642-1681)
- ✅ **Cliente API MCP** en `ventas/services/mcp_api_client.py`
- ✅ **Servicio CRM** en `ventas/services/crm_service.py`
- ✅ **Vistas CRM** en `ventas/views/crm_views.py`

### 3. **API FastAPI** ✅
- ✅ Servidor desplegado en Render
- ✅ Endpoints de propuestas personalizadas
- ✅ Motor de recomendaciones con 9 estrategias por segmento RFM
- ✅ Generación de emails HTML personalizados

---

## 📋 Pasos Finales para Completar

### **Paso 1: Crear Templates HTML**

Crear carpeta: `ventas/templates/ventas/crm/`

```bash
cd /Users/jorgeaguilera/Documents/GitHub/booking-system-aremko/ventas/templates/ventas
mkdir -p crm
```

#### **1.1 Dashboard** (`crm/dashboard.html`)

```django
{% extends "ventas/base.html" %}
{% load static %}

{% block content %}
<div class="container-fluid py-4">
    <h1 class="mb-4">CRM Dashboard</h1>

    {% if stats %}
    <div class="row">
        <!-- Métricas Principales -->
        <div class="col-md-3">
            <div class="card">
                <div class="card-body">
                    <h5>Clientes Totales</h5>
                    <h2>{{ stats.clientes.total }}</h2>
                    <small class="text-muted">{{ stats.clientes.con_historial }} con historial</small>
                </div>
            </div>
        </div>

        <div class="col-md-3">
            <div class="card">
                <div class="card-body">
                    <h5>Servicios este Mes</h5>
                    <h2>{{ stats.mes_actual.servicios }}</h2>
                </div>
            </div>
        </div>

        <div class="col-md-3">
            <div class="card">
                <div class="card-body">
                    <h5>Ingresos este Mes</h5>
                    <h2>${{ stats.mes_actual.ingresos|floatformat:0 }}</h2>
                </div>
            </div>
        </div>

        <div class="col-md-3">
            <div class="card">
                <div class="card-body">
                    <a href="{% url 'crm_buscar' %}" class="btn btn-primary btn-block">
                        <i class="fas fa-search"></i> Buscar Cliente
                    </a>
                </div>
            </div>
        </div>
    </div>

    <!-- Top Servicios -->
    <div class="row mt-4">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h5>Top Servicios</h5>
                </div>
                <div class="card-body">
                    <ul class="list-group">
                        {% for servicio in stats.top_servicios %}
                        <li class="list-group-item d-flex justify-content-between">
                            <span>{{ servicio.service_name }}</span>
                            <span class="badge badge-primary">{{ servicio.cantidad }}</span>
                        </li>
                        {% endfor %}
                    </ul>
                </div>
            </div>
        </div>

        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h5>Por Categoría</h5>
                </div>
                <div class="card-body">
                    <ul class="list-group">
                        {% for cat in stats.por_categoria %}
                        <li class="list-group-item d-flex justify-content-between">
                            <span>{{ cat.service_type }}</span>
                            <span>
                                <span class="badge badge-info">{{ cat.cantidad }}</span>
                                <span class="text-muted">${{ cat.ingresos|floatformat:0 }}</span>
                            </span>
                        </li>
                        {% endfor %}
                    </ul>
                </div>
            </div>
        </div>
    </div>
    {% else %}
    <div class="alert alert-warning">No se pudieron cargar las estadísticas.</div>
    {% endif %}
</div>
{% endblock %}
```

#### **1.2 Búsqueda** (`crm/buscar.html`)

```django
{% extends "ventas/base.html" %}
{% load static %}

{% block content %}
<div class="container py-4">
    <h1>Buscar Cliente</h1>

    <form method="get" class="mb-4">
        <div class="input-group">
            <input type="text" name="q" class="form-control"
                   placeholder="Buscar por nombre, teléfono o email..."
                   value="{{ query }}">
            <button type="submit" class="btn btn-primary">
                <i class="fas fa-search"></i> Buscar
            </button>
        </div>
    </form>

    {% if resultados %}
    <div class="card">
        <div class="card-header">
            <h5>Resultados ({{ resultados|length }})</h5>
        </div>
        <div class="list-group list-group-flush">
            {% for cliente in resultados %}
            <a href="{% url 'cliente_detalle' cliente.id %}"
               class="list-group-item list-group-item-action">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-1">{{ cliente.nombre }}</h6>
                        <small class="text-muted">{{ cliente.telefono }}</small>
                    </div>
                    <div class="text-right">
                        <span class="badge badge-primary">{{ cliente.total_servicios }} servicios</span>
                        {% if cliente.ultimo_servicio %}
                        <br><small class="text-muted">Último: {{ cliente.ultimo_servicio }}</small>
                        {% endif %}
                    </div>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
    {% elif query %}
    <div class="alert alert-info">No se encontraron resultados para "{{ query }}"</div>
    {% endif %}
</div>
{% endblock %}
```

#### **1.3 Detalle de Cliente** (`crm/cliente_detalle.html`)

```django
{% extends "ventas/base.html" %}
{% load static %}

{% block content %}
<div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h1>{{ cliente.nombre }}</h1>
        <div>
            <button class="btn btn-info" onclick="generarPropuesta()">
                <i class="fas fa-magic"></i> Generar Propuesta
            </button>
            <button class="btn btn-success" onclick="enviarPropuesta()" id="btnEnviar" style="display:none;">
                <i class="fas fa-paper-plane"></i> Enviar Email
            </button>
        </div>
    </div>

    <!-- Info del Cliente -->
    <div class="row">
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5>Información</h5>
                </div>
                <div class="card-body">
                    <p><strong>Teléfono:</strong> {{ cliente.telefono }}</p>
                    <p><strong>Email:</strong> {{ cliente.email|default:"No especificado" }}</p>
                    <p><strong>País:</strong> {{ cliente.pais|default:"No especificado" }}</p>
                </div>
            </div>

            <div class="card mt-3">
                <div class="card-header">
                    <h5>Métricas</h5>
                </div>
                <div class="card-body">
                    <p><strong>Total Servicios:</strong> {{ perfil.metricas.total_servicios }}</p>
                    <p><strong>Gasto Total:</strong> ${{ perfil.metricas.gasto_total|floatformat:0 }}</p>
                    <p><strong>Ticket Promedio:</strong> ${{ perfil.metricas.ticket_promedio|floatformat:0 }}</p>
                    <p><strong>Cliente desde:</strong> {{ perfil.metricas.primer_servicio }}</p>
                    <p><strong>Último servicio:</strong> {{ perfil.metricas.ultimo_servicio }}</p>
                </div>
            </div>

            <div class="card mt-3">
                <div class="card-header">
                    <h5>Segmentación</h5>
                </div>
                <div class="card-body">
                    <h4>
                        <span class="badge badge-{% if perfil.segmentacion.is_vip %}success{% elif perfil.segmentacion.en_riesgo %}warning{% else %}info{% endif %}">
                            {{ perfil.segmentacion.rfm_segment }}
                        </span>
                    </h4>
                </div>
            </div>
        </div>

        <!-- Historial -->
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h5>Historial Reciente</h5>
                </div>
                <div class="card-body">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Fecha</th>
                                <th>Servicio</th>
                                <th>Tipo</th>
                                <th>Precio</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for servicio in perfil.historial_reciente %}
                            <tr>
                                <td>{{ servicio.fecha }}</td>
                                <td>{{ servicio.servicio }}</td>
                                <td><span class="badge badge-secondary">{{ servicio.tipo }}</span></td>
                                <td>${{ servicio.precio|floatformat:0 }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Preview de Propuesta -->
            <div class="card mt-3" id="propuestaCard" style="display:none;">
                <div class="card-header">
                    <h5>Propuesta Personalizada</h5>
                </div>
                <div class="card-body" id="propuestaContent">
                    <!-- Se llena con AJAX -->
                </div>
            </div>
        </div>
    </div>
</div>

<script>
function generarPropuesta() {
    fetch("{% url 'generar_propuesta' cliente.id %}", {
        method: 'POST',
        headers: {
            'X-CSRFToken': '{{ csrf_token }}',
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('propuestaCard').style.display = 'block';
            document.getElementById('propuestaContent').innerHTML = data.propuesta.email_body;
            document.getElementById('btnEnviar').style.display = 'inline-block';
            alert('Propuesta generada exitosamente!');
        } else {
            alert('Error generando propuesta: ' + data.error);
        }
    })
    .catch(error => alert('Error: ' + error));
}

function enviarPropuesta() {
    if (confirm('¿Enviar propuesta por email a {{ cliente.email }}?')) {
        fetch("{% url 'enviar_propuesta' cliente.id %}", {
            method: 'POST',
            headers: {
                'X-CSRFToken': '{{ csrf_token }}',
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Propuesta enviada exitosamente!');
            } else {
                alert('Error enviando: ' + data.error);
            }
        })
        .catch(error => alert('Error: ' + error));
    }
}
</script>
{% endblock %}
```

---

### **Paso 2: Agregar Rutas**

Editar `ventas/urls.py` y agregar:

```python
from ventas.views import crm_views

urlpatterns = [
    # ... rutas existentes ...

    # ============ CRM Routes ============
    path('crm/', crm_views.crm_dashboard, name='crm_dashboard'),
    path('crm/buscar/', crm_views.crm_buscar, name='crm_buscar'),
    path('crm/cliente/<int:cliente_id>/', crm_views.cliente_detalle, name='cliente_detalle'),
    path('crm/cliente/<int:cliente_id>/propuesta/', crm_views.generar_propuesta, name='generar_propuesta'),
    path('crm/cliente/<int:cliente_id>/enviar/', crm_views.enviar_propuesta, name='enviar_propuesta'),
    path('crm/cliente/<int:cliente_id>/historial/', crm_views.historial_servicios, name='historial_servicios'),
    path('crm/cliente/<int:cliente_id>/preview/', crm_views.propuesta_preview, name='propuesta_preview'),
]
```

---

### **Paso 3: Actualizar URL del API**

Editar `ventas/services/mcp_api_client.py` línea 13:

```python
BASE_URL = "https://TU_URL_RENDER.onrender.com/aremko"  # Actualizar con tu URL real
```

---

### **Paso 4: Instalar Dependencias**

```bash
cd /Users/jorgeaguilera/Documents/GitHub/booking-system-aremko
pip install httpx
```

---

### **Paso 5: Probar Localmente**

```bash
cd /Users/jorgeaguilera/Documents/GitHub/booking-system-aremko
python manage.py runserver
```

**URLs para probar:**
- Dashboard CRM: `http://localhost:8000/crm/`
- Buscar Cliente: `http://localhost:8000/crm/buscar/`
- Detalle Cliente: `http://localhost:8000/crm/cliente/1/`

---

## 🎯 Funcionalidades Implementadas

### ✅ **Dashboard CRM**
- Métricas generales (clientes totales, servicios del mes, ingresos)
- Top servicios más vendidos
- Distribución por categorías

### ✅ **Búsqueda de Clientes**
- Por nombre, teléfono o email
- Muestra total de servicios y último servicio

### ✅ **Vista 360° del Cliente**
- Información completa del cliente
- Historial de servicios
- Métricas (gasto total, ticket promedio, etc.)
- Segmento RFM calculado

### ✅ **Propuestas Personalizadas con IA**
- Genera propuesta basada en historial y comportamiento
- Preview antes de enviar
- Envío por email con un click
- HTML personalizado por segmento RFM

---

## 📊 Arquitectura Final

```
┌─────────────────────────────────────────────────────┐
│                Django (Aremko)                      │
│                                                     │
│  ┌──────────────┐      ┌──────────────┐           │
│  │   Views      │◄────►│   Services   │           │
│  │  (CRM)       │      │  - CRM       │           │
│  └──────┬───────┘      │  - MCP API   │           │
│         │              └──────┬────────┘           │
│         │                     │                    │
│  ┌──────▼───────┐      ┌─────▼────────┐          │
│  │  Templates   │      │   Models     │           │
│  │  (HTML)      │      │  - Cliente   │           │
│  └──────────────┘      │  - Service   │           │
│                        │    History   │           │
│                        └──────┬────────┘           │
└───────────────────────────────┼────────────────────┘
                                │
                        ┌───────▼────────┐
                        │   PostgreSQL   │
                        │   (Render)     │
                        │  26,158 svcs   │
                        └───────▲────────┘
                                │
┌───────────────────────────────┼────────────────────┐
│            FastAPI (MCP Server - Render)           │
│                                                    │
│  ┌──────────────┐      ┌──────────────┐          │
│  │  Proposals   │◄────►│ Recommenda-  │          │
│  │  Endpoints   │      │ tions Engine │          │
│  └──────────────┘      └──────────────┘          │
│                                                    │
│  - RFM Analysis (9 segments)                      │
│  - Personalized recommendations                   │
│  - HTML email generation                          │
│  - Promo code generation                          │
└───────────────────────────────────────────────────┘
```

---

## 🔧 Troubleshooting

### Error: "Module 'httpx' not found"
```bash
pip install httpx
```

### Error: "Template does not exist"
Verificar que la carpeta `ventas/templates/ventas/crm/` existe con los templates.

### Error: "No module named 'ventas.services.crm_service'"
Verificar que el archivo `ventas/services/crm_service.py` existe.

### Error en API: "Connection refused"
Verificar que la URL del API en `mcp_api_client.py` es correcta.

---

## 📝 Próximos Pasos Opcionales

1. **Agregar al Admin de Django** - Para gestionar ServiceHistory
2. **Mejorar Templates** - Agregar gráficos con Chart.js
3. **Agregar Filtros** - Por segmento RFM, fecha, categoría
4. **Exportar Reportes** - CSV/Excel de clientes y métricas
5. **Notificaciones** - Alertas para clientes en riesgo
6. **Dashboard Avanzado** - Gráficos de tendencias y análisis

---

## ✅ Checklist de Implementación

- [x] Modelo ServiceHistory agregado
- [x] Cliente API creado
- [x] Servicio CRM creado
- [x] Vistas CRM creadas
- [ ] Templates HTML creados
- [ ] Rutas agregadas a urls.py
- [ ] URL del API actualizada
- [ ] Dependencias instaladas
- [ ] Probado localmente
- [ ] Desplegado a producción

---

## 🎉 ¡Listo para Usar!

Una vez completados los pasos finales, tendrás un CRM completo con:
- ✅ 26,158 servicios históricos
- ✅ Análisis RFM automático
- ✅ Propuestas personalizadas con IA
- ✅ Envío de emails automatizado
- ✅ Dashboard con métricas en tiempo real

**Desarrollado con ❤️ por Claude Code**
