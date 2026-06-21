import json
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from ..models import Servicio, CategoriaServicio, HomepageConfig, Lead, Producto, CategoriaProducto # Relative import, ADD HomepageConfig, Lead, Producto, CategoriaProducto


def homepage_view(request):
    """
    Vista que renderiza la página de inicio pública de Aremko.cl
    Muestra los servicios disponibles y permite realizar reservas.
    """
    # Obtener servicios activos Y publicados en la web
    servicios = Servicio.objects.filter(activo=True, publicado_web=True).select_related('categoria')
    categorias = CategoriaServicio.objects.all()

    # Obtener carrito de compras de la sesión o crear uno nuevo
    cart = request.session.get('cart', {'servicios': [], 'total': 0})

    # --- Fetch Homepage Config ---
    hero_image_url = None
    philosophy_image_url = None # Add variable for philosophy image
    gallery_image_1_url = None  # Add variable for gallery image 1
    gallery_image_2_url = None  # Add variable for gallery image 2
    gallery_image_3_url = None  # Add variable for gallery image 3

    # Default texts (fallback)
    hero_title = "Desconecta y Renueva Tus Sentidos en Aremko Spa"
    hero_subtitle = "Sumérgete en un oasis de tranquilidad en Puerto Varas. Descubre experiencias únicas de masajes, tinas calientes y alojamiento diseñadas para tu bienestar total."
    hero_cta_text = "Descubre Tu Experiencia Ideal"
    hero_cta_link = "#servicios"

    philosophy_title = "Vive la Experiencia Aremko"
    philosophy_text_1 = "Más que un spa, somos un refugio para el alma. En Aremko, creemos en el poder sanador de la naturaleza y la desconexión. Nuestra filosofía se centra en ofrecerte un espacio de paz donde puedas renovar tu energía, cuidar tu cuerpo y calmar tu mente."
    philosophy_text_2 = "Desde masajes terapéuticos hasta la inmersión en nuestras tinajas calientes bajo las estrellas, cada detalle está pensado para tu máximo bienestar. Ven y descubre por qué nuestros visitantes nos eligen como su escape perfecto en Puerto Varas."
    philosophy_cta_text = "Explora Nuestros Servicios"

    cta_title = "¿Listo para Vivir la Experiencia Aremko?"
    cta_subtitle = "Regálate el descanso que mereces. Elige tu masaje ideal, sumérgete en nuestras tinajas o planifica tu estancia completa. ¡Tu momento de paz te espera!"
    cta_button_text = "Reservar Mi Experiencia Ahora"


    try:
        # HomepageConfig is a singleton, get the instance
        config = HomepageConfig.get_solo()
        # Get hero image URL
        if config.hero_background_image:
            hero_image_url = config.hero_background_image.url
        # Get philosophy image URL
        if config.philosophy_image:
            philosophy_image_url = config.philosophy_image.url
        # Get gallery image URLs
        if config.gallery_image_1:
            gallery_image_1_url = config.gallery_image_1.url
        if config.gallery_image_2:
            gallery_image_2_url = config.gallery_image_2.url
        if config.gallery_image_3:
            gallery_image_3_url = config.gallery_image_3.url
        
        # Get texts
        hero_title = config.hero_title
        hero_subtitle = config.hero_subtitle
        hero_cta_text = config.hero_cta_text
        hero_cta_link = config.hero_cta_link
        
        philosophy_title = config.philosophy_title
        philosophy_text_1 = config.philosophy_text_1
        philosophy_text_2 = config.philosophy_text_2
        philosophy_cta_text = config.philosophy_cta_text
        
        cta_title = config.cta_title
        cta_subtitle = config.cta_subtitle
        cta_button_text = config.cta_button_text

    except HomepageConfig.DoesNotExist:
        # Handle case where the config hasn't been created yet
        pass
    # --- End Fetch Homepage Config ---

    # Canonical URL for SEO (build safely)
    try:
        canonical_url = request.build_absolute_uri(request.path)
    except Exception:
        canonical_url = request.path

    # --- JSON-LD de Productos/Offers por servicio (SEO: precio en resultados) ---
    # Se construye con json.dumps para garantizar escape correcto (comillas,
    # saltos de línea en descripciones). Solo servicios publicados con precio > 0.
    try:
        base_url = request.build_absolute_uri('/').rstrip('/')
    except Exception:
        base_url = ''
    producto_items = []
    posicion = 0
    for s in servicios:
        precio = int(s.precio_base) if s.precio_base else 0
        if precio <= 0:
            continue  # omite cortesía/gratis (ej. tina Yates)
        posicion += 1
        descripcion = (s.descripcion_web or f"{s.nombre} en Aremko Spa Boutique, Puerto Varas.").strip()
        if len(descripcion) > 300:
            descripcion = descripcion[:297] + "..."
        producto = {
            "@type": "Product",
            "name": s.nombre,
            "description": descripcion,
            "brand": {"@type": "Brand", "name": "Aremko Spa"},
            "offers": {
                "@type": "Offer",
                "price": str(precio),
                "priceCurrency": "CLP",
                "availability": "https://schema.org/InStock",
                "url": f"{base_url}/#servicios",
            },
        }
        try:
            if s.imagen:
                producto["image"] = request.build_absolute_uri(s.imagen.url)
        except Exception:
            pass
        producto_items.append({"@type": "ListItem", "position": posicion, "item": producto})

    productos_jsonld = ""
    if producto_items:
        productos_jsonld = json.dumps({
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": "Servicios de Aremko Spa Puerto Varas",
            "itemListElement": producto_items,
        }, ensure_ascii=False).replace("<", "\\u003c")  # evita romper el </script>

    context = {
        'servicios': servicios,
        'productos_jsonld': productos_jsonld,
        'categorias': categorias,
        'cart': cart,
        'hero_image_url': hero_image_url,
        'philosophy_image_url': philosophy_image_url, # Add philosophy URL to context
        'gallery_image_1_url': gallery_image_1_url,   # Add gallery 1 URL to context
        'gallery_image_2_url': gallery_image_2_url,   # Add gallery 2 URL to context
        'gallery_image_3_url': gallery_image_3_url,   # Add gallery 3 URL to context
        
        # Text Context
        'hero_title': hero_title,
        'hero_subtitle': hero_subtitle,
        'hero_cta_text': hero_cta_text,
        'hero_cta_link': hero_cta_link,
        'philosophy_title': philosophy_title,
        'philosophy_text_1': philosophy_text_1,
        'philosophy_text_2': philosophy_text_2,
        'philosophy_cta_text': philosophy_cta_text,
        'cta_title': cta_title,
        'cta_subtitle': cta_subtitle,
        'cta_button_text': cta_button_text,
        'canonical_url': canonical_url,
    }
    return render(request, 'ventas/homepage.html', context)


