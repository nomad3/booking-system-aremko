from django.contrib import admin, messages
from solo.admin import SingletonModelAdmin
from django import forms
from django.db import models
from .forms import PagoInlineForm, PagoInlineFormSet, VentaReservaAdminForm
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
    # Massage Management Models
    MasajistaEspecialidad, HorarioMasajista, SalaServicio,
    # CRM Models
    Lead, Company, Contact, Activity, Campaign, Deal, CampaignInteraction,
    HomepageConfig, HomepageSettings,
    # Email Templates
    EmailSubjectTemplate, EmailContentTemplate,
    # Premios y Tramos
    Premio, ClientePremio, HistorialTramo,
    # Email Campaigns
    CampaignEmailTemplate, EmailCampaign, EmailRecipient, EmailDeliveryLog,
    # Communication System
    CommunicationLog, CommunicationLimit, ClientPreferences, SMSTemplate,
    # Corporate Services
    CotizacionEmpresa,
    # Service Blocking
    ServicioBloqueo,
    ServicioSlotBloqueo,
    # Newsletter
    NewsletterSubscriber,
    # SEO
    SEOContent,
    # Resumen de Reserva
    ConfiguracionResumen,
    # Tips Post-Pago
    ConfiguracionTips,
    # Sistema de Pagos a Masajistas
    PagoMasajista, DetalleServicioPago
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
    fields = ['servicio', 'fecha_agendamiento', 'hora_inicio', 'cantidad_personas', 'mostrar_valor_unitario', 'mostrar_valor_total', 'proveedor_asignado']
    readonly_fields = ['mostrar_valor_unitario', 'mostrar_valor_total']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "servicio":
            kwargs["queryset"] = Servicio.objects.order_by('nombre')  # Ordena alfabéticamente por nombre
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class ReservaProductoInline(admin.TabularInline):
    model = ReservaProducto
    extra = 1
    fields = ['producto', 'cantidad', 'fecha_entrega', 'mostrar_valor_unitario', 'mostrar_valor_total']
    readonly_fields = ['mostrar_valor_unitario', 'mostrar_valor_total']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "producto":
            kwargs["queryset"] = Producto.objects.order_by('nombre')  # Ordena alfabéticamente por nombre
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class PagoInline(admin.TabularInline):
    model = Pago
    form = PagoInlineForm
    formset = PagoInlineFormSet
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
    fields = ['codigo', 'monto_inicial', 'destinatario_nombre', 'estado', 'enviado_email', 'ver_giftcard']
    readonly_fields = ['codigo', 'monto_inicial', 'destinatario_nombre', 'estado', 'enviado_email', 'ver_giftcard']
    verbose_name = "GiftCard"
    verbose_name_plural = "GiftCards de esta Venta"
    can_delete = False

    def ver_giftcard(self, obj):
        """Botón para ver la GiftCard"""
        from django.utils.html import format_html
        from django.urls import reverse
        from urllib.parse import quote
        from django.conf import settings

        if obj and obj.codigo:
            # URL para ver la GiftCard
            view_url = reverse('ventas:giftcard_mobile_view', args=[obj.codigo])

            # Construir URL completa
            # Intentar obtener el dominio de settings, si no usar el de producción
            base_url = getattr(settings, 'SITE_URL', 'https://aremko-booking-system.onrender.com')
            full_url = f"{base_url}{view_url}"

            # Obtener información del destinatario y comprador
            destinatario = obj.destinatario_nombre or "Cliente"
            telefono_destinatario = getattr(obj, 'cliente_destinatario', None)

            # Mensaje personalizado para WhatsApp
            if destinatario != "Cliente":
                mensaje_whatsapp = f"¡Hola {destinatario}! 🎁 Te han regalado una GiftCard de Aremko por ${obj.monto_inicial:,.0f}. Tu código es: {obj.codigo}. Puedes verla y descargarla aquí: {full_url}"
            else:
                mensaje_whatsapp = f"¡Hola! 🎁 Te comparto tu GiftCard de Aremko por ${obj.monto_inicial:,.0f}. Tu código es: {obj.codigo}. Puedes verla y descargarla aquí: {full_url}"

            # Si hay teléfono del destinatario, incluirlo en el link de WhatsApp
            if telefono_destinatario and hasattr(telefono_destinatario, 'telefono'):
                # Limpiar el número de teléfono (quitar espacios, guiones, etc)
                telefono = ''.join(filter(str.isdigit, str(telefono_destinatario.telefono)))
                if telefono.startswith('56'):
                    whatsapp_url = f"https://wa.me/{telefono}?text={quote(mensaje_whatsapp)}"
                elif telefono:
                    # Si no empieza con código de país, asumir Chile (56)
                    whatsapp_url = f"https://wa.me/56{telefono}?text={quote(mensaje_whatsapp)}"
                else:
                    whatsapp_url = f"https://wa.me/?text={quote(mensaje_whatsapp)}"
            else:
                # Sin número específico
                whatsapp_url = f"https://wa.me/?text={quote(mensaje_whatsapp)}"

            return format_html(
                '<a href="{}" target="_blank" style="background-color: #4CAF50; color: white; padding: 5px 10px; '
                'text-decoration: none; border-radius: 3px; display: inline-block; margin-right: 10px;">📱 Ver GiftCard</a>'
                '<a href="{}" target="_blank" style="background-color: #25D366; color: white; padding: 5px 10px; '
                'text-decoration: none; border-radius: 3px; display: inline-block;" title="Compartir por WhatsApp">📤 WhatsApp</a>',
                view_url, whatsapp_url
            )
        return '-'
    ver_giftcard.short_description = 'Acciones'

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
    form = VentaReservaAdminForm
    change_form_template = 'admin/ventas/ventareserva/change_form.html'
    change_list_template = 'admin/ventas/ventareserva/change_list.html'
    list_per_page = 50
    autocomplete_fields = ['cliente']
    list_display = (
        'id', 'cliente_info', 'fecha_reserva_corta', 'estado_pago',
        'estado_reserva', 'servicios_y_cantidades',
        'productos_y_cantidades', 'total_servicios',
        'total_productos', 'total', 'pagado', 'saldo_pendiente',
        'generar_cotizacion_link', 'generar_resumen_link', 'generar_tips_link'
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
                'estado_pago',
                'estado_reserva'
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
        # Si fecha_reserva solo tiene fecha (sin hora), agregar hora actual
        if obj.fecha_reserva:
            if isinstance(obj.fecha_reserva, date) and not isinstance(obj.fecha_reserva, datetime):
                # Es un objeto date, convertir a datetime con hora actual
                obj.fecha_reserva = timezone.make_aware(
                    datetime.combine(obj.fecha_reserva, timezone.now().time())
                )
            elif isinstance(obj.fecha_reserva, datetime):
                # Es datetime, verificar si es naive y si tiene hora 00:00:00
                if timezone.is_naive(obj.fecha_reserva):
                    # Datetime naive, hacerlo aware con la hora actual si es 00:00:00
                    if obj.fecha_reserva.time() == datetime.min.time():
                        obj.fecha_reserva = timezone.make_aware(
                            datetime.combine(obj.fecha_reserva.date(), timezone.now().time())
                        )
                    else:
                        # Tiene hora específica, solo hacerlo aware
                        obj.fecha_reserva = timezone.make_aware(obj.fecha_reserva)

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

    def generar_resumen_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('ventas:generar_resumen_prepago', args=[obj.id])
        return format_html('<a class="button" href="{}" target="_blank">📋 Resumen</a>', url)
    generar_resumen_link.short_description = 'Resumen'

    def generar_tips_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('ventas:generar_tips_postpago', args=[obj.id])
        return format_html('<a class="button" href="{}" target="_blank">💡 Tips</a>', url)
    generar_tips_link.short_description = 'Tips'

    def generar_cotizacion_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('ventas:generar_cotizacion', args=[obj.id])
        return format_html('<a class="button" href="{}" target="_blank">💰 Cotización</a>', url)
    generar_cotizacion_link.short_description = 'Cotización'

    class Media:
        css = {
            'all': ('admin/css/custom.css',)
        }
        js = ('admin/js/autocomplete_config.js',)

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'es_masajista', 'porcentaje_comision', 'telefono', 'email', 'banco')
    list_filter = ('es_masajista', 'banco')
    search_fields = ('nombre', 'rut', 'email')

    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'direccion', 'telefono', 'email')
        }),
        ('Configuración de Pagos', {
            'fields': ('es_masajista', 'porcentaje_comision', 'rut'),
            'description': 'Configuración para el sistema de pagos a masajistas'
        }),
        ('Datos Bancarios', {
            'fields': ('banco', 'tipo_cuenta', 'numero_cuenta'),
            'classes': ('collapse',),
            'description': 'Información bancaria para transferencias'
        }),
    )

    def get_list_display(self, request):
        """Muestra columnas adicionales solo si hay masajistas"""
        if Proveedor.objects.filter(es_masajista=True).exists():
            return ('nombre', 'es_masajista', 'porcentaje_comision', 'telefono', 'email', 'banco')
        return ('nombre', 'telefono', 'email')

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
    autocomplete_fields = ['cliente_comprador', 'cliente_destinatario', 'venta_reserva']  # FIX: Agregar venta_reserva para evitar N+1
    change_list_template = 'admin/ventas/giftcard/change_list.html'
    list_select_related = ('cliente_comprador', 'cliente_destinatario', 'venta_reserva')  # Optimizar list view

    def get_queryset(self, request):
        """Optimizar queries con select_related para evitar N+1 queries"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 GiftCardAdmin.get_queryset() llamado para path: {request.path}")

        qs = super().get_queryset(request)
        return qs.select_related(
            'cliente_comprador',
            'cliente_destinatario',
            'venta_reserva',
            'venta_reserva__cliente'  # Pre-cargar también el cliente de la venta
        )

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override para agregar logging y diagnosticar lentitud"""
        import logging
        import time
        logger = logging.getLogger(__name__)

        inicio = time.time()
        logger.info(f"⏱️  Iniciando change_view para GiftCard ID={object_id}")

        try:
            response = super().change_view(request, object_id, form_url, extra_context)
            elapsed = time.time() - inicio
            logger.info(f"✅ change_view completado en {elapsed:.2f}s para GiftCard ID={object_id}")
            return response
        except Exception as e:
            elapsed = time.time() - inicio
            logger.error(f"❌ Error en change_view después de {elapsed:.2f}s para GiftCard ID={object_id}: {e}")
            raise

    def changelist_view(self, request, extra_context=None):
        """Agregar botón de diagnóstico en la vista de listado"""
        extra_context = extra_context or {}
        extra_context['diagnostico_url'] = '/ventas/diagnostico/giftcards/'
        return super().changelist_view(request, extra_context=extra_context)

class CategoriaProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)  # Añadir search_fields

class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio_base', 'publicado_web', 'orden', 'cantidad_disponible', 'vista_previa_imagen')
    search_fields = ('nombre', 'categoria__nombre', 'descripcion_web')
    list_filter = ('publicado_web', 'categoria', 'proveedor')
    list_editable = ('publicado_web', 'orden')
    autocomplete_fields = ['proveedor', 'categoria']
    ordering = ('orden', 'nombre')

    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'categoria', 'proveedor', 'precio_base', 'cantidad_disponible')
        }),
        ('Publicación Web', {
            'fields': ('publicado_web', 'descripcion_web', 'imagen', 'orden'),
            'description': 'Configuración para mostrar el producto en el catálogo web público. '
                          'Los clientes verán estos productos y podrán consultar por WhatsApp.'
        }),
    )

    def vista_previa_imagen(self, obj):
        """Mostrar miniatura de la imagen en el listado"""
        from django.utils.html import format_html
        if obj.imagen:
            try:
                return format_html(
                    '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 4px;" />',
                    obj.imagen.url
                )
            except:
                return format_html('<span style="color: #999;">Error al cargar</span>')
        return format_html('<span style="color: #999;">Sin imagen</span>')
    vista_previa_imagen.short_description = 'Imagen' 

class ClienteAdmin(admin.ModelAdmin):
    search_fields = ('nombre', 'telefono', 'email')
    list_display = ('nombre', 'telefono', 'email')
    actions = ['exportar_a_excel']

    def get_search_results(self, request, queryset, search_term):
        """
        Optimiza búsqueda de clientes limitando resultados para autocomplete.
        Reduce payload y mejora rendimiento.
        """
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )
        # Limitar resultados a 50 para autocomplete
        if 'autocomplete' in request.path:
            queryset = queryset[:50]
        return queryset, use_distinct

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
    list_display = ('nombre', 'precio_base', 'duracion', 'categoria', 'publicado_web', 'permite_reserva_web', 'visible_en_matriz')
    list_filter = ('categoria', 'tipo_servicio', 'activo', 'publicado_web', 'permite_reserva_web', 'visible_en_matriz')
    list_editable = ('publicado_web', 'permite_reserva_web', 'visible_en_matriz')
    search_fields = ('nombre', 'descripcion_web')
    filter_horizontal = ('proveedores',)  # Para manejar ManyToMany de proveedores
    readonly_fields = ('imagen_preview',)

    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'categoria', 'tipo_servicio', 'precio_base', 'duracion')
        }),
        ('Configuración de Capacidad', {
            'fields': ('capacidad_minima', 'capacidad_maxima')
        }),
        ('Horarios', {
            'fields': ('horario_apertura', 'horario_cierre', 'slots_disponibles')
        }),
        ('Proveedores', {
            'fields': ('proveedores',)
        }),
        ('Visibilidad', {
            'fields': ('activo', 'publicado_web', 'permite_reserva_web', 'visible_en_matriz'),
            'description': 'Control de visibilidad del servicio en diferentes partes del sistema. Si permite_reserva_web está desmarcado, se mostrará opción de WhatsApp.'
        }),
        ('Información Web', {
            'fields': ('imagen_preview', 'imagen', 'descripcion_web'),
            'description': 'Contenido e imágenes para la página web pública'
        })
    )

    def imagen_preview(self, obj):
        """Vista previa de la imagen del servicio"""
        if not obj or not obj.imagen:
            return format_html('<p style="color: #999;">No hay imagen cargada</p>')
        try:
            return format_html(
                '<div style="margin-top: 10px;">'
                '<img src="{}" style="max-width: 600px; max-height: 400px; object-fit: contain; border: 1px solid #ddd; border-radius: 4px; padding: 5px;" />'
                '<p style="color: #666; font-size: 12px; margin-top: 5px;">URL: {}</p>'
                '</div>',
                obj.imagen.url,
                obj.imagen.url
            )
        except Exception:
            return format_html('<p style="color: #999;">No se puede generar vista previa</p>')
    imagen_preview.short_description = 'Vista previa actual'

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
@admin.register(CategoriaServicio)
class CategoriaServicioAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'imagen_preview')
    list_display_links = ('id', 'nombre')
    search_fields = ('nombre',)
    fields = ('nombre', 'horarios', 'imagen', 'imagen_preview_large')
    readonly_fields = ('imagen_preview_large',)

    def imagen_preview(self, obj):
        """Vista previa pequeña de la imagen en la lista"""
        if not obj or not obj.imagen:
            return '-'
        try:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 100px; object-fit: cover; border-radius: 4px;" />',
                obj.imagen.url
            )
        except Exception:
            return '-'
    imagen_preview.short_description = 'Vista previa'

    def imagen_preview_large(self, obj):
        """Vista previa grande de la imagen en el formulario de edición"""
        if not obj or not obj.imagen:
            return format_html('<p style="color: #999;">No hay imagen cargada</p>')
        try:
            return format_html(
                '<div style="margin-top: 10px;">'
                '<img src="{}" style="max-width: 600px; max-height: 400px; object-fit: contain; border: 1px solid #ddd; border-radius: 4px; padding: 5px;" />'
                '<p style="color: #666; font-size: 12px; margin-top: 5px;">URL: {}</p>'
                '</div>',
                obj.imagen.url,
                obj.imagen.url
            )
        except Exception:
            return format_html('<p style="color: #999;">No se puede generar vista previa</p>')
    imagen_preview_large.short_description = 'Vista previa actual'


