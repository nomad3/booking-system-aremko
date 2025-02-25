document.addEventListener('DOMContentLoaded', function() {
    // Delegación de eventos para inlines dinámicos
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('actualizar-horarios')) {
            console.log('Botón clickeado');
            const row = e.target.closest('.dynamic-reservaservicio');
            const servicioId = row.querySelector('.field-servicio select').value;
            const fecha = row.querySelector('.field-fecha_agendamiento input').value;
            const selectHora = row.querySelector('.field-hora_inicio select');

            console.log('Servicio ID:', servicioId);
            console.log('Fecha:', fecha);
            console.log('Select Hora:', selectHora);

            if (servicioId && fecha) {
                console.log('Haciendo fetch...');
                fetch(`/admin/ventas/servicio/${servicioId}/slots/?fecha=${fecha}`)
                    .then(response => {
                        console.log('Respuesta recibida, status:', response.status);
                        return response.json();
                    })
                    .then(data => {
                        console.log('Datos recibidos:', data);
                        selectHora.innerHTML = data.slots
                            .map(slot => `<option value="${slot}">${slot}</option>`)
                            .join('');
                        console.log('Opciones actualizadas:', selectHora.options.length);
                    })
                    .catch(error => console.error('Error en fetch:', error));
            }
        }
    });
}); 