def categoria_detail_view(request, categoria_id):
    """
    Vista que muestra los servicios de una categoría específica.
    """
    categoria = get_object_or_404(CategoriaServicio, id=categoria_id)
    # Filter by category, active, AND published
    servicios = Servicio.objects.filter(categoria=categoria, activo=True, publicado_web=True)
    categorias = CategoriaServicio.objects.all() # For potential navigation/filtering

    # Build canonical URL safely
    try:
        canonical_url = request.build_absolute_uri(request.path)
    except Exception:
        canonical_url = request.path

    # Get category hero image safely (handle missing files in cloud storage)
    category_hero_image = None
    try:
        if categoria.imagen:
            category_hero_image = categoria.imagen.url
    except Exception:
        # File exists in DB but not in cloud storage - gracefully handle
        pass

    # Get SEO content if available (optional - handles case when migration hasn't run)
    seo_content = None
    try:
        if hasattr(categoria, 'seo_content'):
            seo_content = categoria.seo_content
    except Exception:
        pass

    # Decoraciones (Ambientaciones) como complemento visible SOLO en la vista de Tinas.
    # Se ofrecen como cross-sell: el cliente agrega una decoración a su reserva de tina
    # y el staff coordina la hora con la de la tina.
    decoraciones = None
    if categoria.nombre.lower() == 'tinas':
        decoraciones = Servicio.objects.filter(
            categoria__nombre__iexact='Ambientaciones',
            activo=True,
            publicado_web=True,
        ).order_by('precio_base', 'nombre')

    context = {
        'categoria_actual': categoria,
        'servicios': servicios,
        'categorias': categorias,
        'cart': request.session.get('cart', {'servicios': [], 'total': 0}), # Include cart context
        'canonical_url': canonical_url,
        'category_hero_image': category_hero_image,
        'seo_content': seo_content,  # Pass SEO content to template
        'decoraciones': decoraciones,
    }
    return render(request, 'ventas/category_detail.html', context)


