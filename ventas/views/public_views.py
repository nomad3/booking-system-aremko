from django.shortcuts import render, get_object_or_404
from ..models import Servicio, CategoriaServicio, HomepageConfig # Relative import, ADD HomepageConfig


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

    except HomepageConfig.DoesNotExist:
        # Handle case where the config hasn't been created yet
        pass
    # --- End Fetch Homepage Config ---

    # Canonical URL for SEO (build safely)
    try:
        canonical_url = request.build_absolute_uri(request.path)
    except Exception:
        canonical_url = request.path

    context = {
        'servicios': servicios,
        'categorias': categorias,
        'cart': cart,
        'hero_image_url': hero_image_url,
        'philosophy_image_url': philosophy_image_url, # Add philosophy URL to context
        'gallery_image_1_url': gallery_image_1_url,   # Add gallery 1 URL to context
        'gallery_image_2_url': gallery_image_2_url,   # Add gallery 2 URL to context
        'gallery_image_3_url': gallery_image_3_url,   # Add gallery 3 URL to context
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

    context = {
        'categoria_actual': categoria,
        'servicios': servicios,
        'categorias': categorias,
        'cart': request.session.get('cart', {'servicios': [], 'total': 0}), # Include cart context
        'canonical_url': canonical_url,
        'category_hero_image': category_hero_image,
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


def empresas_view(request):
    """
    Vista para la landing page de servicios empresariales
    """
    context = {
        'page_title': 'Reuniones con Resultados: Productividad + Bienestar',
        'meta_description': 'Espacios únicos para reuniones empresariales en Puerto Varas. Sala de reuniones, desayuno sureño y tinas calientes para tu equipo.',
    }
    return render(request, 'ventas/empresas.html', context)


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
