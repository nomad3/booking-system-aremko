from django.contrib import admin
from django import forms
from .forms import PagoInlineForm
from django.forms import DateTimeInput
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db.models import Sum
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.forms import DateInput, TimeInput, Select
# Updated model imports to include HomepageConfig and CRM models
from .models import (
    Proveedor, CategoriaProducto, Producto, VentaReserva, ReservaProducto,
    Pago, Cliente, CategoriaServicio, Servicio, ReservaServicio,
    MovimientoCliente, Compra, DetalleCompra, GiftCard, HomepageConfig,
    Lead, Company, Contact, Activity, Campaign, Deal, CampaignInteraction, HomepageSettings,
    # Communication models
    CommunicationLimit, ClientPreferences, CommunicationLog, SMSTemplate, MailParaEnviar,
    # Advanced Email Campaign models
    EmailCampaign, EmailRecipient, EmailDeliveryLog, EmailBlacklist, EmailTemplate, EmailSubjectTemplate, EmailContentTemplate,
    # Historical data
    ServiceHistory,
    # Sistema de Tramos y Premios
    Premio, ClientePremio, HistorialTramo
)
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.urls import path, reverse
from django.utils.html import format_html
import json
import xlwt
from django.core.paginator import Paginator
from openpyxl import load_workbook
from solo.admin import SingletonModelAdmin
from .views import admin_views
from django.http import HttpResponseRedirect
from django.utils.html import format_html # Import format_html

# --- Standard Model Inlines ---

class ReservaServicioInline(admin.TabularInline):
    model = ReservaServicio
    fields = ['servicio', 'fecha_agendamiento', 'hora_inicio', 'cantidad_personas', 'proveedor_asignado']
    readonly_fields = []
    autocomplete_fields = ['servicio', 'proveedor_asignado']
    extra = 1
    min_num = 0
    verbose_name = "Servicio Reservado"
    verbose_name_plural = "Servicios Reservados"

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if 'hora_inicio' in formset.form.base_fields and isinstance(formset.form.base_fields['hora_inicio'].widget, forms.TextInput):
             formset.form.base_fields['hora_inicio'].widget.attrs.update({'placeholder': 'HH:MM', 'style': 'width: 7em;'})
        return formset

class ReservaProductoInline(admin.TabularInline):
    model = ReservaProducto
    extra = 1
    autocomplete_fields = ['producto']
    verbose_name = "Producto Reservado"
    verbose_name_plural = "Productos Reservados"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "producto":
            kwargs["queryset"] = Producto.objects.order_by('nombre')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class PagoInline(admin.TabularInline):
    model = Pago
    form = PagoInlineForm
    extra = 1
    fields = ['fecha_pago', 'monto', 'metodo_pago', 'giftcard']
    autocomplete_fields = ['giftcard']
    verbose_name = "Pago"
    verbose_name_plural = "Pagos"

class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 1
    autocomplete_fields = ['producto']
    fields = ['producto', 'descripcion', 'cantidad', 'precio_unitario']
    verbose_name = "Detalle de Compra"
    verbose_name_plural = "Detalles de Compra"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "producto":
            kwargs["queryset"] = Producto.objects.order_by('nombre')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# --- CRM Inlines ---

class ActivityInline(admin.TabularInline):
    model = Activity
    verbose_name = "Actividad"
    verbose_name_plural = "Actividades Recientes"
    fields = ('activity_date', 'activity_type', 'subject', 'created_by', 'notes', 'campaign')
    readonly_fields = ('created_at', 'updated_at', 'activity_date')
    extra = 0
    autocomplete_fields = ['created_by', 'campaign']
    ordering = ('-activity_date',)
    max_num = 5

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
    verbose_name_plural = "Leads (Prospectos) Asociados"
    fields = ('first_name', 'last_name', 'email', 'status', 'source')
    readonly_fields = ('created_at', 'updated_at')
    extra = 0
    autocomplete_fields = []

class ContactInline(admin.TabularInline):
    model = Contact
    verbose_name = "Contacto"
    verbose_name_plural = "Contactos"
    fields = ('first_name', 'last_name', 'email', 'phone', 'job_title')
    readonly_fields = ('created_at', 'updated_at')
    extra = 1

class CampaignInteractionInline(admin.TabularInline):
    model = CampaignInteraction
    verbose_name = "Interacción de Campaña"
    verbose_name_plural = "Interacciones Recientes"
    fields = ('timestamp', 'interaction_type', 'campaign', 'activity', 'details')
    readonly_fields = ('timestamp',)
    extra = 0
    autocomplete_fields = ['campaign', 'activity']
    ordering = ('-timestamp',)
    max_num = 10

# --- ModelAdmins ---
# Registration happens in apps.py

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
        header_style = xlwt.easyxf('font: bold on; pattern: pattern solid, fore_colour gray25;')
        headers = ['Nombre', 'Teléfono', 'Email']
        for col, header in enumerate(headers):
            ws.write(0, col, header, header_style)
            ws.col(col).width = 256 * 20
        for row, cliente in enumerate(queryset, 1):
            ws.write(row, 0, cliente.nombre)
            ws.write(row, 1, cliente.telefono)
            ws.write(row, 2, cliente.email)
        wb.save(response)
        return response
    exportar_a_excel.short_description = "Exportar clientes seleccionados a Excel"