def tinas_view(request):
    """
    Vista para acceso directo a la categoría de Tinas Calientes
    Redirige a la vista de categoría con ID=1 (Tinas)
    """
    return categoria_detail_view(request, categoria_id=1)


def masajes_view(request):
    """
    Vista para acceso directo a la categoría de Masajes
    Redirige a la vista de categoría con ID=2 (Masajes)
    """
    return categoria_detail_view(request, categoria_id=2)


def alojamientos_view(request):
    """
    Vista para acceso directo a la categoría de Alojamientos
    Redirige a la vista de categoría con ID=3 (Alojamientos)
    """
    return categoria_detail_view(request, categoria_id=3)


def productos_view(request):
    """
    Vista para mostrar el catálogo de productos publicados en la web.
    Los productos se muestran solo como catálogo, no son agregables al carrito.
    Los clientes contactan vía WhatsApp para comprar.
    """
    # Obtener solo productos publicados en web, ordenados
    productos = Producto.objects.filter(
        publicado_web=True
    ).select_related('categoria').order_by('orden', 'nombre')

    # Agrupar por categoría para mejor organización visual
    categorias = CategoriaProducto.objects.filter(
        producto__publicado_web=True
    ).distinct().order_by('nombre')

    # Build canonical URL safely
    try:
        canonical_url = request.build_absolute_uri(request.path)
    except Exception:
        canonical_url = request.path

    # WhatsApp business number - CAMBIAR AL NÚMERO REAL DE AREMKO
    whatsapp_number = "56957902525"  # WhatsApp oficial Aremko

    context = {
        'productos': productos,
        'categorias': categorias,
        'canonical_url': canonical_url,
        'whatsapp_number': whatsapp_number,
        'cart': request.session.get('cart', {'servicios': [], 'giftcards': [], 'total': 0}),
    }
    return render(request, 'ventas/productos.html', context)


def empresas_view(request):
    """
    Vista para la landing page de servicios empresariales
    """
    context = {
        'page_title': 'Reuniones con Resultados: Productividad + Bienestar',
        'meta_description': 'Espacios únicos para reuniones empresariales en Puerto Varas. Sala de reuniones, desayuno sureño y tinas calientes para tu equipo.',
    }
    return render(request, 'ventas/empresas.html', context)


def empresas_presentacion_view(request):
    """
    Presentación del Convenio Empresarial Aremko en formato visual tipo presentación.
    Página independiente para compartir con clientes corporativos.
    """
    context = {
        'page_title': 'Convenio Empresarial - Aremko Spa Boutique',
        'meta_description': 'Convenio empresarial Aremko Spa Boutique. Descuentos permanentes en cabañas, tinas calientes y masajes junto al Río Pescado, Puerto Varas.',
    }
    return render(request, 'ventas/empresas_presentacion.html', context)

def privacy_policy_view(request):
    """
    Vista para la página de Política de Privacidad.
    Requerida para cumplimiento con proveedores de email marketing (SendGrid).
    """
    return render(request, 'ventas/privacy_policy.html')


