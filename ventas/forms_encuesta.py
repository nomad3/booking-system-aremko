"""
Form para la encuesta de satisfacción (Tarea 1.4 plan maestro).

Reemplaza el Google Form externo. Captura nativa a BD para análisis IA semanal.
"""
from django import forms
from .models import EncuestaSatisfaccion


SERVICIOS_CHOICES = [
    ('tina_hidromasaje', 'Tina con hidromasaje'),
    ('tina_sin_hidromasaje', 'Tina sin hidromasaje'),
    ('masaje', 'Masaje'),
    ('alojamiento', 'Alojamiento (cabaña)'),
]


class EncuestaSatisfaccionForm(forms.ModelForm):
    """ModelForm con widgets custom: calificaciones radio 1-5, NPS radio 0-10."""

    servicios_contratados = forms.MultipleChoiceField(
        choices=SERVICIOS_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label='¿Qué servicios contrataste durante tu visita?',
        help_text='Marca todos los que correspondan',
    )

    class Meta:
        model = EncuestaSatisfaccion
        fields = [
            # Datos contacto
            'contacto_nombre', 'contacto_email', 'contacto_telefono',
            # Servicios
            'servicios_contratados',
            # Calificaciones operativas (opcionales según servicio)
            'cal_temperatura_tina', 'cal_transparencia_agua', 'cal_limpieza_tinas',
            'cal_limpieza_cabana', 'cal_temperatura_cabana',
            'cal_limpieza_sala_masajes', 'cal_servicio_masajes',
            # Calificaciones comerciales
            'cal_calidad_precio', 'cal_atencion_ventas', 'cal_compra_web', 'cal_atencion_visita',
            # General + NPS
            'cal_experiencia_general', 'nps_score',
            # Texto libre
            'lo_que_mas_gusto', 'sugerencias', 'decepcion',
            # Comercial / segmentación
            'como_se_entero', 'como_se_entero_otro',
            'ocasion_visita', 'intencion_volver',
            # Permisos
            'permite_uso_comentarios_redes', 'quiere_newsletter', 'permite_seguimiento',
        ]
        widgets = {
            'contacto_nombre': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Nombre y apellido'
            }),
            'contacto_email': forms.EmailInput(attrs={
                'class': 'form-control', 'placeholder': 'tu@email.com'
            }),
            'contacto_telefono': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': '+56 9 1234 5678',
                'inputmode': 'tel', 'autocomplete': 'tel',
            }),
            'lo_que_mas_gusto': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Lo que recordarás de Aremko...'
            }),
            'sugerencias': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Algo que podemos mejorar...'
            }),
            'decepcion': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Si hubo algo que no cumplió tus expectativas, contanos acá'
            }),
            'como_se_entero_otro': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Especificar...'
            }),
            'como_se_entero': forms.Select(attrs={'class': 'form-select'}),
            'ocasion_visita': forms.Select(attrs={'class': 'form-select'}),
            'intencion_volver': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'contacto_nombre': 'Tu nombre',
            'contacto_email': 'Tu email',
            'contacto_telefono': 'Tu teléfono (opcional)',
            'cal_temperatura_tina': 'Temperatura del agua de la tina',
            'cal_transparencia_agua': 'Transparencia del agua de la tina',
            'cal_limpieza_tinas': 'Limpieza de las tinas y su entorno',
            'cal_limpieza_cabana': 'Limpieza de la cabaña',
            'cal_temperatura_cabana': 'Temperatura de la cabaña',
            'cal_limpieza_sala_masajes': 'Limpieza de la sala de masajes',
            'cal_servicio_masajes': 'Calidad del servicio de masajes',
            'cal_calidad_precio': 'Relación calidad-precio',
            'cal_atencion_ventas': 'Atención por WhatsApp / Instagram / Facebook',
            'cal_compra_web': 'Facilidad de la compra a través de la web',
            'cal_atencion_visita': 'Atención del personal durante tu visita',
            'cal_experiencia_general': '¿Cómo calificarías tu experiencia general?',
            'nps_score': '¿Recomendarías Aremko a un amigo o familiar?',
            'lo_que_mas_gusto': '¿Qué fue lo que más te gustó?',
            'sugerencias': '¿Qué podríamos mejorar?',
            'decepcion': '¿Hubo algo que te decepcionó?',
            'como_se_entero': '¿Cómo nos conociste?',
            'como_se_entero_otro': 'Si elegiste "Otro", contanos',
            'ocasion_visita': '¿En qué ocasión nos visitaste?',
            'intencion_volver': '¿Volverías a visitarnos?',
            'permite_uso_comentarios_redes': 'Acepto que Aremko use mis comentarios (anónimos) en redes sociales',
            'quiere_newsletter': 'Quiero recibir el newsletter mensual de Aremko',
            'permite_seguimiento': '¿Podemos contactarte si necesitamos más información sobre tus comentarios?',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Marcar como obligatorios solo los esenciales
        for nombre_campo in [
            'contacto_nombre', 'contacto_email',
            'cal_experiencia_general',
            'cal_calidad_precio', 'cal_atencion_visita',
            'nps_score',
            'como_se_entero', 'ocasion_visita',
        ]:
            if nombre_campo in self.fields:
                self.fields[nombre_campo].required = True

        # El resto, opcional explícito (algunos heredan required del modelo)
        for nombre_campo in [
            'contacto_telefono',
            'cal_temperatura_tina', 'cal_transparencia_agua', 'cal_limpieza_tinas',
            'cal_limpieza_cabana', 'cal_temperatura_cabana',
            'cal_limpieza_sala_masajes', 'cal_servicio_masajes',
            'cal_atencion_ventas', 'cal_compra_web',
            'lo_que_mas_gusto', 'sugerencias', 'decepcion',
            'como_se_entero_otro', 'intencion_volver',
            'permite_uso_comentarios_redes', 'quiere_newsletter', 'permite_seguimiento',
        ]:
            if nombre_campo in self.fields:
                self.fields[nombre_campo].required = False

    def clean(self):
        cleaned = super().clean()
        servicios = cleaned.get('servicios_contratados') or []

        # Si NO contrató tina → ignorar calificaciones de tina
        if not any(s.startswith('tina_') for s in servicios):
            for f in ('cal_temperatura_tina', 'cal_transparencia_agua', 'cal_limpieza_tinas'):
                cleaned[f] = None
        # Si NO contrató cabaña → ignorar calificaciones de cabaña
        if 'alojamiento' not in servicios:
            for f in ('cal_limpieza_cabana', 'cal_temperatura_cabana'):
                cleaned[f] = None
        # Si NO contrató masaje → ignorar calificaciones de masaje
        if 'masaje' not in servicios:
            for f in ('cal_limpieza_sala_masajes', 'cal_servicio_masajes'):
                cleaned[f] = None

        # Si "otro" en cómo se enteró, exigir explicación
        if cleaned.get('como_se_entero') == 'otro' and not cleaned.get('como_se_entero_otro'):
            self.add_error('como_se_entero_otro', 'Cuéntanos cómo te enteraste (este campo es obligatorio si elegiste "Otro").')

        return cleaned
