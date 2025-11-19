"""
Forms para Control de Gestión

Incluye validación de WIP=1 en el formulario para mostrar
errores amigables en el admin.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Task, TaskState, Priority, TimeCriticality, Swimlane

User = get_user_model()


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


class EmergencyTaskForm(forms.ModelForm):
    """
    Formulario para crear tareas de emergencia
    """

    # Campo para asignar a grupo (opcional)
    assign_to_group = forms.CharField(
        label="Asignar a grupo",
        required=False,
        help_text="Nombre del grupo (OPERACIONES, RECEPCION, etc)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: OPERACIONES, RECEPCION'
        })
    )

    # Campo para asignar a usuario específico
    owner = forms.ModelChoiceField(
        label="Asignar a usuario específico",
        queryset=User.objects.filter(is_active=True),
        required=False,
        empty_label="Sin asignar",
        help_text="Si se especifica, ignora el grupo",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    class Meta:
        model = Task
        fields = ['title', 'description', 'swimlane', 'owner']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Título de la emergencia',
                'autofocus': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descripción completa de la emergencia'
            }),
            'swimlane': forms.Select(attrs={
                'class': 'form-control'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer que los campos sean requeridos con mensajes personalizados
        self.fields['title'].required = True
        self.fields['title'].error_messages = {'required': 'El título de la emergencia es obligatorio'}

        self.fields['description'].required = True
        self.fields['description'].label = "Descripción"
        self.fields['description'].error_messages = {'required': 'La descripción es obligatoria'}

        self.fields['swimlane'].label = "Área"
        self.fields['swimlane'].required = True
        self.fields['swimlane'].error_messages = {'required': 'Debes seleccionar un área'}

    def save(self, commit=True):
        task = super().save(commit=False)

        # Configurar valores predefinidos para emergencia
        task.time_criticality = TimeCriticality.EMERGENCY

        task.priority = Priority.ALTA
        task.queue_position = 1
        task.state = TaskState.BACKLOG

        # Si se especificó un grupo y no un usuario
        if self.cleaned_data.get('assign_to_group') and not task.owner:
            # Aquí se podría implementar la lógica para asignar según el grupo
            # Por ahora lo dejamos sin asignar si no se especifica usuario
            pass

        if commit:
            task.save()

        return task

