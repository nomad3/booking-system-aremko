"""
Vistas para gestión de plantillas de tareas recurrentes

Interfaz amigable para crear y gestionar plantillas sin usar el admin.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from .models import TaskTemplate, Swimlane, Priority
import json


@login_required
def plantillas_dashboard(request):
    """
    Dashboard principal de plantillas recurrentes
    
    Muestra todas las plantillas existentes y permite crear/editar.
    """
    plantillas = TaskTemplate.objects.all().order_by('swimlane', 'queue_position')
    
    # Estadísticas
    stats = {
        'total': plantillas.count(),
        'activas': plantillas.filter(activa=True).count(),
        'por_area': {},
        'solo_martes': plantillas.filter(solo_martes=True).count()
    }
    
    # Por área
    for lane in Swimlane:
        count = plantillas.filter(swimlane=lane).count()
        if count > 0:
            stats['por_area'][lane.label] = count
    
    context = {
        'plantillas': plantillas,
        'stats': stats
    }
    
    return render(request, 'control_gestion/plantillas_dashboard.html', context)


@login_required
def plantillas_crear(request):
    """
    Formulario simple para crear plantilla de tarea recurrente
    """
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            title = request.POST.get('title_template')
            description = request.POST.get('description')
            swimlane = request.POST.get('swimlane')
            priority = request.POST.get('priority', 'NORMAL')
            asignar_a_grupo = request.POST.get('asignar_a_grupo')

            # Asignar a usuario específico
            asignar_a_usuario = None
            usuario_id = request.POST.get('asignar_a_usuario')
            if usuario_id:
                asignar_a_usuario = User.objects.get(id=usuario_id)

            # Frecuencia
            frecuencia = request.POST.get('frecuencia', 'DIARIA')

            # Días de la semana (solo para DIARIA)
            dias_activa = []
            if frecuencia == 'DIARIA':
                for i in range(7):
                    if request.POST.get(f'dia_{i}'):
                        dias_activa.append(i)

            solo_martes = request.POST.get('solo_martes') == 'on'
            activa = request.POST.get('activa', 'on') == 'on'

            # Día del mes (para MENSUAL/TRIMESTRAL/SEMESTRAL/ANUAL)
            dia_del_mes = request.POST.get('dia_del_mes')
            dia_del_mes = int(dia_del_mes) if dia_del_mes else None

            # Mes de inicio (para TRIMESTRAL/SEMESTRAL/ANUAL)
            mes_inicio = request.POST.get('mes_inicio')
            mes_inicio = int(mes_inicio) if mes_inicio else None

            # Crear plantilla
            plantilla = TaskTemplate.objects.create(
                title_template=title,
                description=description,
                swimlane=swimlane,
                priority=priority,
                frecuencia=frecuencia,
                dias_activa=dias_activa,
                dia_del_mes=dia_del_mes,
                mes_inicio=mes_inicio,
                asignar_a_grupo=asignar_a_grupo,
                asignar_a_usuario=asignar_a_usuario,
                solo_martes=solo_martes,
                activa=activa
            )
            
            messages.success(request, f'✅ Plantilla "{title}" creada exitosamente')
            return redirect('control_gestion:plantillas_dashboard')
        
        except Exception as e:
            messages.error(request, f'❌ Error al crear plantilla: {str(e)}')
    
    # GET - mostrar formulario
    # Obtener todos los usuarios para el dropdown
    usuarios = User.objects.all().order_by('username')

    context = {
        'swimlanes': Swimlane.choices,
        'priorities': Priority.choices,
        'grupos': ['OPERACIONES', 'RECEPCION', 'VENTAS', 'ATENCION', 'SUPERVISION', 'MUCAMA'],
        'usuarios': usuarios,
        'dias_semana': [
            (0, 'Lunes'),
            (1, 'Martes'),
            (2, 'Miércoles'),
            (3, 'Jueves'),
            (4, 'Viernes'),
            (5, 'Sábado'),
            (6, 'Domingo'),
        ],
        'dias_mes': range(1, 32),  # 1-31
        'meses': [
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'),
            (4, 'Abril'), (5, 'Mayo'), (6, 'Junio'),
            (7, 'Julio'), (8, 'Agosto'), (9, 'Septiembre'),
            (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
        ]
    }
    
    return render(request, 'control_gestion/plantillas_crear.html', context)


@login_required
def plantillas_editar(request, plantilla_id):
    """
    Editar plantilla existente
    """
    plantilla = get_object_or_404(TaskTemplate, id=plantilla_id)
    
    if request.method == 'POST':
        try:
            plantilla.title_template = request.POST.get('title_template')
            plantilla.description = request.POST.get('description')
            plantilla.swimlane = request.POST.get('swimlane')
            plantilla.priority = request.POST.get('priority')
            plantilla.asignar_a_grupo = request.POST.get('asignar_a_grupo')

            # Asignar a usuario específico
            usuario_id = request.POST.get('asignar_a_usuario')
            if usuario_id:
                plantilla.asignar_a_usuario = User.objects.get(id=usuario_id)
            else:
                plantilla.asignar_a_usuario = None

            # Frecuencia
            frecuencia = request.POST.get('frecuencia', 'DIARIA')
            plantilla.frecuencia = frecuencia

            # Días (solo para DIARIA)
            dias_activa = []
            if frecuencia == 'DIARIA':
                for i in range(7):
                    if request.POST.get(f'dia_{i}'):
                        dias_activa.append(i)
            plantilla.dias_activa = dias_activa

            plantilla.solo_martes = request.POST.get('solo_martes') == 'on'
            plantilla.activa = request.POST.get('activa', 'on') == 'on'

            # Día del mes (para MENSUAL/TRIMESTRAL/SEMESTRAL/ANUAL)
            dia_del_mes = request.POST.get('dia_del_mes')
            plantilla.dia_del_mes = int(dia_del_mes) if dia_del_mes else None

            # Mes de inicio (para TRIMESTRAL/SEMESTRAL/ANUAL)
            mes_inicio = request.POST.get('mes_inicio')
            plantilla.mes_inicio = int(mes_inicio) if mes_inicio else None

            plantilla.save()
            
            messages.success(request, f'✅ Plantilla "{plantilla.title_template}" actualizada')
            return redirect('control_gestion:plantillas_dashboard')
        
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    
    # Obtener todos los usuarios para el dropdown
    usuarios = User.objects.all().order_by('username')

    context = {
        'plantilla': plantilla,
        'swimlanes': Swimlane.choices,
        'priorities': Priority.choices,
        'grupos': ['OPERACIONES', 'RECEPCION', 'VENTAS', 'ATENCION', 'SUPERVISION', 'MUCAMA'],
        'usuarios': usuarios,
        'dias_semana': [
            (0, 'Lunes'),
            (1, 'Martes'),
            (2, 'Miércoles'),
            (3, 'Jueves'),
            (4, 'Viernes'),
            (5, 'Sábado'),
            (6, 'Domingo'),
        ],
        'dias_mes': range(1, 32),  # 1-31
        'meses': [
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'),
            (4, 'Abril'), (5, 'Mayo'), (6, 'Junio'),
            (7, 'Julio'), (8, 'Agosto'), (9, 'Septiembre'),
            (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
        ]
    }
    
    return render(request, 'control_gestion/plantillas_editar.html', context)


@login_required
def plantillas_toggle(request, plantilla_id):
    """
    Activar/desactivar plantilla rápidamente
    """
    plantilla = get_object_or_404(TaskTemplate, id=plantilla_id)
    plantilla.activa = not plantilla.activa
    plantilla.save()
    
    estado = "activada" if plantilla.activa else "desactivada"
    messages.success(request, f'✅ Plantilla "{plantilla.title_template}" {estado}')
    
    return redirect('control_gestion:plantillas_dashboard')


@login_required
def plantillas_eliminar(request, plantilla_id):
    """
    Eliminar plantilla
    """
    plantilla = get_object_or_404(TaskTemplate, id=plantilla_id)
    titulo = plantilla.title_template
    plantilla.delete()
    
    messages.success(request, f'✅ Plantilla "{titulo}" eliminada')
    return redirect('control_gestion:plantillas_dashboard')