class VentaReservaAdmin(admin.ModelAdmin):
    list_per_page = 50
    autocomplete_fields = ['cliente']
    list_display = (
        'id', 'cliente_info', 'fecha_reserva_corta', 'estado_pago',
        'estado_reserva', 'servicios_y_cantidades',
        'productos_y_cantidades', 'total_servicios',
        'total_productos', 'total', 'pagado', 'saldo_pendiente', 'pdf_link'
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

    def servicios_y_cantidades(self, obj):
        servicios_list = [
            f"{reserva_servicio.servicio.nombre} (x{reserva_servicio.cantidad_personas})"
            for reserva_servicio in obj.reservaservicios.all()
        ]
        return ", ".join(servicios_list)
    servicios_y_cantidades.short_description = 'Servicios y Cantidades'

    def productos_y_cantidades(self, obj):
        productos_list = [
            f"{reserva_producto.producto.nombre} (x{reserva_producto.cantidad})"
            for reserva_producto in obj.reservaproductos.all()
        ]
        return ", ".join(productos_list)
    productos_y_cantidades.short_description = 'Productos y Cantidades'

    def total_servicios(self, obj):
        total = sum(
            reserva_servicio.servicio.precio_base * reserva_servicio.cantidad_personas
            for reserva_servicio in obj.reservaservicios.all() if reserva_servicio.servicio
        )
        return f"{int(total):,} CLP".replace(",", ".")
    total_servicios.short_description = 'Total de Servicios'

    def total_productos(self, obj):
        total = sum(
            reserva_producto.producto.precio_base * reserva_producto.cantidad
            for reserva_producto in obj.reservaproductos.all() if reserva_producto.producto
        )
        return f"{int(total):,} CLP".replace(",", ".")
    total_productos.short_description = 'Total de Productos'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.prefetch_related(
            'reservaproductos__producto',
            'reservaservicios__servicio',
            'pagos',
        ).select_related('cliente')
        return queryset

    def cliente_info(self, obj):
        return f"{obj.cliente.nombre} - {obj.cliente.telefono}"
    cliente_info.short_description = 'Cliente'
    cliente_info.admin_order_field = 'cliente__nombre'

    def fecha_reserva_corta(self, obj):
        if obj.fecha_reserva:
            local_time = timezone.localtime(obj.fecha_reserva)
            return local_time.strftime('%Y-%m-%d')
        return '-'
    fecha_reserva_corta.short_description = 'Fecha'
    fecha_reserva_corta.admin_order_field = 'fecha_reserva'

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        instance = form.instance
        instance.calcular_total()

    def get_urls(self):
        urls = super().get_urls()
        app_label = self.model._meta.app_label
        model_name = self.model._meta.model_name
        custom_urls = [
            path('<int:reserva_id>/pdf/',
                 self.admin_site.admin_view(admin_views.generate_reserva_pdf),
                 name=f'{app_label}_{model_name}_pdf'),
        ]
        return custom_urls + urls

    def pdf_link(self, obj):
        opts = obj._meta
        url = reverse(f'admin:{opts.app_label}_{opts.model_name}_pdf', args=[obj.pk])
        return format_html('<a class="button" href="{}" target="_blank">Ver PDF</a>', url)
    pdf_link.short_description = 'PDF'
    pdf_link.allow_tags = True

    class Media:
        css = {
            'all': ('admin/css/custom.css',)
        }
        js = (
            'admin/js/reserva_servicio_inline.js',
        )

class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'direccion', 'telefono', 'email')
    search_fields = ('nombre',)

class CompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_compra', 'proveedor', 'metodo_pago', 'numero_documento', 'total')
    list_filter = ('fecha_compra', 'metodo_pago', 'proveedor')
    search_fields = ('numero_documento', 'proveedor__nombre')
    inlines = [DetalleCompraInline]
    date_hierarchy = 'fecha_compra'
    readonly_fields = ('total',)
    autocomplete_fields = ['proveedor']
    list_select_related = ('proveedor',)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.calcular_total()
        form.instance.save()

class GiftCardAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'cliente_comprador', 'cliente_destinatario', 'monto_inicial', 'monto_disponible', 'fecha_emision', 'fecha_vencimiento', 'estado')
    search_fields = ('codigo', 'cliente_comprador__nombre', 'cliente_destinatario__nombre')
    list_filter = ('estado', 'fecha_emision', 'fecha_vencimiento')
    readonly_fields = ('codigo', 'monto_disponible')
    autocomplete_fields = ['cliente_comprador', 'cliente_destinatario']

class CategoriaProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio_base', 'cantidad_disponible', 'proveedor', 'categoria')
    search_fields = ('nombre', 'categoria__nombre')
    list_filter = ('categoria', 'proveedor')
    autocomplete_fields = ['proveedor', 'categoria']

class ServicioAdminForm(forms.ModelForm):
    class Meta:
        model = Servicio
        fields = '__all__'
        widgets = {
            'slots_disponibles': forms.Textarea(attrs={'rows': 10, 'cols': 60, 'placeholder': '{\n    "monday": ["16:00", "18:00"],\n    "tuesday": [],\n    ...\n}'}),
        }

    def clean_slots_disponibles(self):
        slots_data = self.cleaned_data.get('slots_disponibles')
        if isinstance(slots_data, str):
            try:
                if not slots_data.strip(): slots_data = {}
                else: slots_data = json.loads(slots_data)
            except json.JSONDecodeError as e: raise ValidationError(f"JSON inválido: {e}")
        if not isinstance(slots_data, dict): slots_data = {}
        valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        for day, slots in slots_data.items():
            if day not in valid_days: raise ValidationError(f"Clave de día inválida: '{day}'. Use nombres de días en inglés en minúsculas.")
            if not isinstance(slots, list): raise ValidationError(f"El valor para '{day}' debe ser una lista de horarios.")
            for slot in slots:
                if not isinstance(slot, str): raise ValidationError(f"El horario '{slot}' en '{day}' debe ser texto.")
                try: datetime.strptime(slot, "%H:%M")
                except ValueError: raise ValidationError(f"Formato de horario inválido: '{slot}' en '{day}'. Use HH:MM.")
        for day in valid_days: slots_data.setdefault(day, [])
        return slots_data

