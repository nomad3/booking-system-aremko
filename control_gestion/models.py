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
    BACKLOG = "BACKLOG", "Por Ejecutar"
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


class TimeCriticality(models.TextChoices):
    """Criticidad temporal de la tarea"""
    EMERGENCY = "EMERGENCY", "Emergencia - Ejecución inmediata"
    CRITICAL = "CRITICAL", "Crítica - Hora exacta"
    SCHEDULED = "SCHEDULED", "Programada - Rango horario"
    FLEXIBLE = "FLEXIBLE", "Flexible - Durante el día"


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
    dentro de cada swimlane. Los usuarios pueden trabajar en múltiples tareas
    simultáneamente sin restricciones.
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
    time_criticality = models.CharField(
        max_length=12,
        choices=TimeCriticality.choices,
        default=TimeCriticality.FLEXIBLE,
        verbose_name="Criticidad Temporal",
        help_text="Define la urgencia temporal: CRITICAL=hora exacta, FLEXIBLE=durante el día"
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


class TaskOwnerConfig(models.Model):
    """
    Configuración de responsables por tipo de tarea automática

    Permite configurar desde Django Admin quién debe ser responsable
    de cada tipo de tarea generada automáticamente, sin hardcodear
    en el código.

    Ejemplo de uso:
    - Tipo "preparacion_servicio" → Usuario Ernesto (Operación)
    - Tipo "vaciado_tina" → Grupo OPERACIONES
    - Tipo "monitoreo_temperatura" → Usuario Jorge (Comercial)
    """

    class TipoTarea(models.TextChoices):
        PREPARACION_SERVICIO = 'preparacion_servicio', 'Preparación de Servicio (1h antes)'
        VACIADO_TINA = 'vaciado_tina', 'Vaciado de Tina (después del servicio)'
        ATENCION_CLIENTES = 'atencion_clientes', 'Atención de Clientes en Servicio (20 min después check-in)'
        APERTURA_AM = 'apertura_am', 'Apertura AM - Limpieza'
        REPORTE_DIARIO = 'reporte_diario', 'Reporte Diario'
        MONITOREO = 'monitoreo', 'Monitoreo General'
        MANTENCION = 'mantencion', 'Mantención y Reparaciones'
        ALIMENTACION = 'alimentacion', 'Alimentación de Animales'
        OTROS = 'otros', 'Otros (por defecto)'

    # Identificación del tipo de tarea
    tipo_tarea = models.CharField(
        max_length=32,
        choices=TipoTarea.choices,
        unique=True,
        verbose_name="Tipo de Tarea",
        help_text="Tipo de tarea automática a configurar"
    )

    # Asignación (prioridad: usuario específico > grupo > fallback)
    asignar_a_usuario = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_owner_configs',
        verbose_name="Asignar a Usuario",
        help_text="Usuario específico (tiene prioridad sobre grupo)"
    )

    asignar_a_grupo = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Asignar a Grupo",
        help_text="Nombre del grupo (ej: OPERACIONES, RECEPCION, COMERCIAL)"
    )

    usuario_fallback = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_owner_fallback_configs',
        verbose_name="Usuario Fallback",
        help_text="Usuario a usar si no se encuentra el usuario/grupo configurado"
    )

    # Metadata
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Si está inactivo, usará comportamiento por defecto del sistema"
    )

    notas = models.TextField(
        blank=True,
        verbose_name="Notas",
        help_text="Notas internas sobre esta configuración"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )

    class Meta:
        verbose_name = "Configuración de Responsable"
        verbose_name_plural = "Configuraciones de Responsables"
        ordering = ['tipo_tarea']

    def __str__(self):
        asignado = self.get_asignado_display()
        return f"{self.get_tipo_tarea_display()} → {asignado}"

    def get_asignado_display(self):
        """Retorna string con información de asignación"""
        if self.asignar_a_usuario:
            return f"{self.asignar_a_usuario.username} (usuario)"
        elif self.asignar_a_grupo:
            return f"{self.asignar_a_grupo} (grupo)"
        elif self.usuario_fallback:
            return f"{self.usuario_fallback.username} (fallback)"
        else:
            return "Sin configurar"

    def obtener_responsable(self):
        """
        Obtiene el usuario responsable según la configuración

        Lógica de prioridad:
        1. Usuario específico configurado
        2. Primer usuario del grupo configurado
        3. Usuario fallback
        4. Primer usuario del sistema (último recurso)

        Returns:
            User: Usuario responsable
        """
        # Prioridad 1: Usuario específico
        if self.asignar_a_usuario:
            return self.asignar_a_usuario

        # Prioridad 2: Primer usuario del grupo
        if self.asignar_a_grupo:
            usuario_grupo = User.objects.filter(
                groups__name=self.asignar_a_grupo
            ).first()
            if usuario_grupo:
                return usuario_grupo

        # Prioridad 3: Usuario fallback
        if self.usuario_fallback:
            return self.usuario_fallback

        # Prioridad 4: Primer usuario del sistema (último recurso)
        return User.objects.first()

    @classmethod
    def obtener_responsable_por_tipo(cls, tipo_tarea: str):
        """
        Método de clase para obtener responsable por tipo de tarea

        Args:
            tipo_tarea: String del tipo (ej: 'preparacion_servicio')

        Returns:
            User: Usuario responsable o None si no existe configuración

        Ejemplo de uso:
            owner = TaskOwnerConfig.obtener_responsable_por_tipo('preparacion_servicio')
            if not owner:
                owner = User.objects.first()  # Fallback manual
        """
        try:
            config = cls.objects.get(tipo_tarea=tipo_tarea, activo=True)
            return config.obtener_responsable()
        except cls.DoesNotExist:
            return None


# Importar modelos adicionales de templates
from .models_templates import TaskTemplate, EmpleadoDisponibilidad

__all__ = [
    'Task', 'ChecklistItem', 'TaskLog', 'CustomerSegment', 'DailyReport',
    'TaskOwnerConfig',
    'TaskTemplate', 'EmpleadoDisponibilidad',
    'Swimlane', 'TaskState', 'Priority', 'TaskSource', 'LocationRef', 'TimeCriticality'
]

