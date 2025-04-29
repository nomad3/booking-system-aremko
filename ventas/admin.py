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
    Lead, Company, Contact, Activity, Campaign, Deal, CampaignInteraction, HomepageSettings # Added HomepageSettings
)
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.urls import path, reverse
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
        'total_productos', 'total', 'pagado', 'saldo_pendiente',
        'ver_resumen_pdf'
    )
    list_filter = ('estado_pago', 'estado_reserva', 'fecha_reserva')
    search_fields = ('id', 'cliente__nombre', 'cliente__telefono')
    inlines = [ReservaServicioInline, ReservaProductoInline, PagoInline]
    readonly_fields = (
        'id', 'total', 'pagado', 'saldo_pendiente', 'estado_pago',
        'productos_y_cantidades', 'servicios_y_cantidades',
        'total_productos', 'total_servicios',
        'enlace_resumen_pdf'
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

    def _get_pdf_url(self, obj):
        return reverse('ventas:reserva_pdf', args=[obj.id])

    def ver_resumen_pdf(self, obj):
        url = self._get_pdf_url(obj)
        return format_html('<a href="{}" target="_blank" class="button">Ver PDF</a>', url)
    ver_resumen_pdf.short_description = 'Resumen PDF'

    def enlace_resumen_pdf(self, obj):
        if obj.pk:
            url = self._get_pdf_url(obj)
            return format_html('<a href="{}" target="_blank">Abrir Resumen PDF</a>', url)
        return "-"
    enlace_resumen_pdf.short_description = 'Resumen PDF'

    class Media:
        css = {
            'all': ('admin/css/custom.css',)
        }

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
