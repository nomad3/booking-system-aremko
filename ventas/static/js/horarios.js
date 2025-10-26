document.addEventListener('DOMContentLoaded', function () {
    function obtenerHorariosDesdeServidor(servicioId, horaField) {
        fetch(`/api/horarios/${servicioId}/`)
            .then(response => response.json())
            .then(data => {
                // Limpia el campo de hora
                horaField.innerHTML = '<option value="">Seleccione un horario</option>';
                
                // Si hay horarios disponibles
                if (data.horarios && data.horarios.length > 0) {
                    data.horarios.forEach(function (hora) {
                        const option = document.createElement('option');
                        option.value = hora;
                        option.text = hora;
                        horaField.appendChild(option);
                    });
                } else {
                    horaField.innerHTML = '<option value="">No hay horarios disponibles</option>';
                }
            })
            .catch(error => {
                console.error('Error al obtener los horarios:', error);
            });
    }

    // Agrega el evento 'change' a todos los campos de servicio en el momento de la carga de la página
    const servicioFields = document.querySelectorAll('select[name$="-servicio"]');
    servicioFields.forEach(function(servicioField) {
        servicioField.addEventListener('change', function () {
            const servicioId = this.value;
            const horaField = this.closest('tr').querySelector('select[name$="-hora"]');
            
            // Verificar si hay un servicio seleccionado y llamar a la función para obtener los horarios
            if (servicioId) {
                obtenerHorariosDesdeServidor(servicioId, horaField);
            }
        });
    });

    // Si se agrega una nueva fila en el formulario inline
    document.addEventListener('click', function (event) {
        if (event.target && event.target.classList.contains('add-row')) {
            // Esperar un pequeño tiempo para asegurarse de que la nueva fila está añadida al DOM
            setTimeout(function () {
                const newServicioField = document.querySelector('tr.dynamic-reservaservicios:last-of-type select[name$="-servicio"]');
                if (newServicioField) {
                    newServicioField.addEventListener('change', function () {
                        const servicioId = this.value;
                        const horaField = this.closest('tr').querySelector('select[name$="-hora"]');
                        
                        if (servicioId) {
                            obtenerHorariosDesdeServidor(servicioId, horaField);
                        }
                    });
                }
            }, 500);
        }
    });
});
