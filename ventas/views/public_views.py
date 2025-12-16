from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from ..models import Servicio, CategoriaServicio, HomepageConfig, Lead, Producto, CategoriaProducto, SeoContent # Relative import, ADD HomepageConfig, Lead, Producto, CategoriaProducto, SeoContent


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

    context = {
        'servicios': servicios,
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

    context = {
        'categoria_actual': categoria,
        'servicios': servicios,
        'categorias': categorias,
        'cart': request.session.get('cart', {'servicios': [], 'total': 0}), # Include cart context
        'canonical_url': canonical_url,
        'category_hero_image': category_hero_image,
        'seo_content': seo_content,  # Pass SEO content to template
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
    whatsapp_number = "56912345678"  # TODO: Actualizar con el número real

    # Obtener contenido SEO para la página de productos
    seo_content = None
    try:
        seo_content = SeoContent.objects.filter(page_type='productos').first()
    except SeoContent.DoesNotExist:
        pass

    context = {
        'productos': productos,
        'categorias': categorias,
        'canonical_url': canonical_url,
        'whatsapp_number': whatsapp_number,
        'seo_content': seo_content,  # Agregar contenido SEO al contexto
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

def privacy_policy_view(request):
    """
    Vista para la página de Política de Privacidad.
    Requerida para cumplimiento con proveedores de email marketing (SendGrid).
    """
    return render(request, 'ventas/privacy_policy.html')


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



def unsubscribe_view(request, email):
    """
    Maneja la desuscripción marcando el NewsletterSubscriber como inactivo.
    Nota: En un sistema más robusto, se usaría un token firmado.
    """
    from ..models import NewsletterSubscriber
    try:
        # Buscar suscriptores con ese email
        subscribers = NewsletterSubscriber.objects.filter(email=email, is_active=True)
        count = subscribers.count()
        if count > 0:
            subscribers.update(is_active=False)
            messages.success(request, f'Te has dado de baja exitosamente ({email}).')
        else:
            messages.info(request, 'No encontramos una suscripción activa con ese correo.')
    except Exception as e:
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
