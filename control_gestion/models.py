"""
Modelos para Control de Gestión - Sistema de tareas operativas

Este módulo implementa un sistema de gestión de tareas con:
- Tareas organizadas por swimlanes (áreas)
- Cola priorizada por tarea
- Regla WIP=1 (una tarea en curso por persona)
- Integración con sistema de reservas
"""

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Swimlane(models.TextChoices):
    """Áreas de trabajo (swimlanes)"""
    COMERCIAL = "COM", "Comercial"
    ATENCION = "CS", "Atención Cliente"
    OPERACION = "OPS", "Operación"
    RECEPCION = "RX", "Recepción"
    SUPERVISION = "SUP", "Marketing y Supervisión"
    MUCAMA = "MUC", "Mucama"


class TaskState(models.TextChoices):
    """Estados posibles de una tarea"""
    BACKLOG = "BACKLOG", "Backlog"
    IN_PROGRESS = "IN_PROGRESS", "En curso"
    BLOCKED = "BLOCKED", "Bloqueada"
    DONE = "DONE", "Hecha"


class Priority(models.TextChoices):
    """Niveles de prioridad"""
    NORMAL = "NORMAL", "Normal"
    ALTA_CLIENTE_EN_SITIO = "ALTA", "Alta (Cliente en sitio)"


class TaskSource(models.TextChoices):
    """Origen de la tarea"""
    IDEA = "IDEA", "Idea"
    INCIDENTE = "INCIDENTE", "Incidente"
    SOLICITUD = "SOLICITUD", "Solicitud Cliente"
    RUTINA = "RUTINA", "Rutina"
    SISTEMA = "SISTEMA", "Sistema"


class LocationRef(models.TextChoices):
    """Referencias de ubicación en el spa"""
    RECEPCION = "RECEPCION", "Recepción"
    CAFETERIA = "CAFETERIA", "Cafetería"
    TINA_1 = "TINA_1", "Tina 1"
    TINA_2 = "TINA_2", "Tina 2"
    TINA_3 = "TINA_3", "Tina 3"
    TINA_4 = "TINA_4", "Tina 4"
    TINA_5 = "TINA_5", "Tina 5"
    TINA_6 = "TINA_6", "Tina 6"
    TINA_7 = "TINA_7", "Tina 7"
    TINA_8 = "TINA_8", "Tina 8"
    SALA_1 = "SALA_1", "Sala 1"
    SALA_2 = "SALA_2", "Sala 2"
    SALA_3 = "SALA_3", "Sala 3"
    CAB_1 = "CAB_1", "Cabaña 1"
    CAB_2 = "CAB_2", "Cabaña 2"
    CAB_3 = "CAB_3", "Cabaña 3"
    CAB_4 = "CAB_4", "Cabaña 4"
    CAB_5 = "CAB_5", "Cabaña 5"


class Task(models.Model):
    """
    Tarea operativa del sistema de Control de Gestión
    
    Las tareas se organizan por swimlane (área) y tienen un orden de prioridad
    dentro de cada swimlane. Se aplica la regla WIP=1 (Work In Progress = 1)
    para cada responsable.
    """
    
    # Información básica
    title = models.CharField(
        max_length=160,
        verbose_name="Título",
        help_text="Título corto y descriptivo de la tarea"
    )
    description = models.TextField(
        verbose_name="Descripción",
        help_text="Descripción detallada de la tarea"
    )
    
    # Organización
    swimlane = models.CharField(
        max_length=3,
        choices=Swimlane.choices,
        verbose_name="Área",
        help_text="Área responsable de la tarea"
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_tasks",
        verbose_name="Responsable",
        help_text="Persona asignada a la tarea"
    )
    
    # Estado y prioridad
    state = models.CharField(
        max_length=12,
        choices=TaskState.choices,
        default=TaskState.BACKLOG,
        verbose_name="Estado"
    )
    source = models.CharField(
        max_length=12,
        choices=TaskSource.choices,
        default=TaskSource.RUTINA,
        verbose_name="Origen"
    )
    priority = models.CharField(
        max_length=8,
        choices=Priority.choices,
        default=Priority.NORMAL,
        verbose_name="Prioridad"
    )
    queue_position = models.PositiveIntegerField(
        default=1,
        db_index=True,
        verbose_name="Posición en cola",
        help_text="Orden en la cola de tareas del swimlane"
    )
    
    # Fechas
    promise_due_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Promesa de entrega",
        help_text="Fecha/hora comprometida para completar la tarea"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_tasks",
        verbose_name="Creado por"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    
    # Contexto de reserva/cliente (sin ForeignKey, solo referencia)
    reservation_id = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="ID Reserva",
        help_text="Identificador de la reserva relacionada (sin ForeignKey)"
    )
    customer_phone_last9 = models.CharField(
        max_length=9,
        blank=True,
        verbose_name="Teléfono cliente (últimos 9)",
        help_text="Últimos 9 dígitos del teléfono del cliente (sin +56)"
    )
    
    # Ubicación y servicio
    location_ref = models.CharField(
        max_length=16,
        choices=LocationRef.choices,
        blank=True,
        verbose_name="Ubicación",
        help_text="Ubicación física relacionada con la tarea"
    )
    service_type = models.CharField(
        max_length=32,
        blank=True,
        verbose_name="Tipo de servicio",
        help_text="Tipo: TINA_SIMPLE, TINA_HIDRO, MASAJE, CABANA, F&B"
    )
    segment_tag = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Segmento/Tramo",
        help_text="Segmento del cliente: BRONCE/PLATA/ORO/DIAMANTE o Tramo N"
    )
    
    # Media
    media = models.FileField(
        upload_to="task_media/",
        null=True,
        blank=True,
        verbose_name="Archivo adjunto",
        help_text="Foto, documento o evidencia relacionada"
    )
    
    class Meta:
        ordering = ["swimlane", "queue_position", "created_at"]
        verbose_name = "Tarea"
        verbose_name_plural = "Tareas"
        indexes = [
            models.Index(fields=["swimlane", "queue_position"]),
            models.Index(fields=["owner", "state"]),
            models.Index(fields=["state", "promise_due_at"]),
        ]
    
    def __str__(self):
        return f"[{self.get_swimlane_display()}] {self.title}"


