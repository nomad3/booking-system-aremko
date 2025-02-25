from django.contrib import admin
from django import forms
from .forms import PagoInlineForm
from django.forms import DateTimeInput
from datetime import date, datetime, timedelta  # Importa date, datetime, y timedelta
from django.utils import timezone
from django.db.models import Sum
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.forms import DateInput, TimeInput, Select, RadioSelect
from .models import Proveedor, CategoriaProducto, Producto, VentaReserva, ReservaProducto, Pago, Cliente, CategoriaServicio, Servicio, ReservaServicio, MovimientoCliente, Compra, DetalleCompra, GiftCard
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.urls import path
from django.db import models
from django.urls import path
from django.urls import reverse
from django.urls import re_path
from django.urls import get_object_or_404

# Personalización del título de la administración
admin.site.site_header = _("Sistema de Gestión de Ventas")
admin.site.site_title = _("Panel de Administración")
admin.site.index_title = _("Bienvenido al Panel de Control")

# Formulario personalizado para elegir los slots de horas según el servicio
class HorarioRadioSelect(RadioSelect):
    template_name = 'ventas/horario_radio.html'

class ReservaServicioForm(forms.ModelForm):
    class Meta:
        model = ReservaServicio
        fields = '__all__'
        widgets = {
            'hora_inicio': forms.Select()
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hora_inicio'].widget.attrs.update({'class': 'hora-inicio-select'})
        self.fields['_actualizar'] = forms.CharField(
            widget=forms.ButtonInput(attrs={
                'type': 'button',
                'class': 'actualizar-horarios',
                'value': 'Consultar Disponibilidad'
            }),
            required=False
        )

class ReservaServicioInline(admin.TabularInline):
    model = ReservaServicio
    form = ReservaServicioForm
    extra = 1

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields['hora_inicio'].widget.can_add_related = False
        formset.form.base_fields['hora_inicio'].widget.can_change_related = False
        return formset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "servicio":
            kwargs["queryset"] = Servicio.objects.filter(activo=True).order_by('nombre')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    class Media:
        js = ('ventas/js/admin_reservas.js',)

class ReservaProductoInline(admin.TabularInline):
    model = ReservaProducto
    extra = 1

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "producto":
            kwargs["queryset"] = Producto.objects.order_by('nombre')  # Ordena alfabéticamente por nombre
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class PagoInline(admin.TabularInline):
    model = Pago
    form = PagoInlineForm
    extra = 1
    fields = ['fecha_pago', 'monto', 'metodo_pago', 'giftcard']
    autocomplete_fields = ['giftcard']

    def save_model(self, request, obj, form, change):
        if not change:  # If this is a new instance
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

# Método para registrar movimientos en el sistema
def registrar_movimiento(cliente, tipo_movimiento, descripcion, usuario):
    MovimientoCliente.objects.create(
        cliente=cliente,
        tipo_movimiento=tipo_movimiento,
        comentarios=descripcion,          # Cambiar a comentarios
        usuario=usuario
    )

class VentaReservaAdmin(admin.ModelAdmin):
    list_per_page = 50  
    autocomplete_fields = ['cliente']
    list_display = (
        'id', 'cliente_info', 'fecha_reserva_corta', 'estado_pago', 
        'estado_reserva', 'servicios_y_cantidades', 
        'productos_y_cantidades', 'total_servicios', 
        'total_productos', 'total', 'pagado', 'saldo_pendiente'
    )
    list_filter = ('estado_pago', 'estado_reserva', 'fecha_reserva')
    search_fields = ('id', 'cliente__nombre', 'cliente__telefono')
    inlines = [ReservaServicioInline, ReservaProductoInline, PagoInline]
    readonly_fields = (
        'id', 'total', 'pagado', 'saldo_pendiente', 'estado_pago',
        'productos_y_cantidades', 'servicios_y_cantidades',
        'total_productos', 'total_servicios'
    )
    fieldsets = (
        (None, {
            'fields': (
                'numero_documento_fiscal',
                'cliente',
                'fecha_reserva',
                'total',
                'pagado',
                'saldo_pendiente',
                'servicios_y_cantidades',
                'productos_y_cantidades',
                'cobrado',
                'estado_pago',
                'estado_reserva',
                'codigo_giftcard',
                'total_servicios',
                'total_productos'
            )
        }),
        ('Detalles', {
            'fields': ('comentarios',)
        }),
    )
    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context=extra_context)
    
    # Guardar cambios con registro de movimiento
    def save_model(self, request, obj, form, change):
        # First save the object without checking for usuario
        super().save_model(request, obj, form, change)
        
        # Then create the movement record
        if not change:  # Only for new instances
            MovimientoCliente.objects.create(
                cliente=obj.cliente,
                tipo_movimiento='Venta',
                comentarios=f'Venta/Reserva #{obj.id}',
                usuario=request.user,
                venta_reserva=obj
            )

    # Eliminar con registro de movimiento
    def delete_model(self, request, obj):
        descripcion = f"Se ha eliminado la venta/reserva con ID {obj.id} del cliente {obj.cliente.nombre}."
        registrar_movimiento(obj.cliente, "Eliminación de Venta/Reserva", descripcion, request.user)
        super().delete_model(request, obj)

    # Mostrar servicios junto con cantidades en la misma fila
    def servicios_y_cantidades(self, obj):
        servicios_list = [
            f"{reserva_servicio.servicio.nombre} (x{reserva_servicio.cantidad_personas})" 
            for reserva_servicio in obj.reservaservicios.all()
        ]
        return ", ".join(servicios_list)
    servicios_y_cantidades.short_description = 'Servicios y Cantidades'

    # Mostrar productos junto con cantidades en la misma fila
    def productos_y_cantidades(self, obj):
        productos_list = [
            f"{reserva_producto.producto.nombre} (x{reserva_producto.cantidad})" 
            for reserva_producto in obj.reservaproductos.all()
        ]
        return ", ".join(productos_list)
    productos_y_cantidades.short_description = 'Productos y Cantidades'

    # Calcular total de servicios
    def total_servicios(self, obj):
        total = sum(
            reserva_servicio.servicio.precio_base * reserva_servicio.cantidad_personas 
            for reserva_servicio in obj.reservaservicios.all()
        )
        return f"{total} CLP"
    total_servicios.short_description = 'Total de Servicios'

    # Calcular total de productos
    def total_productos(self, obj):
        total = sum(
            reserva_producto.producto.precio_base * reserva_producto.cantidad 
            for reserva_producto in obj.reservaproductos.all()
        )
        return f"{total} CLP"
    total_productos.short_description = 'Total de Productos'

    # Optimización de consultas con prefetch_related
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.prefetch_related(
            'reservaproductos__producto',
            'reservaservicios__servicio',
        ).select_related('cliente')
        return queryset

    def cliente_info(self, obj):
        return f"{obj.cliente.nombre} - {obj.cliente.telefono}"
    cliente_info.short_description = 'Cliente'
    cliente_info.admin_order_field = 'cliente__nombre'

    def fecha_reserva_corta(self, obj):
        if obj.fecha_reserva:
            return obj.fecha_reserva.strftime('%Y-%m-%d')
        return '-'
    fecha_reserva_corta.short_description = 'Fecha'
    fecha_reserva_corta.admin_order_field = 'fecha_reserva'

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        instance = form.instance
        instance.calcular_total()  # Recalcular total después de guardar relaciones
        
        # Validar disponibilidad para reservas nuevas
        if not change:
            for reserva_servicio in instance.reservaservicios.all():
                if not verificar_disponibilidad(
                    servicio=reserva_servicio.servicio,
                    fecha_propuesta=reserva_servicio.fecha_agendamiento,
                    hora_propuesta=reserva_servicio.hora_inicio,
                    cantidad_personas=reserva_servicio.cantidad_personas
                ):
                    messages.error(request, 
                        f"Slot {reserva_servicio.hora_inicio} no disponible para {reserva_servicio.servicio.nombre}")
                    reserva_servicio.delete()

    class Media:
        css = {
            'all': ('admin/css/custom.css',)
        }

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'direccion', 'telefono', 'email')
    search_fields = ('nombre',)