def encuesta_satisfaccion_view(request):
    """
    Formulario de encuesta de satisfacción post-visita.

    Reemplaza el Google Form histórico con captura nativa a BD para
    análisis IA semanal (Tarea 1.4 plan maestro).

    URL: /encuesta-satisfaccion/?cliente=<id>
    El email D+1 incluye el `?cliente=X` para prellenar nombre/email.
    """
    from ..forms_encuesta import EncuestaSatisfaccionForm
    from ..models import Cliente, EncuestaSatisfaccion, VentaReserva

    # Resolver cliente si vino el parámetro
    cliente = None
    cliente_id = request.GET.get('cliente') or request.POST.get('cliente_id')
    if cliente_id:
        try:
            cliente = Cliente.objects.filter(id=int(cliente_id)).first()
        except (ValueError, TypeError):
            cliente = None

    # Última reserva (para prellenar fecha_visita y servicios sugeridos)
    ultima_reserva = None
    if cliente:
        ultima_reserva = (VentaReserva.objects
                          .filter(cliente=cliente)
                          .order_by('-fecha_reserva')
                          .first())

    if request.method == 'POST':
        form = EncuestaSatisfaccionForm(request.POST)
        if form.is_valid():
            encuesta = form.save(commit=False)
            encuesta.origen = 'formulario_web'

            # Auto-match por email si no viene cliente_id en URL
            # (cierra el gap cuando el cliente abre la URL directamente sin ?cliente=)
            if not cliente and encuesta.contacto_email:
                cliente = Cliente.objects.filter(
                    email__iexact=encuesta.contacto_email.strip()
                ).first()
                if cliente and not ultima_reserva:
                    ultima_reserva = (VentaReserva.objects
                                      .filter(cliente=cliente)
                                      .order_by('-fecha_reserva')
                                      .first())

            if cliente:
                encuesta.cliente = cliente
                # Prellenar contacto si no vino
                if not encuesta.contacto_nombre:
                    encuesta.contacto_nombre = cliente.nombre or ''
                if not encuesta.contacto_email:
                    encuesta.contacto_email = cliente.email or ''
                if not encuesta.contacto_telefono:
                    encuesta.contacto_telefono = cliente.telefono or ''
            if ultima_reserva:
                encuesta.venta_reserva = ultima_reserva
                if not encuesta.fecha_visita and ultima_reserva.fecha_reserva:
                    encuesta.fecha_visita = ultima_reserva.fecha_reserva.date() \
                        if hasattr(ultima_reserva.fecha_reserva, 'date') else ultima_reserva.fecha_reserva
            # JSONField MultipleChoiceField devuelve lista, lo guardamos tal cual
            encuesta.servicios_contratados = form.cleaned_data.get('servicios_contratados') or []
            encuesta.save()

            # Suscribir a newsletter si lo pidió
            if encuesta.quiere_newsletter and encuesta.contacto_email:
                from ..models import NewsletterSubscriber
                NewsletterSubscriber.objects.get_or_create(
                    email=encuesta.contacto_email.strip().lower(),
                    defaults={'nombre': encuesta.contacto_nombre or ''}
                )

            return redirect(f"{reverse('encuesta_gracias')}?id={encuesta.id}")
        # else: cae al render con form.errors
    else:
        # GET: prefill con datos del cliente
        initial = {}
        if cliente:
            initial['contacto_nombre'] = cliente.nombre or ''
            initial['contacto_email'] = cliente.email or ''
            initial['contacto_telefono'] = cliente.telefono or ''
        form = EncuestaSatisfaccionForm(initial=initial)

    context = {
        'form': form,
        'cliente': cliente,
        'cliente_id': cliente.id if cliente else '',
        'page_title': 'Encuesta de Satisfacción - Aremko',
        'meta_description': 'Cuéntanos cómo te fue en Aremko. Tu opinión nos ayuda a mejorar.',
    }
    return render(request, 'ventas/encuesta_satisfaccion.html', context)


def encuesta_gracias_view(request):
    """
    Página de "Gracias" tras enviar encuesta.

    Implementa "Review Funnel": muestra botones de Google Reviews + TripAdvisor
    SOLO si la encuesta marca experiencia positiva (4-5⭐ o NPS>=7).
    Para clientes con experiencia negativa: mensaje empático sin presionar reviews públicas.

    Query param: ?id=<encuesta_id>
    """
    from ..models import EncuestaSatisfaccion
    from django.conf import settings as djsettings

    encuesta = None
    encuesta_id = request.GET.get('id')
    if encuesta_id:
        try:
            encuesta = EncuestaSatisfaccion.objects.filter(id=int(encuesta_id)).first()
        except (ValueError, TypeError):
            encuesta = None

    califica_review_publico = encuesta.califica_para_review_publico if encuesta else False

    context = {
        'encuesta': encuesta,
        'califica_review_publico': califica_review_publico,
        'google_reviews_url': 'https://g.page/r/CbKKwbV5UmD_EBM/review',
        'tripadvisor_url': getattr(djsettings, 'TRIPADVISOR_URL',
                                   'https://www.tripadvisor.com.ar/Hotel_Review-g294299-d7138437-Reviews-Aremko_Aguas_Calientes_Spa-Puerto_Varas_Los_Lagos_Region.html'),
        'page_title': 'Gracias por tu opinión - Aremko',
    }
    return render(request, 'ventas/encuesta_gracias.html', context)


def tarjetas_qr_reviews_view(request):
    """
    Vista interna para imprimir tarjetas QR con link de Google Reviews.
    Diseñada para usar Cmd+P / Ctrl+P y guardar como PDF o imprimir directo.

    URL: /tarjetas-qr-reviews/  (sin login porque la URL no es discoverable
    y el contenido no es sensible — es un asset operativo).
    """
    return render(request, 'ventas/tarjetas_qr_reviews.html')


