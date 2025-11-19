"""
Forms para Control de Gestión

Se eliminó la validación WIP=1 - los usuarios pueden tener
múltiples tareas en curso simultáneamente.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Task, TaskState, Priority, TimeCriticality, Swimlane

User = get_user_model()


class TaskAdminForm(forms.ModelForm):
    """
    Form personalizado para Task

    Se puede usar para validaciones adicionales en el admin.
    Actualmente sin restricciones especiales.
    """
    
    class Meta:
        model = Task
        fields = '__all__'
    
    def clean(self):
        """Validar datos del formulario"""
        cleaned_data = super().clean()
        # Se eliminó la validación WIP=1 - los usuarios pueden tener múltiples tareas en curso
        return cleaned_data


class EmergencyTaskForm(forms.ModelForm):
    """
    Formulario para crear tareas de emergencia
    """

    # Definir grupos disponibles
    GRUPOS_CHOICES = [
        ('', '-- Sin asignar a grupo --'),
        ('OPERACIONES', 'Operaciones'),
        ('RECEPCION', 'Recepción'),
        ('MUCAMAS', 'Mucamas'),
        ('VENTAS', 'Ventas'),
    ]

    # Campo para asignar a grupo (opcional)
    assign_to_group = forms.ChoiceField(
        label="Asignar a grupo",
        choices=GRUPOS_CHOICES,
        required=False,
        help_text="Selecciona un grupo para asignar la tarea",
        widget=forms.Select(attrs={
            'class': 'form-control'
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

        task.priority = Priority.ALTA_CLIENTE_EN_SITIO
        task.queue_position = 1
        task.state = TaskState.BACKLOG

        # Si se especificó un grupo y no un usuario
        grupo = self.cleaned_data.get('assign_to_group')
        if grupo and not task.owner:
            # TODO: Implementar lógica para asignar automáticamente según el grupo
            # Por ejemplo:
            # - OPERACIONES: Asignar al operador disponible
            # - RECEPCION: Asignar al recepcionista de turno
            # - MUCAMAS: Asignar a la mucama con menos carga
            # - VENTAS: Asignar al vendedor disponible
            # Por ahora la tarea queda sin asignar pero con el grupo registrado
            task.notes = f"[Grupo asignado: {grupo}] {task.notes or ''}"

        if commit:
            task.save()

        return task