class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 1
    autocomplete_fields = ['producto']
    fields = ['producto', 'descripcion', 'cantidad', 'precio_unitario']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "producto":
            kwargs["queryset"] = Producto.objects.order_by('nombre')  # Ordena alfabéticamente por nombre
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_compra', 'proveedor', 'metodo_pago', 'numero_documento', 'total')
    list_filter = ('fecha_compra', 'metodo_pago', 'proveedor')
    search_fields = ('numero_documento', 'proveedor__nombre')
    inlines = [DetalleCompraInline]
    date_hierarchy = 'fecha_compra'
    readonly_fields = ('total',)
    autocomplete_fields = ['proveedor']
    list_select_related = ('proveedor',)

@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'cliente_comprador', 'cliente_destinatario', 'monto_inicial', 'monto_disponible', 'fecha_emision', 'fecha_vencimiento', 'estado')
    search_fields = ('codigo', 'cliente_comprador__nombre', 'cliente_destinatario__nombre')
    list_filter = ('estado', 'fecha_emision', 'fecha_vencimiento')
    readonly_fields = ('codigo', 'monto_disponible')
    autocomplete_fields = ['cliente_comprador', 'cliente_destinatario']  # Habilitar autocompletar

class CategoriaProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)  # Añadir search_fields

class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio_base', 'cantidad_disponible', 'proveedor', 'categoria')
    search_fields = ('nombre', 'categoria__nombre')
    list_filter = ('categoria', 'proveedor')
    autocomplete_fields = ['proveedor', 'categoria'] 

