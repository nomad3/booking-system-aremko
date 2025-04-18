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
import xlwt # Added for Excel export
from django.core.paginator import Paginator
from openpyxl import load_workbook

# Import CRM models & messages framework
from .models import Lead, Company, Contact, Activity, Campaign, Deal
from django.contrib import messages # Import messages

# Personalización del título de la administración
admin.site.site_header = _("Sistema de Gestión de Ventas")
admin.site.site_title = _("Panel de Administración")

# Removed ReservaServicioInlineForm as it's no longer needed for custom widget/JS

class ReservaServicioInline(admin.TabularInline):
    model = ReservaServicio
    # Use default form but explicitly list fields to ensure order and inclusion
    fields = ['servicio', 'fecha_agendamiento', 'hora_inicio', 'cantidad_personas', 'proveedor_asignado']
    readonly_fields = [] # Ensure no fields are inadvertently read-only here
    autocomplete_fields = ['servicio', 'proveedor_asignado'] # Use autocomplete
    extra = 1
    min_num = 0

    # Removed custom formfield_for_foreignkey - let autocomplete handle filtering based on search_fields in related admin
    # Removed Media class

    # Add back get_formset to set placeholder for hora_inicio CharField
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if 'hora_inicio' in formset.form.base_fields and isinstance(formset.form.base_fields['hora_inicio'].widget, forms.TextInput):
             formset.form.base_fields['hora_inicio'].widget.attrs.update({'placeholder': 'HH:MM', 'style': 'width: 7em;'}) # Add placeholder and width
        return formset

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
    # We removed the extra 'slots_input' field. We now directly use the 'slots_disponibles' field.

    class Meta:
        model = Servicio
        fields = '__all__' # Include the actual model field
        widgets = {
            # Use a Textarea for the JSONField for easier editing
            'slots_disponibles': forms.Textarea(attrs={'rows': 10, 'cols': 60, 'placeholder': '{\n    "monday": ["16:00", "18:00"],\n    "tuesday": [],\n    ...\n}'}),
        }
    
    # No custom __init__ needed for this approach

    def clean_slots_disponibles(self):
        """Validate the JSON input directly from the slots_disponibles field."""
        slots_data = self.cleaned_data.get('slots_disponibles') 
        
        # The default JSONField widget might already return a dict if input is valid JSON,
        # but we should handle the case where it might be a string if invalid.
        if isinstance(slots_data, str):
            try:
                # Try parsing if it's still a string (e.g., invalid JSON submitted)
                if not slots_data.strip():
                     slots_data = {}
                else:
                     slots_data = json.loads(slots_data)
            except json.JSONDecodeError as e:
                raise ValidationError(f"JSON inválido: {e}")
        
        # Ensure it's a dictionary after potential parsing
        if not isinstance(slots_data, dict):
            # Provide a default empty dict if it's None or not a dict somehow
            slots_data = {} 
            # Optionally raise an error if you require a dict structure
            # raise ValidationError("La entrada debe ser un diccionario JSON válido.")

        # Proceed with validation if we have a dictionary
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

        # Return the validated dictionary. This will be stored in cleaned_data['slots_disponibles']
        return slots_data

    # No custom clean or save method needed anymore. 
    # clean_slots_disponibles handles validation, and default save handles persistence.

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    form = ServicioAdminForm
    list_display = ('nombre', 'categoria', 'tipo_servicio', 'precio_base', 'duracion', 'capacidad_minima', 'capacidad_maxima', 'activo', 'publicado_web', 'imagen') # Added capacity fields
    list_filter = ('categoria', 'activo', 'publicado_web', 'tipo_servicio')
    search_fields = ('nombre', 'categoria__nombre', 'proveedores__nombre') # Added proveedores to search
    filter_horizontal = ('proveedores',) # Use a nice widget for ManyToMany
    fieldsets = (
        (None, {
            # Changed 'proveedor' to 'proveedores', added 'descripcion_web'
            'fields': ('nombre', 'categoria', 'tipo_servicio', 'descripcion_web', 'precio_base', 'duracion', 'capacidad_minima', 'capacidad_maxima', 'imagen', 'proveedores', 'activo', 'publicado_web')
        }),
        ('Configuración Horaria', {
            'fields': (
                'horario_apertura',
                'horario_cierre',
                # 'capacidad_maxima', # Moved to main fieldset
                'slots_disponibles'
            )
        }),
    )

    # Remove slots_preview as the default widget shows the JSON now
    # def slots_preview(self, obj): ...
    # slots_preview.short_description = 'Slots Disponibles' # Keep description if needed, but method is removed

    # Removed get_urls and get_slots as they are no longer needed

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


# --- Configuraciones Admin CRM & Marketing ---

# Inlines primero

class ActivityInline(admin.TabularInline):
    model = Activity
    verbose_name = "Actividad"
    verbose_name_plural = "Actividades"
    fields = ('activity_date', 'activity_type', 'subject', 'created_by', 'notes')
    readonly_fields = ('created_at', 'updated_at')
    extra = 1
    autocomplete_fields = ['created_by']

class DealInline(admin.TabularInline):
    model = Deal
    verbose_name = "Oportunidad"
    verbose_name_plural = "Oportunidades"
    fields = ('name', 'stage', 'amount', 'expected_close_date', 'campaign')
    readonly_fields = ('created_at', 'updated_at')
    extra = 1
    autocomplete_fields = ['campaign']

class LeadInline(admin.TabularInline):
    model = Lead
    verbose_name = "Lead (Prospecto)"
    verbose_name_plural = "Leads (Prospectos)"
    fields = ('first_name', 'last_name', 'email', 'status', 'source')
    readonly_fields = ('created_at', 'updated_at')
    extra = 1

