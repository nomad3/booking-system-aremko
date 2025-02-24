document.addEventListener('DOMContentLoaded', function() {
    // Usar delegación de eventos para inlines dinámicos
    django.jQuery(document).on('change', '[id^="id_reservaservicios-"][id$="-servicio"]', function() {
        const $row = django.jQuery(this).closest('.dynamic-reservaservicio');
        const servicioId = django.jQuery(this).val();
        const selectName = django.jQuery(this).attr('id').replace('-servicio', '-hora_inicio');
        const $horaInicio = $row.find('#' + selectName);
        const $container = $row.find('.horario-radio-container');

        console.log('Servicio ID:', servicioId); // Debug 1
        
        if (servicioId) {
            django.jQuery.ajax({
                url: `/admin/ventas/servicio/${servicioId}/slots/`,
                success: function(data) {
                    console.log('Respuesta AJAX:', data); // Debug 2
                    $horaInicio.empty();
                    if (data.html) {
                        $container.html(data.html);
                    } else {
                        // Generar HTML manualmente
                        const options = data.slots.map(slot => `
                            <label class="horario-option">
                                <input type="radio" name="${$container.find('input[type="radio"]').attr('name')}" value="${slot}">
                                <span class="horario-label">${slot}</span>
                            </label>
                        `).join('');
                        $container.html(options);
                    }
                    
                    // Forzar actualización de Select2 si está presente
                    if (django.jQuery.fn.select2) {
                        $horaInicio.select2('destroy').select2();
                    }
                    
                    // Trigger para actualizar el UI
                    $container.trigger('change');
                },
                error: function(xhr) {
                    console.error('Error AJAX:', xhr.responseText); // Debug 3
                }
            });
        }
    });
});
