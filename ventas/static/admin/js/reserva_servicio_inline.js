(function($) {
    $(document).on('formset:added', function(event, $row, formsetName) {
        // Se ejecuta cuando se añade un nuevo formulario inline (ej: 'Agregar otro Servicio Reservado')
        if (formsetName === 'reservaservicios') { // Asegúrate de que el formset name es correcto
            initializeRowListeners($row);
        }
    });

    $(document).ready(function() {
        // Se ejecuta para los formularios inline existentes al cargar la página
        $('.dynamic-reservaservicios').each(function() {
            initializeRowListeners($(this));
        });
    });

    function initializeRowListeners($row) {
        const servicioSelect = $row.find('.field-servicio select'); // Ajusta el selector si es necesario
        const fechaInput = $row.find('.field-fecha_agendamiento input'); // Asume un input de fecha estándar
        const horaSelectOriginal = $row.find('.field-hora_inicio select, .field-hora_inicio input'); // Puede ser select o input inicialmente

        if (!servicioSelect.length || !fechaInput.length || !horaSelectOriginal.length) {
            console.warn("No se encontraron los campos esperados en la fila:", $row);
            return;
        }

        // Guardar el valor original de la hora si existe (para edición)
        const originalHoraValue = horaSelectOriginal.val();

        // Escuchar cambios en Servicio y Fecha
        servicioSelect.add(fechaInput).on('change', function() {
            const servicioId = servicioSelect.val();
            const fecha = fechaInput.val(); // Formato YYYY-MM-DD esperado por la vista

            if (servicioId && fecha) {
                fetchAndPopulateHoras(servicioId, fecha, horaSelectOriginal, originalHoraValue);
            } else {
                // Si no hay servicio o fecha, volver al estado original o limpiar
                 resetHoraField(horaSelectOriginal, originalHoraValue);
            }
        });

        // Trigger inicial si ya hay valores (para formularios existentes al cargar)
        if (servicioSelect.val() && fechaInput.val()) {
            fetchAndPopulateHoras(servicioSelect.val(), fechaInput.val(), horaSelectOriginal, originalHoraValue);
        }
    }

    async function fetchAndPopulateHoras(servicioId, fecha, horaFieldElement, originalValue) {
        // Construye la URL - Asegúrate de que esta URL sea correcta y accesible desde el admin
        // Probablemente necesites definirla globalmente en la plantilla admin base o pasarla de otra forma.
        // Por ahora, usamos un placeholder. Necesitarás reemplazar '/get_available_hours/' con la URL real.
        const url = `/get_available_hours/?servicio_id=${servicioId}&fecha=${fecha}`;

        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`Error fetching hours: ${response.statusText}`);
            }
            const data = await response.json();

            // Reemplazar el input/select existente con un nuevo select poblado
            const newSelect = $('<select></select>').attr({
                id: horaFieldElement.attr('id'),
                name: horaFieldElement.attr('name'),
                class: horaFieldElement.attr('class') // Mantener clases originales si es necesario
            });

            if (data.available_hours && data.available_hours.length > 0) {
                newSelect.append($('<option></option>').attr('value', '').text('---------')); // Opción vacía
                data.available_hours.forEach(function(hora) {
                    const option = $('<option></option>').attr('value', hora).text(hora);
                    if (hora === originalValue) { // Seleccionar valor original si coincide
                        option.prop('selected', true);
                    }
                    newSelect.append(option);
                });
            } else {
                newSelect.append($('<option></option>').attr('value', '').text('No hay horas disponibles'));
                newSelect.prop('disabled', true);
            }

            // Reemplazar el elemento viejo con el nuevo select
            horaFieldElement.replaceWith(newSelect);

        } catch (error) {
            console.error("Error fetching or populating hours:", error);
            // Podrías mostrar un mensaje de error o volver al estado original
            resetHoraField(horaFieldElement, originalValue);
        }
    }

    function resetHoraField(horaFieldElement, originalValue) {
        // Esta función podría necesitar ser más inteligente,
        // por ahora simplemente limpia o restaura un select vacío.
        const newSelect = $('<select></select>').attr({
            id: horaFieldElement.attr('id'),
            name: horaFieldElement.attr('name'),
            class: horaFieldElement.attr('class')
        });
        newSelect.append($('<option></option>').attr('value', '').text('Seleccione servicio y fecha'));
        newSelect.prop('disabled', true);
        // Si reemplazaste el original, necesitas reemplazarlo de nuevo
         if (horaFieldElement.parent().length) { // Check if element still exists
             horaFieldElement.replaceWith(newSelect);
         } else {
            // Si el elemento original fue reemplazado y luego necesitas resetear,
            // busca el nuevo select por ID y actualízalo.
            const currentSelect = $(`#${newSelect.attr('id')}`);
            currentSelect.empty().append($('<option></option>').attr('value', '').text('Seleccione servicio y fecha')).prop('disabled', true);
         }

    }

})(django.jQuery); // Usar el jQuery del admin de Django 