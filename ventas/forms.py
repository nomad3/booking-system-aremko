"""
Formularios personalizados para la aplicación ventas
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import Cliente, Region, Comuna
import re


class PhoneCountryWidget(forms.MultiWidget):
    """
    Widget personalizado que separa código de país y número de teléfono
    """
    COUNTRY_CODES = [
        ('', '-- Seleccione país --'),
        ('+56', 'Chile (+56)'),
        ('+54', 'Argentina (+54)'),
        ('+55', 'Brasil (+55)'),
        ('+57', 'Colombia (+57)'),
        ('+51', 'Perú (+51)'),
        ('+52', 'México (+52)'),
        ('+1', 'USA/Canadá (+1)'),
        ('+34', 'España (+34)'),
        ('+33', 'Francia (+33)'),
        ('+44', 'Reino Unido (+44)'),
        ('+49', 'Alemania (+49)'),
        ('+39', 'Italia (+39)'),
        ('+86', 'China (+86)'),
        ('+81', 'Japón (+81)'),
        ('+91', 'India (+91)'),
        ('other', 'Otro país'),
    ]

    def __init__(self, attrs=None):
        widgets = [
            forms.Select(attrs={'class': 'country-code-select'}, choices=self.COUNTRY_CODES),
            forms.TextInput(attrs={'class': 'phone-number-input', 'placeholder': 'Número de teléfono'})
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        """
        Separa un número de teléfono completo en código de país y número
        """
        if value:
            # Buscar coincidencia con códigos conocidos
            for code, _ in self.COUNTRY_CODES[1:-1]:  # Excluir vacío y 'other'
                if value.startswith(code):
                    return [code, value[len(code):]]
            # Si no coincide con ninguno, asumir que es otro
            if value.startswith('+'):
                # Intentar extraer código de país (máximo 4 dígitos después del +)
                match = re.match(r'(\+\d{1,4})(\d+)', value)
                if match:
                    return ['other', value]
            return ['', value]
        return ['', '']


class ClienteForm(forms.ModelForm):
    """
    Formulario personalizado para Cliente con lógica condicional
    """
    # Campo personalizado para teléfono con código de país
    telefono_completo = forms.CharField(
        label='Teléfono',
        widget=PhoneCountryWidget(),
        required=True
    )

    # Código de país personalizado para cuando se selecciona "Otro"
    codigo_pais_otro = forms.CharField(
        label='Código de país',
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Ej: +598',
            'class': 'codigo-pais-otro',
            'style': 'display:none;'
        })
    )

    class Meta:
        model = Cliente
        fields = ['nombre', 'email', 'documento_identidad', 'pais', 'ciudad', 'region', 'comuna']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'documento_identidad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'RUT/DNI/Pasaporte'
            }),
            'pais': forms.TextInput(attrs={
                'class': 'form-control pais-input',
                'style': 'display:none;',
                'placeholder': 'País (si no es Chile)'
            }),
            'ciudad': forms.TextInput(attrs={
                'class': 'form-control ciudad-input',
                'style': 'display:none;',
                'placeholder': 'Ciudad (si no es Chile)'
            }),
            'region': forms.Select(attrs={'class': 'form-control region-select'}),
            'comuna': forms.Select(attrs={'class': 'form-control comuna-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si estamos editando, descomponer el teléfono
        if self.instance.pk and self.instance.telefono:
            self.fields['telefono_completo'].initial = self.instance.telefono

        # Hacer campos opcionales según lógica
        self.fields['pais'].required = False
        self.fields['ciudad'].required = False
        self.fields['region'].required = False
        self.fields['comuna'].required = False

        # Configurar queryset para comuna basado en región si existe
        if self.instance.pk and self.instance.region:
            self.fields['comuna'].queryset = Comuna.objects.filter(region=self.instance.region)
        else:
            self.fields['comuna'].queryset = Comuna.objects.none()

    def clean(self):
        cleaned_data = super().clean()

        # Procesar teléfono
        telefono_data = cleaned_data.get('telefono_completo')
        if telefono_data:
            codigo_pais = self.data.get('telefono_completo_0', '')
            numero = self.data.get('telefono_completo_1', '')

            if not numero:
                raise ValidationError('El número de teléfono es requerido')

            # Limpiar el número de espacios y guiones
            numero = re.sub(r'[\s\-\(\)]', '', numero)

            # Si se seleccionó "otro", usar el código personalizado
            if codigo_pais == 'other':
                codigo_pais_otro = cleaned_data.get('codigo_pais_otro', '').strip()
                if not codigo_pais_otro:
                    raise ValidationError('Debe ingresar el código de país')
                if not codigo_pais_otro.startswith('+'):
                    codigo_pais_otro = '+' + codigo_pais_otro
                codigo_pais = codigo_pais_otro

            # Construir número completo
            if codigo_pais:
                telefono_completo = codigo_pais + numero
            else:
                raise ValidationError('Debe seleccionar un código de país')

            # Validación específica para Chile
            if codigo_pais == '+56':
                # Números chilenos deben tener 9 dígitos
                if not re.match(r'^\d{9}$', numero):
                    raise ValidationError('Los números chilenos deben tener 9 dígitos')

                # Región y comuna son requeridos para Chile
                if not cleaned_data.get('region'):
                    raise ValidationError({'region': 'La región es requerida para clientes de Chile'})
                if not cleaned_data.get('comuna'):
                    raise ValidationError({'comuna': 'La comuna es requerida para clientes de Chile'})

                # País y ciudad deben estar vacíos para Chile
                cleaned_data['pais'] = 'Chile'
                cleaned_data['ciudad'] = ''
            else:
                # Para otros países, país y ciudad son requeridos
                if not cleaned_data.get('pais'):
                    raise ValidationError({'pais': 'El país es requerido para números internacionales'})
                if not cleaned_data.get('ciudad'):
                    raise ValidationError({'ciudad': 'La ciudad es requerida para números internacionales'})

                # Región y comuna deben estar vacíos
                cleaned_data['region'] = None
                cleaned_data['comuna'] = None

            # Guardar el teléfono procesado
            self.cleaned_data['telefono'] = telefono_completo

        return cleaned_data

    def save(self, commit=True):
        # Asignar el teléfono procesado al modelo
        self.instance.telefono = self.cleaned_data.get('telefono', '')
        return super().save(commit=commit)


class ClienteAdminForm(ClienteForm):
    """
    Versión del formulario para el admin con JavaScript adicional
    """
    class Media:
        js = ('ventas/js/cliente_form.js',)
        css = {
            'all': ('ventas/css/cliente_form.css',)
        }