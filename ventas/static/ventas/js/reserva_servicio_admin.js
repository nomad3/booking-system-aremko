document.addEventListener('DOMContentLoaded', function() {
    // Usar django.jQuery en lugar de $
    django.jQuery(document).on('change', '.field-servicio select', function() {
        console.log('Servicio cambiado'); // Debug 1
        var $form = django.jQuery(this).closest('.dynamic-reservaservicio');
        var servicioId = django.jQuery(this).val();
        console.log('ID Servicio:', servicioId); // Debug 2
        
        if(servicioId) {
            django.jQuery.ajax({
                url: '/admin/ventas/servicio/' + servicioId + '/slots/',
                success: function(data) {
                    console.log('Respuesta API:', data); // Debug 3
                    var $horaInicio = $form.find('.field-hora_inicio select');
                    $horaInicio.empty();
                    django.jQuery.each(data.slots, function(index, value) {
                        console.log('Agregando slot:', value); // Debug 4
                        $horaInicio.append(
                            django.jQuery('<option></option>')
                                .attr('value', value)
                                .text(value)
                        );
                    });
                },
                error: function(xhr) {
                    console.error('Error en la solicitud:', xhr.statusText); // Debug 5
                }
            });
        }
    });
});
