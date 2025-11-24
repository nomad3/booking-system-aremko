from django.contrib import admin, messages
from django import forms
from django.db import models
from .forms import PagoInlineForm
from django.forms import DateTimeInput
from datetime import date, datetime, timedelta  # Importa date, datetime, y timedelta
from django.utils import timezone
from django.db.models import Sum
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.forms import DateInput, TimeInput, Select
from .models import (
    Proveedor, CategoriaProducto, Producto, VentaReserva, ReservaProducto,
    Pago, Cliente, CategoriaServicio, Servicio, ReservaServicio,
    MovimientoCliente, Compra, DetalleCompra, GiftCard, GiftCardExperiencia, PackDescuento,
    # CRM Models
    Lead, Company, Contact, Activity, Campaign, Deal, CampaignInteraction,
    HomepageConfig,
    # Email Templates
    EmailSubjectTemplate, EmailContentTemplate,
    # Premios y Tramos
    Premio, ClientePremio, HistorialTramo,
    # Email Campaigns
    CampaignEmailTemplate, EmailCampaign, EmailRecipient, EmailDeliveryLog
)
from django.http import HttpResponse
import xlwt

# Personalización del título de la administración
admin.site.site_header = _("Sistema de Gestión de Ventas")
admin.site.site_title = _("Panel de Administración")
admin.site.index_title = _("Bienvenido al Panel de Control")

# Formulario personalizado para elegir los slots de horas según el servicio
class ReservaServicioInlineForm(forms.ModelForm):
    class Meta:
        model = ReservaServicio
        fields = ['servicio', 'fecha_agendamiento', 'hora_inicio', 'cantidad_personas', 'proveedor_asignado']

    def clean_fecha_agendamiento(self):
        """
        Convertir el campo `fecha_agendamiento` en un objeto datetime si es necesario.
        """
        fecha_agendamiento = self.cleaned_data.get('fecha_agendamiento')

        # Verificar si fecha_agendamiento es un string y convertirlo a datetime
        if isinstance(fecha_agendamiento, str):
            try:
                fecha_agendamiento = datetime.strptime(fecha_agendamiento, '%Y-%m-%d %H:%M')
                fecha_agendamiento = timezone.make_aware(fecha_agendamiento)  # Asegurarnos de que sea "aware"
            except ValueError:
                raise forms.ValidationError("El formato de la fecha de agendamiento no es válido. Debe ser YYYY-MM-DD HH:MM.")

        return fecha_agendamiento

class ReservaServicioInline(admin.TabularInline):
    model = ReservaServicio
    form = ReservaServicioInlineForm
    extra = 1
    autocomplete_fields = ['proveedor_asignado']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "servicio":
            kwargs["queryset"] = Servicio.objects.order_by('nombre')  # Ordena alfabéticamente por nombre
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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

class GiftCardInline(admin.TabularInline):
    model = GiftCard
    extra = 0
    fields = ['codigo', 'monto_inicial', 'destinatario_nombre', 'estado', 'enviado_email']
    readonly_fields = ['codigo', 'monto_inicial', 'destinatario_nombre', 'estado', 'enviado_email']
    verbose_name = "GiftCard"
    verbose_name_plural = "GiftCards de esta Venta"
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

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
    inlines = [ReservaServicioInline, ReservaProductoInline, GiftCardInline, PagoInline]
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

class ServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio_base', 'duracion', 'categoria', 'publicado_web')
    list_filter = ('categoria', 'tipo_servicio', 'activo', 'publicado_web')
    search_fields = ('nombre', 'descripcion_web')
    filter_horizontal = ('proveedores',)  # Para manejar ManyToMany de proveedores

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
admin.site.register(Servicio, ServicioAdmin)
admin.site.register(CategoriaServicio)

# ============================================
# CRM MODELS ADMIN
# ============================================

