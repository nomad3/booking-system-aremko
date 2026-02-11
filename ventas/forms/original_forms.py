from django import forms
from django.forms import BaseInlineFormSet
from ..models import ReservaProducto, Pago, Campaign, VentaReserva
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, time
from decimal import Decimal
from collections import defaultdict


class VentaReservaAdminForm(forms.ModelForm):
    """Formulario personalizado para VentaReserva que solo muestra fecha (sin hora)."""

    class Meta:
        model = VentaReserva
        fields = '__all__'
        widgets = {
            'fecha_reserva': forms.DateInput(
                attrs={'type': 'date'},
                format='%Y-%m-%d'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Configurar el campo de fecha para aceptar solo fechas
        if 'fecha_reserva' in self.fields:
            # Cambiar a DateField en lugar de DateTimeField
            from django.forms import DateField
            self.fields['fecha_reserva'] = DateField(
                required=False,
                widget=forms.DateInput(
                    attrs={'type': 'date'},
                    format='%Y-%m-%d'
                ),
                input_formats=['%Y-%m-%d'],
                label='Fecha Venta Reserva'
            )

            # Si hay una instancia, establecer el valor inicial
            if self.instance and self.instance.pk and self.instance.fecha_reserva:
                if isinstance(self.instance.fecha_reserva, datetime):
                    self.fields['fecha_reserva'].initial = self.instance.fecha_reserva.date()
                else:
                    self.fields['fecha_reserva'].initial = self.instance.fecha_reserva
            else:
                # Para nuevas reservas, usar la fecha actual
                self.fields['fecha_reserva'].initial = timezone.now().date()

        # No modificar el widget de cliente - dejarlo como está

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

        # Validaciones básicas (la validación de saldo se hace en PagoInlineFormSet)
        if metodo_pago == 'giftcard':
            if not giftcard:
                raise ValidationError("Debe seleccionar una gift card para este método de pago.")
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

class PagoInlineFormSet(BaseInlineFormSet):
    """
    Formset personalizado para validar múltiples pagos con la misma GiftCard.
    Solo valida NUEVOS pagos (sin pk) contra el saldo disponible actual.
    """

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        # Agrupar SOLO pagos NUEVOS por GiftCard (que no tienen pk/id)
        giftcard_usage = defaultdict(Decimal)

        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                # IMPORTANTE: Solo validar pagos nuevos (sin pk)
                # Los pagos existentes ya fueron descontados del saldo
                instance = form.instance
                if instance.pk:
                    # Este pago ya existe en la BD, skip
                    continue

                metodo_pago = form.cleaned_data.get('metodo_pago')
                giftcard = form.cleaned_data.get('giftcard')
                monto = form.cleaned_data.get('monto')

                if metodo_pago == 'giftcard' and giftcard and monto:
                    # Convertir a Decimal
                    monto_decimal = Decimal(str(monto))

                    # Validar fecha de vencimiento
                    if giftcard.fecha_vencimiento < timezone.now().date():
                        raise ValidationError(
                            f"La gift card {giftcard.codigo} ha expirado."
                        )

                    # Acumular uso de esta giftcard (solo pagos nuevos)
                    giftcard_usage[giftcard.id] += monto_decimal

        # Validar que cada GiftCard tenga saldo suficiente para los pagos NUEVOS
        for giftcard_id, total_usado in giftcard_usage.items():
            # Buscar la giftcard
            from ..models import GiftCard
            giftcard = GiftCard.objects.get(id=giftcard_id)
            saldo_disponible = Decimal(str(giftcard.monto_disponible))

            if total_usado > saldo_disponible:
                raise ValidationError(
                    f"El total de pagos nuevos con la GiftCard {giftcard.codigo} ({total_usado}) "
                    f"excede el saldo disponible ({saldo_disponible})."
                )

class SelectCampaignForm(forms.Form):
    campaign = forms.ModelChoiceField(
        queryset=Campaign.objects.filter(status='Active').order_by('name'), # Show only active campaigns
        label="Seleccionar Campaña",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}) # Optional: Add styling
    )
    # Hidden field to pass selected client IDs
    selected_clients = forms.CharField(widget=forms.HiddenInput())