# ============================================
# SEO CONTENT ADMIN
# ============================================
@admin.register(SEOContent)
class SEOContentAdmin(admin.ModelAdmin):
    list_display = ('categoria', 'meta_title', 'imagen_categoria_preview', 'updated_at')
    list_filter = ('categoria', 'updated_at')
    search_fields = ('meta_title', 'meta_description', 'contenido_principal', 'keywords')
    readonly_fields = ('categoria_imagen_info',)

    def imagen_categoria_preview(self, obj):
        """Vista previa de la imagen de la categoría en la lista"""
        if not obj or not obj.categoria or not obj.categoria.imagen:
            return '-'
        try:
            return format_html(
                '<img src="{}" style="max-height: 40px; max-width: 80px; object-fit: cover; border-radius: 4px;" />',
                obj.categoria.imagen.url
            )
        except Exception:
            return '-'
    imagen_categoria_preview.short_description = 'Imagen Hero'

    def categoria_imagen_info(self, obj):
        """Muestra información y vista previa de la imagen hero de la categoría"""
        if not obj or not obj.categoria:
            return format_html('<p style="color: #999;">Selecciona una categoría primero</p>')

        categoria = obj.categoria

        if categoria.imagen:
            try:
                return format_html(
                    '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6;">'
                    '<h3 style="margin-top: 0; color: #495057;">Imagen Hero Actual</h3>'
                    '<img src="{}" style="max-width: 100%; max-height: 300px; object-fit: contain; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 10px;" />'
                    '<p style="color: #6c757d; font-size: 13px; margin: 5px 0;"><strong>URL:</strong> {}</p>'
                    '<p style="color: #6c757d; font-size: 13px; margin: 5px 0;"><strong>Path:</strong> {}</p>'
                    '<a href="/admin/ventas/categoriaservicio/{}/change/" target="_blank" '
                    'style="display: inline-block; margin-top: 10px; padding: 8px 16px; background: #007bff; color: white; '
                    'text-decoration: none; border-radius: 4px; font-size: 13px;">'
                    '📝 Cambiar imagen de la categoría'
                    '</a>'
                    '</div>',
                    categoria.imagen.url,
                    categoria.imagen.url,
                    categoria.imagen.name,
                    categoria.id
                )
            except Exception:
                return format_html(
                    '<div style="background: #fff3cd; padding: 15px; border-radius: 8px; border: 1px solid #ffc107;">'
                    '<p style="color: #856404; margin: 0;">⚠️ Hay una imagen configurada pero no se puede cargar</p>'
                    '<a href="/admin/ventas/categoriaservicio/{}/change/" target="_blank" '
                    'style="display: inline-block; margin-top: 10px; padding: 8px 16px; background: #007bff; color: white; '
                    'text-decoration: none; border-radius: 4px; font-size: 13px;">'
                    '📝 Revisar imagen de la categoría'
                    '</a>'
                    '</div>',
                    categoria.id
                )
        else:
            return format_html(
                '<div style="background: #f8d7da; padding: 15px; border-radius: 8px; border: 1px solid #f5c6cb;">'
                '<p style="color: #721c24; margin: 0;">❌ Esta categoría no tiene imagen hero configurada</p>'
                '<a href="/admin/ventas/categoriaservicio/{}/change/" target="_blank" '
                'style="display: inline-block; margin-top: 10px; padding: 8px 16px; background: #28a745; color: white; '
                'text-decoration: none; border-radius: 4px; font-size: 13px;">'
                '➕ Agregar imagen a la categoría'
                '</a>'
                '</div>',
                categoria.id
            )
    categoria_imagen_info.short_description = 'Imagen Hero de la Categoría'

    fieldsets = (
        ('Categoría', {
            'fields': ('categoria', 'categoria_imagen_info'),
            'description': 'Selecciona la categoría y gestiona su imagen hero'
        }),
        ('Meta Tags SEO', {
            'fields': ('meta_title', 'meta_description', 'keywords'),
            'description': 'Optimización para motores de búsqueda'
        }),
        ('Contenido Principal', {
            'fields': ('subtitulo_principal', 'contenido_principal'),
            'description': 'Texto principal que aparecerá en la página (180-300 palabras recomendadas)'
        }),
        ('Beneficios/Características', {
            'fields': (
                ('beneficio_1_titulo', 'beneficio_1_descripcion'),
                ('beneficio_2_titulo', 'beneficio_2_descripcion'),
                ('beneficio_3_titulo', 'beneficio_3_descripcion'),
            ),
            'description': 'Destaca los principales beneficios del servicio'
        }),
        ('Preguntas Frecuentes', {
            'fields': (
                ('faq_1_pregunta', 'faq_1_respuesta'),
                ('faq_2_pregunta', 'faq_2_respuesta'),
                ('faq_3_pregunta', 'faq_3_respuesta'),
                ('faq_4_pregunta', 'faq_4_respuesta'),
                ('faq_5_pregunta', 'faq_5_respuesta'),
                ('faq_6_pregunta', 'faq_6_respuesta'),
            ),
            'description': 'Agrega entre 4-6 preguntas frecuentes para mejorar el SEO'
        }),
    )

    def save_model(self, request, obj, form, change):
        """Override to add validation for word count in contenido_principal"""
        word_count = len(obj.contenido_principal.split())
        if word_count < 180 or word_count > 300:
            messages.warning(
                request,
                f'El contenido principal tiene {word_count} palabras. '
                f'Se recomienda entre 180-300 palabras para mejor SEO.'
            )
        super().save_model(request, obj, form, change)


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