# CRM Models Admin
@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'email', 'phone', 'status', 'source',
                   'created_at', 'company_name')
    list_filter = ('status', 'source', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'phone', 'company_name', 'notes')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Información de Contacto', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('Estado del Lead', {
            'fields': ('status', 'source', 'campaign')
        }),
        ('Información Adicional', {
            'fields': ('company_name', 'notes')
        })
    )

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    get_full_name.short_description = 'Nombre'
    get_full_name.admin_order_field = 'first_name'

    actions = ['convertir_a_cliente']

    def convertir_a_cliente(self, request, queryset):
        """Convertir leads seleccionados en clientes"""
        convertidos = 0
        for lead in queryset.filter(status='Qualified'):
            cliente, created = Cliente.objects.get_or_create(
                email=lead.email,
                defaults={
                    'nombre': f"{lead.first_name} {lead.last_name}",
                    'telefono': lead.phone or '',
                    'pais': 'Chile',
                    'ciudad': lead.company_name or ''
                }
            )
            if created:
                lead.status = 'Converted'
                lead.save()
                convertidos += 1

        self.message_user(request, f'{convertidos} leads convertidos a clientes.')

    convertir_a_cliente.short_description = 'Convertir a cliente'


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact', 'stage', 'amount', 'probability',
                   'expected_close_date', 'created_at')
    list_filter = ('stage', 'expected_close_date', 'created_at', 'campaign')
    search_fields = ('name', 'contact__first_name', 'contact__last_name',
                    'contact__email', 'notes')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Información de la Oportunidad', {
            'fields': ('name', 'contact', 'stage')
        }),
        ('Detalles Financieros', {
            'fields': ('amount', 'probability', 'expected_close_date')
        }),
        ('Vínculos', {
            'fields': ('related_booking', 'campaign')
        }),
        ('Notas', {
            'fields': ('notes',)
        })
    )

    autocomplete_fields = ['contact', 'related_booking', 'campaign']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('contact', 'campaign', 'related_booking')


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'website', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'website')
    date_hierarchy = 'created_at'


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'email', 'phone', 'company', 'created_at')
    list_filter = ('company', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'phone', 'company__name')
    date_hierarchy = 'created_at'
    autocomplete_fields = ['company']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    get_full_name.short_description = 'Nombre Completo'


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('activity_type', 'subject', 'related_contact', 'campaign',
                   'created_at', 'created_by')
    list_filter = ('activity_type', 'created_at', 'campaign')
    search_fields = ('subject', 'notes', 'related_contact__first_name',
                    'related_contact__last_name')
    date_hierarchy = 'created_at'
    autocomplete_fields = ['related_contact', 'campaign']


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'start_date', 'end_date', 'budget',
                   'created_at')
    list_filter = ('status', 'start_date', 'end_date')
    search_fields = ('name', 'description')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'status', 'goal')
        }),
        ('Fechas y Presupuesto', {
            'fields': ('start_date', 'end_date', 'budget')
        }),
        ('Segmentación', {
            'fields': ('target_min_visits', 'target_min_spend')
        }),
        ('Plantillas de Contenido', {
            'fields': ('email_subject_template', 'email_body_template', 'sms_template', 'whatsapp_template'),
            'classes': ('collapse',)
        }),
        ('Automatización', {
            'fields': ('automation_notes',),
            'classes': ('collapse',)
        })
    )


@admin.register(CampaignInteraction)
class CampaignInteractionAdmin(admin.ModelAdmin):
    list_display = ('interaction_type', 'campaign', 'contact', 'timestamp')
    list_filter = ('interaction_type', 'timestamp')
    search_fields = ('campaign__name', 'contact__email', 'contact__first_name', 'contact__last_name')
    date_hierarchy = 'timestamp'
    autocomplete_fields = ['campaign', 'contact']


@admin.register(EmailSubjectTemplate)
class EmailSubjectTemplateAdmin(admin.ModelAdmin):
    list_display = ('subject_template', 'estilo', 'activo', 'created_at')
    list_filter = ('activo', 'estilo', 'created_at')
    search_fields = ('subject_template',)


@admin.register(EmailContentTemplate)
class EmailContentTemplateAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'estilo', 'activo', 'created_at')
    list_filter = ('activo', 'estilo', 'created_at')
    search_fields = ('nombre', 'saludo', 'introduccion')
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 20, 'cols': 100})},
    }


# Sistema de Premios y Tramos

