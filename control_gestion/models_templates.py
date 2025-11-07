"""
Modelos para Plantillas de Tareas Recurrentes

Permite configurar tareas que se repiten ciertos días de la semana
y se asignan solo a empleados que trabajan ese día.
"""

from django.db import models
from django.contrib.auth import get_user_model
from .models import Swimlane, Priority, TaskSource

User = get_user_model()


class TaskTemplate(models.Model):
    """
    Plantilla para tareas recurrentes
    
    Ejemplo: "Apertura AM - limpieza tinas" se repite lun-vie
    """
    
    DIAS_SEMANA = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    # Información de la tarea
    title_template = models.CharField(
        max_length=160,
        verbose_name="Título plantilla",
        help_text="Puede usar {fecha}, {dia} en el título"
    )
    description = models.TextField(
        verbose_name="Descripción",
        help_text="Descripción completa de la tarea recurrente"
    )
    
    # Configuración
    swimlane = models.CharField(
        max_length=3,
        choices=Swimlane.choices,
        verbose_name="Área"
    )
    priority = models.CharField(
        max_length=8,
        choices=Priority.choices,
        default='NORMAL',
        verbose_name="Prioridad"
    )
    queue_position = models.PositiveIntegerField(
        default=1,
        verbose_name="Posición en cola"
    )
    
    # Días de la semana que aplica (JSONField con lista de días)
    dias_activa = models.JSONField(
        default=list,
        verbose_name="Días activa",
        help_text="Lista de días de semana: [0,1,2,3,4] = Lun-Vie, [1] = Solo martes"
    )
    
    # Asignación
    asignar_a_grupo = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Asignar a grupo",
        help_text="Nombre del grupo (OPERACIONES, RECEPCION, etc.)"
    )
    asignar_a_usuario = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Asignar a usuario específico",
        help_text="Si se especifica, ignora el grupo"
    )
    
    # Control
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Si está inactiva, no se generará"
    )
    
    # Solo para martes (mantenciones especiales)
    solo_martes = models.BooleanField(
        default=False,
        verbose_name="Solo martes",
        help_text="Tarea especial de mantención que solo se genera los martes"
    )
    
    class Meta:
        verbose_name = "Plantilla de Tarea Recurrente"
        verbose_name_plural = "Plantillas de Tareas Recurrentes"
        ordering = ['swimlane', 'queue_position']
    
    def __str__(self):
        dias_str = self.get_dias_str()
        return f"[{self.get_swimlane_display()}] {self.title_template} ({dias_str})"
    
    def get_dias_str(self):
        """Retorna string con días (ej: 'Lun-Vie', 'Mar', etc.)"""
        if not self.dias_activa:
            return "Sin días"
        
        if self.solo_martes:
            return "Solo Martes"
        
        dias_nombres = {0: 'Lun', 1: 'Mar', 2: 'Mié', 3: 'Jue', 4: 'Vie', 5: 'Sáb', 6: 'Dom'}
        
        # Si es lun-vie (0,1,2,3,4)
        if sorted(self.dias_activa) == [0, 1, 2, 3, 4]:
            return "Lun-Vie"
        
        # Si son todos los días
        if len(self.dias_activa) == 7:
            return "Todos los días"
        
        # Mostrar días individuales
        return ", ".join([dias_nombres.get(d, str(d)) for d in sorted(self.dias_activa)])
    
    def aplica_hoy(self):
        """Verifica si esta plantilla aplica para el día actual"""
        from django.utils import timezone
        today = timezone.localdate()
        dia_semana = today.weekday()  # 0=lunes, 1=martes, etc.
        
        # Si es solo martes y hoy es martes
        if self.solo_martes:
            return dia_semana == 1
        
        # Si hoy NO es martes y la tarea NO es solo_martes
        if dia_semana == 1 and not self.solo_martes:
            return False  # Martes = no rutinas normales
        
        # Verificar si hoy está en la lista de días
        return dia_semana in self.dias_activa
    
    def generar_tarea(self, fecha=None):
        """
        Genera una tarea Task a partir de esta plantilla
        
        Returns:
            Task creado o None
        """
        from django.utils import timezone
        from .models import Task, TaskState
        
        if not self.activa:
            return None
        
        if not self.aplica_hoy():
            return None
        
        fecha = fecha or timezone.localdate()
        
        # Formatear título con variables
        title = self.title_template.format(
            fecha=fecha.strftime('%d/%m/%Y'),
            dia=fecha.strftime('%A')
        )
        
        # Determinar responsable
        owner = self.asignar_a_usuario
        if not owner and self.asignar_a_grupo:
            owner = User.objects.filter(groups__name=self.asignar_a_grupo).first()
        if not owner:
            owner = User.objects.first()
        
        # Crear tarea
        task = Task.objects.create(
            title=title,
            description=self.description,
            swimlane=self.swimlane,
            owner=owner,
            created_by=owner,
            state=TaskState.BACKLOG,
            priority=self.priority,
            queue_position=self.queue_position,
            source=TaskSource.RUTINA
        )
        
        return task


class EmpleadoDisponibilidad(models.Model):
    """
    Disponibilidad de empleados por día de la semana
    
    Permite configurar qué días trabaja cada empleado
    """
    
    DIAS_SEMANA = TaskTemplate.DIAS_SEMANA
    
    empleado = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='disponibilidad',
        verbose_name="Empleado"
    )
    
    dias_trabajo = models.JSONField(
        default=list,
        verbose_name="Días que trabaja",
        help_text="Lista de días: [0,1,2,3,4] = Lun-Vie"
    )
    
    notas = models.TextField(
        blank=True,
        verbose_name="Notas",
        help_text="Ej: 'Martes solo medio día', 'Fines de semana a veces'"
    )
    
    class Meta:
        verbose_name = "Disponibilidad de Empleado"
        verbose_name_plural = "Disponibilidad de Empleados"
    
    def __str__(self):
        dias_str = self.get_dias_str()
        return f"{self.empleado.username}: {dias_str}"
    
    def get_dias_str(self):
        """Retorna string con días"""
        if not self.dias_trabajo:
            return "Sin días configurados"
        
        dias_nombres = {0: 'Lun', 1: 'Mar', 2: 'Mié', 3: 'Jue', 4: 'Vie', 5: 'Sáb', 6: 'Dom'}
        
        if sorted(self.dias_trabajo) == [0, 1, 2, 3, 4]:
            return "Lun-Vie"
        if len(self.dias_trabajo) == 7:
            return "Todos los días"
        
        return ", ".join([dias_nombres.get(d, str(d)) for d in sorted(self.dias_trabajo)])
    
    def trabaja_hoy(self):
        """Verifica si el empleado trabaja hoy"""
        from django.utils import timezone
        today = timezone.localdate()
        dia_semana = today.weekday()
        return dia_semana in self.dias_trabajo