class ServicioAdmin(admin.ModelAdmin):
    form = ServicioAdminForm
    list_display = ('nombre', 'categoria', 'tipo_servicio', 'precio_base', 'duracion', 'capacidad_minima', 'capacidad_maxima', 'activo', 'publicado_web', 'imagen')
    list_filter = ('categoria', 'activo', 'publicado_web', 'tipo_servicio')
    search_fields = ('nombre', 'categoria__nombre', 'proveedores__nombre')
    filter_horizontal = ('proveedores',)
    fieldsets = (
        (None, {'fields': ('nombre', 'categoria', 'tipo_servicio', 'descripcion_web', 'precio_base', 'duracion', 'capacidad_minima', 'capacidad_maxima', 'imagen', 'proveedores', 'activo', 'publicado_web')}),
        ('Configuración Horaria', {'fields': ('horario_apertura', 'horario_cierre', 'slots_disponibles')}),
    )

class PagoAdmin(admin.ModelAdmin):
    list_display = ('id', 'venta_reserva_link', 'monto_formateado', 'metodo_pago', 'fecha_pago', 'usuario')
    list_filter = ('metodo_pago', 'fecha_pago', 'usuario')
    search_fields = ('venta_reserva__id', 'venta_reserva__cliente__nombre', 'usuario__username')
    autocomplete_fields = ['venta_reserva', 'usuario', 'giftcard']
    readonly_fields = ('venta_reserva_link',)

    def venta_reserva_link(self, obj):
        link = reverse("admin:ventas_ventareserva_change", args=[obj.venta_reserva.id])
        return format_html('<a href="{}">Venta/Reserva #{}</a>', link, obj.venta_reserva.id)
    venta_reserva_link.short_description = 'Venta/Reserva'

    def monto_formateado(self, obj):
        return f"{int(obj.monto):,} CLP".replace(",", ".")
    monto_formateado.short_description = 'Monto'
    monto_formateado.admin_order_field = 'monto'

    def save_model(self, request, obj, form, change):
        if not obj.usuario_id: obj.usuario = request.user
        super().save_model(request, obj, form, change)
        if obj.venta_reserva: obj.venta_reserva.calcular_total()

    def delete_model(self, request, obj):
        venta_reserva_temp = obj.venta_reserva
        super().delete_model(request, obj)
        if venta_reserva_temp: venta_reserva_temp.calcular_total()

class CategoriaServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'imagen')
    search_fields = ('nombre',)

class HomepageConfigAdmin(SingletonModelAdmin):
    pass

# --- Configuraciones Admin CRM & Marketing ---

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
                    first_name=lead.first_name, last_name=lead.last_name,
                    email=lead.email, phone=lead.phone, company=company,
                )
                Deal.objects.create(
                    name=f"Oportunidad Inicial para {contact.first_name} {contact.last_name}",
                    contact=contact, stage='Qualification', campaign=lead.campaign
                )
                lead.status = 'Converted'
                lead.save(update_fields=['status'])
                Activity.objects.create(
                    activity_type='Status Change', subject=f'Lead Convertido a Contacto: {contact}',
                    related_lead=lead, created_by=request.user
                )
                converted_count += 1
            else:
                 messages.warning(request, f"Contacto con email {lead.email} ya existe. Conversión omitida para Lead ID {lead.id}.")
                 skipped_count += 1
        if converted_count > 0: messages.success(request, f'{converted_count} leads calificados convertidos exitosamente.')
        if skipped_count == 0 and converted_count == 0: messages.info(request, 'No se seleccionaron leads calificados o elegibles para conversión.')
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

class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'website', 'created_at')
    search_fields = ('name', 'website')
    inlines = [ContactInline]
    readonly_fields = ('created_at', 'updated_at')

class ContactAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'company', 'job_title', 'linked_user', 'created_at')
    list_filter = ('company', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'phone', 'company__name', 'linked_user__username')
    inlines = [DealInline, ActivityInline, CampaignInteractionInline] # Added Interaction inline
    autocomplete_fields = ['company', 'linked_user']
    fieldsets = (
        (None, {'fields': ('first_name', 'last_name', 'email', 'phone', 'job_title')}),
        ('Asociación', {'fields': ('company', 'linked_user')}),
        ('Detalles', {'fields': ('notes',)}),
        ('Interacciones Recientes', {'fields': (), 'classes': ('collapse',)}), # Placeholder for inline
        ('Marcas de Tiempo', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at', 'updated_at')

class ActivityAdmin(admin.ModelAdmin):
    list_display = ('subject', 'activity_type', 'activity_date', 'related_lead', 'related_contact', 'related_deal', 'created_by', 'campaign') # Added campaign
    list_filter = ('activity_type', 'activity_date', 'created_by', 'campaign') # Added campaign
    search_fields = ('subject', 'notes', 'related_lead__email', 'related_contact__email', 'related_deal__name', 'created_by__username', 'campaign__name')
    autocomplete_fields = ['related_lead', 'related_contact', 'related_deal', 'created_by', 'campaign'] # Added campaign
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('activity_type', 'subject', 'activity_date', 'created_by')}),
        ('Relacionado Con', {'fields': ('related_lead', 'related_contact', 'related_deal', 'campaign')}), # Added campaign
        ('Detalles', {'fields': ('notes',)}),
        ('Marcas de Tiempo', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'start_date', 'end_date', 'target_min_visits', 'target_min_spend', 'budget', 'get_associated_leads_count', 'get_won_deals_count', 'get_won_deals_value')
    list_filter = ('status', 'start_date', 'end_date')
    search_fields = ('name', 'description', 'goal')
    inlines = [LeadInline, ActivityInline, CampaignInteractionInline] # Added Activity and Interaction inlines
    fieldsets = (
        (None, {'fields': ('name', 'status', 'description', 'goal')}),
        ('Fechas y Presupuesto', {'fields': ('start_date', 'end_date', 'budget')}),
        ('Criterios de Segmentación (Clientes)', {
            'fields': ('target_min_visits', 'target_min_spend'),
            'description': 'Definir criterios para seleccionar Clientes existentes para esta campaña (usado por API/automatización).'
        }),
        ('Plantillas de Contenido (para n8n)', {
            'fields': ('email_subject_template', 'email_body_template', 'sms_template', 'whatsapp_template'),
            'classes': ('collapse',),
            'description': 'Escriba las plantillas de mensajes aquí. Use {nombre_cliente}, {apellido_cliente} como placeholders que n8n reemplazará.'
        }),
        ('Notas de Automatización', {
            'fields': ('automation_notes',),
            'classes': ('collapse',),
        }),
        ('Interacciones Recientes', {'fields': (), 'classes': ('collapse',)}), # Placeholder for inline
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
        return f"${int(value):,} CLP".replace(",", ".") if value else "$0 CLP"
    get_won_deals_value.short_description = 'Valor Ganado'


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

class CampaignInteractionAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'contact', 'campaign', 'interaction_type', 'activity', 'details') # Added details
    list_filter = ('interaction_type', 'campaign', 'timestamp')
    search_fields = ('contact__first_name', 'contact__last_name', 'contact__email', 'campaign__name', 'details')
    autocomplete_fields = ['contact', 'campaign', 'activity']
    readonly_fields = ('timestamp',) # Only timestamp should be read-only by default
    list_select_related = ('contact', 'campaign', 'activity') # Optimize queries
    date_hierarchy = 'timestamp'

@admin.register(HomepageSettings)
class HomepageSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'hero_background_image')
    # Prevent adding more than one instance from the admin list view
    def has_add_permission(self, request):
        return not HomepageSettings.objects.exists()


# --- Admin para Modelos de Comunicación Inteligente ---

@admin.register(CommunicationLimit)
class CommunicationLimitAdmin(admin.ModelAdmin):
    list_display = (
        'cliente', 'sms_count_daily', 'sms_count_monthly', 
        'email_count_weekly', 'birthday_sms_sent_this_year',
        'reactivation_emails_this_quarter', 'updated_at'
    )
    list_filter = (
        'birthday_sms_sent_this_year', 'last_sms_date', 'last_email_date',
        'created_at', 'updated_at'
    )
    search_fields = ('cliente__nombre', 'cliente__telefono', 'cliente__email')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Cliente', {
            'fields': ('cliente',)
        }),
        ('Límites SMS', {
            'fields': (
                'sms_count_daily', 'sms_count_monthly', 'last_sms_date',
                'last_sms_reset_daily', 'last_sms_reset_monthly'
            )
        }),
        ('Límites Email', {
            'fields': (
                'email_count_weekly', 'email_count_monthly', 'last_email_date',
                'last_email_reset_weekly', 'last_email_reset_monthly'
            )
        }),
        ('Límites Especiales', {
            'fields': (
                'birthday_sms_sent_this_year', 'last_birthday_sms_year',
                'reactivation_emails_this_quarter', 'last_reactivation_quarter'
            )
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('cliente')


@admin.register(ClientPreferences)
class ClientPreferencesAdmin(admin.ModelAdmin):
    list_display = (
        'cliente', 'accepts_sms', 'accepts_email', 'accepts_promotional',
        'accepts_newsletters', 'opt_out_date'
    )
    list_filter = (
        'accepts_sms', 'accepts_email', 'accepts_promotional', 
        'accepts_newsletters', 'accepts_birthday_messages',
        'accepts_booking_confirmations', 'accepts_booking_reminders',
        'opt_out_date'
    )
    search_fields = ('cliente__nombre', 'cliente__telefono', 'cliente__email')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Cliente', {
            'fields': ('cliente',)
        }),
        ('Preferencias Generales', {
            'fields': ('accepts_sms', 'accepts_email', 'accepts_whatsapp')
        }),
        ('Preferencias Específicas', {
            'fields': (
                'accepts_booking_confirmations', 'accepts_booking_reminders',
                'accepts_birthday_messages', 'accepts_promotional',
                'accepts_newsletters', 'accepts_reactivation'
            )
        }),
        ('Horarios de Contacto', {
            'fields': ('preferred_contact_hour_start', 'preferred_contact_hour_end')
        }),
        ('Opt-out', {
            'fields': ('opt_out_date',),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['set_opt_out_all']
    
    def set_opt_out_all(self, request, queryset):
        """Acción para marcar clientes como opt-out completo"""
        for preference in queryset:
            preference.set_opt_out_all()
        self.message_user(
            request,
            f"Se configuró opt-out completo para {queryset.count()} cliente(s)."
        )
    set_opt_out_all.short_description = "Configurar opt-out completo"


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    list_display = (
        'cliente', 'communication_type', 'message_type', 'status',
        'destination', 'sent_at', 'cost'
    )
    list_filter = (
        'communication_type', 'message_type', 'status',
        'sent_at', 'delivered_at', 'created_at'
    )
    search_fields = (
        'cliente__nombre', 'cliente__telefono', 'destination',
        'subject', 'external_id'
    )
    readonly_fields = (
        'created_at', 'updated_at', 'sent_at', 'delivered_at',
        'read_at', 'replied_at'
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Cliente y Campaña', {
            'fields': ('cliente', 'campaign')
        }),
        ('Detalles del Mensaje', {
            'fields': (
                'communication_type', 'message_type', 'subject',
                'content', 'destination'
            )
        }),
        ('Estado y Tracking', {
            'fields': (
                'status', 'external_id', 'sent_at', 'delivered_at',
                'read_at', 'replied_at'
            )
        }),
        ('Contexto', {
            'fields': ('booking_id', 'triggered_by', 'cost'),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_as_delivered', 'mark_as_failed']
    
    def mark_as_delivered(self, request, queryset):
        """Acción para marcar mensajes como entregados"""
        updated = 0
        for log in queryset.filter(status='SENT'):
            log.mark_as_delivered()
            updated += 1
        self.message_user(
            request,
            f"Se marcaron {updated} mensaje(s) como entregados."
        )
    mark_as_delivered.short_description = "Marcar como entregado"
    
    def mark_as_failed(self, request, queryset):
        """Acción para marcar mensajes como fallidos"""
        updated = 0
        for log in queryset.exclude(status='FAILED'):
            log.mark_as_failed()
            updated += 1
        self.message_user(
            request,
            f"Se marcaron {updated} mensaje(s) como fallidos."
        )
    mark_as_failed.short_description = "Marcar como fallido"


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'message_type', 'is_active', 'requires_approval',
        'max_uses_per_client_per_day', 'created_by', 'created_at'
    )
    list_filter = (
        'message_type', 'is_active', 'requires_approval', 'created_at'
    )
    search_fields = ('name', 'content')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'message_type', 'content')
        }),
        ('Configuración', {
            'fields': ('is_active', 'requires_approval')
        }),
        ('Límites de Uso', {
            'fields': (
                'max_uses_per_client_per_day',
                'max_uses_per_client_per_month'
            )
        }),
        ('Metadatos', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        """Asignar usuario creador automáticamente"""
        if not change:  # Solo al crear
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['activate_templates', 'deactivate_templates']
    
    def activate_templates(self, request, queryset):
        """Acción para activar plantillas"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"Se activaron {updated} plantilla(s)."
        )
    activate_templates.short_description = "Activar plantillas seleccionadas"
    
    def deactivate_templates(self, request, queryset):
        """Acción para desactivar plantillas"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"Se desactivaron {updated} plantilla(s)."
        )
    deactivate_templates.short_description = "Desactivar plantillas seleccionadas"