class ContactInline(admin.TabularInline):
    model = Contact
    verbose_name = "Contacto"
    verbose_name_plural = "Contactos"
    fields = ('first_name', 'last_name', 'email', 'phone', 'job_title')
    readonly_fields = ('created_at', 'updated_at')
    extra = 1


# ModelAdmins

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):

    def convert_to_contact(self, request, queryset):
        """Acción Admin para convertir prospectos calificados a contactos y oportunidades."""
        converted_count = 0
        skipped_count = 0
        for lead in queryset.filter(status='Qualified'):
            if not Contact.objects.filter(email=lead.email).exists():
                company = None
                if lead.company_name:
                    company, _ = Company.objects.get_or_create(name=lead.company_name)
                contact = Contact.objects.create(
                    first_name=lead.first_name,
                    last_name=lead.last_name,
                    email=lead.email,
                    phone=lead.phone,
                    company=company,
                )
                Deal.objects.create(
                    name=f"Oportunidad Inicial para {contact.first_name} {contact.last_name}",
                    contact=contact,
                    stage='Qualification',
                    campaign=lead.campaign
                )
                lead.status = 'Converted'
                lead.save(update_fields=['status'])
                Activity.objects.create(
                    activity_type='Status Change',
                    subject=f'Lead Convertido a Contacto: {contact}',
                    related_lead=lead,
                    created_by=request.user
                )
                converted_count += 1
            else:
                 messages.warning(request, f"Contacto con email {lead.email} ya existe. Conversión omitida para Lead ID {lead.id}.")
                 skipped_count += 1

        if converted_count > 0:
            messages.success(request, f'{converted_count} leads calificados convertidos exitosamente.')
        if skipped_count == 0 and converted_count == 0:
             messages.info(request, 'No se seleccionaron leads calificados o elegibles para conversión.')

    convert_to_contact.short_description = "Convertir Leads Calificados a Contactos"

    list_display = ('email', 'first_name', 'last_name', 'status', 'source', 'campaign', 'created_at', 'updated_at')
    list_filter = ('status', 'source', 'campaign', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'company_name')
    inlines = [ActivityInline]
    autocomplete_fields = ['campaign']
    fieldsets = (
        (None, {'fields': ('first_name', 'last_name', 'email', 'phone', 'company_name')}),
        ('Estado y Fuente', {'fields': ('status', 'source', 'campaign')}),
        ('Detalles', {'fields': ('notes',)}),
        ('Marcas de Tiempo', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at', 'updated_at')
    actions = [convert_to_contact]

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'website', 'created_at')
    search_fields = ('name', 'website')
    inlines = [ContactInline]
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'company', 'job_title', 'linked_user', 'created_at')
    list_filter = ('company', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'phone', 'company__name', 'linked_user__username')
    inlines = [DealInline, ActivityInline]
    autocomplete_fields = ['company', 'linked_user']
    fieldsets = (
        (None, {'fields': ('first_name', 'last_name', 'email', 'phone', 'job_title')}),
        ('Asociación', {'fields': ('company', 'linked_user')}),
        ('Detalles', {'fields': ('notes',)}),
        ('Marcas de Tiempo', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('subject', 'activity_type', 'activity_date', 'related_lead', 'related_contact', 'related_deal', 'created_by')
    list_filter = ('activity_type', 'activity_date', 'created_by')
    search_fields = ('subject', 'notes', 'related_lead__email', 'related_contact__email', 'related_deal__name', 'created_by__username')
    autocomplete_fields = ['related_lead', 'related_contact', 'related_deal', 'created_by']
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('activity_type', 'subject', 'activity_date', 'created_by')}),
        ('Relacionado Con (Vincular solo UNO)', {'fields': ('related_lead', 'related_contact', 'related_deal')}),
        ('Detalles', {'fields': ('notes',)}),
        ('Marcas de Tiempo', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'start_date', 'end_date', 'budget', 'get_associated_leads_count', 'get_won_deals_count', 'get_won_deals_value')
    list_filter = ('status', 'start_date', 'end_date')
    search_fields = ('name', 'description', 'goal')
    inlines = [LeadInline]
    fieldsets = (
        (None, {'fields': ('name', 'status', 'description', 'goal')}),
        ('Fechas y Presupuesto', {'fields': ('start_date', 'end_date', 'budget')}),
        ('Marcas de Tiempo', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at', 'updated_at')

    def get_associated_leads_count(self, obj):
        return obj.get_associated_leads_count()
    get_associated_leads_count.short_description = 'Leads Asociados'

    def get_won_deals_count(self, obj):
        return obj.get_won_deals_count()
    get_won_deals_count.short_description = 'Oportunidades Ganadas'

    def get_won_deals_value(self, obj):
        value = obj.get_won_deals_value()
        return f"${value:,.0f}" if value else "$0" # Format as currency without decimals
    get_won_deals_value.short_description = 'Valor Ganado'


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact', 'stage', 'amount', 'expected_close_date', 'probability', 'campaign', 'related_booking')
    list_filter = ('stage', 'campaign', 'expected_close_date')
    search_fields = ('name', 'contact__first_name', 'contact__last_name', 'contact__email', 'campaign__name')
    inlines = [ActivityInline]
    autocomplete_fields = ['contact', 'campaign', 'related_booking']
    fieldsets = (
        (None, {'fields': ('name', 'contact', 'stage')}),
        ('Valor y Fechas', {'fields': ('amount', 'probability', 'expected_close_date')}),
        ('Asociación', {'fields': ('campaign', 'related_booking')}),
        ('Detalles', {'fields': ('notes',)}),
        ('Marcas de Tiempo', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at', 'updated_at')