class ClienteAdmin(admin.ModelAdmin):
    search_fields = ('nombre', 'telefono', 'email')
    list_display = ('nombre', 'telefono', 'email')
    actions = ['exportar_a_excel']

    def exportar_a_excel(self, request, queryset):
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="clientes_{}.xls"'.format(
            datetime.now().strftime('%Y%m%d_%H%M%S')
        )

        wb = xlwt.Workbook(encoding='utf-8')
        ws = wb.add_sheet('Clientes')

        # Estilos
        header_style = xlwt.easyxf('font: bold on; pattern: pattern solid, fore_colour gray25;')

        # Headers
        headers = ['Nombre', 'Teléfono', 'Email']
        for col, header in enumerate(headers):
            ws.write(0, col, header, header_style)
            ws.col(col).width = 256 * 20

        # Datos
        for row, cliente in enumerate(queryset, 1):
            ws.write(row, 0, cliente.nombre)
            ws.write(row, 1, cliente.telefono)
            ws.write(row, 2, cliente.email)

        wb.save(response)
        return response

    exportar_a_excel.short_description = "Exportar clientes seleccionados a Excel"

class ServicioAdminForm(forms.ModelForm):
    slots_input = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'HH:MM separados por comas ej: 09:00,10:30'}),
        help_text="Horarios disponibles en formato HH:MM"
    )

    class Meta:
        model = Servicio
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.slots_disponibles:
            self.initial['slots_input'] = ', '.join(self.instance.slots_disponibles)

    def clean_slots_input(self):
        slots = [s.strip() for s in self.cleaned_data['slots_input'].split(',')]
        for slot in slots:
            try:
                datetime.strptime(slot, "%H:%M")
            except ValueError:
                raise ValidationError(f"Formato inválido: {slot}. Use HH:MM")
        return slots

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.slots_disponibles = self.cleaned_data['slots_input']
        if commit:
            instance.save()
        return instance

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    form = ServicioAdminForm
    list_display = ('nombre', 'horario_apertura', 'horario_cierre', 'capacidad_maxima', 'slots_preview')
    fieldsets = (
        (None, {
            'fields': ('nombre', 'precio_base', 'duracion', 'categoria', 'proveedor')
        }),
        ('Configuración Horaria', {
            'fields': (
                'horario_apertura', 
                'horario_cierre',
                ('capacidad_maxima', 'slots_input')
            )
        }),
    )

    def slots_preview(self, obj):
        return ', '.join(obj.slots_disponibles) if obj.slots_disponibles else '-'
    slots_preview.short_description = 'Slots Disponibles'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:servicio_id>/slots/',
                self.admin_site.admin_view(self.slots_view),
                name='servicio_slots'
            ),
        ]
        return custom_urls + urls
    
    def slots_view(self, request, servicio_id):
        servicio = get_object_or_404(Servicio, id=servicio_id)
        fecha = request.GET.get('fecha')
        
        # Implementa tu lógica de validación de fecha aquí
        slots = servicio.slots_para_fecha(fecha) if fecha else []
        
        return JsonResponse({
            'slots': slots
        })

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('venta_reserva', 'monto', 'metodo_pago', 'fecha_pago')

    def save_model(self, request, obj, form, change):
        if not obj.usuario:
            obj.usuario = request.user
        if change:
            tipo = "Actualización de Pago"
            descripcion = f"Se ha actualizado el pago de {obj.monto} para la venta/reserva #{obj.venta_reserva.id}."
        else:
            tipo = "Registro de Pago"
            descripcion = f"Se ha registrado un nuevo pago de {obj.monto} para la venta/reserva #{obj.venta_reserva.id}."
        super().save_model(request, obj, form, change)
        registrar_movimiento(obj.venta_reserva.cliente, tipo, descripcion, request.user)

    def delete_model(self, request, obj):
        descripcion = f"Se ha eliminado el pago de {obj.monto} de la venta/reserva #{obj.venta_reserva.id}."
        registrar_movimiento(obj.venta_reserva.cliente, "Eliminación de Pago", descripcion, request.user)
        super().delete_model(request, obj)

admin.site.register(CategoriaProducto, CategoriaProductoAdmin)
admin.site.register(Producto, ProductoAdmin)
admin.site.register(VentaReserva, VentaReservaAdmin)
admin.site.register(Cliente, ClienteAdmin)
admin.site.register(CategoriaServicio)