@admin.register(MailParaEnviar)
class MailParaEnviarAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'email', 'ciudad', 'estado', 'prioridad', 'campana', 'creado_en', 'enviado_en']
    list_filter = ['estado', 'prioridad', 'campana', 'ciudad', 'rubro', 'creado_en']
    search_fields = ['nombre', 'email', 'asunto']
    readonly_fields = ['enviado_en']
    list_editable = ['estado', 'prioridad']
    
    fieldsets = (
        ('Destinatario', {
            'fields': ('nombre', 'email', 'ciudad', 'rubro')
        }),
        ('Contenido', {
            'fields': ('asunto', 'contenido_html')
        }),
        ('Control de Envío', {
            'fields': ('estado', 'prioridad', 'campana', 'notas')
        }),
        ('Timestamps', {
            'fields': ('creado_en', 'enviado_en'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['marcar_como_pendiente', 'marcar_como_pausado', 'duplicar_emails']
    
    def marcar_como_pendiente(self, request, queryset):
        updated = queryset.update(estado='PENDIENTE')
        self.message_user(request, f'{updated} emails marcados como PENDIENTE.')
    marcar_como_pendiente.short_description = "Marcar como PENDIENTE"
    
    def marcar_como_pausado(self, request, queryset):
        updated = queryset.update(estado='PAUSADO')
        self.message_user(request, f'{updated} emails marcados como PAUSADO.')
    marcar_como_pausado.short_description = "Marcar como PAUSADO"
    
    def duplicar_emails(self, request, queryset):
        count = 0
        for obj in queryset:
            obj.pk = None
            obj.estado = 'PENDIENTE'
            obj.enviado_en = None
            obj.save()
            count += 1
        self.message_user(request, f'{count} emails duplicados como PENDIENTE.')
    duplicar_emails.short_description = "Duplicar emails como PENDIENTE"


# =============================================================================
# ADMIN PARA SISTEMA DE CAMPAÑAS AVANZADO
# =============================================================================

class EmailRecipientInline(admin.TabularInline):
    """Inline para mostrar destinatarios de una campaña"""
    model = EmailRecipient
    fields = ['email', 'name', 'status', 'send_enabled', 'priority', 'sent_at']
    readonly_fields = ['sent_at']
    extra = 0
    can_delete = False
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('client')


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    """Administrador para campañas de email"""
    list_display = [
        'name', 'status', 'total_recipients', 'emails_sent', 
        'progress_display', 'created_at', 'created_by'
    ]
    list_filter = ['status', 'created_at', 'ai_variation_enabled']
    search_fields = ['name', 'description']
    readonly_fields = [
        'created_at', 'updated_at', 'total_recipients', 'emails_sent',
        'emails_delivered', 'emails_opened', 'emails_clicked', 
        'emails_bounced', 'spam_complaints'
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'status', 'created_by')
        }),
        ('Criterios de Selección', {
            'fields': ('criteria',),
            'classes': ('collapse',)
        }),
        ('Configuración de Envío', {
            'fields': ('schedule_config',),
            'classes': ('collapse',)
        }),
        ('Template de Email', {
            'fields': ('email_subject_template', 'email_body_template'),
            'classes': ('collapse',)
        }),
        ('Configuración Avanzada', {
            'fields': ('ai_variation_enabled',),
            'classes': ('collapse',)
        }),
        ('Estadísticas', {
            'fields': (
                'total_recipients', 'emails_sent', 'emails_delivered',
                'emails_opened', 'emails_clicked', 'emails_bounced',
                'spam_complaints'
            ),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [EmailRecipientInline]
    
    def progress_display(self, obj):
        """Muestra el progreso de la campaña"""
        if obj.total_recipients == 0:
            return "0%"
        progress = obj.progress_percentage
        color = "red" if progress < 25 else "orange" if progress < 75 else "green"
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, progress
        )
    progress_display.short_description = "Progreso"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')


@admin.register(EmailRecipient)
class EmailRecipientAdmin(admin.ModelAdmin):
    """Administrador para destinatarios de email"""
    list_display = [
        'email', 'name', 'campaign', 'status', 'send_enabled',
        'priority', 'sent_at', 'delivered_at'
    ]
    list_filter = ['status', 'send_enabled', 'campaign', 'sent_at']
    search_fields = ['email', 'name', 'campaign__name']
    readonly_fields = [
        'sent_at', 'delivered_at', 'opened_at', 'clicked_at',
        'client_total_spend', 'client_visit_count', 'client_last_visit'
    ]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('campaign', 'client', 'email', 'name')
        }),
        ('Contenido Personalizado', {
            'fields': ('personalized_subject', 'personalized_body'),
            'classes': ('collapse',)
        }),
        ('Control de Envío', {
            'fields': ('send_enabled', 'priority', 'status')
        }),
        ('Tracking', {
            'fields': (
                'scheduled_at', 'sent_at', 'delivered_at', 
                'opened_at', 'clicked_at'
            ),
            'classes': ('collapse',)
        }),
        ('Información del Cliente', {
            'fields': (
                'client_total_spend', 'client_visit_count', 
                'client_last_visit', 'client_city'
            ),
            'classes': ('collapse',)
        }),
        ('Diagnósticos', {
            'fields': ('error_message', 'bounce_reason', 'user_agent', 'ip_address'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['marcar_como_pendiente', 'deshabilitar_envio', 'habilitar_envio']
    
    def marcar_como_pendiente(self, request, queryset):
        updated = queryset.update(status='pending')
        self.message_user(request, f'{updated} destinatarios marcados como pendientes.')
    marcar_como_pendiente.short_description = "Marcar como pendiente"
    
    def deshabilitar_envio(self, request, queryset):
        updated = queryset.update(send_enabled=False)
        self.message_user(request, f'{updated} destinatarios deshabilitados para envío.')
    deshabilitar_envio.short_description = "Deshabilitar envío"
    
    def habilitar_envio(self, request, queryset):
        updated = queryset.update(send_enabled=True)
        self.message_user(request, f'{updated} destinatarios habilitados para envío.')
    habilitar_envio.short_description = "Habilitar envío"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('campaign', 'client')


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    """Administrador para templates de email"""
    list_display = ['name', 'campaign_type', 'year', 'month', 'giftcard_amount', 'is_active', 'created_at']
    list_filter = ['campaign_type', 'year', 'month', 'is_active']
    search_fields = ['name', 'subject']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'campaign_type', 'is_active')
        }),
        ('Configuración', {
            'fields': ('year', 'month', 'giftcard_amount')
        }),
        ('Contenido', {
            'fields': ('subject', 'body_html')
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(EmailDeliveryLog)
class EmailDeliveryLogAdmin(admin.ModelAdmin):
    """Administrador para logs de entrega de email"""
    list_display = ['recipient', 'log_type', 'timestamp', 'error_code', 'smtp_response_short']
    list_filter = ['log_type', 'timestamp', 'campaign', 'error_code']
    search_fields = ['recipient__email', 'recipient__name', 'smtp_response', 'error_message']
    readonly_fields = ['timestamp']
    
    def smtp_response_short(self, obj):
        """Muestra una versión corta de la respuesta SMTP"""
        if obj.smtp_response:
            return obj.smtp_response[:50] + "..." if len(obj.smtp_response) > 50 else obj.smtp_response
        return "-"
    smtp_response_short.short_description = "Respuesta SMTP"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('campaign', 'recipient')


@admin.register(EmailBlacklist)
class EmailBlacklistAdmin(admin.ModelAdmin):
    """Administrador para lista negra de emails"""
    list_display = ['email', 'reason', 'added_at', 'is_active', 'domain']
    list_filter = ['reason', 'is_active', 'added_at', 'domain']
    search_fields = ['email', 'reason', 'notes', 'domain']
    readonly_fields = ['added_at', 'domain']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('email', 'reason', 'is_active')
        }),
        ('Detalles', {
            'fields': ('notes', 'domain', 'expires_at')
        }),
        ('Metadatos', {
            'fields': ('added_at', 'added_by'),
            'classes': ('collapse',)
        })
    )


