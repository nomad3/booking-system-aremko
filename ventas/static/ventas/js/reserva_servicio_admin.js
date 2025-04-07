document.addEventListener('DOMContentLoaded', function() {
    // Actualizar slots al cambiar servicio
    $(document).on('change', '.field-servicio select', function() {
        var $form = $(this).closest('.dynamic-reservaservicio');
        var servicioId = $(this).val();
        var $horaInicio = $form.find('.field-hora_inicio select');
        
        if(servicioId) {
            $.ajax({
                url: '/admin/ventas/servicio/' + servicioId + '/slots/',
                success: function(data) {
                    $horaInicio.empty();
                    $.each(data.slots, function(index, value) {
                        $horaInicio.append($('<option></option>').attr('value', value).text(value));
                    });
                }
            });
        }
    });
});
