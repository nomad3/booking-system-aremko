"""
Formulario para gestionar Packs de Descuento
"""
from django import forms
from django.core.exceptions import ValidationError
from ..models import PackDescuento, Servicio
import json


class PackDescuentoForm(forms.ModelForm):
    """Formulario para crear/editar packs de descuento"""

    # Días de la semana como checkboxes
    DIAS_CHOICES = [
        (0, 'Domingo'),
        (1, 'Lunes'),
        (2, 'Martes'),
        (3, 'Miércoles'),
        (4, 'Jueves'),
        (5, 'Viernes'),
        (6, 'Sábado'),
    ]

    dias_semana = forms.MultipleChoiceField(
        choices=DIAS_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Días de la semana válidos',
        help_text='Selecciona los días en que aplica el descuento'
    )

    # Servicios específicos - Mostrar SOLO servicios publicados en web
    # Filtrar por publicado_web=True para mostrar solo servicios visibles en www.aremko.cl
    servicios_especificos = forms.ModelMultipleChoiceField(
        queryset=Servicio.objects.filter(
            publicado_web=True  # Solo servicios visibles en la web
        ).order_by('nombre'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Servicios específicos del pack',
        help_text='Selecciona los servicios que forman este pack (solo servicios publicados en web)'
    )

    # Tipo de pack
    tipo_pack = forms.ChoiceField(
        choices=[
            ('especifico', 'Servicios Específicos (ej: Cabaña Torre + Tina Puyehue)'),
            ('por_tipo', 'Por Tipo de Servicio (ej: Cualquier Cabaña + Cualquier Tina)')
        ],
        initial='especifico',
        widget=forms.RadioSelect,
        label='Tipo de Pack'
    )

    class Meta:
        model = PackDescuento
        fields = [
            'nombre', 'descripcion', 'descuento', 'activo',
            'fecha_inicio', 'fecha_fin', 'prioridad',
            'cantidad_minima_noches', 'misma_fecha'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Pack Romance Puyehue'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe el pack y sus beneficios'
            }),
            'descuento': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Monto en pesos chilenos',
                'min': '0'
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'fecha_fin': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'prioridad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100'
            }),
            'cantidad_minima_noches': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '30'
            })
        }
        labels = {
            'misma_fecha': '¿Los servicios deben ser para la misma fecha?',
            'cantidad_minima_noches': 'Noches mínimas de alojamiento'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Personalizar cómo se muestran los servicios en el formulario
        self.fields['servicios_especificos'].label_from_instance = lambda obj: f"{obj.nombre} (${obj.precio_base:,.0f}) {'✓' if obj.activo else '✗'}"

        # SIEMPRE agregar el campo tipos_servicio (no solo cuando editamos)
        self.fields['tipos_servicio'] = forms.MultipleChoiceField(
            choices=PackDescuento.TIPO_SERVICIO_CHOICES,
            widget=forms.CheckboxSelectMultiple,
            required=False,
            label='Tipos de servicio requeridos'
        )

        # Si estamos editando
        if self.instance.pk:
            # Cargar días de la semana
            self.fields['dias_semana'].initial = self.instance.dias_semana_validos

            # Determinar tipo de pack
            if self.instance.usa_servicios_especificos:
                self.fields['tipo_pack'].initial = 'especifico'
            else:
                self.fields['tipo_pack'].initial = 'por_tipo'
                # Cargar tipos de servicio seleccionados
                self.fields['tipos_servicio'].initial = self.instance.servicios_requeridos

    def clean(self):
        cleaned_data = super().clean()
        tipo_pack = cleaned_data.get('tipo_pack')
        servicios_especificos = cleaned_data.get('servicios_especificos')

        # Validar que se seleccionaron servicios si el pack es específico
        if tipo_pack == 'especifico' and not servicios_especificos:
            raise ValidationError('Debes seleccionar al menos un servicio específico')

        # Si es pack por tipo, necesitamos los tipos de servicio
        if tipo_pack == 'por_tipo':
            tipos_servicio = self.data.getlist('tipos_servicio')
            if not tipos_servicio:
                raise ValidationError('Debes seleccionar al menos un tipo de servicio')
            cleaned_data['tipos_servicio'] = tipos_servicio

        return cleaned_data

    def save(self, commit=True):
        pack = super().save(commit=False)

        # Guardar días de la semana
        dias_semana = self.cleaned_data.get('dias_semana', [])
        pack.dias_semana_validos = [int(dia) for dia in dias_semana]

        # Configurar según tipo de pack
        if self.cleaned_data['tipo_pack'] == 'especifico':
            pack.usa_servicios_especificos = True
            pack.servicios_requeridos = []  # Limpiar tipos
        else:
            pack.usa_servicios_especificos = False
            pack.servicios_requeridos = self.cleaned_data.get('tipos_servicio', [])

        if commit:
            pack.save()

            # Guardar servicios específicos si aplica
            if pack.usa_servicios_especificos:
                pack.servicios_especificos.set(self.cleaned_data.get('servicios_especificos', []))

        return pack