@admin.register(EmailSubjectTemplate)
class EmailSubjectTemplateAdmin(admin.ModelAdmin):
    """Administrador para asuntos de email variables"""
    list_display = ['subject_template', 'estilo', 'activo', 'veces_usado', 'created_at']
    list_filter = ['estilo', 'activo', 'created_at']
    search_fields = ['subject_template']
    readonly_fields = ['veces_usado', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Asunto del Email', {
            'fields': ('subject_template', 'estilo', 'activo'),
            'description': 'Usa {nombre} en el asunto para insertar el nombre del cliente. Ejemplo: "{nombre}, tenemos algo especial para ti"'
        }),
        ('Estadísticas', {
            'fields': ('veces_usado', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['reset_usage_counter', 'activate_subjects', 'deactivate_subjects']
    
    def reset_usage_counter(self, request, queryset):
        """Reinicia el contador de uso"""
        queryset.update(veces_usado=0)
        self.message_user(request, f"Contador reiniciado para {queryset.count()} asuntos")
    reset_usage_counter.short_description = "Reiniciar contador de uso"
    
    def activate_subjects(self, request, queryset):
        """Activa asuntos seleccionados"""
        queryset.update(activo=True)
        self.message_user(request, f"{queryset.count()} asuntos activados")
    activate_subjects.short_description = "Activar asuntos"
    
    def deactivate_subjects(self, request, queryset):
        """Desactiva asuntos seleccionados"""
        queryset.update(activo=False)
        self.message_user(request, f"{queryset.count()} asuntos desactivados")
    deactivate_subjects.short_description = "Desactivar asuntos"


@admin.register(EmailContentTemplate)
class EmailContentTemplateAdmin(admin.ModelAdmin):
    """Administrador para templates de contenido de email editables"""
    list_display = ['nombre', 'estilo', 'activo', 'updated_at', 'created_by']
    list_filter = ['estilo', 'activo', 'created_at']
    search_fields = ['nombre', 'saludo', 'introduccion']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'estilo', 'activo')
        }),
        ('Contenido del Email', {
            'fields': ('saludo', 'introduccion', 'seccion_ofertas_titulo', 'seccion_ofertas_intro', 'oferta_texto', 'cierre', 'firma'),
            'description': '''
                <strong>Placeholders disponibles:</strong><br>
                - <code>{nombre}</code>: Nombre del cliente<br>
                - <code>{servicios_narrativa}</code>: Narrativa generada del historial<br>
                - <code>{oferta_porcentaje}</code>: Porcentaje de descuento<br>
                - <code>{oferta_servicios}</code>: Servicios en oferta<br>
                - <code>{mes_actual}</code>: Mes actual<br>
                - <code>{segmento}</code>: Segmento RFM del cliente
            '''
        }),
        ('Call to Action', {
            'fields': ('call_to_action_texto',)
        }),
        ('Estilos y Colores', {
            'fields': ('color_principal', 'color_secundario', 'fuente_tipografia'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['duplicate_template', 'activate_template', 'deactivate_template']
    
    def save_model(self, request, obj, form, change):
        """Guardar el creador del template"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def duplicate_template(self, request, queryset):
        """Duplica templates seleccionados"""
        for template in queryset:
            template.pk = None
            template.nombre = f"{template.nombre} (Copia)"
            template.activo = False
            template.created_by = request.user
            template.save()
        self.message_user(request, f"{queryset.count()} templates duplicados")
    duplicate_template.short_description = "Duplicar templates"
    
    def activate_template(self, request, queryset):
        """Activa templates seleccionados"""
        queryset.update(activo=True)
        self.message_user(request, f"{queryset.count()} templates activados")
    activate_template.short_description = "Activar templates"
    
    def deactivate_template(self, request, queryset):
        """Desactiva templates seleccionados"""
        queryset.update(activo=False)
        self.message_user(request, f"{queryset.count()} templates desactivados")
    deactivate_template.short_description = "Desactivar templates"


# ================================================================================
# SERVICI HISTORY (DATOS HISTÓRICOS IMPORTADOS)
# ================================================================================

@admin.register(ServiceHistory)
class ServiceHistoryAdmin(admin.ModelAdmin):
    """
    Admin para servicios históricos importados desde CSV
    Permite visualizar y verificar los 26K+ servicios históricos (2020-2024)
    """
    list_display = ('id', 'cliente_link', 'service_name', 'service_type',
                    'service_date', 'price_paid', 'season', 'year', 'reserva_id')
    list_filter = ('service_type', 'season', 'year', 'service_date')
    search_fields = ('cliente__nombre', 'cliente__email', 'cliente__telefono',
                     'service_name', 'reserva_id')
    readonly_fields = ('id', 'cliente', 'reserva_id', 'service_type', 'service_name',
                       'service_date', 'quantity', 'price_paid', 'season', 'year')
    list_per_page = 50
    date_hierarchy = 'service_date'

    fieldsets = (
        ('Cliente', {
            'fields': ('cliente',)
        }),
        ('Servicio', {
            'fields': ('reserva_id', 'service_type', 'service_name', 'quantity', 'price_paid')
        }),
        ('Fecha y Temporada', {
            'fields': ('service_date', 'year', 'season')
        }),
    )

    def cliente_link(self, obj):
        """Link al cliente en el admin"""
        if obj.cliente:
            url = reverse('admin:ventas_cliente_change', args=[obj.cliente.id])
            return format_html('<a href="{}">{}</a>', url, obj.cliente.nombre)
        return '-'
    cliente_link.short_description = 'Cliente'

    def has_add_permission(self, request):
        """No permitir agregar servicios históricos manualmente"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Solo superusers pueden eliminar"""
        return request.user.is_superuser

    class Media:
        css = {
            'all': ('admin/css/custom.css',)
        }

# ============================================================================
# ADMIN: SISTEMA DE TRAMOS Y PREMIOS
# ============================================================================

@admin.register(Premio)
class PremioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'valor_monetario', 'dias_validez', 'activo', 'fecha_creacion')
    list_filter = ('tipo', 'activo', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion_corta')
    readonly_fields = ('fecha_creacion', 'fecha_modificacion')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'tipo', 'activo')
        }),
        ('Descripciones', {
            'fields': ('descripcion_corta', 'descripcion_legal')
        }),
        ('Valores y Descuentos', {
            'fields': (
                'porcentaje_descuento_tinas',
                'porcentaje_descuento_masajes',
                'valor_monetario'
            )
        }),
        ('Configuración', {
            'fields': ('dias_validez', 'restricciones')
        }),
        ('Metadata', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ClientePremio)
