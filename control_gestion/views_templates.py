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
            
            # Días de la semana (checkboxes)
            dias_activa = []
            for i in range(7):
                if request.POST.get(f'dia_{i}'):
                    dias_activa.append(i)
            
            solo_martes = request.POST.get('solo_martes') == 'on'
            activa = request.POST.get('activa', 'on') == 'on'
            
            # Crear plantilla
            plantilla = TaskTemplate.objects.create(
                title_template=title,
                description=description,
                swimlane=swimlane,
                priority=priority,
                dias_activa=dias_activa,
                asignar_a_grupo=asignar_a_grupo,
                solo_martes=solo_martes,
                activa=activa
            )
            
            messages.success(request, f'✅ Plantilla "{title}" creada exitosamente')
            return redirect('control_gestion:plantillas_dashboard')
        
        except Exception as e:
            messages.error(request, f'❌ Error al crear plantilla: {str(e)}')
    
    # GET - mostrar formulario
    context = {
        'swimlanes': Swimlane.choices,
        'priorities': Priority.choices,
        'grupos': ['OPERACIONES', 'RECEPCION', 'VENTAS', 'ATENCION', 'SUPERVISION'],
        'dias_semana': [
            (0, 'Lunes'),
            (1, 'Martes'),
            (2, 'Miércoles'),
            (3, 'Jueves'),
            (4, 'Viernes'),
            (5, 'Sábado'),
            (6, 'Domingo'),
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
            
            # Días
            dias_activa = []
            for i in range(7):
                if request.POST.get(f'dia_{i}'):
                    dias_activa.append(i)
            plantilla.dias_activa = dias_activa
            
            plantilla.solo_martes = request.POST.get('solo_martes') == 'on'
            plantilla.activa = request.POST.get('activa', 'on') == 'on'
            
            plantilla.save()
            
            messages.success(request, f'✅ Plantilla "{plantilla.title_template}" actualizada')
            return redirect('control_gestion:plantillas_dashboard')
        
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    
    context = {
        'plantilla': plantilla,
        'swimlanes': Swimlane.choices,
        'priorities': Priority.choices,
        'grupos': ['OPERACIONES', 'RECEPCION', 'VENTAS', 'ATENCION', 'SUPERVISION'],
        'dias_semana': [
            (0, 'Lunes'),
            (1, 'Martes'),
            (2, 'Miércoles'),
            (3, 'Jueves'),
            (4, 'Viernes'),
            (5, 'Sábado'),
            (6, 'Domingo'),
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

