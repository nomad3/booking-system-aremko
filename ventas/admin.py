from django.contrib import admin
from django import forms
from .forms import PagoInlineForm
from django.forms import DateTimeInput
from datetime import date, datetime, timedelta  # Importa date, datetime, y timedelta
from django.utils import timezone
from django.db.models import Sum
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.forms import DateInput, TimeInput, Select
from .models import Proveedor, CategoriaProducto, Producto, VentaReserva, ReservaProducto, Pago, Cliente, CategoriaServicio, Servicio, ReservaServicio, MovimientoCliente, Compra, DetalleCompra, GiftCard
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.urls import path
import json # Import json module

# Personalización del título de la administración
admin.site.site_header = _("Sistema de Gestión de Ventas")
admin.site.site_title = _("Panel de Administración")
admin.site.index_title = _("Bienvenido al Panel de Control")

# Formulario personalizado para elegir los slots de horas según el servicio
class ReservaServicioInlineForm(forms.ModelForm):
    hora_inicio = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'hora-inicio-select'})
    )
    
    class Meta:
        model = ReservaServicio
        fields = ['servicio', 'fecha_agendamiento', 'hora_inicio', 'cantidad_personas']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Actualizar opciones del servicio
        self.fields['servicio'].queryset = Servicio.objects.filter(activo=True)
        
        # Cargar slots si ya hay un servicio seleccionado
        if self.instance and self.instance.servicio_id:
            servicio = self.instance.servicio
            self.fields['hora_inicio'].choices = [(t, t) for t in servicio.slots_disponibles]
        elif 'servicio' in self.initial:
            servicio = Servicio.objects.get(pk=self.initial['servicio'])
            self.fields['hora_inicio'].choices = [(t, t) for t in servicio.slots_disponibles]

class ReservaServicioInline(admin.TabularInline):
    model = ReservaServicio
    form = ReservaServicioInlineForm
    extra = 1
    min_num = 0

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
        # Corrected path based on file structure
        js = ('ventas/js/reserva_servicio_admin.js',) 

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
    # Restore the date filter
    list_filter = ('estado_pago', 'estado_reserva', 'fecha_reserva')
    search_fields = ('id', 'cliente__nombre', 'cliente__telefono')
    # Restore inlines
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
        # Ensure we handle potential None value and only format the date part
        if obj.fecha_reserva:
            # Use timezone.localtime to convert to local time before formatting
            local_time = timezone.localtime(obj.fecha_reserva)
            return local_time.strftime('%Y-%m-%d') # Format as date only
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
    # Use a TextArea for better JSON editing experience
    slots_input = forms.CharField(
        label="Horarios Disponibles por Día (JSON)", # More descriptive label
        widget=forms.Textarea(attrs={'rows': 10, 'cols': 60, 'placeholder': '{\n    "monday": ["16:00", "18:00"],\n    "tuesday": [],\n    ...\n}'}),
        help_text='''Define los slots por día en formato JSON. Claves: "monday", "tuesday", etc. Valores: listas de strings "HH:MM".'''
    )

    class Meta:
        model = Servicio
        fields = '__all__' # Include the actual model field
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate the text area with the JSON string representation of the dictionary
        if self.instance and self.instance.pk:
            # Ensure slots_disponibles is a dict before dumping
            slots_data = self.instance.slots_disponibles if isinstance(self.instance.slots_disponibles, dict) else {}
            try:
                # Pretty print the JSON for better readability in the admin
                self.initial['slots_input'] = json.dumps(slots_data, indent=4, ensure_ascii=False)
            except TypeError:
                 # Fallback if JSON serialization fails
                 self.initial['slots_input'] = '{}'
        # Don't set a default empty structure here, let the field be blank if no data
        # elif not self.initial.get('slots_input'):
        #      self.initial['slots_input'] = json.dumps({ ... }, indent=4)


    def clean_slots_input(self):
        """Validate the JSON input from the text area and return the dictionary."""
        slots_data_str = self.cleaned_data.get('slots_input', '{}') # Get the raw string
        try:
            if not slots_data_str.strip():
                slots_data = {}
            else:
                slots_data = json.loads(slots_data_str)
        except json.JSONDecodeError as e:
            raise ValidationError(f"JSON inválido: {e}")

        if not isinstance(slots_data, dict):
            raise ValidationError("La entrada debe ser un diccionario JSON válido (ej: {\"monday\": [\"10:00\"]}).")

        valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        
        for day, slots in slots_data.items():
            if day not in valid_days:
                raise ValidationError(f"Clave de día inválida: '{day}'. Use nombres de días en inglés en minúsculas (monday, tuesday, etc.).")
            if not isinstance(slots, list):
                raise ValidationError(f"El valor para '{day}' debe ser una lista de horarios (ej: [\"10:00\", \"11:30\"]).")
            for slot in slots:
                if not isinstance(slot, str):
                    raise ValidationError(f"El horario '{slot}' en '{day}' debe ser una cadena de texto (ej: \"10:00\").")
                try:
                    datetime.strptime(slot, "%H:%M")
                except ValueError:
                    raise ValidationError(f"Formato de horario inválido: '{slot}' en '{day}'. Use HH:MM (ej: \"10:00\", \"14:30\").")

        for day in valid_days:
            slots_data.setdefault(day, [])

        # Return the validated dictionary. It will be stored in cleaned_data['slots_input']
        return slots_data

    def clean(self):
        """Assign the validated dictionary from slots_input to slots_disponibles."""
        cleaned_data = super().clean()
        # Get the dictionary validated by clean_slots_input
        slots_dict = cleaned_data.get('slots_input') 
        
        # Assign the dictionary to the actual model field's cleaned data
        if slots_dict is not None: # Check if clean_slots_input ran successfully
             cleaned_data['slots_disponibles'] = slots_dict
        else:
             # Handle case where slots_input might be missing or failed cleaning earlier
             # Assigning an empty dict might be safer depending on model null/blank settings
             cleaned_data['slots_disponibles'] = {} 
             # Optionally add a non-field error if needed
             # self.add_error(None, "Error processing schedule input.")

        return cleaned_data

    # No custom save method needed anymore. Default save will use cleaned_data['slots_disponibles']

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    form = ServicioAdminForm
    list_display = ('nombre', 'categoria', 'tipo_servicio', 'precio_base', 'duracion', 'activo', 'publicado_web', 'imagen') # Added tipo_servicio, publicado_web
    list_filter = ('categoria', 'activo', 'publicado_web', 'tipo_servicio') # Added publicado_web, tipo_servicio
    search_fields = ('nombre', 'categoria__nombre')
    fieldsets = (
        (None, {
            'fields': ('nombre', 'categoria', 'tipo_servicio', 'precio_base', 'duracion', 'imagen', 'proveedor', 'activo', 'publicado_web') # Added tipo_servicio, publicado_web
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
            path('<int:pk>/slots/', self.admin_site.admin_view(self.get_slots))
        ]
        return custom_urls + urls
    
    def get_slots(self, request, pk):
        servicio = Servicio.objects.get(pk=pk)
        return JsonResponse({'slots': servicio.slots_disponibles})

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

# Custom Admin for CategoriaServicio to show image field
@admin.register(CategoriaServicio)
class CategoriaServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'imagen')
    search_fields = ('nombre',)

admin.site.register(CategoriaProducto, CategoriaProductoAdmin)
admin.site.register(Producto, ProductoAdmin)
admin.site.register(VentaReserva, VentaReservaAdmin)
admin.site.register(Cliente, ClienteAdmin)
# CategoriaServicio is now registered with the custom class above
