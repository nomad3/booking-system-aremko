from django import forms
from ..models import ReservaProducto, Pago, Campaign, VentaReserva
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, time

class VentaReservaAdminForm(forms.ModelForm):
    """Formulario personalizado para VentaReserva que solo muestra fecha (sin hora)."""

    # Sobrescribir el campo para usar DateField en lugar de DateTimeField en el formulario
    fecha_reserva = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Fecha Venta Reserva'
    )

    class Meta:
        model = VentaReserva
        fields = '__all__'

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
    class Meta:
        model = Pago
        fields = ['fecha_pago', 'monto', 'metodo_pago', 'giftcard']

    def clean(self):
        cleaned_data = super().clean()
        metodo_pago = cleaned_data.get('metodo_pago')
        giftcard = cleaned_data.get('giftcard')
        monto = cleaned_data.get('monto')

        if metodo_pago == 'giftcard':
            if not giftcard:
                raise ValidationError("Debe seleccionar una gift card para este método de pago.")

            # Asegurar que monto y monto_disponible sean del mismo tipo (Decimal)
            from decimal import Decimal
            monto_decimal = Decimal(str(monto)) if monto else Decimal('0')
            saldo_disponible = Decimal(str(giftcard.monto_disponible))

            # Validar saldo disponible
            if saldo_disponible < monto_decimal:
                raise ValidationError(
                    f"El monto ({monto_decimal}) excede el saldo disponible en la gift card ({saldo_disponible})."
                )

            # Validar fecha de vencimiento
            if giftcard.fecha_vencimiento < timezone.now().date():
                raise ValidationError("La gift card ha expirado.")
        else:
            if giftcard:
                raise ValidationError("No debe seleccionar una gift card para este método de pago.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk:  # If this is a new instance
            instance.usuario = self.request.user if hasattr(self, 'request') else None
        if commit:
            instance.save()
        return instance

class SelectCampaignForm(forms.Form):
    campaign = forms.ModelChoiceField(
        queryset=Campaign.objects.filter(status='Active').order_by('name'), # Show only active campaigns
        label="Seleccionar Campaña",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}) # Optional: Add styling
    )
    # Hidden field to pass selected client IDs
    selected_clients = forms.CharField(widget=forms.HiddenInput())