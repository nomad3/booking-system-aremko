"""
Vista de calendario para seleccionar servicios y agregarlos a una reserva.
Similar a calendario_matriz_view pero optimizada para selección desde el formulario de reserva.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.db import transaction
from datetime import datetime, date
from ..models import (
    Servicio,
    CategoriaServicio,
    ReservaServicio,
    VentaReserva
)
from .calendario_matriz_view import generar_matriz_disponibilidad


def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff"""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)


@staff_required
@xframe_options_sameorigin
def calendario_seleccion_view(request):
    """
    Vista del calendario en modo selección para agregar servicios a una reserva.
    Muestra la matriz de disponibilidad y permite hacer click en slots disponibles.
    """
    try:
        # Obtener ID de reserva si existe
        reserva_id = request.GET.get('reserva_id', '')

        # Obtener parámetros de la request
        fecha_str = request.GET.get('fecha', date.today().strftime('%Y-%m-%d'))

        # Obtener todas las categorías para el selector
        categorias = CategoriaServicio.objects.all().order_by('nombre')

        # Buscar la categoría "Tinas Calientes" para usarla como default
        tinas_categoria = categorias.filter(nombre='Tinas Calientes').first()
        if not tinas_categoria:
            tinas_categoria = categorias.filter(nombre__icontains='tina').exclude(nombre__icontains='empresarial').first()
        if not tinas_categoria:
            tinas_categoria = categorias.filter(nombre__icontains='tina').first()

        default_categoria_id = str(tinas_categoria.id) if tinas_categoria else '1'

        # Obtener el ID de categoría del request o usar Tinas como default
        categoria_id = request.GET.get('categoria', default_categoria_id)

        try:
            fecha_seleccionada = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_seleccionada = date.today()

        # Obtener la categoría seleccionada
        try:
            categoria = CategoriaServicio.objects.get(id=categoria_id)
        except CategoriaServicio.DoesNotExist:
            categoria = tinas_categoria if tinas_categoria else categorias.first()
            categoria_id = categoria.id if categoria else None

        # Obtener servicios de la categoría que sean visibles en matriz
        servicios = Servicio.objects.filter(
            categoria=categoria,
            activo=True,
            visible_en_matriz=True
        ).order_by('nombre')

        # Generar la matriz de disponibilidad
        matriz_data = generar_matriz_disponibilidad(
            fecha_seleccionada,
            categoria,
            servicios
        )

        # Crear una estructura de datos más simple para el template
        matriz_simple = []
        for slot in matriz_data['slots']:
            fila = {'slot': slot, 'celdas': []}
            for recurso in matriz_data['recursos']:
                if slot in matriz_data['matriz'] and recurso in matriz_data['matriz'][slot]:
                    celda = matriz_data['matriz'][slot][recurso]
                else:
                    celda = {'estado': 'disponible', 'cliente': None, 'personas': None}
                fila['celdas'].append(celda)
            matriz_simple.append(fila)

        # Contexto para el template
        context = {
            'fecha_seleccionada': fecha_seleccionada,
            'fecha_str': fecha_seleccionada.strftime('%Y-%m-%d'),
            'categoria_seleccionada': categoria,
            'categoria_id': int(categoria_id) if categoria_id else None,
            'categorias': categorias,
            'matriz': matriz_data['matriz'],
            'matriz_simple': matriz_simple,
            'slots_horarios': matriz_data['slots'],
            'recursos': matriz_data['recursos'],
            'resumen': matriz_data['resumen'],
            'reserva_id': reserva_id,
            'modo_seleccion': True,  # Flag para indicar que estamos en modo selección
        }

        # Usar template específico para selección
        return render(request, 'ventas/calendario_seleccion.html', context)

    except Exception as e:
        # En caso de error, mostrar página de error con detalles
        from django.http import HttpResponse
        import traceback
        error_html = f"""
        <html>
        <head><title>Error en Calendario de Selección</title></head>
        <body>
        <h1>Error al cargar el calendario</h1>
        <p><strong>Error:</strong> {str(e)}</p>
        <pre>{traceback.format_exc()}</pre>
        </body>
        </html>
        """
        return HttpResponse(error_html, status=500)