@admin.register(Premio)
class PremioAdmin(admin.ModelAdmin):
    list_display = (
        'nombre',
        'tipo',
        'valor_formateado',
        'tramo_hito',
        'dias_validez',
        'activo',
        'stock_display'
    )
    list_filter = ('tipo', 'activo', 'tramo_hito')
    search_fields = ('nombre', 'descripcion_corta')
    ordering = ['-activo', 'tramo_hito', 'nombre']

    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'descripcion', 'tipo', 'activo')
        }),
        ('Configuración del Premio', {
            'fields': ('valor', 'condiciones', 'dias_validez', 'tramo_minimo')
        }),
        ('Control de Stock', {
            'fields': ('stock_disponible', 'stock_inicial'),
            'description': 'Dejar en blanco para stock ilimitado'
        })
    )

    def valor_formateado(self, obj):
        """Muestra el valor formateado según el tipo"""
        if obj.tipo == 'descuento_porcentaje':
            return f'{obj.valor}%'
        elif obj.tipo in ['descuento_monto', 'credito']:
            return f'${obj.valor:,.0f}'
        else:
            return obj.valor
    valor_formateado.short_description = 'Valor'

    def stock_display(self, obj):
        """Muestra el stock disponible"""
        if obj.stock_disponible is None:
            return format_html('<span style="color: green;">Ilimitado</span>')
        elif obj.stock_disponible == 0:
            return format_html('<span style="color: red;">Agotado</span>')
        elif obj.stock_disponible < 10:
            return format_html(
                '<span style="color: orange;">{} disponibles</span>',
                obj.stock_disponible
            )
        else:
            return format_html(
                '<span style="color: green;">{} disponibles</span>',
                obj.stock_disponible
            )
    stock_display.short_description = 'Stock'

@admin.register(ClientePremio)
class ClientePremioAdmin(admin.ModelAdmin):
    list_display = (
        'codigo_link',
        'cliente_link',
        'premio',
        'estado_badge',
        'fecha_ganado',
        'fecha_expiracion',
        'dias_restantes'
    )
    list_filter = ('estado', 'premio__tipo', 'fecha_ganado', 'fecha_expiracion')
    search_fields = (
        'codigo_unico',
        'cliente__nombre',
        'cliente__email',
        'premio__nombre'
    )
    readonly_fields = (
        'codigo_unico',
        'fecha_ganado',
        'fecha_uso',
        'fecha_expiracion',
        'venta_donde_uso'
    )
    date_hierarchy = 'fecha_ganado'

    fieldsets = (
        ('Información del Premio', {
            'fields': ('cliente', 'premio', 'codigo_unico', 'estado')
        }),
        ('Fechas', {
            'fields': ('fecha_ganado', 'fecha_expiracion', 'fecha_uso')
        }),
        ('Uso', {
            'fields': ('venta_donde_uso', 'notas'),
            'classes': ('collapse',)
        })
    )

    def codigo_link(self, obj):
        """Código con formato monospace"""
        return format_html(
            '<code style="background-color: #f5f5f5; padding: 2px 6px; '
            'border-radius: 3px;">{}</code>',
            obj.codigo_unico
        )
    codigo_link.short_description = 'Código'
    codigo_link.admin_order_field = 'codigo_unico'

    def cliente_link(self, obj):
        """Link al cliente"""
        if obj.cliente:
            url = reverse('admin:ventas_cliente_change', args=[obj.cliente.id])
            return format_html('<a href="{}">{}</a>', url, obj.cliente.nombre)
        return '-'
    cliente_link.short_description = 'Cliente'
    cliente_link.admin_order_field = 'cliente__nombre'

    def estado_badge(self, obj):
        """Badge colorido para el estado"""
        colors = {
            'pendiente': '#ffc107',
            'aprobado': '#28a745',
            'enviado': '#17a2b8',
            'usado': '#6c757d',
            'expirado': '#dc3545',
            'cancelado': '#dc3545'
        }

        # Verificar si está expirado
        if obj.estado in ['aprobado', 'enviado'] and obj.fecha_expiracion < timezone.now():
            estado_display = 'EXPIRADO'
            color = colors['expirado']
        else:
            estado_display = obj.get_estado_display()
            color = colors.get(obj.estado, '#6c757d')

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            estado_display
        )
    estado_badge.short_description = 'Estado'

    def dias_restantes(self, obj):
        """Días restantes para usar el premio"""
        if obj.estado == 'usado':
            return format_html('<span style="color: gray;">Usado</span>')

        dias = (obj.fecha_expiracion - timezone.now()).days

        if dias < 0:
            return format_html('<span style="color: red;">Expirado</span>')
        elif dias == 0:
            return format_html('<span style="color: red;">Hoy</span>')
        elif dias <= 7:
            return format_html('<span style="color: orange;">{} días</span>', dias)
        else:
            return format_html('<span style="color: green;">{} días</span>', dias)

    dias_restantes.short_description = 'Vigencia'

    def has_delete_permission(self, request, obj=None):
        """Solo superusers pueden eliminar"""
        return request.user.is_superuser

    actions = ['enviar_notificacion', 'extender_vigencia', 'marcar_como_enviado']

    def enviar_notificacion(self, request, queryset):
        """Enviar notificación del premio al cliente"""
        enviados = 0
        for premio in queryset.filter(estado='aprobado'):
            # Aquí iría la lógica de envío
            premio.estado = 'enviado'
            premio.save()
            enviados += 1

        self.message_user(request, f'{enviados} notificaciones enviadas')
    enviar_notificacion.short_description = 'Enviar notificación al cliente'

    def extender_vigencia(self, request, queryset):
        """Extender vigencia por 30 días"""
        for premio in queryset:
            premio.fecha_expiracion += timedelta(days=30)
            premio.save()

        self.message_user(
            request,
            f'{queryset.count()} premios extendidos por 30 días'
        )
    extender_vigencia.short_description = 'Extender vigencia (+30 días)'

    def marcar_como_enviado(self, request, queryset):
        """Marcar como enviado"""
        actualizados = queryset.filter(estado='aprobado').update(estado='enviado')
        self.message_user(request, f'{actualizados} premios marcados como enviados')
    marcar_como_enviado.short_description = 'Marcar como enviado'