class ChecklistItem(models.Model):
    """
    Item de checklist asociado a una tarea
    
    Las tareas pueden tener múltiples items de checklist que ayudan
    a verificar que todos los pasos se completaron correctamente.
    """
    
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="checklist",
        verbose_name="Tarea"
    )
    text = models.CharField(
        max_length=180,
        verbose_name="Texto",
        help_text="Descripción del ítem del checklist"
    )
    done = models.BooleanField(
        default=False,
        verbose_name="Completado"
    )
    
    class Meta:
        ordering = ["id"]
        verbose_name = "Item de Checklist"
        verbose_name_plural = "Items de Checklist"
    
    def __str__(self):
        return f"{'✔' if self.done else '□'} {self.text}"


class TaskLog(models.Model):
    """
    Log de acciones realizadas sobre una tarea
    
    Registra todas las acciones importantes: creación, cambios de estado,
    reasignaciones, comentarios, etc.
    """
    
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="Tarea"
    )
    when = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Cuándo"
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name="Quién"
    )
    action = models.CharField(
        max_length=50,
        verbose_name="Acción",
        help_text="CREATED/UPDATED/STARTED/BLOCKED/UNBLOCKED/REORDERED/DONE/COMMENT/PROMISE_MOVED/QA_RESULT"
    )
    note = models.TextField(
        blank=True,
        verbose_name="Nota",
        help_text="Detalles adicionales de la acción"
    )
    
    class Meta:
        ordering = ["-when"]
        verbose_name = "Log de Tarea"
        verbose_name_plural = "Logs de Tareas"
        indexes = [
            models.Index(fields=["task", "-when"]),
        ]
    
    def __str__(self):
        return f"{self.when.strftime('%Y-%m-%d %H:%M')} - {self.actor} - {self.action}"


class CustomerSegment(models.Model):
    """
    Definición de segmentos de clientes
    
    Complementa el sistema de tramos del módulo ventas, definiendo
    beneficios y rangos de gasto para cada segmento.
    """
    
    name = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Nombre",
        help_text="Nombre del segmento: ORO, PLATA, Tramo N, etc."
    )
    min_spend = models.PositiveIntegerField(
        verbose_name="Gasto mínimo",
        help_text="Gasto mínimo en CLP para este segmento"
    )
    max_spend = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Gasto máximo",
        help_text="Gasto máximo en CLP (null = sin límite)"
    )
    benefit = models.CharField(
        max_length=120,
        verbose_name="Beneficio",
        help_text="Descripción del beneficio del segmento"
    )
    
    class Meta:
        ordering = ["min_spend"]
        verbose_name = "Segmento de Cliente"
        verbose_name_plural = "Segmentos de Clientes"
    
    def __str__(self):
        max_str = f"{self.max_spend:,}" if self.max_spend else "∞"
        return f"{self.name} (${self.min_spend:,} - ${max_str})"


class DailyReport(models.Model):
    """
    Reporte diario generado por IA
    
    Se generan reportes automáticos con resumen de tareas completadas,
    pendientes, bloqueadas y prioridades para el siguiente día.
    """
    
    date = models.DateField(
        verbose_name="Fecha",
        help_text="Fecha del reporte"
    )
    generated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Generado el"
    )
    summary = models.TextField(
        verbose_name="Resumen",
        help_text="Resumen generado por IA del día"
    )
    
    class Meta:
        ordering = ["-date"]
        verbose_name = "Reporte Diario"
        verbose_name_plural = "Reportes Diarios"
        indexes = [
            models.Index(fields=["-date"]),
        ]
    
    def __str__(self):
        return f"Reporte {self.date.strftime('%Y-%m-%d')}"


# Importar modelos adicionales de templates
from .models_templates import TaskTemplate, EmpleadoDisponibilidad

__all__ = [
    'Task', 'ChecklistItem', 'TaskLog', 'CustomerSegment', 'DailyReport',
    'TaskTemplate', 'EmpleadoDisponibilidad',
    'Swimlane', 'TaskState', 'Priority', 'TaskSource', 'LocationRef'
]