def obtener_personas_por_defecto(nombre_servicio):
    """
    Determina la cantidad de personas por defecto según el nombre del servicio.

    Reglas:
    - Tina Osorno, Calbuco: 4 personas
    - Tina Hornopiren, Tronador, Puntiagudo, Llaima, Villarrica, Puyehue: 2 personas
    - Cabañas: 1 (se cobra por cabaña, no por persona)
    - Masajes: 1 (una entrada por masajista)
    - Otros: 2 (valor por defecto)
    """
    nombre_lower = nombre_servicio.lower()

    # Cabañas: 1 persona (se cobra por cabaña)
    if 'cabaña' in nombre_lower or 'cabana' in nombre_lower:
        return 1

    # Masajes: 1 persona
    if 'masaje' in nombre_lower:
        return 1

    # Tinas específicas con 4 personas
    if 'osorno' in nombre_lower or 'calbuco' in nombre_lower:
        return 4

    # Tinas específicas con 2 personas
    tinas_2_personas = ['hornopiren', 'tronador', 'puntiagudo', 'llaima', 'villarrica', 'puyehue']
    if any(nombre in nombre_lower for nombre in tinas_2_personas):
        return 2

    # Para otras tinas no especificadas, usar 2 como default
    if 'tina' in nombre_lower:
        return 2

    # Default para otros servicios
    return 2


@staff_required
@require_POST
def agregar_servicio_a_reserva(request):
    """
    API endpoint para agregar un servicio a una reserva existente o crear una nueva.

    POST params:
    - reserva_id: ID de la reserva (opcional, si no existe se crea una nueva)
    - servicio_nombre: Nombre del servicio
    - fecha: Fecha del servicio (YYYY-MM-DD)
    - hora: Hora del servicio (HH:MM)
    """
    try:
        import json
        data = json.loads(request.body)

        reserva_id = data.get('reserva_id')
        servicio_nombre = data.get('servicio_nombre')
        fecha_str = data.get('fecha')
        hora_str = data.get('hora')

        # Validar datos requeridos
        if not servicio_nombre or not fecha_str or not hora_str:
            return JsonResponse({
                'success': False,
                'error': 'Faltan datos requeridos'
            }, status=400)

        # Buscar el servicio
        try:
            servicio = Servicio.objects.get(nombre=servicio_nombre, activo=True)
        except Servicio.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Servicio "{servicio_nombre}" no encontrado'
            }, status=404)

        # Convertir fecha
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Formato de fecha inválido'
            }, status=400)

        # Obtener o crear la reserva
        if reserva_id:
            try:
                venta_reserva = VentaReserva.objects.get(pk=reserva_id)
            except VentaReserva.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Reserva no encontrada'
                }, status=404)
        else:
            # Si no hay reserva_id, no podemos crear una reserva sin cliente
            # Esto debe manejarse desde el formulario del admin
            return JsonResponse({
                'success': False,
                'error': 'Debe crear la reserva primero antes de agregar servicios'
            }, status=400)

        # Determinar cantidad de personas por defecto
        cantidad_personas = obtener_personas_por_defecto(servicio.nombre)

        # Crear el servicio en la reserva con precio congelado
        with transaction.atomic():
            reserva_servicio = ReservaServicio.objects.create(
                venta_reserva=venta_reserva,
                servicio=servicio,
                fecha_agendamiento=fecha,
                hora_inicio=hora_str,
                cantidad_personas=cantidad_personas,
                precio_unitario_venta=servicio.precio_base  # Congelar el precio
            )

            # Recalcular el total de la reserva
            venta_reserva.calcular_total()
            venta_reserva.save()

        return JsonResponse({
            'success': True,
            'mensaje': f'Servicio "{servicio.nombre}" agregado correctamente',
            'reserva_servicio_id': reserva_servicio.id,
            'cantidad_personas': cantidad_personas,
            'precio_unitario': str(servicio.precio_base),
            'subtotal': str(servicio.precio_base * cantidad_personas)
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Error al decodificar JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error inesperado: {str(e)}'
        }, status=500)
