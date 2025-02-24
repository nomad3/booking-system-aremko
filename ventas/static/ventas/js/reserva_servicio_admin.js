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
                    // Usar la clase del contenedor .field-hora_inicio
                    var $horaInicio = $row.find('.field-hora_inicio select');
                    
                    // Debug: Verificar si encontró el elemento
                    console.log('Elemento select:', $horaInicio);
                    
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
                    
                    // Forzar actualización visual
                    $horaInicio.trigger('change');
                },
                error: function(xhr) {
                    console.error('Error en la solicitud:', xhr.statusText); // Debug 5
                }
            });
        }
    });
});
