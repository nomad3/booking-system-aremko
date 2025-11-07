"""
Admin para Control de Gestión

Admin completo con inlines, acciones y validaciones para el sistema de tareas.
"""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from .models import Task, ChecklistItem, TaskLog, CustomerSegment, DailyReport, TaskState, Priority


class ChecklistInline(admin.TabularInline):
    """Inline para items de checklist"""
    model = ChecklistItem
    extra = 0
    fields = ('text', 'done')


class TaskLogInline(admin.TabularInline):
    """Inline para logs de la tarea (solo lectura)"""
    model = TaskLog
    extra = 0
    readonly_fields = ('when', 'actor', 'action', 'note')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


# ===== ACCIONES ADMIN =====

@admin.action(description="⬆️ Mover arriba en la cola")
def move_up(modeladmin, request, queryset):
    """Mueve las tareas seleccionadas hacia arriba en la cola"""
    for task in queryset:
        if task.queue_position > 1:
            task.queue_position -= 1
            task.save()
            TaskLog.objects.create(
                task=task,
                actor=request.user,
                action="REORDERED",
                note=f"Movida arriba en cola (posición {task.queue_position})"
            )
    messages.success(request, f"{queryset.count()} tarea(s) movida(s) arriba en la cola.")


@admin.action(description="⬇️ Mover abajo en la cola")
def move_down(modeladmin, request, queryset):
    """Mueve las tareas seleccionadas hacia abajo en la cola"""
    for task in queryset:
        task.queue_position += 1
        task.save()
        TaskLog.objects.create(
            task=task,
            actor=request.user,
            action="REORDERED",
            note=f"Movida abajo en cola (posición {task.queue_position})"
        )
    messages.success(request, f"{queryset.count()} tarea(s) movida(s) abajo en la cola.")


@admin.action(description="▶️ Marcar EN CURSO (respeta WIP=1)")
def mark_in_progress(modeladmin, request, queryset):
    """Marca tareas como en curso, respetando WIP=1"""
    errors = []
    success_count = 0
    
    for task in queryset:
        try:
            task.state = TaskState.IN_PROGRESS
            task.save()
            TaskLog.objects.create(
                task=task,
                actor=request.user,
                action="STARTED",
                note="Tarea iniciada"
            )
            success_count += 1
        except ValidationError as e:
            errors.append(f"{task.title}: {str(e)}")
    
    if success_count > 0:
        messages.success(request, f"✅ {success_count} tarea(s) marcada(s) en curso.")
    
    if errors:
        for error in errors:
            messages.error(request, error)


@admin.action(description="✅ Marcar HECHA")
def mark_done(modeladmin, request, queryset):
    """Marca tareas como completadas"""
    count = queryset.update(state=TaskState.DONE)
    
    for task in queryset:
        TaskLog.objects.create(
            task=task,
            actor=request.user,
            action="DONE",
            note="Tarea completada"
        )
    
    messages.success(request, f"✅ {count} tarea(s) completada(s).")


@admin.action(description="🚫 Marcar BLOQUEADA")
def mark_blocked(modeladmin, request, queryset):
    """Marca tareas como bloqueadas"""
    count = queryset.update(state=TaskState.BLOCKED)
    
    for task in queryset:
        TaskLog.objects.create(
            task=task,
            actor=request.user,
            action="BLOCKED",
            note="Tarea bloqueada"
        )
    
    messages.warning(request, f"🚫 {count} tarea(s) bloqueada(s).")


@admin.action(description="🤖 Generar checklist IA")
def ai_generate_checklist_action(modeladmin, request, queryset):
    """Genera checklist automático usando IA"""
    try:
        from . import ai
        
        count = 0
        for task in queryset:
            # Preparar contexto para IA
            ctx = {
                "swimlane": task.swimlane,
                "servicio": task.service_type,
                "ubicacion": task.location_ref,
                "titulo": task.title,
                "descripcion": task.description[:500]
            }
            
            try:
                items = ai.generate_checklist(ctx)
                
                for item_text in items:
                    ChecklistItem.objects.create(task=task, text=item_text)
                
                TaskLog.objects.create(
                    task=task,
                    actor=request.user,
                    action="COMMENT",
                    note=f"Checklist IA generado ({len(items)} items)"
                )
                count += 1
            except Exception as e:
                messages.warning(request, f"Error generando checklist para '{task.title}': {str(e)}")
        
        if count > 0:
            messages.success(request, f"🤖 Checklist IA generado para {count} tarea(s).")
    
    except ImportError:
        messages.error(request, "⚠️ Módulo de IA no disponible aún (se implementará en Etapa 2)")


# ===== ADMIN DE TASK =====

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'swimlane',
        'owner',
        'state',
        'priority',
        'queue_position',
        'promise_due_at',
        'updated_at',
        'reservation_id'
    )
    list_filter = (
        'swimlane',
        'state',
        'priority',
        'owner',
        'source',
        'created_at'
    )
    search_fields = (
        'title',
        'description',
        'reservation_id',
        'customer_phone_last9',
        'segment_tag'
    )
    
    inlines = [ChecklistInline, TaskLogInline]
    
    actions = [
        move_up,
        move_down,
        mark_in_progress,
        mark_done,
        mark_blocked,
        ai_generate_checklist_action
    ]
    
    readonly_fields = ('created_at', 'updated_at')
    
    list_per_page = 50
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('title', 'description', 'swimlane', 'owner', 'created_by')
        }),
        ('Estado y Prioridad', {
            'fields': ('state', 'priority', 'queue_position', 'promise_due_at', 'source')
        }),
        ('Contexto de Reserva/Cliente', {
            'fields': ('reservation_id', 'customer_phone_last9', 'segment_tag'),
            'classes': ('collapse',)
        }),
        ('Ubicación y Servicio', {
            'fields': ('location_ref', 'service_type'),
            'classes': ('collapse',)
        }),
        ('Evidencia', {
            'fields': ('media',),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Asignar created_by si es nuevo y validar WIP=1"""
        if not change:
            obj.created_by = request.user
        
        try:
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            # Capturar ValidationError (ej: WIP=1) y mostrarlo como mensaje
            from django.contrib import messages
            messages.error(request, str(e))
            # Re-lanzar para que el formulario no se guarde
            raise


# ===== ADMIN DE CUSTOMER SEGMENT =====

@admin.register(CustomerSegment)
class CustomerSegmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_spend', 'max_spend', 'benefit')
    list_filter = ('name',)
    search_fields = ('name', 'benefit')
    ordering = ['min_spend']


# ===== ADMIN DE DAILY REPORT =====

@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ('date', 'generated_at')
    list_filter = ('date',)
    search_fields = ('summary',)
    readonly_fields = ('generated_at',)
    ordering = ['-date']