@admin.register(HistorialTramo)
class HistorialTramoAdmin(admin.ModelAdmin):
    list_display = (
        'cliente_link',
        'cambio_tramo',
        'gasto_momento',
        'fecha_cambio',
        'premio_link'
    )
    list_filter = ('fecha_cambio', 'tramo_hasta')
    search_fields = ('cliente__nombre', 'cliente__email')
    readonly_fields = (
        'cliente',
        'tramo_desde',
        'tramo_hasta',
        'fecha_cambio',
        'gasto_en_momento',
        'premio_generado'
    )

    def cliente_link(self, obj):
        """Link al cliente"""
        if obj.cliente:
            url = reverse('admin:ventas_cliente_change', args=[obj.cliente.id])
            return format_html('<a href="{}">{}</a>', url, obj.cliente.nombre)
        return '-'
    cliente_link.short_description = 'Cliente'

    def cambio_tramo(self, obj):
        """Visualización del cambio de tramo"""
        return format_html(
            '<span style="font-weight: bold;">Tramo {} → {}</span>',
            obj.tramo_desde,
            obj.tramo_hasta
        )
    cambio_tramo.short_description = 'Cambio'

    def gasto_momento(self, obj):
        """Gasto formateado"""
        return f'${obj.gasto_en_momento:,.0f}'
    gasto_momento.short_description = 'Gasto'

    def premio_link(self, obj):
        """Link al premio generado"""
        if obj.premio_generado:
            url = reverse('admin:ventas_clientepremio_change', args=[obj.premio_generado.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.premio_generado.premio.nombre
            )
        return '-'
    premio_link.short_description = 'Premio Generado'

    def has_add_permission(self, request):
        """No permitir crear manualmente"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Solo superusers pueden eliminar"""
        return request.user.is_superuser




# ============================================
# PACK DE DESCUENTOS ADMIN
# ============================================

@admin.register(PackDescuento)
class PackDescuentoAdmin(admin.ModelAdmin):
    """Admin para gestionar Packs de Descuento"""

    list_display = (
        'nombre',
        'descuento_formateado',
        'servicios_display',
        'dias_display',
        'activo',
        'vigencia_display',
        'prioridad'
    )

    list_filter = ('activo', 'fecha_inicio', 'fecha_fin')

    search_fields = ('nombre', 'descripcion')

    ordering = ['-activo', '-prioridad', '-descuento']

    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'descripcion', 'descuento', 'activo')
        }),
        ('Servicios Requeridos', {
            'fields': ('servicios_requeridos',),
            'description': 'Ingrese los tipos de servicios como lista JSON: ["ALOJAMIENTO", "TINA"]'
        }),
        ('Restricciones de Fecha', {
            'fields': ('dias_semana_validos', 'fecha_inicio', 'fecha_fin'),
            'description': 'Días: 0=Domingo, 1=Lunes... 6=Sábado. Ej: [0,1,2,3,4] para Dom-Jue'
        }),
        ('Configuración Adicional', {
            'fields': ('prioridad', 'cantidad_minima_noches', 'misma_fecha')
        })
    )

    def descuento_formateado(self, obj):
        """Muestra el descuento formateado"""
        return f'${obj.descuento:,.0f}'
    descuento_formateado.short_description = 'Descuento'

    def servicios_display(self, obj):
        """Muestra los servicios requeridos"""
        if obj.servicios_requeridos:
            return ', '.join(obj.servicios_requeridos)
        return 'Sin servicios definidos'
    servicios_display.short_description = 'Servicios Requeridos'

    def dias_display(self, obj):
        """Muestra los días válidos"""
        return obj.get_dias_semana_display()
    dias_display.short_description = 'Días Válidos'

    def vigencia_display(self, obj):
        """Muestra el período de vigencia"""
        inicio = obj.fecha_inicio.strftime('%d/%m/%Y')
        fin = obj.fecha_fin.strftime('%d/%m/%Y') if obj.fecha_fin else 'Sin límite'
        return f'{inicio} - {fin}'
    vigencia_display.short_description = 'Vigencia'

    def save_model(self, request, obj, form, change):
        """Validaciones al guardar"""
        # Validar que servicios_requeridos sea una lista
        if not isinstance(obj.servicios_requeridos, list):
            messages.error(request, 'Los servicios requeridos deben ser una lista.')
            return

        # Validar que días_semana_validos sea una lista
        if obj.dias_semana_validos and not isinstance(obj.dias_semana_validos, list):
            messages.error(request, 'Los días de la semana deben ser una lista.')
            return

        super().save_model(request, obj, form, change)

        if not change:
            messages.success(request, f'Pack "{obj.nombre}" creado exitosamente.')
        else:
            messages.success(request, f'Pack "{obj.nombre}" actualizado.')

    class Media:
        css = {
            'all': ('admin/css/forms.css',)
        }
        js = ('admin/js/jquery.init.js',)