def garantia_view(request):
    """
    Página dedicada a la Garantía Aremko.
    Diferenciador único: ningún competidor de Puerto Varas ofrece garantía explícita.
    Atacar la objeción #1 detectada en el reporte 7 Maletas: inconsistencia de
    temperatura del agua.
    """
    try:
        canonical_url = request.build_absolute_uri(request.path)
    except Exception:
        canonical_url = request.path

    context = {
        'page_title': 'Garantía Aremko: si tu tina llega a 37°C o menos, es gratis',
        'meta_description': 'Las tinas Aremko están a 38°C. Si llegan a 37°C o menos, la tina es gratis. La única garantía de temperatura de spa en Puerto Varas.',
        'canonical_url': canonical_url,
    }
    return render(request, 'ventas/garantia.html', context)


def subscribe_view(request):
    """
    Maneja la suscripción al newsletter creando un NewsletterSubscriber.
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            from ..models import NewsletterSubscriber
            # Verificar si ya existe
            subscriber, created = NewsletterSubscriber.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': '',
                    'last_name': '',
                    'source': 'Website Footer',
                    'is_active': True
                }
            )
            if created:
                messages.success(request, '¡Gracias por suscribirte a nuestro boletín!')
            else:
                if not subscriber.is_active:
                    subscriber.is_active = True
                    subscriber.save()
                    messages.success(request, '¡Tu suscripción ha sido reactivada!')
                else:
                    messages.info(request, 'Ya estás suscrito a nuestro boletín.')
        else:
            messages.error(request, 'Por favor ingresa un correo electrónico válido.')
    
    # Redirigir a la página desde donde vino
    return redirect(request.META.get('HTTP_REFERER', 'homepage'))



@csrf_exempt
def unsubscribe_view(request, email):
    """
    Baja de comunicaciones de marketing.
    - GET: link "darse de baja" del footer (muestra página de confirmación).
    - POST: one-click unsubscribe de Gmail/Yahoo (header List-Unsubscribe-Post);
      responde 200 sin UI. csrf_exempt porque el POST lo hace el proveedor de correo.
    Además de desactivar NewsletterSubscriber, registra el email en EmailBlacklist
    (reason='unsubscribe') — es lo que consulta enviar_campana_email para excluir.
    Nota: En un sistema más robusto, se usaría un token firmado.
    """
    from django.http import HttpResponse
    from ..models import NewsletterSubscriber, EmailBlacklist
    try:
        NewsletterSubscriber.objects.filter(email=email, is_active=True).update(is_active=False)

        email_norm = (email or '').strip().lower()
        if email_norm and '@' in email_norm:
            obj, created = EmailBlacklist.objects.get_or_create(
                email=email_norm,
                defaults={'reason': 'unsubscribe',
                          'notes': 'Baja vía link del footer / one-click del cliente de correo'},
            )
            if not created and not obj.is_active:
                obj.is_active = True
                obj.reason = 'unsubscribe'
                obj.save(update_fields=['is_active', 'reason'])

        if request.method == 'POST':
            return HttpResponse('OK')  # one-click: el cliente de correo no espera HTML
        messages.success(request, f'Te has dado de baja exitosamente ({email}).')
    except Exception:
        if request.method == 'POST':
            return HttpResponse('OK')
        messages.error(request, 'Ocurrió un error al procesar tu solicitud.')

    return render(request, 'ventas/unsubscribe_success.html')


def email_preview_compliance(request):
    """
    Vista auxiliar para que el usuario pueda tomar captura del template de email
    para enviar a SendGrid como prueba de cumplimiento.
    """
    return render(request, 'ventas/email/marketing_base.html', {'email': 'cliente@ejemplo.com'})





def solicitar_cotizacion_empresa(request):
    """
    Procesa el formulario de cotización empresarial
    Envía email a ventas@aremko.cl y responde al cliente
    """
    from django.http import JsonResponse
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings
    from ..models import CotizacionEmpresa
    import logging

    logger = logging.getLogger(__name__)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    try:
        # Obtener datos del formulario
        nombre_empresa = request.POST.get('nombre_empresa', '').strip()
        nombre_contacto = request.POST.get('nombre_contacto', '').strip()
        email = request.POST.get('email', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        servicio_interes = request.POST.get('servicio_interes', '')
        numero_personas = request.POST.get('numero_personas', '')
        fecha_tentativa = request.POST.get('fecha_tentativa', '')
        mensaje_adicional = request.POST.get('mensaje_adicional', '').strip()

        # Validaciones básicas
        if not all([nombre_empresa, nombre_contacto, email, telefono, servicio_interes, numero_personas]):
            return JsonResponse({
                'success': False,
                'error': 'Por favor completa todos los campos obligatorios'
            }, status=400)

        # Validar número de personas
        try:
            numero_personas = int(numero_personas)
            if numero_personas < 1:
                raise ValueError
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'El número de personas debe ser un número válido mayor a 0'
            }, status=400)

        # Procesar fecha tentativa (opcional)
        from datetime import datetime
        fecha_obj = None
        if fecha_tentativa:
            try:
                fecha_obj = datetime.strptime(fecha_tentativa, '%Y-%m-%d').date()
            except ValueError:
                pass  # Fecha opcional, si falla simplemente se guarda como None

        # Crear registro en la base de datos
        cotizacion = CotizacionEmpresa.objects.create(
            nombre_empresa=nombre_empresa,
            nombre_contacto=nombre_contacto,
            email=email,
            telefono=telefono,
            servicio_interes=servicio_interes,
            numero_personas=numero_personas,
            fecha_tentativa=fecha_obj,
            mensaje_adicional=mensaje_adicional,
            estado='pendiente'
        )

        logger.info(f"Nueva cotización empresarial creada: {cotizacion.id} - {nombre_empresa}")

        # Preparar datos para los emails
        servicio_nombre = cotizacion.get_servicio_interes_display()
        fecha_formateada = fecha_obj.strftime('%d/%m/%Y') if fecha_obj else 'Por definir'

        # ===== EMAIL 1: Notificación a ventas@aremko.cl =====
        context_ventas = {
            'cotizacion': cotizacion,
            'servicio_nombre': servicio_nombre,
            'fecha_formateada': fecha_formateada,
            'admin_url': f"{request.scheme}://{request.get_host()}/admin/ventas/cotizacionempresa/{cotizacion.id}/change/"
        }

        email_ventas_html = render_to_string('emails/cotizacion_empresa_notificacion.html', context_ventas)

        email_ventas = EmailMultiAlternatives(
            subject=f'Nueva Cotización Empresarial - {nombre_empresa} ({numero_personas} personas)',
            body=f"""
