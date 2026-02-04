# 🔧 Guía de Desarrollo - Aremko Booking System

## 📑 Tabla de Contenidos

- [Configuración del Entorno](#configuración-del-entorno)
- [Estándares de Código](#estándares-de-código)
- [Flujo de Trabajo Git](#flujo-de-trabajo-git)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Desarrollo de Features](#desarrollo-de-features)
- [Testing](#testing)
- [Debugging](#debugging)
- [Deployment](#deployment)
- [Mejores Prácticas](#mejores-prácticas)
- [Recursos Útiles](#recursos-útiles)

## 💻 Configuración del Entorno

### Entorno de Desarrollo Recomendado

```bash
# Herramientas recomendadas
- IDE: VS Code o PyCharm
- Python: 3.11+
- Git: 2.30+
- PostgreSQL: 13+
- Docker: 20+ (opcional)
```

### Configuración VS Code

```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.formatting.blackPath": "black",
  "editor.formatOnSave": true,
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".pytest_cache": true
  }
}
```

### Extensiones VS Code Recomendadas

```json
// .vscode/extensions.json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "batisteo.vscode-django",
    "wholroyd.jinja",
    "coenraads.bracket-pair-colorizer-2",
    "streetsidesoftware.code-spell-checker",
    "streetsidesoftware.code-spell-checker-spanish"
  ]
}
```

### Pre-commit Hooks

```bash
# Instalar pre-commit
pip install pre-commit

# Configurar hooks
pre-commit install
```

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 22.3.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/flake8
    rev: 4.0.1
    hooks:
      - id: flake8
        args: ['--max-line-length=120', '--exclude=migrations']

  - repo: https://github.com/pycqa/isort
    rev: 5.10.1
    hooks:
      - id: isort
        args: ['--profile', 'black']
```

## 📝 Estándares de Código

### Python (PEP 8 + Django)

```python
# Imports - ordenados con isort
import os
import sys
from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

from ventas.models import Cliente
from .utils import calculate_discount


# Constantes
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30


# Clases - CamelCase
class ReservaService:
    """
    Servicio para gestionar reservas.

    Este servicio maneja la lógica de negocio relacionada
    con la creación y gestión de reservas.
    """

    def __init__(self, user=None):
        self.user = user
        self._cache = {}

    def create_reservation(self, service_id: int, date: datetime) -> 'VentaReserva':
        """
        Crea una nueva reserva.

        Args:
            service_id: ID del servicio a reservar
            date: Fecha y hora de la reserva

        Returns:
            VentaReserva: Instancia de la reserva creada

        Raises:
            ValidationError: Si el servicio no está disponible
        """
        # Implementación...
        pass


# Funciones - snake_case
def calculate_total_with_discount(subtotal: float, discount_percent: float) -> float:
    """Calcula el total aplicando descuento."""
    if not 0 <= discount_percent <= 100:
        raise ValueError("El descuento debe estar entre 0 y 100")

    discount = subtotal * (discount_percent / 100)
    return subtotal - discount


# Variables - snake_case
user_count = User.objects.filter(is_active=True).count()
is_valid = True
```

### Modelos Django

```python
class Servicio(models.Model):
    """
    Modelo para servicios ofrecidos por el spa.
    """
    # Campos básicos
    nombre = models.CharField(
        max_length=200,
        help_text="Nombre del servicio"
    )
    slug = models.SlugField(
        unique=True,
        help_text="URL amigable del servicio"
    )

    # Relaciones
    categoria = models.ForeignKey(
        'CategoriaServicio',
        on_delete=models.PROTECT,
        related_name='servicios'
    )

    # Campos de precio
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Precio en CLP"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"
        ordering = ['categoria', 'nombre']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['categoria', 'activo']),
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        """Validación del modelo."""
        if self.precio < 0:
            raise ValidationError("El precio no puede ser negativo")

    def save(self, *args, **kwargs):
        """Override save para auto-generar slug."""
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    @property
    def precio_formateado(self):
        """Retorna el precio formateado como moneda."""
        return f"${self.precio:,.0f}"

    def esta_disponible(self, fecha):
        """Verifica disponibilidad en fecha específica."""
        # Lógica de disponibilidad
        return True
```

### Vistas Django

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q

from .models import Servicio, VentaReserva
from .forms import ReservaForm


class ServicioListView(ListView):
    """Vista para listar servicios disponibles."""
    model = Servicio
    template_name = 'ventas/servicio_list.html'
    context_object_name = 'servicios'
    paginate_by = 12

    def get_queryset(self):
        """Filtra servicios activos y por categoría si se especifica."""
        queryset = super().get_queryset().filter(activo=True)

        # Filtro por categoría
        categoria_slug = self.kwargs.get('categoria_slug')
        if categoria_slug:
            queryset = queryset.filter(categoria__slug=categoria_slug)

        # Búsqueda
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(nombre__icontains=q) |
                Q(descripcion__icontains=q)
            )

        return queryset.select_related('categoria').prefetch_related('imagenes')

    def get_context_data(self, **kwargs):
        """Agrega contexto adicional."""
        context = super().get_context_data(**kwargs)
        context['categorias'] = CategoriaServicio.objects.all()
        context['q'] = self.request.GET.get('q', '')
        return context


def crear_reserva(request, servicio_id):
    """
    Vista funcional para crear una reserva.

    Maneja GET para mostrar formulario y POST para procesar.
    """
    servicio = get_object_or_404(Servicio, id=servicio_id, activo=True)

    if request.method == 'POST':
        form = ReservaForm(request.POST, servicio=servicio)
        if form.is_valid():
            try:
                reserva = form.save(commit=False)
                reserva.usuario = request.user if request.user.is_authenticated else None
                reserva.save()

                messages.success(
                    request,
                    f"Reserva creada exitosamente. Código: {reserva.codigo}"
                )
                return redirect('checkout', reserva_id=reserva.id)

            except Exception as e:
                messages.error(request, f"Error al crear reserva: {str(e)}")
        else:
            messages.error(request, "Por favor corrige los errores del formulario")
    else:
        form = ReservaForm(servicio=servicio)

    context = {
        'servicio': servicio,
        'form': form,
        'horarios_disponibles': servicio.get_horarios_disponibles(),
    }

    return render(request, 'ventas/crear_reserva.html', context)
```

### JavaScript

```javascript
// static/js/reservas.js

/**
 * Módulo de gestión de reservas
 */
const ReservasModule = (function() {
    'use strict';

    // Variables privadas
    let selectedDate = null;
    let selectedTime = null;
    let availableSlots = {};

    /**
     * Inicializa el módulo
     */
    function init() {
        bindEvents();
        loadAvailableSlots();
    }

    /**
     * Vincula eventos del DOM
     */
    function bindEvents() {
        // Cambio de fecha
        document.getElementById('fecha-reserva')?.addEventListener('change', handleDateChange);

        // Click en slot de hora
        document.querySelectorAll('.time-slot').forEach(slot => {
            slot.addEventListener('click', handleTimeSlotClick);
        });

        // Formulario submit
        document.getElementById('form-reserva')?.addEventListener('submit', handleFormSubmit);
    }

    /**
     * Maneja cambio de fecha
     */
    function handleDateChange(event) {
        selectedDate = event.target.value;
        updateAvailableSlots();
    }

    /**
     * Carga slots disponibles via AJAX
     */
    async function loadAvailableSlots() {
        try {
            const response = await fetch('/api/disponibilidad/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    servicio_id: servicioId,
                    fecha: selectedDate
                })
            });

            if (!response.ok) throw new Error('Error al cargar disponibilidad');

            availableSlots = await response.json();
            renderTimeSlots();

        } catch (error) {
            console.error('Error:', error);
            showError('No se pudo cargar la disponibilidad');
        }
    }

    /**
     * Obtiene CSRF token
     */
    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    /**
     * Muestra mensaje de error
     */
    function showError(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.querySelector('.messages-container')?.appendChild(alertDiv);
    }

    // API pública
    return {
        init: init,
        getSelectedSlot: () => ({ date: selectedDate, time: selectedTime })
    };
})();

// Inicializar cuando DOM esté listo
document.addEventListener('DOMContentLoaded', ReservasModule.init);
```

### CSS/SCSS

```scss
// static/css/components/_reservas.scss

// Variables
$primary-color: #2c3e50;
$accent-color: #e74c3c;
$success-color: #27ae60;
$border-radius: 8px;

// Componente de calendario
.calendario-reservas {
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;

    &__header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.5rem;

        h2 {
            color: $primary-color;
            font-size: 1.5rem;
            margin: 0;
        }
    }

    &__grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 0.5rem;

        @media (max-width: 768px) {
            grid-template-columns: repeat(4, 1fr);
        }
    }

    &__slot {
        padding: 1rem;
        text-align: center;
        border: 2px solid #e0e0e0;
        border-radius: $border-radius;
        cursor: pointer;
        transition: all 0.3s ease;

        &:hover:not(.disabled) {
            border-color: $accent-color;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }

        &.selected {
            background-color: $accent-color;
            color: white;
            border-color: $accent-color;
        }

        &.disabled {
            opacity: 0.5;
            cursor: not-allowed;
            background-color: #f5f5f5;
        }

        &__time {
            font-weight: bold;
            font-size: 1.1rem;
        }

        &__status {
            font-size: 0.875rem;
            margin-top: 0.25rem;
            color: #666;
        }
    }
}

// Utilidades responsive
@media print {
    .no-print {
        display: none !important;
    }
}
```

## 🌿 Flujo de Trabajo Git

### Estructura de Ramas

```
main (producción)
├── develop (desarrollo)
│   ├── feature/nueva-funcionalidad
│   ├── feature/mejora-dashboard
│   └── feature/fix-calendario
├── hotfix/error-critico
└── release/v1.2.0
```

### Convenciones de Commits

```bash
# Formato
<tipo>(<alcance>): <descripción corta>

<descripción detallada opcional>

<referencias opcionales>

# Tipos
feat:     Nueva funcionalidad
fix:      Corrección de bug
docs:     Cambios en documentación
style:    Cambios de formato (no afectan código)
refactor: Refactorización de código
test:     Agregar o modificar tests
chore:    Tareas de mantenimiento

# Ejemplos
feat(reservas): agregar filtro por categoría en listado

fix(pagos): corregir cálculo de descuento en checkout

docs(api): actualizar documentación de endpoints

refactor(models): simplificar método de validación en Servicio

test(giftcards): agregar tests para generación de PDF
```

### Flujo de Feature

```bash
# 1. Crear rama desde develop
git checkout develop
git pull origin develop
git checkout -b feature/nombre-feature

# 2. Desarrollar y commitear
git add .
git commit -m "feat(modulo): descripción"

# 3. Actualizar con develop
git checkout develop
git pull origin develop
git checkout feature/nombre-feature
git merge develop

# 4. Push y crear PR
git push origin feature/nombre-feature
# Crear Pull Request en GitHub

# 5. Después de aprobación, merge
git checkout develop
git merge --no-ff feature/nombre-feature
git push origin develop

# 6. Limpiar
git branch -d feature/nombre-feature
git push origin --delete feature/nombre-feature
```

## 📁 Estructura del Proyecto

### Organización de Apps Django

```python
# ventas/
ventas/
├── __init__.py
├── apps.py              # Configuración de la app
├── models.py            # Modelos (si es pequeño)
├── models/              # Modelos (si es grande)
│   ├── __init__.py
│   ├── cliente.py
│   ├── servicio.py
│   └── reserva.py
├── views/               # Vistas organizadas
│   ├── __init__.py
│   ├── public.py
│   └── admin.py
├── forms.py             # Formularios
├── admin.py             # Admin config
├── urls.py              # URLs de la app
├── signals.py           # Señales
├── managers.py          # Managers personalizados
├── services/            # Lógica de negocio
│   ├── __init__.py
│   └── payment.py
├── utils/               # Utilidades
├── tests/               # Tests
│   ├── __init__.py
│   ├── test_models.py
│   └── test_views.py
├── management/          # Comandos
│   └── commands/
├── migrations/          # Migraciones
├── templates/           # Templates
│   └── ventas/
├── static/              # Estáticos
│   └── ventas/
└── locale/              # Traducciones
```

### Organización de Templates

```
templates/
├── base.html            # Template base global
├── includes/            # Fragmentos reutilizables
│   ├── header.html
│   ├── footer.html
│   └── messages.html
├── ventas/              # Templates de app
│   ├── base_ventas.html
│   ├── servicio_list.html
│   └── servicio_detail.html
├── emails/              # Templates de email
│   ├── base_email.html
│   └── confirmacion.html
└── errors/              # Páginas de error
    ├── 404.html
    └── 500.html
```

## 🚀 Desarrollo de Features

### Checklist para Nueva Feature

```markdown
## Feature: [Nombre de la feature]

### Planificación
- [ ] Definir requerimientos
- [ ] Diseñar modelo de datos
- [ ] Crear mockups/wireframes
- [ ] Estimar tiempo
- [ ] Identificar dependencias

### Desarrollo
- [ ] Crear rama feature/nombre
- [ ] Implementar modelos
- [ ] Crear migraciones
- [ ] Implementar vistas
- [ ] Crear templates
- [ ] Agregar URLs
- [ ] Implementar forms
- [ ] Agregar validaciones
- [ ] Implementar lógica JS

### Testing
- [ ] Tests unitarios
- [ ] Tests de integración
- [ ] Testing manual
- [ ] Testing en móviles

### Documentación
- [ ] Docstrings
- [ ] README actualizado
- [ ] Documentación de API

### Review
- [ ] Self code review
- [ ] Crear PR
- [ ] Pasar CI/CD
- [ ] Code review aprobado

### Despliegue
- [ ] Merge a develop
- [ ] Test en staging
- [ ] Merge a main
- [ ] Verificar producción
```

### Ejemplo: Agregar Sistema de Cupones

```python
# 1. Modelo
# ventas/models/cupon.py
class Cupon(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    descuento_porcentaje = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    usos_maximos = models.IntegerField(default=1)
    usos_actuales = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    def es_valido(self):
        now = timezone.now()
        return (
            self.activo and
            self.fecha_inicio <= now <= self.fecha_fin and
            self.usos_actuales < self.usos_maximos
        )

    def aplicar(self):
        if not self.es_valido():
            raise ValidationError("Cupón no válido")
        self.usos_actuales += 1
        self.save()


# 2. Form
# ventas/forms.py
class CuponForm(forms.Form):
    codigo = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese código de cupón'
        })
    )

    def clean_codigo(self):
        codigo = self.cleaned_data['codigo'].upper()
        try:
            cupon = Cupon.objects.get(codigo=codigo)
            if not cupon.es_valido():
                raise forms.ValidationError("Cupón no válido o expirado")
        except Cupon.DoesNotExist:
            raise forms.ValidationError("Cupón no encontrado")
        return codigo


# 3. Vista
# ventas/views/checkout.py
def aplicar_cupon(request):
    if request.method == 'POST':
        form = CuponForm(request.POST)
        if form.is_valid():
            codigo = form.cleaned_data['codigo']
            cupon = Cupon.objects.get(codigo=codigo)

            # Aplicar a carrito en sesión
            cart = Cart(request)
            cart.apply_coupon(cupon)

            messages.success(
                request,
                f"Cupón aplicado: {cupon.descuento_porcentaje}% de descuento"
            )
            return redirect('checkout')

    return redirect('cart')


# 4. Template
# templates/ventas/includes/cupon_form.html
<div class="cupon-form mb-4">
    <h4>¿Tienes un cupón?</h4>
    <form method="post" action="{% url 'aplicar_cupon' %}">
        {% csrf_token %}
        <div class="input-group">
            {{ form.codigo }}
            <button type="submit" class="btn btn-primary">
                Aplicar
            </button>
        </div>
        {% if form.codigo.errors %}
            <div class="text-danger mt-2">
                {{ form.codigo.errors.0 }}
            </div>
        {% endif %}
    </form>
</div>


# 5. Test
# ventas/tests/test_cupon.py
class CuponTestCase(TestCase):
    def setUp(self):
        self.cupon = Cupon.objects.create(
            codigo="TEST2024",
            descuento_porcentaje=10,
            fecha_inicio=timezone.now() - timedelta(days=1),
            fecha_fin=timezone.now() + timedelta(days=30),
            usos_maximos=100
        )

    def test_cupon_valido(self):
        self.assertTrue(self.cupon.es_valido())

    def test_cupon_aplicar(self):
        usos_antes = self.cupon.usos_actuales
        self.cupon.aplicar()
        self.assertEqual(self.cupon.usos_actuales, usos_antes + 1)

    def test_cupon_expirado(self):
        self.cupon.fecha_fin = timezone.now() - timedelta(days=1)
        self.cupon.save()
        self.assertFalse(self.cupon.es_valido())
```

## 🧪 Testing

### Estructura de Tests

```python
# ventas/tests/test_models.py
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from ventas.models import Servicio, Cliente, VentaReserva


class ServicioModelTest(TestCase):
    """Tests para modelo Servicio."""

    @classmethod
    def setUpTestData(cls):
        """Configurar datos que no se modifican en los tests."""
        cls.categoria = CategoriaServicio.objects.create(
            nombre="Test Category",
            slug="test-category"
        )

    def setUp(self):
        """Configurar datos para cada test."""
        self.servicio = Servicio.objects.create(
            nombre="Servicio Test",
            categoria=self.categoria,
            precio=50000,
            duracion=60
        )

    def test_string_representation(self):
        """Test del método __str__."""
        self.assertEqual(str(self.servicio), "Servicio Test")

    def test_precio_no_negativo(self):
        """Test que precio no puede ser negativo."""
        self.servicio.precio = -1000
        with self.assertRaises(ValidationError):
            self.servicio.full_clean()

    def test_slug_auto_generado(self):
        """Test que slug se genera automáticamente."""
        servicio = Servicio.objects.create(
            nombre="Nuevo Servicio",
            categoria=self.categoria,
            precio=30000
        )
        self.assertEqual(servicio.slug, "nuevo-servicio")


# ventas/tests/test_views.py
class ReservaViewTest(TestCase):
    """Tests para vistas de reserva."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.servicio = Servicio.objects.create(
            nombre="Test Service",
            precio=50000
        )

    def test_crear_reserva_get(self):
        """Test GET muestra formulario."""
        response = self.client.get(
            reverse('crear_reserva', args=[self.servicio.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reservar')
        self.assertIsInstance(response.context['form'], ReservaForm)

    def test_crear_reserva_post_valida(self):
        """Test POST crea reserva."""
        self.client.login(username='testuser', password='testpass123')

        data = {
            'fecha': timezone.now().date() + timedelta(days=1),
            'hora': '10:00',
            'cantidad_personas': 2,
            'nombre': 'Test User',
            'email': 'test@example.com',
            'telefono': '+56912345678'
        }

        response = self.client.post(
            reverse('crear_reserva', args=[self.servicio.id]),
            data
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(VentaReserva.objects.count(), 1)

        reserva = VentaReserva.objects.first()
        self.assertEqual(reserva.cliente.nombre, 'Test User')


# ventas/tests/test_integration.py
class CheckoutIntegrationTest(TransactionTestCase):
    """Test de integración del proceso completo de checkout."""

    def test_proceso_completo_checkout(self):
        """Test del flujo completo de reserva y pago."""
        # 1. Seleccionar servicio
        response = self.client.get(reverse('servicio_detail', args=[1]))
        self.assertEqual(response.status_code, 200)

        # 2. Agregar al carrito
        response = self.client.post(reverse('add_to_cart'), {
            'servicio_id': 1,
            'cantidad': 1
        })
        self.assertEqual(response.status_code, 302)

        # 3. Ir a checkout
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 200)

        # 4. Completar datos
        checkout_data = {
            'nombre': 'Cliente Test',
            'email': 'cliente@test.com',
            'telefono': '+56912345678',
            'metodo_pago': 'flow'
        }
        response = self.client.post(reverse('checkout'), checkout_data)

        # 5. Verificar redirección a pago
        self.assertEqual(response.status_code, 302)
        self.assertIn('flow.cl', response.url)
```

### Coverage

```bash
# Instalar coverage
pip install coverage

# Ejecutar tests con coverage
coverage run --source='.' manage.py test
coverage report
coverage html

# Ver reporte HTML
open htmlcov/index.html
```

### Tests de Performance

```python
# ventas/tests/test_performance.py
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
import time


class PerformanceTest(TestCase):
    """Tests de rendimiento."""

    @override_settings(DEBUG=False)
    def test_homepage_load_time(self):
        """Test que homepage carga en menos de 200ms."""
        start = time.time()
        response = self.client.get(reverse('homepage'))
        end = time.time()

        self.assertEqual(response.status_code, 200)
        self.assertLess(end - start, 0.2)  # 200ms

    def test_query_optimization(self):
        """Test que queries están optimizadas."""
        with self.assertNumQueries(3):  # Esperamos máximo 3 queries
            response = self.client.get(reverse('servicio_list'))
            list(response.context['servicios'])  # Forzar evaluación
```

## 🐛 Debugging

### Django Debug Toolbar

```python
# settings_dev.py
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

    INTERNAL_IPS = ['127.0.0.1']

    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
        'SHOW_TEMPLATE_CONTEXT': True,
    }

# urls.py
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
```

### Logging

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/django.log',
            'maxBytes': 1024*1024*10,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'ventas': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# Uso en código
import logging

logger = logging.getLogger('ventas')

def process_payment(payment_id):
    logger.info(f"Procesando pago {payment_id}")
    try:
        # Lógica de pago
        logger.debug(f"Pago {payment_id} procesado exitosamente")
    except Exception as e:
        logger.error(f"Error procesando pago {payment_id}: {str(e)}", exc_info=True)
        raise
```

### PDB (Python Debugger)

```python
# Debugging interactivo
def problematic_function():
    import pdb; pdb.set_trace()  # Breakpoint

    # O con Python 3.7+
    breakpoint()  # Más limpio

    # Código a debuggear
    result = complex_calculation()
    return result

# Comandos útiles en PDB:
# n - next line
# s - step into
# c - continue
# l - list code
# p variable - print variable
# pp variable - pretty print
# h - help
```

### Django Shell Plus

```bash
# Instalar django-extensions
pip install django-extensions

# Agregar a INSTALLED_APPS
INSTALLED_APPS += ['django_extensions']

# Usar shell mejorado
python manage.py shell_plus --print-sql

# Auto-importa todos los modelos
# In: Servicio.objects.all()
# SQL: SELECT * FROM ventas_servicio;
# Out: <QuerySet [...]>
```

## 🚢 Deployment

### Checklist Pre-Deploy

```bash
# 1. Tests pasando
python manage.py test

# 2. Migraciones al día
python manage.py makemigrations --check

# 3. Collectstatic funciona
python manage.py collectstatic --noinput --clear

# 4. Check de Django
python manage.py check --deploy

# 5. Requirements actualizado
pip freeze > requirements.txt

# 6. Variables de entorno configuradas
# Verificar .env.production

# 7. DEBUG = False
# Verificar settings.py
```

### Deploy a Staging

```bash
# 1. Merge a develop
git checkout develop
git merge feature/mi-feature

# 2. Tag de pre-release
git tag -a v1.2.0-rc.1 -m "Release candidate 1"
git push origin v1.2.0-rc.1

# 3. Deploy automático o manual a staging
# (Configurado en CI/CD)
```

### Deploy a Producción

```bash
# 1. Merge develop a main
git checkout main
git merge develop

# 2. Tag de release
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin v1.2.0

# 3. Deploy se activa automáticamente en Render
```

### Rollback

```bash
# En caso de problemas

# 1. Revertir en Git
git checkout main
git revert HEAD
git push origin main

# 2. O restaurar tag anterior
git checkout v1.1.0
git checkout -b hotfix/rollback-1.2.0
git push origin hotfix/rollback-1.2.0

# 3. Render detectará cambios y re-desplegará
```

## 🎯 Mejores Prácticas

### Code Quality

1. **DRY (Don't Repeat Yourself)**
   - Extraer código común a funciones/clases
   - Usar mixins y herencia cuando sea apropiado
   - Crear utilities para lógica compartida

2. **SOLID Principles**
   - Single Responsibility
   - Open/Closed
   - Liskov Substitution
   - Interface Segregation
   - Dependency Inversion

3. **Fat Models, Thin Views**
   - Lógica de negocio en modelos/servicios
   - Vistas solo para control de flujo
   - Templates sin lógica compleja

### Seguridad

```python
# 1. Siempre validar entrada de usuario
def procesar_input(user_input):
    # Sanitizar
    cleaned = bleach.clean(user_input)

    # Validar
    if not es_valido(cleaned):
        raise ValidationError("Input inválido")

    return cleaned

# 2. Usar ORM, no SQL raw
# MAL
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# BIEN
User.objects.filter(id=user_id)

# 3. CSRF protection en forms
{% csrf_token %}

# 4. Permisos y autorización
@login_required
@permission_required('ventas.add_reserva')
def crear_reserva(request):
    pass

# 5. Secrets en variables de entorno
SECRET_KEY = os.getenv('SECRET_KEY')
# Nunca hardcodear secrets
```

### Performance

```python
# 1. Usar select_related y prefetch_related
reservas = VentaReserva.objects.select_related(
    'cliente',
    'metodo_pago'
).prefetch_related(
    'servicios',
    'productos'
)

# 2. Índices en campos de búsqueda frecuente
class Meta:
    indexes = [
        models.Index(fields=['fecha', 'estado']),
        models.Index(fields=['cliente', '-created_at']),
    ]

# 3. Caché cuando sea apropiado
from django.core.cache import cache

def get_servicios_populares():
    key = 'servicios_populares'
    result = cache.get(key)

    if result is None:
        result = Servicio.objects.filter(
            destacado=True
        ).order_by('-reservas_count')[:10]

        cache.set(key, result, 3600)  # 1 hora

    return result

# 4. Paginación en listados grandes
from django.core.paginator import Paginator

def listado(request):
    todos_items = Item.objects.all()
    paginator = Paginator(todos_items, 25)  # 25 por página

    page_number = request.GET.get('page')
    items = paginator.get_page(page_number)

    return render(request, 'lista.html', {'items': items})
```

## 📚 Recursos Útiles

### Documentación Oficial
- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)

### Herramientas
- [Django Debug Toolbar](https://django-debug-toolbar.readthedocs.io/)
- [Django Extensions](https://django-extensions.readthedocs.io/)
- [Black Formatter](https://black.readthedocs.io/)
- [Pre-commit](https://pre-commit.com/)

### Libros Recomendados
- "Two Scoops of Django" - Best Practices
- "Django for Professionals" - William Vincent
- "Test-Driven Development with Python" - Harry Percival

### Comunidad
- [Django Forum](https://forum.djangoproject.com/)
- [Django Discord](https://discord.gg/django)
- [Stack Overflow Django Tag](https://stackoverflow.com/questions/tagged/django)

---

<p align="center">
  Happy Coding! 🚀
</p>