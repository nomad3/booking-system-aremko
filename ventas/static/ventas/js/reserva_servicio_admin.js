document.addEventListener('DOMContentLoaded', function() {
    // Usar django.jQuery en lugar de $
    django.jQuery(document).on('change', '.field-servicio select', function() {
        console.log('Servicio cambiado'); // Debug 1
        var $row = django.jQuery(this).closest('.dynamic-reservaservicio');
        var servicioId = django.jQuery(this).val();
        console.log('ID Servicio:', servicioId); // Debug 2
        
        if(servicioId) {
            django.jQuery.ajax({
                url: '/admin/ventas/servicio/' + servicioId + '/slots/',
                success: function(data) {
                    console.log('Respuesta API:', data); // Debug 3
                    // Selector por atributo name que termina con "-hora_inicio"
                    var $horaInicio = $row.find('select[name$="-hora_inicio"]');
                    console.log('Elemento select encontrado:', $horaInicio.length); // Debug
                    
                    $horaInicio.empty();
                    django.jQuery.each(data.slots, function(index, value) {
                        console.log('Agregando slot:', value); // Debug 4
                        $horaInicio.append(
                            django.jQuery('<option>', {
                                value: value,
                                text: value
                            })
                        );
                    });
                    
                    // Si usas Select2
                    if (django.jQuery.fn.select2) {
                        $horaInicio.trigger('change.select2');
                    }
                },
                error: function(xhr) {
                    console.error('Error en la solicitud:', xhr.statusText); // Debug 5
                }
            });
        }
    });
});