Nueva solicitud de cotización recibida:

Empresa: {nombre_empresa}
Contacto: {nombre_contacto}
Email: {email}
Teléfono: {telefono}
Servicio: {servicio_nombre}
Personas: {numero_personas}
Fecha tentativa: {fecha_formateada}

Mensaje:
{mensaje_adicional if mensaje_adicional else 'Sin mensaje adicional'}

Ver en admin: {context_ventas['admin_url']}
            """.strip(),
            from_email=getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl'),
            to=['ventas@aremko.cl'],
            reply_to=[email]
        )
        email_ventas.attach_alternative(email_ventas_html, "text/html")
        email_ventas.send()

        logger.info(f"Email de notificación enviado a ventas@aremko.cl para cotización {cotizacion.id}")

        # ===== EMAIL 2: Confirmación al cliente =====
        context_cliente = {
            'nombre_contacto': nombre_contacto,
            'nombre_empresa': nombre_empresa,
            'servicio_nombre': servicio_nombre,
            'numero_personas': numero_personas,
            'fecha_formateada': fecha_formateada,
        }

        email_cliente_html = render_to_string('emails/cotizacion_empresa_confirmacion.html', context_cliente)

        email_cliente = EmailMultiAlternatives(
            subject='Recibimos tu solicitud de cotización - Aremko Empresas',
            body=f"""
Hola {nombre_contacto},

Gracias por tu interés en nuestros servicios corporativos de Aremko.

Hemos recibido tu solicitud:
- Servicio: {servicio_nombre}
- Número de personas: {numero_personas}
- Fecha tentativa: {fecha_formateada}

Nuestro equipo se pondrá en contacto contigo dentro de las próximas 24 horas para enviarte una cotización personalizada.

