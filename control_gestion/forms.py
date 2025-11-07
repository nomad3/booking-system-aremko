"""
Forms para Control de Gestión

Incluye validación de WIP=1 en el formulario para mostrar
errores amigables en el admin.
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import Task, TaskState


class TaskAdminForm(forms.ModelForm):
    """
    Form personalizado para Task que valida WIP=1 antes de save
    
    Esto permite mostrar el error en el formulario del admin
    en vez de un Server Error 500.
    """
    
    class Meta:
        model = Task
        fields = '__all__'
    
    def clean(self):
        """Validar WIP=1 antes de guardar"""
        cleaned_data = super().clean()
        state = cleaned_data.get('state')
        owner = cleaned_data.get('owner')
        
        # Solo validar si el estado es IN_PROGRESS
        if state == TaskState.IN_PROGRESS and owner:
            # Verificar si el owner ya tiene otra tarea en curso
            otras_en_curso = Task.objects.filter(
                owner=owner,
                state=TaskState.IN_PROGRESS
            )
            
            # Si estamos editando una tarea existente, excluirla
            if self.instance and self.instance.pk:
                otras_en_curso = otras_en_curso.exclude(pk=self.instance.pk)
            
            if otras_en_curso.exists():
                tarea_actual = otras_en_curso.first()
                raise ValidationError(
                    f"🚫 WIP=1: El usuario {owner.username} ya tiene una tarea 'En curso': "
                    f"'{tarea_actual.title}'. Debes completarla o bloquearla antes de iniciar otra."
                )
        
        return cleaned_data