@admin.register(GiftCardExperiencia)
class GiftCardExperienciaAdmin(admin.ModelAdmin):
    """
    Administración de Experiencias para Gift Cards
    """
    list_display = (
        'id_experiencia',
        'nombre',
        'categoria',
        'precio_display',
        'activo',
        'orden',
        'modificado'
    )
    list_filter = (
        'categoria',
        'activo',
        'creado',
        'modificado'
    )
    search_fields = (
        'id_experiencia',
        'nombre',
        'descripcion',
        'descripcion_giftcard'
    )
    ordering = ('categoria', 'orden', 'nombre')
    list_editable = ('activo', 'orden')

    fieldsets = (
        ('Identificación', {
            'fields': ('id_experiencia', 'categoria', 'nombre')
        }),
        ('Descripciones', {
            'fields': ('descripcion', 'descripcion_giftcard')
        }),
        ('Imagen', {
            'fields': ('imagen',),
            'description': 'Sube la imagen de la experiencia (recomendado: 800x600px, formato JPG/PNG)'
        }),
        ('Precios', {
            'fields': ('monto_fijo', 'montos_sugeridos'),
            'description': (
                'Si tiene monto fijo: ingresar solo "monto_fijo".<br>'
                'Si es tarjeta de valor: dejar "monto_fijo" vacío y llenar "montos_sugeridos" '
                'como lista JSON: [30000, 50000, 75000]'
            )
        }),
        ('Configuración', {
            'fields': ('activo', 'orden')
        }),
        ('Metadatos', {
            'fields': ('creado', 'modificado'),
            'classes': ('collapse',)
        })
    )

    readonly_fields = ('creado', 'modificado')

    def precio_display(self, obj):
        """Muestra el precio en formato legible"""
        if obj.monto_fijo:
            return f"${obj.monto_fijo:,}"
        elif obj.montos_sugeridos:
            montos = [f"${m:,}" for m in obj.montos_sugeridos]
            return f"Variable: {', '.join(montos[:3])}"
        return "Sin precio"
    precio_display.short_description = "Precio"

    def save_model(self, request, obj, form, change):
        """Validaciones al guardar"""
        # Validar que tenga al menos un tipo de precio
        if not obj.monto_fijo and not obj.montos_sugeridos:
            messages.warning(
                request,
                'Debes especificar al menos un monto_fijo o montos_sugeridos'
            )

        super().save_model(request, obj, form, change)

        if not change:
            messages.success(request, f'✅ Experiencia "{obj.nombre}" creada exitosamente.')
        else:
            messages.success(request, f'✅ Experiencia "{obj.nombre}" actualizada.')

    class Media:
        css = {
            'all': ('admin/css/forms.css',)
        }