Saludos,
El equipo de Aremko
Aguas Calientes & Spa | Puerto Varas, Chile
            """.strip(),
            from_email=getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl'),
            to=[email],
            reply_to=[getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')]
        )
        email_cliente.attach_alternative(email_cliente_html, "text/html")
        email_cliente.send()

        logger.info(f"Email de confirmación enviado al cliente {email} para cotización {cotizacion.id}")

        # Respuesta exitosa
        return JsonResponse({
            'success': True,
            'message': '¡Solicitud enviada! Te contactaremos dentro de 24 horas.',
            'cotizacion_id': cotizacion.id
        })

    except Exception as e:
        logger.error(f"Error procesando cotización empresarial: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Ocurrió un error al procesar tu solicitud. Por favor intenta nuevamente o contáctanos por WhatsApp.'
        }, status=500)


# ──────────────────────────────────────────────────────────────────────
#  Landing "Refugio Aremko" — vistas públicas (campaña 15-jun-2026)
# ──────────────────────────────────────────────────────────────────────

def _get_client_ip(request):
    """Extrae IP del request respetando X-Forwarded-For (Render proxy)."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        # Primer IP de la lista (el cliente real)
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def refugio_landing_view(request):
    """Landing page pública de la campaña Refugio Aremko.

    Texto + precio + galería editables vía RefugioConfig singleton.
    Si `RefugioConfig.activo == False` devuelve 404 (campaña cerrada).
    """
    from django.http import Http404
    from ..models import RefugioConfig, RefugioImagen

    config = RefugioConfig.get_solo()
    if not config.activo:
        raise Http404("Campaña Refugio no activa")

    # Galería ordenable desde admin
    imagenes = list(RefugioImagen.objects.filter(activa=True).order_by('orden', 'id'))

    # Canonical + meta SEO
    try:
        canonical_url = request.build_absolute_uri(request.path)
    except Exception:
        canonical_url = request.path

    # Capturar UTM en la sesión para que sobrevivan el submit (POST)
    utm_keys = ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term')
    utm_data = {k: request.GET.get(k, '') for k in utm_keys if request.GET.get(k)}
    if utm_data:
        request.session['refugio_utm'] = utm_data

    context = {
        'config': config,
        'imagenes': imagenes,
        'canonical_url': canonical_url,
        # Bloques SEO consumidos por base_public.html
        'page_title': config.seo_title,
        'meta_description': config.seo_description,
        'og_image_url': config.og_image.url if config.og_image else None,
    }
    return render(request, 'ventas/refugio_landing.html', context)


def ritual_rio_landing_view(request):
    """Landing OCULTA del producto insignia "Noche de ritual junto al río" (Plan Río / H-031).

    NO enlazada en el menú, NO en el sitemap, con meta robots noindex,nofollow.
    Visible solo con el link directo /ritual-del-rio/ hasta decidir dónde colocarla.
    CTA único → WhatsApp (mecanismo de alto valor: deseo → conversación → abono).
    """
    try:
        canonical_url = request.build_absolute_uri(request.path)
    except Exception:
        canonical_url = request.path
    whatsapp_url = (
        'https://wa.me/56957902525?text='
        'Hola%2C%20quiero%20reservar%20la%20Noche%20de%20Ritual%20junto%20al%20r%C3%ADo'
    )
    try:
        from ventas.models import RitualRioLandingConfig
        config = RitualRioLandingConfig.get_solo()
    except Exception:
        config = None
    resenas = []
    if config:
        resenas = [
            (config.resena1_foto, config.resena1_texto, config.resena1_autor),
            (config.resena2_foto, config.resena2_texto, config.resena2_autor),
            (config.resena3_foto, config.resena3_texto, config.resena3_autor),
        ]
    return render(request, 'ventas/ritual_rio_landing.html', {
        'canonical_url': canonical_url,
        'whatsapp_url': whatsapp_url,
        'config': config,
        'resenas': resenas,
    })


