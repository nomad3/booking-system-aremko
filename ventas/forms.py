from django import forms
from django.forms import DateTimeInput, Select
from .models import ReservaProducto, Pago
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime

class ReservaProductoForm(forms.ModelForm):
    class Meta:
        model = ReservaProducto
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(ReservaProductoForm, self).__init__(*args, **kwargs)

        if self.instance and self.instance.producto and not self.instance.producto.es_reservable:
            self.fields.pop('fecha_agendamiento')

        # Definir opciones de horas para cada tipo de servicio
        if 'servicio' in self.initial:
            servicio = self.initial['servicio']
            if servicio.tipo == 'cabañas':
                self.fields['hora'].choices = [
                    ('16:00', '16:00'),
                ]
            elif servicio.tipo == 'tinas':
                self.fields['hora'].choices = [
                    ('14:00', '14:00'),
                    ('14:30', '14:30'),
                    ('17:00', '17:00'),
                    ('19:00', '19:00'),
                    ('19:30', '19:30'),
                    ('21:30', '21:30'),
                    ('22:00', '22:00'),
                ]
            elif servicio.tipo == 'masajes':
                self.fields['hora'].choices = [
                    ('13:00', '13:00'),
                    ('14:15', '14:15'),
                    ('15:30', '15:30'),
                    ('16:45', '16:45'),
                    ('18:00', '18:00'),
                    ('19:15', '19:15'),
                    ('20:30', '20:30'),
                ]

class PagoInlineForm(forms.ModelForm):
    fecha_pago = forms.DateTimeField(
        widget=DateTimeInput(
            attrs={'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M'
        ),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S'],
        required=True
    )

    class Meta:
        model = Pago
        exclude = ['usuario']
        widgets = {
            'giftcard': Select(attrs={'class': 'select2'})
        }

    def clean_fecha_pago(self):
        fecha_pago = self.cleaned_data.get('fecha_pago')
        if isinstance(fecha_pago, str):
            try:
                # Si es string, convertir a datetime
                fecha_pago = datetime.strptime(fecha_pago, '%Y-%m-%dT%H:%M')
            except ValueError:
                try:
                    # Intentar con otro formato si el primero falla
                    fecha_pago = datetime.strptime(fecha_pago, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    raise forms.ValidationError('Formato de fecha inválido')
        
        # Asegurarse de que la fecha tenga timezone
        if timezone.is_naive(fecha_pago):
            fecha_pago = timezone.make_aware(fecha_pago)
        
        return fecha_pago

    def clean(self):
        cleaned_data = super().clean()
        metodo_pago = cleaned_data.get('metodo_pago')
        giftcard = cleaned_data.get('giftcard')
        monto = cleaned_data.get('monto')

        if metodo_pago == 'giftcard':
            if not giftcard:
                raise ValidationError("Debe seleccionar una gift card para este método de pago.")
            if giftcard.monto_disponible < monto:
                raise ValidationError("El monto excede el saldo disponible en la gift card.")
            if giftcard.fecha_vencimiento < timezone.now().date():
                raise ValidationError("La gift card ha expirado.")
        else:
            if giftcard:
                raise ValidationError("No debe seleccionar una gift card para este método de pago.")

        return cleaned_data