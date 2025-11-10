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

    Soporta múltiples frecuencias:
    - DIARIA: Se repite ciertos días de la semana
    - SEMANAL: Se repite cada N semanas
    - MENSUAL: Se repite cierto día del mes
    - TRIMESTRAL: Se repite cada 3 meses
    - SEMESTRAL: Se repite cada 6 meses
    - ANUAL: Se repite una vez al año
    """

    class Frecuencia(models.TextChoices):
        DIARIA = 'DIARIA', 'Diaria (ciertos días de semana)'
        SEMANAL = 'SEMANAL', 'Semanal (cada N semanas)'
        MENSUAL = 'MENSUAL', 'Mensual (cierto día del mes)'
        TRIMESTRAL = 'TRIMESTRAL', 'Trimestral (cada 3 meses)'
        SEMESTRAL = 'SEMESTRAL', 'Semestral (cada 6 meses)'
        ANUAL = 'ANUAL', 'Anual (una vez al año)'

    DIAS_SEMANA = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]

    MESES = [
        (1, 'Enero'),
        (2, 'Febrero'),
        (3, 'Marzo'),
        (4, 'Abril'),
        (5, 'Mayo'),
        (6, 'Junio'),
        (7, 'Julio'),
        (8, 'Agosto'),
        (9, 'Septiembre'),
        (10, 'Octubre'),
        (11, 'Noviembre'),
        (12, 'Diciembre'),
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

    # ===== FRECUENCIA Y PERIODICIDAD =====
    frecuencia = models.CharField(
        max_length=12,
        choices=Frecuencia.choices,
        default=Frecuencia.DIARIA,
        verbose_name="Frecuencia",
        help_text="Con qué frecuencia se repite esta tarea"
    )

    # Para tareas DIARIAS: días de la semana que aplica (JSONField con lista de días)
    dias_activa = models.JSONField(
        default=list,
        verbose_name="Días activa",
        help_text="Solo para frecuencia DIARIA: [0,1,2,3,4] = Lun-Vie, [1] = Solo martes"
    )

    # Para tareas MENSUALES/TRIMESTRALES/SEMESTRALES/ANUALES: día del mes
    dia_del_mes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Día del mes",
        help_text="Para frecuencias MENSUAL/TRIMESTRAL/SEMESTRAL/ANUAL: día del mes (1-31, 0 = último día)"
    )

    # Para tareas TRIMESTRALES/SEMESTRALES/ANUALES: mes de inicio
    mes_inicio = models.PositiveIntegerField(
        null=True,
        blank=True,
        choices=MESES,
        verbose_name="Mes de inicio",
        help_text="Para TRIMESTRAL/SEMESTRAL/ANUAL: mes en que comienza el ciclo"
    )

    # Control de última generación (para evitar duplicados)
    ultima_generacion = models.DateField(
        null=True,
        blank=True,
        verbose_name="Última generación",
        help_text="Fecha en que se generó la última tarea (control interno)"
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
        """Retorna string con descripción de frecuencia (ej: 'Lun-Vie', 'Mensual día 1', etc.)"""

        # ===== FRECUENCIA DIARIA =====
        if self.frecuencia == self.Frecuencia.DIARIA:
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

        # ===== FRECUENCIA MENSUAL =====
        elif self.frecuencia == self.Frecuencia.MENSUAL:
            if not self.dia_del_mes:
                return "Mensual (sin día configurado)"
            if self.dia_del_mes == 0:
                return "Mensual - último día"
            return f"Mensual - día {self.dia_del_mes}"

        # ===== FRECUENCIA TRIMESTRAL =====
        elif self.frecuencia == self.Frecuencia.TRIMESTRAL:
            if not self.dia_del_mes or not self.mes_inicio:
                return "Trimestral (sin configurar)"
            mes_nombre = dict(self.MESES).get(self.mes_inicio, str(self.mes_inicio))
            return f"Trimestral - día {self.dia_del_mes} (inicia {mes_nombre})"

        # ===== FRECUENCIA SEMESTRAL =====
        elif self.frecuencia == self.Frecuencia.SEMESTRAL:
            if not self.dia_del_mes or not self.mes_inicio:
                return "Semestral (sin configurar)"
            mes_nombre = dict(self.MESES).get(self.mes_inicio, str(self.mes_inicio))
            return f"Semestral - día {self.dia_del_mes} (inicia {mes_nombre})"

        # ===== FRECUENCIA ANUAL =====
        elif self.frecuencia == self.Frecuencia.ANUAL:
            if not self.dia_del_mes or not self.mes_inicio:
                return "Anual (sin configurar)"
            mes_nombre = dict(self.MESES).get(self.mes_inicio, str(self.mes_inicio))
            return f"Anual - {self.dia_del_mes} de {mes_nombre}"

        return str(self.frecuencia)
    
    def aplica_hoy(self):
        """
        Verifica si esta plantilla aplica para el día actual

        Soporta múltiples frecuencias:
        - DIARIA: Verifica días de semana
        - MENSUAL: Verifica día del mes
        - TRIMESTRAL: Verifica si es tiempo de generar (cada 3 meses)
        - SEMESTRAL: Verifica si es tiempo de generar (cada 6 meses)
        - ANUAL: Verifica si es el mes y día configurado
        """
        from django.utils import timezone
        from dateutil.relativedelta import relativedelta

        today = timezone.localdate()
        dia_semana = today.weekday()  # 0=lunes, 1=martes, etc.

        # ===== FRECUENCIA DIARIA =====
        if self.frecuencia == self.Frecuencia.DIARIA:
            # Si es solo martes y hoy es martes
            if self.solo_martes:
                return dia_semana == 1

            # Si hoy NO es martes y la tarea NO es solo_martes
            if dia_semana == 1 and not self.solo_martes:
                return False  # Martes = no rutinas normales

            # Verificar si hoy está en la lista de días
            return dia_semana in self.dias_activa

        # ===== FRECUENCIA MENSUAL =====
        elif self.frecuencia == self.Frecuencia.MENSUAL:
            if not self.dia_del_mes:
                return False

            # Día 0 = último día del mes
            if self.dia_del_mes == 0:
                import calendar
                ultimo_dia = calendar.monthrange(today.year, today.month)[1]
                return today.day == ultimo_dia

            # Verificar si hoy es el día configurado
            return today.day == self.dia_del_mes

        # ===== FRECUENCIA TRIMESTRAL =====
        elif self.frecuencia == self.Frecuencia.TRIMESTRAL:
            if not self.dia_del_mes or not self.mes_inicio:
                return False

            # Verificar si hoy es el día configurado
            if today.day != self.dia_del_mes:
                return False

            # Calcular si es un mes trimestral desde mes_inicio
            # Ej: mes_inicio=1 (Enero) → genera en Enero, Abril, Julio, Octubre
            meses_desde_inicio = (today.month - self.mes_inicio) % 12
            if meses_desde_inicio % 3 != 0:
                return False

            # Verificar que no se haya generado ya este mes
            if self.ultima_generacion:
                if self.ultima_generacion.year == today.year and self.ultima_generacion.month == today.month:
                    return False  # Ya se generó este mes

            return True

        # ===== FRECUENCIA SEMESTRAL =====
        elif self.frecuencia == self.Frecuencia.SEMESTRAL:
            if not self.dia_del_mes or not self.mes_inicio:
                return False

            # Verificar si hoy es el día configurado
            if today.day != self.dia_del_mes:
                return False

            # Calcular si es un mes semestral desde mes_inicio
            # Ej: mes_inicio=1 (Enero) → genera en Enero y Julio
            meses_desde_inicio = (today.month - self.mes_inicio) % 12
            if meses_desde_inicio % 6 != 0:
                return False

            # Verificar que no se haya generado ya este mes
            if self.ultima_generacion:
                if self.ultima_generacion.year == today.year and self.ultima_generacion.month == today.month:
                    return False

            return True

        # ===== FRECUENCIA ANUAL =====
        elif self.frecuencia == self.Frecuencia.ANUAL:
            if not self.dia_del_mes or not self.mes_inicio:
                return False

            # Verificar si hoy es el mes y día configurado
            if today.month != self.mes_inicio or today.day != self.dia_del_mes:
                return False

            # Verificar que no se haya generado ya este año
            if self.ultima_generacion:
                if self.ultima_generacion.year == today.year:
                    return False

            return True

        return False
    
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

        # Actualizar última generación (para tareas no diarias)
        if self.frecuencia != self.Frecuencia.DIARIA:
            self.ultima_generacion = fecha
            self.save(update_fields=['ultima_generacion'])

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

