document.addEventListener('DOMContentLoaded', function() {
    // Usar django.jQuery en lugar de $
    django.jQuery(document).on('change', '.field-servicio select', function() {
        var $form = django.jQuery(this).closest('.dynamic-reservaservicio');
        var servicioId = django.jQuery(this).val();
        var $horaInicio = $form.find('.field-hora_inicio select');
        
        if(servicioId) {
            django.jQuery.ajax({
                url: '/admin/ventas/servicio/' + servicioId + '/slots/',
                success: function(data) {
                    $horaInicio.empty();
                    django.jQuery.each(data.slots, function(index, value) {
                        $horaInicio.append(django.jQuery('<option></option>').attr('value', value).text(value));
                    });
                }
            });
        }
    });
});