# ============================================
# CAMPAIGN EMAIL TEMPLATE ADMIN
# ============================================

@admin.register(CampaignEmailTemplate)
class CampaignEmailTemplateAdmin(admin.ModelAdmin):
    """Admin para gestionar templates de email reutilizables para campañas"""

    list_display = (
        'name',
        'is_default_badge',
        'is_active',
        'updated_at',
        'created_by'
    )

    list_filter = ('is_default', 'is_active', 'created_at')
    search_fields = ('name', 'description')

    readonly_fields = ('created_at', 'updated_at', 'created_by')

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'is_default', 'is_active')
        }),
        ('Contenido del Template', {
            'fields': ('subject_template', 'body_template'),
            'description': 'Usa {nombre_cliente} para el nombre y {gasto_total} para el gasto total'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    def is_default_badge(self, obj):
        if obj.is_default:
            return format_html('<span style="color: green; font-weight: bold;">✓ POR DEFECTO</span>')
        return '-'
    is_default_badge.short_description = 'Template por Defecto'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ============================================
# EMAIL CAMPAIGN ADMIN
# ============================================

@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    """Admin para gestionar campañas de email"""
    
    list_display = (
        'name',
        'status',
        'total_recipients',
        'emails_sent',
        'created_at'
    )
    
    list_filter = ('status', 'ai_variation_enabled', 'created_at')
    search_fields = ('name', 'description')
    
    readonly_fields = (
        'total_recipients', 'emails_sent', 'emails_delivered',
        'emails_opened', 'emails_clicked', 'emails_bounced',
        'spam_complaints', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'status', 'created_by')
        }),
        ('Template de Email', {
            'fields': ('email_subject_template', 'email_body_template')
        }),
        ('Configuración', {
            'fields': ('schedule_config', 'ai_variation_enabled', 'anti_spam_enabled')
        }),
        ('Estadísticas', {
            'fields': (
                'total_recipients', 'emails_sent', 'emails_delivered',
                'emails_opened', 'emails_clicked', 'emails_bounced', 'spam_complaints'
            ),
            'classes': ('collapse',)
        })
    )


@admin.register(EmailRecipient)
class EmailRecipientAdmin(admin.ModelAdmin):
    """Admin para gestionar destinatarios"""
    
    list_display = ('email', 'name', 'campaign', 'status', 'send_enabled', 'sent_at')
    list_filter = ('status', 'send_enabled', 'campaign')
    search_fields = ('email', 'name', 'campaign__name')
    
    readonly_fields = ('sent_at', 'delivered_at', 'opened_at', 'clicked_at')
    
    fieldsets = (
        ('Información', {
            'fields': ('campaign', 'email', 'name', 'status', 'send_enabled')
        }),
        ('Contenido', {
            'fields': ('personalized_subject', 'personalized_body'),
            'classes': ('collapse',)
        }),
        ('Eventos', {
            'fields': ('sent_at', 'delivered_at', 'opened_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(EmailDeliveryLog)
class EmailDeliveryLogAdmin(admin.ModelAdmin):
    """Admin para logs de entrega"""
    
    list_display = ('recipient', 'campaign', 'log_type', 'timestamp')
    list_filter = ('log_type', 'timestamp')
    search_fields = ('recipient__email', 'campaign__name')
    readonly_fields = ('recipient', 'campaign', 'log_type', 'timestamp', 'smtp_response', 'error_message')
    
    def has_add_permission(self, request):
        return False