@admin.register(CotizacionEmpresa)
class CotizacionEmpresaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'nombre_empresa',
        'nombre_contacto',
        'get_servicio_display',
        'numero_personas',
        'fecha_tentativa',
        'get_estado_badge',
        'get_urgencia_badge',
        'creado'
    )
    list_filter = (
        'estado',
        'servicio_interes',
        'creado',
        'fecha_tentativa',
        'atendido_por'
    )
    search_fields = (
        'nombre_empresa',
        'nombre_contacto',
        'email',
        'telefono',
        'mensaje_adicional',
        'notas_internas'
    )
    date_hierarchy = 'creado'
    readonly_fields = ('creado', 'actualizado', 'get_dias_desde_solicitud')
    autocomplete_fields = ['atendido_por']

    fieldsets = (
        ('📋 Información de la Empresa', {
            'fields': ('nombre_empresa', 'nombre_contacto', 'email', 'telefono')
        }),
        ('🎯 Detalles del Servicio Solicitado', {
            'fields': ('servicio_interes', 'numero_personas', 'fecha_tentativa', 'mensaje_adicional')
        }),
        ('📊 Estado y Seguimiento', {
            'fields': ('estado', 'atendido_por', 'notas_internas')
        }),
        ('🕐 Información de Tiempo', {
            'fields': ('creado', 'actualizado', 'get_dias_desde_solicitud'),
            'classes': ('collapse',)
        })
    )

    actions = ['marcar_contactado', 'marcar_cotizado', 'marcar_pendiente']

    def get_servicio_display(self, obj):
        """Muestra el servicio de forma más legible"""
        return obj.get_servicio_interes_display()
    get_servicio_display.short_description = 'Servicio'
    get_servicio_display.admin_order_field = 'servicio_interes'

    def get_estado_badge(self, obj):
        """Muestra el estado con un badge colorido"""
        colores = {
            'pendiente': '#ffc107',
            'contactado': '#17a2b8',
            'cotizado': '#007bff',
            'convertido': '#28a745',
            'rechazado': '#dc3545',
        }
        color = colores.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display()
        )
    get_estado_badge.short_description = 'Estado'
    get_estado_badge.admin_order_field = 'estado'

    def get_urgencia_badge(self, obj):
        """Muestra si la cotización es urgente"""
        if obj.es_urgente():
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 11px; font-weight: bold;">🚨 URGENTE</span>'
            )
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">✓ Al día</span>'
        )
    get_urgencia_badge.short_description = 'Urgencia'

    def get_dias_desde_solicitud(self, obj):
        """Muestra cuántos días han pasado desde la solicitud"""
        dias = obj.dias_desde_solicitud()
        if dias == 0:
            return 'Hoy'
        elif dias == 1:
            return '1 día'
        else:
            return f'{dias} días'
    get_dias_desde_solicitud.short_description = 'Tiempo desde solicitud'

    def get_queryset(self, request):
        """Optimiza las consultas"""
        qs = super().get_queryset(request)
        return qs.select_related('atendido_por')

    # Acciones personalizadas
    def marcar_contactado(self, request, queryset):
        """Marca las cotizaciones seleccionadas como contactadas"""
        updated = queryset.update(estado='contactado')
        self.message_user(
            request,
            f'{updated} cotización(es) marcada(s) como contactadas.',
            messages.SUCCESS
        )
    marcar_contactado.short_description = '✓ Marcar como contactado'

    def marcar_cotizado(self, request, queryset):
        """Marca las cotizaciones seleccionadas como cotizadas"""
        updated = queryset.update(estado='cotizado')
        self.message_user(
            request,
            f'{updated} cotización(es) marcada(s) como cotizadas.',
            messages.SUCCESS
        )
    marcar_cotizado.short_description = '💰 Marcar como cotizado'

    def marcar_pendiente(self, request, queryset):
        """Marca las cotizaciones seleccionadas como pendientes"""
        updated = queryset.update(estado='pendiente')
        self.message_user(
            request,
            f'{updated} cotización(es) marcada(s) como pendientes.',
            messages.WARNING
        )
    marcar_pendiente.short_description = '⏸ Marcar como pendiente'


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = (
        'email',
        'get_full_name',
        'is_active',
        'source',
        'subscribed_at',
        'email_open_count',
        'email_click_count',
        'last_email_sent'
    )
    list_filter = ('is_active', 'source', 'subscribed_at')
    search_fields = ('email', 'first_name', 'last_name', 'notes')
    date_hierarchy = 'subscribed_at'
    readonly_fields = ('subscribed_at', 'email_open_count', 'email_click_count', 'last_email_sent')
    
    fieldsets = (
        ('📧 Información del Suscriptor', {
            'fields': ('email', 'first_name', 'last_name', 'is_active')
        }),
        ('📊 Origen y Seguimiento', {
            'fields': ('source', 'subscribed_at', 'notes')
        }),
        ('📈 Estadísticas de Engagement', {
            'fields': ('last_email_sent', 'email_open_count', 'email_click_count'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activar_suscriptores', 'desactivar_suscriptores', 'exportar_emails']
    
    def get_full_name(self, obj):
        """Muestra el nombre completo si está disponible"""
        name = obj.get_full_name()
        if name == obj.email:
            return '-'
        return name
    get_full_name.short_description = 'Nombre'
    
    def activar_suscriptores(self, request, queryset):
        """Activa los suscriptores seleccionados"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{updated} suscriptor(es) activado(s).',
            messages.SUCCESS
        )
    activar_suscriptores.short_description = '✓ Activar suscriptores'
    
    def desactivar_suscriptores(self, request, queryset):
        """Desactiva los suscriptores seleccionados"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated} suscriptor(es) desactivado(s).',
            messages.WARNING
        )
    desactivar_suscriptores.short_description = '✗ Desactivar suscriptores'
    
    def exportar_emails(self, request, queryset):
        """Exporta los emails de los suscriptores seleccionados"""
        emails = list(queryset.filter(is_active=True).values_list('email', flat=True))
        emails_str = ', '.join(emails)
        
        self.message_user(
            request,
            f'Emails activos ({len(emails)}): {emails_str}',
            messages.INFO
        )
    exportar_emails.short_description = '📋 Copiar emails activos'


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

    change_list_template = 'admin/ventas/emailcampaign/change_list.html'

    list_display = (
        'name',
        'status',
        'progreso_visual',
        'total_recipients',
        'emails_sent',
        'ver_preview',
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

    actions = ['reanudar_campanas_seleccionadas']

    def progreso_visual(self, obj):
        """Muestra una barra de progreso visual con los números"""
        from django.utils.html import format_html

        if obj.total_recipients == 0:
            porcentaje = 0
        else:
            porcentaje = int((obj.emails_sent / obj.total_recipients) * 100)

        # Color basado en el estado
        if obj.status == 'completed':
            color = '#28a745'  # Verde
        elif obj.status == 'sending':
            color = '#17a2b8'  # Azul
        elif obj.status == 'paused':
            color = '#ffc107'  # Amarillo
        else:
            color = '#6c757d'  # Gris

        return format_html(
            '<div style="width:150px">'
            '<div style="background-color:#e9ecef; border-radius:3px; height:20px; position:relative;">'
            '<div style="background-color:{}; width:{}%; height:100%; border-radius:3px;"></div>'
            '<span style="position:absolute; width:100%; text-align:center; line-height:20px; font-size:11px; font-weight:bold;">'
            '{}/{} ({}%)'
            '</span>'
            '</div>'
            '</div>',
            color, porcentaje, obj.emails_sent, obj.total_recipients, porcentaje
        )

    progreso_visual.short_description = 'Progreso'

    def ver_preview(self, obj):
        """Botón para ver la preview del email"""
        from django.utils.html import format_html
        from django.urls import reverse

        url = reverse('ventas:email_campaign_preview', args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank" style="'
            'display: inline-block; '
            'padding: 5px 12px; '
            'background: #417690; '
            'color: white; '
            'text-decoration: none; '
            'border-radius: 4px; '
            'font-size: 12px; '
            'font-weight: 500; '
            'transition: background 0.3s;'
            '" '
            'onmouseover="this.style.background=\'#205067\'" '
            'onmouseout="this.style.background=\'#417690\'">'
            '👁️ Ver Email'
            '</a>',
            url
        )

    ver_preview.short_description = 'Vista Previa'
    ver_preview.allow_tags = True

    def status(self, obj):
        """Muestra el estado con validación de consistencia"""
        from django.utils.html import format_html

        # Validar consistencia del estado
        if obj.status == 'completed':
            # Una campaña "completada" debe tener TODOS sus emails enviados
            if obj.total_recipients > 0 and obj.emails_sent < obj.total_recipients:
                # INCONSISTENCIA: Marcada como completada pero faltan emails
                return format_html(
                    '<span style="background: #ff4444; color: white; padding: 3px 8px; '
                    'border-radius: 3px; font-weight: bold;">'
                    '⚠️ COMPLETADA (ERROR)</span><br>'
                    '<small style="color: #666;">Solo {}/{} enviados</small>',
                    obj.emails_sent, obj.total_recipients
                )

        # Estado normal
        status_colors = {
            'draft': '#6c757d',
            'ready': '#007bff',
            'sending': '#17a2b8',
            'paused': '#ffc107',
            'completed': '#28a745',
            'cancelled': '#dc3545',
        }
        color = status_colors.get(obj.status, '#6c757d')

        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )

    status.short_description = 'Estado'
    status.allow_tags = True

    def reanudar_campanas_seleccionadas(self, request, queryset):
        """
        Acción del admin para reanudar campañas seleccionadas.
        Ejecuta el comando enviar_campana_email en BACKGROUND para cada campaña.
        """
        import subprocess
        import logging

        logger = logging.getLogger(__name__)
        campanas_procesadas = 0

        # Filtrar solo campañas que se pueden reanudar (ready o sending)
        campanas_validas = queryset.filter(status__in=['ready', 'sending'])

        if not campanas_validas.exists():
            self.message_user(
                request,
                "⚠️ Ninguna de las campañas seleccionadas está en estado 'Lista' o 'Enviando'.",
                level='warning'
            )
            return

        for campana in campanas_validas:
            try:
                # Ejecutar comando en BACKGROUND usando subprocess
                # Esto evita bloquear el worker de Gunicorn con time.sleep()
                subprocess.Popen(
                    ['python', 'manage.py', 'enviar_campana_email', f'--campaign-id={campana.id}', '--batch-size=5'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True  # Desacoplar del proceso padre
                )
                campanas_procesadas += 1
                logger.info(f'Campaña {campana.name} (ID: {campana.id}) iniciada en background por {request.user.username}')
            except Exception as e:
                logger.error(f'Error iniciando campaña {campana.name}: {e}')
                self.message_user(
                    request,
                    f'❌ Error al iniciar "{campana.name}": {str(e)}',
                    level='error'
                )

        if campanas_procesadas > 0:
            self.message_user(
                request,
                f'✅ {campanas_procesadas} campaña(s) iniciada(s) en segundo plano. El envío continuará automáticamente.',
                level='success'
            )

    reanudar_campanas_seleccionadas.short_description = "▶️ Reanudar campañas seleccionadas"

    def get_urls(self):
        """Agregar URL personalizada para el botón de reanudar todas"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('reanudar-todas/', self.admin_site.admin_view(self.reanudar_todas_las_campanas), name='emailcampaign_reanudar_todas'),
        ]
        return custom_urls + urls

    def reanudar_todas_las_campanas(self, request):
        """
        Vista personalizada para reanudar TODAS las campañas pendientes.
        Ejecuta el comando con --auto en BACKGROUND para evitar timeout.
        """
        from django.shortcuts import redirect
        from django.contrib import messages
        import subprocess
        import logging

        logger = logging.getLogger(__name__)

        try:
            # Contar campañas que se van a procesar
            from ventas.models import EmailCampaign
            campanas_pendientes = EmailCampaign.objects.filter(status__in=['ready', 'sending'])
            count = campanas_pendientes.count()

            if count == 0:
                messages.warning(request, '⚠️ No hay campañas pendientes para reanudar.')
                return redirect('..')

            # Ejecutar comando en BACKGROUND usando subprocess
            # Esto evita bloquear el worker de Gunicorn
            subprocess.Popen(
                ['python', 'manage.py', 'enviar_campana_email', '--auto'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Desacoplar del proceso padre
            )

            messages.success(
                request,
                f'✅ Proceso iniciado en segundo plano. Se procesarán {count} campaña(s). '
                f'Los emails se enviarán automáticamente respetando los intervalos configurados.'
            )
            logger.info(f'Usuario {request.user.username} inició reanudación de {count} campañas en background')

        except Exception as e:
            logger.error(f'Error ejecutando reanudar_todas_las_campanas: {e}')
            messages.error(request, f'❌ Error al reanudar campañas: {str(e)}')

        return redirect('..')


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


# ============================================
# COMMUNICATION SYSTEM ADMIN
# ============================================

@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    """Admin para logs de comunicación (SMS, Email, etc)"""

    list_display = (
        'id',
        'cliente',
        'communication_type',
        'message_type',
        'status',
        'destination',
        'booking_id',
        'created_at'
    )

    list_filter = (
        'communication_type',
        'message_type',
        'status',
        'created_at'
    )

    search_fields = (
        'cliente__nombre',
        'destination',
        'subject',
        'booking_id'
    )

    readonly_fields = (
        'cliente',
        'campaign',
        'communication_type',
        'message_type',
        'subject',
        'content',
        'destination',
        'external_id',
        'booking_id',
        'cost',
        'status',
        'triggered_by',
        'created_at',
        'sent_at',
        'delivered_at',
        'read_at',
        'replied_at',
        'updated_at'
    )

    fieldsets = (
        ('Información General', {
            'fields': ('cliente', 'campaign', 'booking_id')
        }),
        ('Tipo de Comunicación', {
            'fields': ('communication_type', 'message_type', 'status')
        }),
        ('Contenido', {
            'fields': ('subject', 'content', 'destination')
        }),
        ('Tracking', {
            'fields': (
                'external_id',
                'sent_at',
                'delivered_at',
                'read_at',
                'replied_at'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('cost', 'triggered_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        return False  # Los logs se crean automáticamente

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Solo superusers pueden eliminar


@admin.register(CommunicationLimit)
class CommunicationLimitAdmin(admin.ModelAdmin):
    """Admin para límites de comunicación anti-spam"""

    list_display = (
        'cliente',
        'sms_count_daily',
        'sms_count_monthly',
        'email_count_weekly',
        'email_count_monthly',
        'last_sms_date',
        'last_email_date'
    )

    search_fields = ('cliente__nombre', 'cliente__telefono', 'cliente__email')

    readonly_fields = (
        'cliente',
        'sms_count_daily',
        'sms_count_monthly',
        'email_count_weekly',
        'email_count_monthly',
        'last_sms_date',
        'last_email_date',
        'last_birthday_sms_year',
        'created_at',
        'updated_at'
    )


@admin.register(ClientPreferences)
class ClientPreferencesAdmin(admin.ModelAdmin):
    """Admin para preferencias de comunicación de clientes"""

    list_display = (
        'cliente',
        'accepts_sms',
        'accepts_email',
        'accepts_promotional',
        'accepts_booking_confirmations'
    )

    list_filter = (
        'accepts_sms',
        'accepts_email',
        'accepts_promotional',
        'accepts_booking_confirmations'
    )

    search_fields = ('cliente__nombre', 'cliente__telefono', 'cliente__email')


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    """Admin para templates de SMS"""

    list_display = ('name', 'message_type', 'is_active', 'created_at')
    list_filter = ('message_type', 'is_active')
    search_fields = ('name', 'content')

    fieldsets = (
        ('Información', {
            'fields': ('name', 'message_type', 'is_active')
        }),
        ('Contenido', {
            'fields': ('content',),
            'description': 'Puedes usar variables como {nombre}, {servicio}, {fecha}, {hora}'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'updated_at')


# ============================================
# HOMEPAGE CONFIGURATION ADMIN
# ============================================

@admin.register(HomepageConfig)
class HomepageConfigAdmin(SingletonModelAdmin):
    """Admin para configuración global del Homepage (Singleton)"""
    fieldsets = (
        ('Hero Section', {
            'fields': ('hero_title', 'hero_subtitle', 'hero_cta_text', 'hero_cta_link', 'hero_background_image')
        }),
        ('Sección Filosofía', {
            'fields': ('philosophy_title', 'philosophy_text_1', 'philosophy_text_2', 'philosophy_cta_text', 'philosophy_image')
        }),
        ('Galería de Espacios', {
            'fields': ('gallery_image_1', 'gallery_image_2', 'gallery_image_3')
        }),
        ('CTA Final', {
            'fields': ('cta_title', 'cta_subtitle', 'cta_button_text')
        })
    )

@admin.register(HomepageSettings)
class HomepageSettingsAdmin(SingletonModelAdmin):
    """Admin para configuración moderna del Homepage (Singleton)"""
    fieldsets = (
        ('Hero Section', {
            'fields': ('hero_background_image',)
        }),
    )


# =============================================================================
# VISUAL EMAIL CAMPAIGN SYSTEM
# =============================================================================

from .models import EmailCampaignTemplate, CampaignSendLog

@admin.register(EmailCampaignTemplate)
class EmailCampaignTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'subject',
        'get_status_badge',
        'total_recipients',
        'progress_percent',
        'created_at',
        'created_by'
    )
    list_filter = ('status', 'audience_type', 'created_at')
    search_fields = ('name', 'subject', 'html_content')
    date_hierarchy = 'created_at'
    readonly_fields = (
        'created_at',
        'updated_at',
        'started_at',
        'completed_at',
        'emails_sent',
        'emails_delivered',
        'emails_opened',
        'emails_clicked',
        'emails_bounced',
        'spam_complaints',
        'progress_percent',
        'open_rate',
        'click_rate',
        'bounce_rate'
    )
    
    fieldsets = (
        ('📋 Información Básica', {
            'fields': ('name', 'subject', 'preview_text', 'status')
        }),
        ('📝 Contenido HTML', {
            'fields': ('html_content', 'uses_personalization'),
            'classes': ('collapse',)
        }),
        ('🎯 Audiencia', {
            'fields': ('audience_type', 'segment_filters','total_recipients')
        }),
        ('⚙️ Configuración de Envío', {
            'fields': ('batch_size', 'batch_delay_minutes', 'scheduled_at')
        }),
        ('📊 Estadísticas', {
            'fields': (
                'emails_sent',
                'emails_delivered',
                'emails_opened',
                'emails_clicked',
                'emails_bounced',
                'spam_complaints',
                'progress_percent',
                'open_rate',
                'click_rate',
                'bounce_rate'
            ),
            'classes': ('collapse',)
        }),
        ('🕐 Timestamps', {
            'fields': ('created_at', 'updated_at', 'started_at', 'completed_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['marcar_como_lista', 'pausar_campana', 'cancelar_campana']
    
    def get_status_badge(self, obj):
        """Muestra el estado con un badge colorido"""
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            self._get_status_color(obj.status),
            obj.get_status_display()
        )
    get_status_badge.short_description = 'Estado'
    get_status_badge.admin_order_field = 'status'
    
    def _get_status_color(self, status):
        colors = {
            'draft': '#6c757d',
            'ready': '#17a2b8',
            'sending': '#007bff',
            'paused': '#ffc107',
            'completed': '#28a745',
            'cancelled': '#dc3545',
        }
        return colors.get(status, '#6c757d')
    
    def marcar_como_lista(self, request, queryset):
        """Marca las campañas como listas para envío"""
        updated = queryset.filter(status='draft').update(status='ready')
        self.message_user(
            request,
            f'{updated} campaña(s) marcada(s) como listas.',
            messages.SUCCESS
        )
    marcar_como_lista.short_description = '✓ Marcar como lista para envío'
    
    def pausar_campana(self, request, queryset):
        """Pausa las campañas en envío"""
        updated = queryset.filter(status='sending').update(status='paused')
        self.message_user(
            request,
            f'{updated} campaña(s) pausada(s).',
            messages.WARNING
        )
    pausar_campana.short_description = '⏸ Pausar campañas'
    
    def cancelar_campana(self, request, queryset):
        """Cancela las campañas"""
        updated = queryset.update(status='cancelled')
        self.message_user(
            request,
            f'{updated} campaña(s) cancelada(s).',
            messages.ERROR
        )
    cancelar_campana.short_description = '✗ Cancelar campañas'


@admin.register(CampaignSendLog)
class CampaignSendLogAdmin(admin.ModelAdmin):
    list_display = (
        'campaign',
        'recipient_email',
        'recipient_name',
        'get_status_badge',
        'sent_at',
        'opened_at',
        'clicked_at'
    )
    list_filter = ('status', 'sent_at', 'campaign')
    search_fields = ('recipient_email', 'recipient_name', 'campaign__name')
    date_hierarchy = 'created_at'
    readonly_fields = (
        'campaign',
        'recipient_email',
        'recipient_name',
        'status',
        'sent_at',
        'delivered_at',
        'opened_at',
        'clicked_at',
        'error_message',
        'bounce_reason',
        'created_at'
    )
    
    fieldsets = (
        ('📧 Información del Envío', {
            'fields': ('campaign', 'recipient_email', 'recipient_name', 'status')
        }),
        ('⏱️ Eventos', {
            'fields': ('sent_at', 'delivered_at', 'opened_at', 'clicked_at')
        }),
        ('❌ Errores', {
            'fields': ('error_message', 'bounce_reason'),
            'classes': ('collapse',)
        })
    )
    
    def get_status_badge(self, obj):
        """Muestra el estado con un badge colorido"""
        colors = {
            'pending': '#6c757d',
            'sending': '#17a2b8',
            'sent': '#007bff',
            'delivered': '#28a745',
            'opened': '#20c997',
            'clicked': '#17a2b8',
            'bounced': '#ffc107',
            'failed': '#dc3545',
            'spam': '#dc3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    get_status_badge.short_description = 'Estado'
    get_status_badge.admin_order_field = 'status'
    
    def has_add_permission(self, request):
        """No permitir crear logs manualmente"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar logs (solo lectura)"""
        return False


# Configuración de Resumen de Reserva (Singleton)
@admin.register(ConfiguracionResumen)
class ConfiguracionResumenAdmin(SingletonModelAdmin):
    fieldsets = (
        ('Encabezado', {
            'fields': ('encabezado',)
        }),
        ('Información de Pago', {
            'fields': ('datos_transferencia', 'link_pago_mercadopago', 'texto_link_pago')
        }),
        ('Cortesías y Garantías', {
            'fields': ('tina_yate_texto', 'sauna_no_disponible')
        }),
        ('Políticas de Cancelación', {
            'fields': ('politica_alojamiento', 'politica_tinas_masajes')
        }),
        ('Información para Alojamiento', {
            'fields': ('equipamiento_cabanas', 'cortesias_alojamiento', 'seguridad_pasarela')
        }),
        ('Cortesías Generales', {
            'fields': ('cortesias_generales',)
        }),
        ('Despedida', {
            'fields': ('despedida',)
        }),
    )


@admin.register(ConfiguracionTips)
class ConfiguracionTipsAdmin(SingletonModelAdmin):
    fieldsets = (
        ('Encabezado', {
            'fields': ('encabezado', 'intro')
        }),
        ('WiFi - Cabañas', {
            'fields': ('wifi_torre', 'wifi_tepa', 'wifi_acantilado', 'wifi_laurel', 'wifi_arrayan'),
            'classes': ('collapse',)
        }),
        ('WiFi - Otras Áreas', {
            'fields': ('wifi_tinas', 'wifi_tinajas', 'wifi_masajes'),
            'classes': ('collapse',)
        }),
        ('Normas (Solo Cabañas)', {
            'fields': ('norma_mascotas', 'norma_cocinar', 'norma_fumar', 'norma_danos'),
            'classes': ('collapse',)
        }),
        ('Check-out (Solo Cabañas)', {
            'fields': ('checkout_semana', 'checkout_finde'),
            'classes': ('collapse',)
        }),
        ('Tips Tinas/Masajes', {
            'fields': ('recordatorio_toallas', 'tip_puntualidad', 'info_vestidores', 'ropa_masaje', 'menores_edad'),
            'classes': ('collapse',)
        }),
        ('Uso de Tinas', {
            'fields': ('uso_tinas_alternancia', 'uso_tinas_prohibiciones', 'recomendacion_ducha_masaje', 'prohibicion_vasos'),
            'classes': ('collapse',)
        }),
        ('Seguridad', {
            'fields': ('seguridad_pasarelas',)
        }),
        ('Horarios', {
            'fields': (
                'horario_porton_semana', 'horario_porton_finde', 'telefono_porton',
                'horario_recepcion_semana', 'horario_recepcion_finde', 'horario_recepcion_domingo',
                'horario_cafeteria_semana', 'horario_cafeteria_finde'
            ),
            'classes': ('collapse',)
        }),
        ('Cafetería', {
            'fields': ('productos_cafeteria', 'menu_cafe'),
            'classes': ('collapse',)
        }),
        ('Ubicación', {
            'fields': ('direccion', 'como_llegar', 'link_google_maps')
        }),
        ('Despedida', {
            'fields': ('despedida', 'contacto_whatsapp')
        }),
    )


# === SISTEMA DE PAGOS A MASAJISTAS ===

class DetalleServicioPagoInline(admin.TabularInline):
    """Inline para mostrar los servicios incluidos en un pago"""
    model = DetalleServicioPago
    extra = 0
    readonly_fields = ('reserva_servicio', 'monto_servicio', 'porcentaje_masajista', 'monto_masajista')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PagoMasajista)
class PagoMasajistaAdmin(admin.ModelAdmin):
    """Administración de pagos a masajistas"""
    list_display = (
        'id', 'proveedor', 'fecha_pago', 'periodo_display',
        'monto_bruto_format', 'monto_retencion_format', 'monto_neto_format',
        'estado_comprobante'
    )
    list_filter = ('fecha_pago', 'proveedor', 'periodo_inicio', 'periodo_fin')
    search_fields = ('proveedor__nombre', 'numero_transferencia')
    readonly_fields = (
        'fecha_pago', 'monto_retencion', 'monto_neto',
        'creado_por', 'preview_comprobante'
    )
    inlines = [DetalleServicioPagoInline]
    date_hierarchy = 'fecha_pago'

    fieldsets = (
        ('Información del Pago', {
            'fields': ('proveedor', 'fecha_pago', 'creado_por')
        }),
        ('Periodo', {
            'fields': ('periodo_inicio', 'periodo_fin')
        }),
        ('Montos', {
            'fields': (
                'monto_bruto', 'porcentaje_retencion',
                'monto_retencion', 'monto_neto'
            ),
            'description': 'El monto de retención y neto se calculan automáticamente'
        }),
        ('Comprobante', {
            'fields': (
                'comprobante', 'preview_comprobante',
                'numero_transferencia', 'observaciones'
            )
        }),
    )

    def periodo_display(self, obj):
        """Muestra el periodo del pago"""
        return f"{obj.periodo_inicio.strftime('%d/%m/%Y')} - {obj.periodo_fin.strftime('%d/%m/%Y')}"
    periodo_display.short_description = 'Periodo'

    def monto_bruto_format(self, obj):
        """Formatea el monto bruto"""
        return f"${obj.monto_bruto:,.0f}"
    monto_bruto_format.short_description = 'Monto Bruto'

    def monto_retencion_format(self, obj):
        """Formatea el monto de retención"""
        return f"${obj.monto_retencion:,.0f}"
    monto_retencion_format.short_description = 'Retención (14.5%)'

    def monto_neto_format(self, obj):
        """Formatea el monto neto"""
        return format_html(
            '<strong style="color: green;">${:,.0f}</strong>',
            obj.monto_neto
        )
    monto_neto_format.short_description = 'Monto Neto'

    def estado_comprobante(self, obj):
        """Muestra si tiene comprobante"""
        if obj.comprobante:
            return format_html(
                '<span style="color: green;">✓ Con comprobante</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Sin comprobante</span>'
        )
    estado_comprobante.short_description = 'Comprobante'

    def preview_comprobante(self, obj):
        """Muestra preview del comprobante"""
        if obj.comprobante:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px;" />',
                obj.comprobante.url
            )
        return "Sin comprobante"
    preview_comprobante.short_description = 'Vista Previa del Comprobante'

    def save_model(self, request, obj, form, change):
        """Guarda el usuario que crea el pago"""
        if not change:  # Solo al crear
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Optimiza las consultas"""
        qs = super().get_queryset(request)
        return qs.select_related('proveedor', 'creado_por')

    actions = ['exportar_a_excel']

    def exportar_a_excel(self, request, queryset):
        """Exporta los pagos seleccionados a Excel"""
        import xlwt
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="pagos_masajistas.xls"'

        wb = xlwt.Workbook(encoding='utf-8')
        ws = wb.add_sheet('Pagos')

        # Encabezados
        row_num = 0
        columns = [
            'ID', 'Masajista', 'RUT', 'Fecha Pago',
            'Periodo Inicio', 'Periodo Fin',
            'Monto Bruto', '% Retención', 'Monto Retención',
            'Monto Neto', 'N° Transferencia', 'Banco'
        ]

        for col_num, column_title in enumerate(columns):
            ws.write(row_num, col_num, column_title)

        # Datos
        for pago in queryset:
            row_num += 1
            ws.write(row_num, 0, pago.id)
            ws.write(row_num, 1, pago.proveedor.nombre)
            ws.write(row_num, 2, pago.proveedor.rut or '')
            ws.write(row_num, 3, pago.fecha_pago.strftime('%d/%m/%Y %H:%M'))
            ws.write(row_num, 4, pago.periodo_inicio.strftime('%d/%m/%Y'))
            ws.write(row_num, 5, pago.periodo_fin.strftime('%d/%m/%Y'))
            ws.write(row_num, 6, float(pago.monto_bruto))
            ws.write(row_num, 7, float(pago.porcentaje_retencion))
            ws.write(row_num, 8, float(pago.monto_retencion))
            ws.write(row_num, 9, float(pago.monto_neto))
            ws.write(row_num, 10, pago.numero_transferencia or '')
            ws.write(row_num, 11, pago.proveedor.banco or '')

        wb.save(response)
        return response

    exportar_a_excel.short_description = "Exportar pagos seleccionados a Excel"


# ============================================================================
# ADMIN: Sistema de Bloqueo de Servicios
# ============================================================================

@admin.register(ServicioBloqueo)
class ServicioBloqueoAdmin(admin.ModelAdmin):
    list_display = (
        'servicio',
        'fecha_inicio',
        'fecha_fin',
        'dias_bloqueados',
        'motivo_corto',
        'activo',
        'creado_por',
        'creado_en'
    )
    list_filter = (
        'activo',
        'servicio__categoria',
        'servicio',
        'creado_en'
    )
    search_fields = (
        'servicio__nombre',
        'motivo',
        'notas'
    )
    readonly_fields = (
        'creado_por',
        'creado_en',
        'dias_bloqueados',
        'ver_reservas_conflicto'
    )

    date_hierarchy = 'fecha_inicio'
    ordering = ('-fecha_inicio',)
    actions = ['activar_bloqueos', 'desactivar_bloqueos', 'duplicar_bloqueo']

    def get_fieldsets(self, request, obj=None):
        """Ajusta fieldsets según si es creación (add) o edición (change)"""
        if obj:  # Editando objeto existente
            return (
                ('Información del Bloqueo', {
                    'fields': (
                        'servicio',
                        ('fecha_inicio', 'fecha_fin'),
                        'dias_bloqueados',
                        'motivo',
                        'activo'
                    )
                }),
                ('Detalles', {
                    'fields': ('notas',),
                    'classes': ('collapse',)
                }),
                ('Validación', {
                    'fields': ('ver_reservas_conflicto',),
                    'classes': ('collapse',),
                    'description': 'Verificación de conflictos con reservas existentes'
                }),
                ('Metadatos', {
                    'fields': (
                        'creado_por',
                        'creado_en'
                    ),
                    'classes': ('collapse',)
                })
            )
        else:  # Creando nuevo objeto
            return (
                ('Información del Bloqueo', {
                    'fields': (
                        'servicio',
                        ('fecha_inicio', 'fecha_fin'),
                        'motivo',
                        'activo'
                    ),
                    'description': 'El sistema validará automáticamente que no haya reservas en este rango al guardar.'
                }),
                ('Detalles', {
                    'fields': ('notas',),
                    'classes': ('collapse',)
                })
            )

    # Widgets personalizados
    formfield_overrides = {
        models.DateField: {'widget': DateInput(attrs={'type': 'date'})},
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 3})}
    }

    def save_model(self, request, obj, form, change):
        """Guardar el usuario que crea el bloqueo"""
        if not change:  # Si es nuevo
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    def dias_bloqueados(self, obj):
        """Muestra cantidad de días bloqueados"""
        dias = obj.get_dias_bloqueados()
        if dias == 1:
            return "1 día"
        return f"{dias} días"
    dias_bloqueados.short_description = 'Duración'

    def motivo_corto(self, obj):
        """Muestra el motivo truncado"""
        if len(obj.motivo) > 50:
            return obj.motivo[:50] + '...'
        return obj.motivo
    motivo_corto.short_description = 'Motivo'

    def ver_reservas_conflicto(self, obj):
        """Muestra si hay reservas en el rango de fechas"""
        # Verificar que el objeto existe y tiene los datos necesarios
        if not obj or not obj.pk:
            return "Guarda primero para verificar conflictos"

        if not obj.servicio or not obj.fecha_inicio or not obj.fecha_fin:
            return "Complete los datos del formulario"

        from ventas.models import ReservaServicio
        try:
            reservas = ReservaServicio.objects.filter(
                servicio=obj.servicio,
                fecha_agendamiento__gte=obj.fecha_inicio,
                fecha_agendamiento__lte=obj.fecha_fin
            ).exclude(
                venta_reserva__estado_reserva='cancelada'
            ).select_related('venta_reserva', 'venta_reserva__cliente')

            if not reservas.exists():
                return format_html('<span style="color: green;">✓ Sin conflictos - No hay reservas en este rango</span>')

            # Hay conflictos
            html = '<div style="padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107;">'
            html += f'<strong style="color: #856404;">⚠ {reservas.count()} reservas encontradas:</strong><ul style="margin: 10px 0;">'

            for reserva in reservas[:10]:  # Mostrar máximo 10
                cliente = reserva.venta_reserva.cliente.nombre if reserva.venta_reserva.cliente else 'Sin cliente'
                estado = reserva.venta_reserva.get_estado_pago_display()
                fecha = reserva.fecha_agendamiento.strftime('%d/%m/%Y')
                html += f'<li>{fecha} - {cliente} ({estado})</li>'

            if reservas.count() > 10:
                html += f'<li><em>...y {reservas.count() - 10} reservas más</em></li>'

            html += '</ul></div>'
            return format_html(html)

        except Exception as e:
            return format_html('<span style="color: red;">Error verificando conflictos: {}</span>', str(e))
    ver_reservas_conflicto.short_description = 'Reservas en el Rango'

    # Acciones personalizadas
    def activar_bloqueos(self, request, queryset):
        """Activa bloqueos seleccionados"""
        updated = queryset.update(activo=True)
        self.message_user(request, f'{updated} bloqueo(s) activado(s)')
    activar_bloqueos.short_description = "Activar bloqueos seleccionados"

    def desactivar_bloqueos(self, request, queryset):
        """Desactiva bloqueos seleccionados"""
        updated = queryset.update(activo=False)
        self.message_user(request, f'{updated} bloqueo(s) desactivado(s)')
    desactivar_bloqueos.short_description = "Desactivar bloqueos seleccionados"

    def duplicar_bloqueo(self, request, queryset):
        """Duplica bloqueos seleccionados para facilitar crear bloqu eos similares"""
        duplicados = 0
        for bloqueo in queryset:
            bloqueo.pk = None
            bloqueo.creado_por = request.user
            bloqueo.creado_en = timezone.now()
            # Adelantar las fechas 7 días para el duplicado
            bloqueo.fecha_inicio = bloqueo.fecha_inicio + timedelta(days=7)
            bloqueo.fecha_fin = bloqueo.fecha_fin + timedelta(days=7)
            try:
                bloqueo.save()
                duplicados += 1
            except Exception as e:
                self.message_user(request, f'Error duplicando bloqueo: {e}', level=messages.ERROR)

        if duplicados:
            self.message_user(request, f'{duplicados} bloqueo(s) duplicado(s) (fechas adelantadas 7 días)')
    duplicar_bloqueo.short_description = "Duplicar bloqueos seleccionados (+7 días)"

    class Media:
        css = {
            'all': ('admin/css/forms.css',)
        }
        js = (
            'admin/js/vendor/jquery/jquery.min.js',
            'admin/js/jquery.init.js',
        )


# ============================================================================
# ADMIN: Sistema de Bloqueo de Slots Específicos
# ============================================================================

class ServicioSlotBloqueoForm(forms.ModelForm):
    """Formulario personalizado para ServicioSlotBloqueo"""
    class Meta:
        model = ServicioSlotBloqueo
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar servicios: solo activos, ordenados alfabéticamente
        self.fields['servicio'].queryset = Servicio.objects.filter(
            activo=True
        ).order_by('nombre')


@admin.register(ServicioSlotBloqueo)
class ServicioSlotBloqueoAdmin(admin.ModelAdmin):
    form = ServicioSlotBloqueoForm
    list_display = ('servicio', 'fecha', 'hora_slot', 'motivo', 'activo')
    list_filter = ('activo', 'fecha')
    fields = ('servicio', 'fecha', 'hora_slot', 'motivo', 'activo', 'notas')

    def save_model(self, request, obj, form, change):
        """Guardar el usuario que crea el bloqueo"""
        if not change:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)


# ============================================
# ADMIN PARA GESTIÓN DE MASAJISTAS
# ============================================

@admin.register(MasajistaEspecialidad)
class MasajistaEspecialidadAdmin(admin.ModelAdmin):
    list_display = ('masajista', 'servicio', 'nivel_experiencia', 'activo')
    list_filter = ('activo', 'nivel_experiencia', 'masajista')
    search_fields = ('masajista__nombre', 'servicio__nombre')
    ordering = ('masajista__nombre', 'servicio__nombre')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "masajista":
            kwargs["queryset"] = Proveedor.objects.filter(es_masajista=True).order_by('nombre')
        elif db_field.name == "servicio":
            kwargs["queryset"] = Servicio.objects.filter(tipo_servicio='masaje').order_by('nombre')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(HorarioMasajista)
class HorarioMasajistaAdmin(admin.ModelAdmin):
    list_display = ('masajista', 'dia_semana', 'hora_inicio', 'hora_fin', 'disponible')
    list_filter = ('disponible', 'dia_semana', 'masajista')
    search_fields = ('masajista__nombre',)
    ordering = ('masajista__nombre', 'dia_semana')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "masajista":
            kwargs["queryset"] = Proveedor.objects.filter(es_masajista=True).order_by('nombre')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class HorarioMasajistaInline(admin.TabularInline):
    model = HorarioMasajista
    extra = 0
    fields = ('dia_semana', 'hora_inicio', 'hora_fin', 'disponible')
    ordering = ('dia_semana',)


class MasajistaEspecialidadInline(admin.TabularInline):
    model = MasajistaEspecialidad
    extra = 0
    fields = ('servicio', 'nivel_experiencia', 'activo')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "servicio":
            kwargs["queryset"] = Servicio.objects.filter(tipo_servicio='masaje').order_by('nombre')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(SalaServicio)
class SalaServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'numero_camillas', 'permite_grupos_mixtos', 'activa')
    list_filter = ('activa', 'permite_grupos_mixtos')
    search_fields = ('nombre', 'descripcion')
    ordering = ('nombre',)
    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'numero_camillas', 'activa')
        }),
        ('Configuración', {
            'fields': ('permite_grupos_mixtos', 'descripcion')
        }),
    )