class ClientePremioAdmin(admin.ModelAdmin):
    list_display = (
        'cliente_link',
        'premio',
        'estado_badge',
        'tramo_info',
        'fecha_ganado',
        'fecha_expiracion',
        'esta_vigente_badge',
        'acciones_rapidas'
    )
    list_filter = (
        'estado',
        'fecha_ganado',
        'tramo_al_ganar',
        'premio__tipo'
    )
    search_fields = (
        'cliente__nombre',
        'cliente__email',
        'codigo_unico',
        'premio__nombre'
    )
    readonly_fields = (
        'fecha_ganado',
        'codigo_unico',
        'tramo_al_ganar',
        'gasto_total_al_ganar',
        'fecha_uso',
        'esta_vigente_badge'
    )
    autocomplete_fields = ['cliente', 'venta_donde_uso']
    
    fieldsets = (
        ('Cliente y Premio', {
            'fields': ('cliente', 'premio', 'estado')
        }),
        ('Tracking de Tramo', {
            'fields': (
                'tramo_al_ganar',
                'tramo_anterior',
                'gasto_total_al_ganar'
            )
        }),
        ('Fechas', {
            'fields': (
                'fecha_ganado',
                'fecha_aprobacion',
                'fecha_enviado',
                'fecha_expiracion',
                'fecha_uso',
                'esta_vigente_badge'
            )
        }),
        ('Email', {
            'fields': ('asunto_email', 'cuerpo_email'),
            'classes': ('collapse',)
        }),
        ('Uso del Premio', {
            'fields': ('codigo_unico', 'venta_donde_uso')
        }),
        ('Notas', {
            'fields': ('notas_admin',)
        }),
    )
    
    actions = ['aprobar_premios', 'marcar_como_enviado', 'cancelar_premios']
    
    def cliente_link(self, obj):
        """Link al cliente"""
        if obj.cliente:
            url = reverse('admin:ventas_cliente_change', args=[obj.cliente.id])
            return format_html('<a href="{}">{}</a>', url, obj.cliente.nombre)
        return '-'
    cliente_link.short_description = 'Cliente'
    
    def estado_badge(self, obj):
        """Badge visual del estado"""
        colors = {
            'pendiente_aprobacion': '#FFA500',
            'aprobado': '#4CAF50',
            'enviado': '#2196F3',
            'usado': '#9C27B0',
            'expirado': '#F44336',
            'cancelado': '#757575',
        }
        color = colors.get(obj.estado, '#757575')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def tramo_info(self, obj):
        """Info de tramo"""
        if obj.tramo_anterior:
            return format_html(
                'Tramo {} → {} <br><small>${:,}</small>',
                obj.tramo_anterior,
                obj.tramo_al_ganar,
                obj.gasto_total_al_ganar
            )
        return format_html(
            'Tramo {} <br><small>${:,}</small>',
            obj.tramo_al_ganar,
            obj.gasto_total_al_ganar
        )
    tramo_info.short_description = 'Tramo'
    
    def esta_vigente_badge(self, obj):
        """Badge de vigencia"""
        if obj.esta_vigente():
            return format_html(
                '<span style="color: green;">✓ Vigente</span>'
            )
        return format_html(
            '<span style="color: red;">✗ No vigente</span>'
        )
    esta_vigente_badge.short_description = 'Vigencia'
    
    def acciones_rapidas(self, obj):
        """Botones de acciones rápidas"""
        buttons = []
        
        if obj.estado == 'pendiente_aprobacion':
            buttons.append(
                '<a class="button" href="{}?ids={}">Aprobar</a>'.format(
                    reverse('admin:ventas_clientepremio_changelist'),
                    obj.id
                )
            )
        
        if obj.estado in ['aprobado', 'enviado'] and obj.esta_vigente():
            buttons.append(
                '<a class="button" href="{}">Ver Email</a>'.format(
                    reverse('admin:ventas_clientepremio_change', args=[obj.id])
                )
            )
        
        return format_html(' '.join(buttons)) if buttons else '-'
    acciones_rapidas.short_description = 'Acciones'
    
    def aprobar_premios(self, request, queryset):
        """Acción para aprobar premios en lote"""
        from django.utils import timezone
        
        updated = queryset.filter(estado='pendiente_aprobacion').update(
            estado='aprobado',
            fecha_aprobacion=timezone.now()
        )
        
        self.message_user(
            request,
            f'{updated} premio(s) aprobado(s) exitosamente.'
        )
    aprobar_premios.short_description = "Aprobar premios seleccionados"
    
    def marcar_como_enviado(self, request, queryset):
        """Acción para marcar como enviado"""
        from django.utils import timezone
        
        updated = queryset.filter(estado='aprobado').update(
            estado='enviado',
            fecha_enviado=timezone.now()
        )
        
        self.message_user(
            request,
            f'{updated} premio(s) marcado(s) como enviado.'
        )
    marcar_como_enviado.short_description = "Marcar como enviado"
    
    def cancelar_premios(self, request, queryset):
        """Acción para cancelar premios"""
        updated = queryset.update(estado='cancelado')
        
        self.message_user(
            request,
            f'{updated} premio(s) cancelado(s).'
        )
    cancelar_premios.short_description = "Cancelar premios seleccionados"


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