def refugio_submit_view(request):
    """Procesa el formulario de la landing /refugio/.

    Endpoint POST que:
        1. Valida campos requeridos
        2. Crea RefugioLead con UTM tracking + IP + UA
        3. Manda email al equipo interno (comunicaciones + aremkospa)
        4. Manda email de confirmación al lead
        5. Devuelve JSON success o error
    """
    from django.http import JsonResponse, Http404
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings
    from datetime import datetime
    from ..models import RefugioConfig, RefugioLead
    import logging

    logger = logging.getLogger(__name__)

    config = RefugioConfig.get_solo()
    if not config.activo:
        raise Http404("Campaña Refugio no activa")

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    try:
        # Datos del formulario
        nombre = request.POST.get('nombre', '').strip()
        email = request.POST.get('email', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        ciudad_origen = request.POST.get('ciudad_origen', '').strip()
        fecha_tentativa = request.POST.get('fecha_tentativa', '').strip()
        num_personas = request.POST.get('num_personas', '2').strip()
        mensaje = request.POST.get('mensaje', '').strip()

        # Validación mínima (CRO: WhatsApp es el campo primario; email opcional)
        if not nombre or not telefono:
            return JsonResponse({
                'success': False,
                'error': 'Nombre y WhatsApp son obligatorios.'
            }, status=400)

        # Parsear num_personas
        try:
            num_personas = int(num_personas)
            if num_personas < 1 or num_personas > 20:
                num_personas = 2
        except (TypeError, ValueError):
            num_personas = 2

        # Parsear fecha (opcional)
        fecha_obj = None
        if fecha_tentativa:
            try:
                fecha_obj = datetime.strptime(fecha_tentativa, '%Y-%m-%d').date()
            except ValueError:
                pass

        # UTM: prioridad a POST hidden inputs, fallback a sesión
        utm_session = request.session.get('refugio_utm', {})
        def _utm(key):
            return (request.POST.get(key) or utm_session.get(key) or '').strip()[:120]

        lead = RefugioLead.objects.create(
            nombre=nombre[:120],
            email=email[:254],
            telefono=telefono[:30],
            ciudad_origen=ciudad_origen[:120],
            fecha_tentativa=fecha_obj,
            num_personas=num_personas,
            mensaje=mensaje,
            utm_source=_utm('utm_source'),
            utm_medium=_utm('utm_medium'),
            utm_campaign=_utm('utm_campaign'),
            utm_content=_utm('utm_content'),
            utm_term=_utm('utm_term'),
            referer=(request.META.get('HTTP_REFERER') or '')[:500],
            ip_address=_get_client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:500],
        )
        logger.info(f"[Refugio] Lead {lead.id} creado: {lead.nombre} <{lead.email}>")

        # --- Email al equipo ---
        # Destinatarios desde settings.REFUGIO_LEAD_NOTIFICACIONES para que
        # se puedan ajustar sin redeploy (env REFUGIO_LEAD_NOTIFICACIONES
        # coma-separados). Fallback hardcoded por seguridad si el setting
        # no está definido.
        try:
            equipo_emails = getattr(
                settings,
                'REFUGIO_LEAD_NOTIFICACIONES',
                ['comunicaciones@aremko.cl', 'aremkospa@gmail.com', 'ventas@aremko.cl'],
            )
            subject_equipo = f"[Refugio] Nuevo lead: {lead.nombre}"
            body_equipo = render_to_string('ventas/emails/refugio_lead_equipo.txt', {
                'lead': lead,
                'config': config,
            })
            email_equipo = EmailMultiAlternatives(
                subject=subject_equipo,
                body=body_equipo,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'comunicaciones@aremko.cl'),
                to=equipo_emails,
                reply_to=[lead.email] if lead.email else None,
            )
            email_equipo.send(fail_silently=True)
        except Exception as e:
            logger.warning(f"[Refugio] No se pudo enviar email al equipo: {e}")

        # --- Email confirmación al lead (solo si dejó email; ahora es opcional) ---
        if lead.email:
            try:
                subject_cli = "Recibimos tu solicitud · Refugio Aremko"
                body_cli = render_to_string('ventas/emails/refugio_lead_confirmacion.txt', {
                    'lead': lead,
                    'config': config,
                })
                email_cli = EmailMultiAlternatives(
                    subject=subject_cli,
                    body=body_cli,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'comunicaciones@aremko.cl'),
                    to=[lead.email],
                    reply_to=[getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')],
                )
                email_cli.send(fail_silently=True)
            except Exception as e:
                logger.warning(f"[Refugio] No se pudo enviar confirmación al lead: {e}")

        return JsonResponse({
            'success': True,
            'message': '¡Gracias! Recibimos tu solicitud y te contactamos dentro de 24 horas.',
            'lead_id': lead.id,
        })

    except Exception as e:
        logger.exception(f"[Refugio] Error procesando submit: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Ocurrió un error al procesar tu solicitud. Intenta nuevamente o escríbenos por WhatsApp.',
        }, status=500)
